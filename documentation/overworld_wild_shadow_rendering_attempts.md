# Overworld Wild Shadow Rendering Attempts

This file tracks the active long-hop shadow issue so repeated fixes do not
circle back through the same failed render knobs.

## Usage Rule

Before trying a new shadow fix:

- Read this file first.
- Add the exact new idea to the attempt log before changing code.
- Record the files, symbols, build result, runtime result, and what the result
  proves after the attempt is tested.
- Do not retry failed attempts unless the new test changes a stated variable.

## Current Issue

- During canopy long-hop movement, the Pokemon body moves through the air, but
  the floor shadow is missing for most of the hop when the jump starts from
  grass or canopy tiles.
- On grass/canopy-to-land jumps, the shadow can blink for a single frame and
  then disappear again.
- The desired behavior is a floor shadow under the airborne Pokemon for the
  whole hop.
- The shadow must not attach to the airborne Pokemon body.
- User verification is the source of truth for this visual bug.

## Constraints

- Overlay 149 is extremely tight, so fixes should avoid adding new overlay-side
  systems.
- ARM9/base space is also tight; prefer replacing failed render code over
  stacking more probes.
- There should be one jump presentation path. Do not add a second independent
  jump system just for shadows.
- Current S64/S65 long-hop presentation keeps `posVec[1]` on the floor,
  mirrors the arc height into `faceVec[1]`, and keeps `object->unk88[1]` as the
  live body-arc carrier. Current source does not have an active
  `OverworldWildSpawns_CanopyLongJumpDrawWrapper`; old draw-wrapper attempts in
  this log are historical, not a live insertion point.

## Known Render Facts

- `OW_WILD_MANKEY_TREE_TOP_DRAW_CALLBACK` names the normal small-Pokemon
  callback at `0x021F7895`, but the tree-top draw-callback override is disabled
  in the current source.
- The live sprite depth setter at `0x02023F1D` writes the primary/secondary
  sprite depth field used by the existing tree-top wrapper.
- The secondary helper at `0x021F77A5` touches render-data slot `+4`, but it did
  not produce a stable midair floor shadow in runtime testing.
- Stock visibility hides objects for `BIT_VANISH`, and `MAPOBJECTFLAG_UNK13`
  is needed when `MAPOBJECTFLAG_UNK12` would otherwise hide the object.
- The stock position builder includes `unk88`; historical long-hop wrappers
  temporarily zeroed `object->unk88[1]` before stock draw, but the current
  stable baseline leaves `unk88[1] = arc` live for body draw.

## Do Not Repeat

- Do not use `posVec[1]` as the arc height. That moved the shadow with the
  Pokemon body instead of leaving it on the floor.
- Do not rely only on `BIT_JUMP_START`, `BIT_MOVE_START`, and
  `MAPOBJECTFLAG_UNK13`; that did not keep midair shadows visible.
- Do not rely only on clearing the render-data refresh/latch bit; build
  `test1470.nds` still had the shadow issue.
- Do not rely only on calling the secondary shadow callback `0x021F77A5`; build
  `test1471.nds` still had the shadow issue.

## Attempt Log

### S1 - Floor `posVec[1]`, Arc In `unk88[1]`

Hypothesis:

- Keep the map object's logical/floor height stable in `posVec[1]`.
- Store visual arc height in `object->unk88[1]`.
- In the draw wrapper, zero `unk88[1]` for stock positioning, lift the body
  through sprite depth, then restore the arc.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Runtime result:

- Avoided the earlier regression where the shadow was attached to the airborne
  body.
- Did not solve the missing/blinking floor shadow.

Conclusion:

- Keep this split, but it is not sufficient by itself.

### S2 - Long-Hop Visibility Flags

Hypothesis:

- Set `BIT_JUMP_START`, `BIT_MOVE_START`, and `MAPOBJECTFLAG_UNK13` while the
  custom long-hop carrier is active.
- Clear `BIT_VANISH`, `MAPOBJECTFLAG_UNK8`, and `MAPOBJECTFLAG_UNK30`.

Files/symbols:

- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Runtime result:

- Did not keep the shadow visible through grass/canopy-origin jumps.

Conclusion:

- These flags are necessary for visibility, but they are not the actual shadow
  source fix.

### S3 - Sync Logical Tile During The Hop

Hypothesis:

- Update the object's logical tile during long-hop travel so the Pokemon is not
  treated as being on the departure tile until landing.

Files/symbols:

- `OverworldWildSpawns_SyncCanopyLongJumpDiagonalLogicalTile`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`

Runtime result:

- Fixed the stale departure-tile behavior.
- Did not solve the midair shadow disappearing on grass/canopy-origin jumps.

Conclusion:

- Do not remove logical tile sync as a shadow shortcut; that would regress
  movement/collision semantics.

### S4 - Clear Render-Data Refresh Latch

Hypothesis:

- Clearing render-data byte `unk108[0x17]` bit 0 during active arc might force
  stock render setup to refresh the shadow state after terrain changes.

Files/symbols:

- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Build:

- Built as `test1470.nds`.

Runtime result:

- User verified the issue remained.

Conclusion:

- The missing shadow is not solved by only clearing the render-data refresh
  latch.

### S5 - Call Stock Secondary Shadow Callback

Hypothesis:

- Calling the stock secondary callback `0x021F77A5` during active arc, while
  `unk88[1]` is zeroed for floor positioning, might draw the floor shadow even
  when the primary body is lifted.

Files/symbols:

- `OW_WILD_MANKEY_TREE_TOP_SHADOW_DRAW_CALLBACK`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Build:

- Built as `test1471.nds`.

Runtime result:

- User verified the issue remained.

Conclusion:

- The secondary callback alone is not the stable midair shadow path. It may be
  a no-op for this object or still depends on the same terrain/state that hides
  the shadow.

### S6 - Force Stock Draw Into Manual Offset Mode During Arc

Hypothesis:

- The stock draw prep appears to have a render-data flag mode that bypasses
  terrain-derived offset/shadow decisions and uses stored/manual object offset
  data instead.
- During active long-hop arc, temporarily set render-data byte `unk108[0x17]`
  bit 2 only around the stock draw callback, then restore the original flags.
- This is different from S4 because S4 cleared the refresh bit; this attempt
  tests the manual-offset branch instead of forcing a refresh.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OW_WILD_MANKEY_TREE_TOP_DRAW_CALLBACK`

Expected success signal:

- Shadow stays visible on the floor for the full hop from grass/canopy to land,
  without becoming attached to the airborne body.

Expected failure signal:

- Shadow still only blinks or disappears, or the body/shadow offset becomes
  visibly incorrect.

Build:

- Failed. The base ARM9 link overflowed by 12 bytes before producing a ROM.

Runtime result:

- Not tested; no ROM was produced.

Conclusion:

- Do not keep this version. It is too expensive for the current base-space
  budget, and helper-agent review found a more specific likely cause: the
  secondary shadow draw helper does not create a secondary sprite by itself.

### S7 - Ensure Secondary Shadow Sprite Before Drawing It

Hypothesis:

- `0x021F77A5` only positions/visibilizes `renderData->secondarySprite`; it
  returns if the secondary sprite pointer is null.
- The one-frame blink matches a lifecycle issue where a secondary sprite exists
  briefly, then disappears or is never created by the long-hop wrapper.
- During active arc, call the stock secondary lifecycle ensure helper before
  the secondary draw helper, then force only the secondary sprite to front
  depth. Keep the existing primary-body lift and `unk88[1]` floor split.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SECONDARY_ENSURE_CALLBACK`
- `OW_WILD_MANKEY_TREE_TOP_SHADOW_DRAW_CALLBACK`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Shadow remains visible on the floor throughout canopy/grass-origin long hops.

Expected failure signal:

- Build overflows, shadow still blinks, or a stale secondary shadow remains
  visible after landing.

Build:

- Failed. The base ARM9 link overflowed by 20 bytes before producing a ROM.

Runtime result:

- Not tested; no ROM was produced.

Conclusion:

- The lifecycle direction is still plausible, but this version is too expensive
  with both the pre-draw body-depth set and secondary-depth set present.

### S8 - Ensure Secondary Shadow Sprite With One Body-Depth Set

Hypothesis:

- The pre-draw primary depth set is probably redundant because the stock draw
  callback can overwrite the live sprite depth anyway.
- Keep the key S7 lifecycle change: ensure the secondary sprite before calling
  the secondary shadow draw helper.
- Save base bytes by only setting the primary sprite depth after stock draw,
  and by not forcing secondary depth in this pass.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- The build fits, body arc remains correct, and the shadow stays visible on the
  floor during grass/canopy-origin long hops.

Expected failure signal:

- Build still overflows, body arc becomes delayed/wrong, or the shadow still
  blinks/disappears.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1472.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning; no shadow-wrapper warning.

Runtime result:

- User verified the issue remained.

Conclusion:

- The secondary sprite lifecycle alone is not enough. The bare secondary draw
  helper still does not establish the depth/shadow plane needed for a stable
  floor shadow.

### S9 - Use Stock Secondary Depth-Aware Shadow Draw Helper

Hypothesis:

- Disassembly shows the helper at `0x021F77A5` only positions the secondary
  sprite and applies visibility.
- The nearby stock helper at `0x021F77D1` still uses `renderData->secondarySprite`
  but also applies `sub_02023F04(sprite, 0x1000)` before positioning and
  visibility when the object is not in the special `0x021F9344` state.
- This tests secondary-depth forcing without adding another helper call, which
  matters because the S8 build has only about 6 base bytes free.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SHADOW_DRAW_CALLBACK`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Shadow remains visible on the floor during grass/canopy-origin long hops.

Expected failure signal:

- Shadow still blinks/disappears, or the new helper moves the secondary shadow
  incorrectly.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1473.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning.
- Base ARM9 size stayed at `31226` bytes, leaving the same 6-byte margin as S8.

Runtime result:

- User verified the issue remained.

Conclusion:

- The depth-aware secondary helper was not enough. Either the secondary helper
  still does not run the stock state update needed for this shadow, or the
  secondary sprite path is being given incomplete direction/render state.

### S10 - Use Full Direction-Aware Secondary Update Helper

Hypothesis:

- Disassembly shows `0x021F772D` is a fuller secondary update path than
  `0x021F77A5` or `0x021F77D1`.
- It uses the current map-object direction to call a direction-specific helper
  from the table at `0x02208AC0`, writes secondary render state bytes, sets a
  render-state field at `0x0205F98C(object) + 8` to `0x800`, then positions and
  applies visibility to the secondary sprite.
- This keeps the S8/S9 call count and base size profile while testing whether
  the missing piece is the full stock secondary state update, not just sprite
  creation or depth.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SHADOW_DRAW_CALLBACK`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Shadow remains visible on the floor during grass/canopy-origin long hops.

Expected failure signal:

- Shadow still blinks/disappears, or the full secondary updater offsets the
  shadow/body incorrectly.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1474.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning.
- Base ARM9 size stayed at `31226` bytes, leaving the same 6-byte margin as S8/S9.

Runtime result:

- User verified the issue remained.

Conclusion:

- The fuller secondary updater alone is not enough. It still bails if the map
  object has the stock no-secondary/special-render flag set.

### S11 - Clear `MAPOBJECTFLAG_UNK22` During Long Hop

Hypothesis:

- The stock secondary helpers tested in S8/S9/S10 all call `0x021FA2D4` or
  equivalent early, which checks `MAPOBJECTFLAG_UNK22`.
- If `MAPOBJECTFLAG_UNK22` is set by grass/canopy terrain state, every secondary
  shadow helper returns before drawing, explaining why helper address swaps did
  not affect the missing shadow.
- The user is fine with shadows being visible no matter terrain, so clear
  `MAPOBJECTFLAG_UNK22` alongside the existing long-hop visibility cleanup.
- This changes an existing overlay-side clear mask instead of adding base-side
  calls, so it should avoid the 6-byte ARM9 margin problem.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `MapObject_ClearBits`

Expected success signal:

- The stock secondary path is allowed to run on grass/canopy-origin long hops,
  making the shadow visible regardless of terrain.

Expected failure signal:

- Shadow still disappears, proving `UNK22` was not the only helper gate.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1475.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning.
- Base ARM9 size stayed at `31226` bytes.
- Overlay 149 object size stayed at `44944` bytes.

Runtime result:

- User verified the issue remained.

Conclusion:

- Clearing the secondary-helper gate was not enough. The shadow still does not
  stay visible, so the secondary sprite path is likely not the missing piece.

### S12 - Planned: Use Stock Primary Sprite State Updater For Lift

Hypothesis:

- All secondary sprite attempts have failed.
- Stock primary draw uses `sub_02023F04(sprite, 0x1000)` as part of normal
  Pokemon ground-shadow/depth state, while the custom long-hop wrapper uses the
  direct `sprite + 0xB8` writer at `0x02023F1D`.
- Replacing the direct writer with the stock sprite-state updater at
  `0x02023F05` keeps the same call count and should fit the 6-byte base margin.
- This deliberately allows the stock sprite state updater to run regardless of
  terrain so shadows can be visible even on grass/canopy tiles.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Body lift still works, and the primary Pokemon shadow remains visible on the
  floor during long hops regardless of terrain.

Expected failure signal:

- Body lift changes/breaks, shadow attaches to the body, or shadow still
  disappears.

Conclusion:

- Superseded before a runtime build. Helper review found this attempt still
  passed an absolute `0x1000 + lift` value into the stock updater, while stock
  primary draw already applies the `0x1000` base state. That would continue to
  replace/warp the stock state instead of adding only the hop lift.

### S13 - Pass Only Hop Lift Delta To Stock Primary Updater

Hypothesis:

- The wrapper should let stock primary draw establish the normal
  ground-shadow/depth state first.
- After stock draw, the custom long-hop wrapper should pass only the visual hop
  lift delta, `arc >> 4`, into `sub_02023F04(sprite, depth)`.
- This avoids the direct `sprite + 0xB8` write and avoids feeding the stock
  updater a second absolute `0x1000` base value.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH`
- `OverworldWildSpawns_CanopyLongJumpSpriteDepth`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Body lift still follows the whole hop arc, and the primary floor shadow stays
  visible for the full hop even when the jump starts on grass/canopy tiles.

Expected failure signal:

- Body lift no longer reaches the intended height, shadow still disappears, or
  tree-top/front-depth presentation regresses because the shared depth setter is
  now the stock updater.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1476.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning.

Runtime result:

- Superseded before user runtime verification. A second helper review found the
  stock updater appears additive/clamping rather than absolute, making the
  shared `0x02023F05` swap risky for stable body arcs.

Conclusion:

- Do not use this as the final fix unless later evidence proves the updater is
  not additive in this path.
- Prefer returning to the direct absolute depth writer and fixing the order of
  operations around stock shadow setup.

### S14 - Ground Primary Sprite Before Stock Shadow Draw

Hypothesis:

- The missing/blinking shadow is caused by stock draw seeing the previous
  frame's lifted primary sprite depth while deciding whether to draw the
  terrain/floor shadow.
- During active arc, reset the primary sprite to floor/front depth before the
  stock draw callback while `unk88[1]` is temporarily zero.
- Remove the failed secondary-shadow calls from the long-hop wrapper.
- After stock draw has made its grounded shadow decision, restore the body lift
  with the direct absolute sprite-depth writer.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_CanopyLongJumpSpriteDepth`

Expected success signal:

- Shadow stays on the floor for the whole hop, even from grass/canopy tiles,
  while the body remains airborne and the shadow does not attach to the body.

Expected failure signal:

- Shadow still disappears, proving terrain/render-state suppression happens
  after the grounded primary reset or outside the primary sprite depth state.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1477.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning.
- `build/linked.o`: text `28482`, data `2728`, total `31210`.
- `build/overworld_wild_spawns.o`: text `1008`, data `1144`, bss `93`,
  total `2245`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44830`, bss `114`, total `44944`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Grounding the primary sprite before stock draw did not bypass the terrain
  shadow/clipping branch. The stock renderer still appears to suppress or move
  the floor shadow based on terrain state after the primary reset.

### S15 - Set Stock Airborne/Special Movement Flag During Long Hop

Hypothesis:

- Disassembly of stock draw `0x021F8D80` shows it only calls the terrain
  clipping/shadow gate `0x021F8FC0` when `sub_0205F888(object)` is false.
- `sub_0205F888` checks map-object flag `0x10`, which corresponds to
  `MAPOBJECTFLAG_UNK4`.
- During custom long-hop, set `MAPOBJECTFLAG_UNK4` with the existing long-hop
  active flags so the stock draw skips `0x021F8FC0`.
- Clear `MAPOBJECTFLAG_UNK4` on landing with the other long-hop flags.
- This keeps `posVec[1]` on the floor and `unk88[1]` as body arc, so the shadow
  should remain floor-anchored rather than attached to the airborne body.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_SetObjectLandingTile`
- `MAPOBJECTFLAG_UNK4`

Expected success signal:

- The floor shadow remains visible throughout grass/canopy-origin long hops
  because stock draw no longer enters the terrain suppression branch.

Expected failure signal:

- Shadow still disappears, meaning the suppression is not controlled by
  `0x021F8FC0`, or setting `MAPOBJECTFLAG_UNK4` has a different no-shadow
  meaning in this render path.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1478.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated `btl_scr_cmd_11A_tryRiptideNegatingAbility`
  unused-parameter warning.
- `build/linked.o`: text `28482`, data `2728`, total `31210`.
- `build/overworld_wild_spawns.o`: text `1008`, data `1144`, bss `93`,
  total `2245`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44830`, bss `114`, total `44944`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Skipping the `sub_0205F888`/`0x021F8FC0` terrain branch through
  `MAPOBJECTFLAG_UNK4` was not sufficient. Either this flag was not the
  relevant stock draw predicate for floor-shadow visibility, or the shadow is
  suppressed by another stock render branch.

### S16 - Set Stock Special/Manual Render Flag During Long Hop

Hypothesis:

- Disassembly of stock primary draw `0x021F8D80` shows another terrain-bypass
  predicate, `0x021F9344(object)`.
- `0x021F9344` checks map-object flag `0x100`, which corresponds to
  `MAPOBJECTFLAG_UNK8`.
- Current custom long-hop code explicitly clears `MAPOBJECTFLAG_UNK8` every
  active frame.
- During custom long-hop, set `MAPOBJECTFLAG_UNK8` with the active long-hop
  flags and stop clearing it midair, then clear it on landing.
- This is different from S15 because it uses the stock special/manual render
  branch instead of only the stock airborne/movement predicate.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_SetObjectLandingTile`
- `MAPOBJECTFLAG_UNK8`

Expected success signal:

- The floor shadow remains visible throughout grass/canopy-origin long hops
  because stock draw uses its special/manual render path regardless of terrain.

Expected failure signal:

- Shadow still disappears, or body/shadow depth changes visibly, proving the
  `0x021F9344` special render predicate is not enough for this floor shadow.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1479.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28482`, data `2728`, total `31210`.
- `build/overworld_wild_spawns.o`: text `1008`, data `1144`, bss `93`,
  total `2245`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44830`, bss `114`, total `44944`.

Runtime result:

- User verified the issue remained.

Conclusion:

- The stock special/manual render predicate is not enough. It may also suppress
  or bypass other shadow setup, so do not keep `MAPOBJECTFLAG_UNK8` as a
  long-hop active flag just for shadow rendering.

### S17 - Clear Stale Terrain Shadow Latch During Long Hop

Hypothesis:

- Disassembly of stock primary draw `0x021F8D80` shows terrain clipping/shadow
  state can be latched in render-data byte `unk108[0x15]`.
- Stock draw only clears that latch in paths that the custom long-hop now
  bypasses through `MAPOBJECTFLAG_UNK4`.
- If the Pokemon starts a hop on grass/canopy, the stale "terrain hides shadow"
  latch can remain set for the whole long-hop even though the body is being
  drawn with a floor-anchored arc.
- During custom long-hop draw, clear the render-data byte at `+0x15` before the
  stock draw callback, keep the S15 airborne/movement flag, and restore the
  pre-S16 behavior that clears `MAPOBJECTFLAG_UNK8` while long-hop is active.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_SetObjectLandingTile`
- `OW_WILD_MAP_OBJECT_RENDER_TERRAIN_LATCH_OFFSET`
- `MAPOBJECTFLAG_UNK8`

Expected success signal:

- The floor shadow stays visible through grass/canopy-origin long hops without
  attaching to the airborne body.

Expected failure signal:

- Shadow still disappears or blinks, proving the stale terrain latch is not the
  only state hiding the floor shadow.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1480.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28482`, data `2728`, total `31210`.
- `build/overworld_wild_spawns.o`: text `1012`, data `1144`, bss `93`,
  total `2249`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44830`, bss `114`, total `44944`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Clearing the terrain latch before the stock draw callback did not solve the
  missing floor shadow. The stock callback may write `unk108[0x15]` again after
  this pre-clear, so the next attempt should test clearing the same latch after
  stock draw has finished updating render state.

### S18 - Clear Terrain Shadow Latch After Stock Draw

Hypothesis:

- S17 cleared render-data byte `+0x15` before stock draw, but stock primary draw
  can set that byte again while processing the terrain/shadow branch.
- The visible frame likely uses the post-callback render data, so the latch
  needs to be cleared after `OW_WILD_MANKEY_TREE_TOP_DRAW_CALLBACK(mapObject)`
  and before the custom body lift is restored.
- This keeps the same one-jump presentation path and changes the ordering of
  S17 instead of adding a new secondary shadow system.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OW_WILD_MAP_OBJECT_RENDER_TERRAIN_LATCH_OFFSET`

Expected success signal:

- The floor shadow remains visible under the Pokemon during grass/canopy-origin
  long hops, while the body arc remains airborne.

Expected failure signal:

- Shadow still disappears or blinks, proving byte `+0x15` is not the final
  post-draw state controlling the missing floor shadow.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1481.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28490`, data `2728`, total `31218`.
- `build/overworld_wild_spawns.o`: text `1016`, data `1144`, bss `93`,
  total `2253`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44830`, bss `114`, total `44944`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Clearing render-data byte `+0x15` after stock draw did not solve the missing
  floor shadow. The shadow path likely needs the normal stock jump offset state
  before or during stock draw, not only a post-draw terrain latch clear.

### S19 - Feed Arc Through Stock Jump Offset During Draw

Hypothesis:

- Disassembly of stock jump update `0x020629CC` shows normal jump movement
  writes the vertical arc into the map object's `faceVec[1]` through
  `0x0205F97C`.
- The custom long-hop path stores the visual arc in `unk88[1]`, zeroes
  `faceVec`, and then zeroes `unk88[1]` before stock draw, so stock draw never
  sees the normal "this object is airborne" offset state that may keep floor
  shadows visible on grass/canopy tiles.
- During custom long-hop draw, temporarily copy `unk88[1]` into `faceVec[1]`
  while `unk88[1]` is zeroed for stock draw. After stock draw, reset
  `faceVec[1]` to the floor value and restore the custom body lift.
- This tests stock jump-shadow state without returning to stock movement or
  adding a second jump system.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`

Expected success signal:

- The stock draw path treats the Pokemon as airborne, keeping the floor shadow
  visible for the full grass/canopy-origin hop while the custom body lift still
  controls the visible arc.

Expected failure signal:

- Shadow still disappears, or the body/shadow visibly double-offsets, proving
  `faceVec[1]` alone is not the missing stock jump-shadow state.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1482.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28498`, data `2728`, total `31226`.
- `build/overworld_wild_spawns.o`: text `1024`, data `1144`, bss `93`,
  total `2261`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44830`, bss `114`, total `44944`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Setting `faceVec[1]` only inside the draw wrapper did not solve the missing
  floor shadow. Either stock draw consumes additional state, or the floor shadow
  decision happens before/after the wrapper scope and loses the temporary
  `faceVec[1]` value when the wrapper clears it.

### S20 - Keep Stock Jump Offset Active For The Whole Carrier Frame

Hypothesis:

- S19 may have set `faceVec[1]` too narrowly. The wrapper clears the vertical
  jump offset immediately after the stock draw callback.
- If shadow visibility/OAM is resolved outside or after `object->unkC8`, the
  renderer never sees a persistent stock jump offset.
- During the active custom long-hop carrier update, mirror the long-hop arc
  into `faceVec[1]` for the full frame instead of only inside the draw wrapper.
- Let landing/reset code clear `faceVec[1]` as it already does.
- This is distinct from S19 because it changes the lifetime of the stock jump
  offset, not just the value passed into the stock callback.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`

Expected success signal:

- The shadow remains visible for the entire hop because any post-wrapper shadow
  stage still sees the object as airborne through stock `faceVec[1]`.

Expected failure signal:

- Shadow still disappears, proving persistent `faceVec[1]` is not sufficient,
  or the body/shadow gets visibly double-offset.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1483.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28490`, data `2728`, total `31218`.
- `build/overworld_wild_spawns.o`: text `1016`, data `1144`, bss `93`,
  total `2253`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Keeping `faceVec[1]` active for the full carrier frame was still not enough
  while the wrapper continued to apply a manual post-draw body-depth override.
  The remaining mismatch from stock jump rendering is likely the custom
  post-draw lift and the extra `MAPOBJECTFLAG_UNK4` airborne flag.

### S21 - Let Stock Draw Own The Jump Presentation

Hypothesis:

- Stock jump movement carries the vertical arc in `faceVec[1]` and sets
  `BIT_JUMP_START | BIT_MOVE_START`, but does not set `MAPOBJECTFLAG_UNK4`.
- The custom long-hop carrier now mirrors the arc into `faceVec[1]`, but the
  draw wrapper still overrides the primary sprite depth after stock draw.
- That post-draw override may detach or suppress the floor shadow state that
  stock draw just prepared.
- During long-hop draw, only zero `unk88[1]` so the carrier arc is not applied
  twice, call stock draw, then restore `unk88[1]`. Do not manually lift the
  primary sprite afterward.
- Also stop setting `MAPOBJECTFLAG_UNK4` while airborne so the active flags
  match stock jump more closely.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`
- `MAPOBJECTFLAG_UNK4`

Expected success signal:

- Body still follows the long-hop arc through stock jump presentation, and the
  floor shadow remains visible on grass/canopy-origin hops.

Expected failure signal:

- Body arc regresses, shadow attaches to the body, or shadow still disappears,
  proving the stock jump vector path alone does not solve the terrain shadow.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1485.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28450`, data `2728`, total `31178`.
- `build/overworld_wild_spawns.o`: text `980`, data `1144`, bss `93`,
  total `2217`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Letting the stock draw callback own the jump arc was not enough. The failure
  is still tied to terrain-origin state, not the body arc path.

### S22 - Force Stock Terrain Primary Update As Land/Normal During Arc

Hypothesis:

- The stock small-Pokemon callback only calls its terrain primary updater
  (`0x02205808`) while render-data byte `+0x17` bit 0 is unset.
- On grass/canopy-origin long hops, that once-per-setup terrain state may keep
  suppressing the floor shadow even after the object has moved over land.
- The tiny stock wrapper at `0x021F902C` fetches `renderData->primarySprite`
  and calls the same terrain primary updater.
- During active long-hop arc, call that wrapper with variant `0` before the
  normal draw callback. Variant `0` uses resource 21 instead of the stock
  terrain variant 1/resource 22, effectively testing the user's acceptable
  fallback: shadows visible regardless of terrain.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_TERRAIN_PRIMARY_UPDATE`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow for the whole
  airborne duration, and the body arc remains stock-owned via `faceVec[1]`.

Expected failure signal:

- Shadow still disappears/blinks, or the helper visibly grounds/offsets the
  Pokemon body because it is not the shadow state owner.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1486.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28474`, data `2728`, total `31202`.
- `build/overworld_wild_spawns.o`: text `1004`, data `1144`, bss `93`,
  total `2241`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained.

Conclusion:

- Forcing the stock terrain primary updater before draw did not change the
  missing/blinking shadow. Because the normal draw callback positions the
  primary sprite after this helper, the pre-draw terrain update is likely
  overwritten or not the shadow owner.

### S23 - Stock Manual Offset Mode With Arc Fed Into Render Data

Hypothesis:

- S6 tried render-data byte `+0x17` bit 2 manual-offset mode but never produced
  a ROM because base ARM9 overflowed.
- S21 removed enough custom draw code to make this path worth testing now.
- Disassembly of `0x021F8D80` shows the manual-offset branch copies
  `faceVec`, then overwrites the Y component from signed render-data byte
  `+0x14` shifted left 12.
- If bit 2 is set without also feeding byte `+0x14`, the branch ignores the
  long-hop arc in `faceVec[1]`. During active long-hop draw, set bit 2 and set
  byte `+0x14` to `arc >> 12`, then restore both values after the stock draw
  callback.
- This is distinct from S6 because the runtime is now buildable and the arc is
  explicitly passed through the field that the stock manual branch actually
  uses.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::unk108[0x14]`
- `LocalMapObject::unk108[0x17]`

Expected success signal:

- Stock draw bypasses the terrain-derived shadow suppression while the Pokemon
  still follows the long-hop arc.

Expected failure signal:

- Shadow still disappears, the body/shadow become attached, or the arc becomes
  visibly coarse/wrong because manual-offset mode is not the correct stock
  shadow path.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1487.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28498`, data `2728`, total `31226`.
- `build/overworld_wild_spawns.o`: text `1024`, data `1144`, bss `93`,
  total `2261`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained. The shadow still only blinked midair when
  going from grass to land.

Conclusion:

- Manual-offset mode did not keep the floor shadow alive. The one-frame blink
  still points at a render-state handoff that is overwritten or hidden after
  the terrain transition, not merely the branch through `0x021F8D80`.

### S24 - Force Terrain Primary Update After Stock Draw

Hypothesis:

- S22 called the terrain primary updater before the normal draw callback, but
  the normal callback can overwrite primary sprite state afterward through
  `0x021F8D80`, `0x021FA3E8`, and `0x021F8C88`.
- The helper at `0x021F902C` fetches `renderData->primarySprite` and forwards
  variant/object/sprite to `0x02205808`.
- During active long-hop draw, call normal stock draw first with `unk88[1]`
  zeroed, then call the terrain primary updater with variant `0` as the final
  sprite-state writer before restoring `unk88[1]`.
- This is distinct from S22 because it tests ordering, not a different helper:
  if the shadow blink is caused by stock draw overwriting S22's pre-draw
  update, a post-draw update should persist for the visible frame.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_TERRAIN_PRIMARY_UPDATE`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the visible
  frame because the terrain-primary update is no longer overwritten by the
  normal draw callback.

Expected failure signal:

- Shadow still blinks/disappears, or the post-draw terrain helper visibly
  grounds or offsets the Pokemon body.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1488.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28474`, data `2728`, total `31202`.
- `build/overworld_wild_spawns.o`: text `1004`, data `1144`, bss `93`,
  total `2241`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained. The shadow still only blinked midair when
  going from grass to land.

Conclusion:

- Post-draw terrain-primary update was still not the owner. The persistent
  failure across S22/S24 means changing primary sprite terrain state before or
  after stock draw is not enough.

### S25 - Draw-Scoped Follower ID For Terrain Shadow Helpers

Hypothesis:

- Several stock terrain/shadow helpers still special-case follower map-object
  ID `0xFD`; for example, `0x022055B0`, `0x02205584`, and related terrain
  nibble helpers return false unless the object ID is `0xFD`.
- Overworld wild objects use reserved IDs `0xE0` through `0xE9`, so the stock
  terrain/shadow path can skip them even though `0x02205544` was patched to
  accept those IDs for palette/terrain-primary setup.
- The one-frame blink when moving from grass to land suggests the shadow can
  appear, but the terrain/follower shadow path is not allowed to stay active
  for wild IDs.
- During active long-hop draw only, temporarily set `mapObject->id` to `0xFD`
  while calling the normal stock draw callback, then restore the original ID
  before returning. Keep `unk88[1]` zeroed during draw and continue to let
  `faceVec[1]` carry the body arc.
- This tests the ID gate without changing spawn identity, object manager state,
  or saved object data outside the draw callback.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::id`

Expected success signal:

- Stock terrain/shadow helpers treat the wild object like the follower for the
  visible draw pass, keeping a stable floor shadow through grass/canopy-origin
  long hops.

Expected failure signal:

- Shadow still blinks/disappears, or follower-only draw side effects appear
  even though the ID is restored before the wrapper returns.

Build:

- Superseded before build by S26 after helper review found a more specific
  primary render-data lifecycle candidate.

Runtime result:

- Not tested.

Conclusion:

- Keep this as a possible later probe, but do not test it before the cheaper
  primary lifecycle rebuild. Draw-scoped ID spoofing is sharper because it can
  touch follower-only branches unrelated to the stale shadow state.

### S26 - Rebuild Primary Render Data Before Stock Draw

Hypothesis:

- The repeated grass-to-land blink suggests the shadow can be produced, but the
  live primary render-data/sprite state inherited from the grass/canopy origin
  does not stay valid.
- `0x021F90D0` snapshots the live primary sprite state through
  `0x021F9610(sprite, renderData + 4)`, calls
  `0x021F95A8(mapObject, renderData)` to release/recreate the primary sprite
  slot, then sets object render flag `0x00200000` with `0x0205F20C`.
- During active long-hop draw, zero `unk88[1]`, call the stock primary rebuild
  wrapper at `0x021F90D1`, then call the normal stock draw callback and restore
  `unk88[1]`.
- This is distinct from S22/S24 because it rebuilds the primary render-data
  lifecycle instead of only updating terrain-primary sprite state.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_PRIMARY_REBUILD`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`

Expected success signal:

- The rebuilt primary slot no longer carries stale grass/canopy-origin shadow
  state, so grass/canopy-origin long hops keep a stable floor shadow.

Expected failure signal:

- Shadow still only blinks/disappears, or the rebuild causes visible sprite
  flicker/duplication because it is too heavy for per-frame draw use.

Build:

- Succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1489.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28466`, data `2728`, total `31194`.
- `build/overworld_wild_spawns.o`: text `992`, data `1144`, bss `93`,
  total `2229`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained. The shadow still only blinked midair when
  going from grass to land.

Conclusion:

- Rebuilding the primary render-data slot during the airborne draw pass did not
  keep the shadow alive. It may also be too much per-frame sprite lifecycle
  churn for a visual-only fix, so future attempts should remove it unless a new
  test changes the render lifecycle variable.

### S27 - Draw-Scoped Follower ID Without Per-Frame Primary Rebuild

Hypothesis:

- S25 documented that several stock terrain/shadow helpers still special-case
  follower object ID `0xFD`, while wild overworld Pokemon use IDs `0xE0`
  through `0xE9`.
- S26 proved that per-frame primary slot rebuild does not solve the blinking
  shadow. The one-frame grass-to-land blink still looks like the stock shadow
  path can produce a floor shadow, but then rejects the wild object identity on
  subsequent frames.
- During active long-hop draw only, remove the S26 primary rebuild and
  temporarily set `mapObject->id` to `0xFD` around the normal stock draw
  callback, restoring the original ID before returning. Keep `unk88[1]` zeroed
  during draw and keep `faceVec[1]` as the body arc carrier.
- Reviewer note before runtime verification: apply this to the active long-hop
  flag state, not only to frames where `unk88[1]` is nonzero. The first/last
  airborne frames can have zero arc but may still seed or clear stock shadow
  state.
- This is distinct from S25 because it replaces the now-failed S26 rebuild
  path instead of stacking on top of it.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::id`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow for the whole
  airborne duration without attaching the shadow to the body.

Expected failure signal:

- Shadow still only blinks/disappears, or follower-only draw side effects
  appear even though the ID is restored before the wrapper returns.

Build:

- Initial arc-only S27 builds produced `test1490.nds` and `test1491.nds`; the
  first emitted a new `savedId` maybe-uninitialized warning, and both were
  superseded before runtime verification by the active-flag refinement above.
- Final refined S27 build succeeded through the UI build path.
- Copied ROM: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1492.nds`.
- The UI opened `test.nds` after the build.
- Build output had only the existing unrelated
  `src/battle/battle_script_commands.c:5516:54` unused-parameter warning.
- `build/linked.o`: text `28466`, data `2728`, total `31194`.
- `build/overworld_wild_spawns.o`: text `992`, data `1144`, bss `93`,
  total `2229`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`:
  text `44834`, bss `114`, total `44948`.

Runtime result:

- User verified the issue remained. The shadow still only blinked midair when
  going from grass to land.

Conclusion:

- The shadow suppression is not solved by draw-scoped follower ID spoofing.
  Either the relevant stock shadow path does not read `LocalMapObject::id` in
  the scoped window, or the state that hides/removes the shadow is owned
  outside the normal small-Pokemon draw callback.

### S28 - Deep Investigation Pass Before Next Runtime Probe

Goal:

- Stop adding render knobs until the blink is explained.
- Re-examine our active long-hop state, stock draw callback ownership, and the
  terrain transition handoff that produces exactly one frame of shadow on
  grass/canopy-to-land jumps.

Investigation questions:

- Is our wrapper only influencing the primary Pokemon body while the shadow is
  managed by a different stock field effect/sprite lifecycle?
- Does the one-frame blink correspond to logical-tile sync crossing from grass
  to land, followed by stock terrain state hiding the shadow again on the next
  frame?
- Are we clearing or rewriting a movement/render flag each frame that prevents
  the stock jump-shadow path from staying active?
- Is the current `faceVec[1]`/`unk88[1]` split feeding the body arc but never
  feeding the shadow owner?

Runtime result:

- No runtime probe was built for this pass. This was a read-only investigation
  plus documentation update.

Findings:

- The normal small-Pokemon callback at `0x021F7895` is mostly the body draw
  path. It creates or refreshes terrain/follower auxiliary state only when
  render-data byte `+0x17` bit 0 is clear, then calls primary draw
  `0x021F8D80`, primary sprite positioning `0x021FA3E8`, and final sprite
  visibility `0x021F8C88`.
- Primary draw `0x021F8D80` copies the current `faceVec` into its draw offset
  for Pokemon objects (`0x02205564`) and writes the resulting vector back with
  `0x0205F97C`. That explains why the body arc works when the overlay mirrors
  the long-hop arc into `faceVec[1]`.
- `0x021FA3E8` positions the primary sprite from `posVec + faceVec + unk88 +
  unk94`. The current wrapper zeroes `unk88[1]` only during the stock draw
  callback, then restores it afterward. Any later effect/shadow phase can still
  see restored `unk88[1]`, while the body has already been positioned from
  `faceVec[1]`.
- The secondary/full follower-style path around `0x021F7505` is not a safe
  drop-in callback. It has a hard follower object check and reads follower
  manager state before it reaches the shared sprite update body.
- The terrain/follower effect lifecycle around `0x0220589C` through
  `0x02206180` is a better candidate for the floor shadow owner than the small
  draw wrapper itself. It is asynchronous state, so it can sample persistent
  map-object state outside the tiny window where the draw wrapper temporarily
  mutates fields.
- The airborne logical sync currently calls
  `OverworldWildSpawns_SetObjectLogicalTileOnly`, which writes `xCurr/yCurr`,
  `xInit/yInit`, and `xPrev/yPrev` all to the same tile every frame while
  leaving `posVec` on the interpolated render position.
- Stock movement state is different: movement start/update preserves previous
  tile history and then advances current tile. During motion, stock code can
  see a real `prev -> curr` edge. The custom long-hop sync instead makes each
  crossed tile look like a fresh stationary/teleported object.
- The one-frame blink when crossing grass/canopy to land fits this model:
  persistent effect/shadow code briefly sees a valid floor condition when the
  logical tile crosses onto land, then loses it because the surrounding movement
  history and stock jump lifecycle do not look like a normal airborne move.

Conclusion:

- The failed S4-S27 attempts make sense if the shadow decision is owned by
  persistent movement/effect state rather than by the primary body draw pass.
- Do not keep cycling primary draw wrapper flags, secondary helper calls,
  render-data latch clears, primary rebuilds, or draw-scoped follower-ID
  spoofing without a new variable. Those only affect the body draw window or
  isolated helper fragments.
- The cheapest coherent next runtime probe is to preserve movement history
  during custom long-hop logical sync while keeping dynamic collision semantics.
  This tests the strongest code-level mismatch without adding a second jump
  system or a new shadow actor.

Recommended next probe:

- Add a tiny long-hop-only logical sync helper:
  - Read the old `MapObject_GetCurrentX/Y`.
  - If the pos-derived tile changed, copy old current tile to `xPrev/yPrev`.
  - Set `xCurr/yCurr` to the pos-derived tile through `MapObject_SetCurrentX/Y`.
  - Leave `xInit/yInit` unchanged during flight.
  - Keep `OverworldWildSpawns_SetObjectLandingTile` as the landing normalizer so
    settled state returns to `prev == curr == init`.
- Expected success signal: grass/canopy-to-land long hops keep a floor shadow
  for the airborne duration because stock effect code sees a moving object
  instead of a series of stationary teleports.
- Expected failure signal: shadow still only blinks, proving the missing state
  is deeper than logical movement history and likely requires either a
  frame-scoped stock Pokemon/follower identity probe or stock jump scratch
  seeding.

Fallback probes if movement history fails:

- Frame-scoped follower-ID probe: keep the object ID as `0xFD` for the whole
  airborne carrier frame/lifecycle and restore it on landing. This is only a
  diagnostic direction; if it works, patch the exact stock ID gates for wild
  IDs instead of keeping object identity spoofed.
- Stock jump scratch probe: identify and seed the normal jump movement scratch
  (`0x02062958`/`0x020629CC`) while the custom carrier still owns long-distance
  X/Z travel, testing whether the shadow owner requires stock jump lifecycle
  state beyond `faceVec[1]`.

### S29 - Preserve Movement History During Long-Hop Logical Sync

Hypothesis:

- S28 found that the active airborne sync calls
  `OverworldWildSpawns_SetObjectLogicalTileOnly`, which collapses `xCurr/yCurr`,
  `xPrev/yPrev`, and `xInit/yInit` to the same pos-derived tile every frame.
- That keeps collision dynamic, but it makes stock render/effect code see a
  series of stationary/teleported tile states instead of a moving airborne
  object.
- Replace only the canopy long-hop sync path with a tiny moving-logical update:
  preserve the old current tile as `xPrev/yPrev` when the pos-derived tile
  changes, update `xCurr/yCurr`, and leave `xInit/yInit` unchanged during
  flight. Keep landing normalization unchanged.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_SyncCanopyLongJumpDiagonalLogicalTile`
- `LocalMapObject::xCurr`, `LocalMapObject::yCurr`
- `LocalMapObject::xPrev`, `LocalMapObject::yPrev`

Expected success signal:

- Grass/canopy-to-land long hops keep a stable floor shadow during the airborne
  duration because persistent stock effect state sees a real movement edge.

Expected failure signal:

- Shadow still only blinks, proving the missing state is deeper than logical
  movement history and the next probe should test stock identity/lifecycle
  state instead.

Runtime result:

- First build attempt failed because overlay 149 `.text` no longer fit in
  region `rom` after adding the separate movement-history helper.
- Before rebuilding, shrank the same S29 probe by inlining the movement-history
  update into `OverworldWildSpawns_SyncCanopyLongJumpDiagonalLogicalTile`,
  removing the unused direction parameter, and writing `xCurr/yCurr` directly.
  The behavior remains scoped to the active canopy long-hop logical sync.
- Rebuild through the Overworld Behavior Profile Viewer server succeeded after
  the shrink. `test.nds` opened successfully and was copied to Delta as
  `test1493.nds`.
- User verified the issue remained. The shadow still only blinked midair when
  going from grass/canopy to land.

Conclusion:

- Preserving `xPrev/yPrev -> xCurr/yCurr` movement history during active
  long-hop sync did not keep the shadow alive. The missing state is not just
  logical tile movement history.

### S30 - Keep `unk88[1]` Floor-Zero For Whole Long-Hop Frame

Hypothesis:

- Current long-hop code mirrors the arc into both `faceVec[1]` and
  `unk88[1]`.
- The draw wrapper zeroes `unk88[1]` only while the stock body callback runs,
  then restores the arc afterward.
- S28 found the likely shadow/effect owner is persistent terrain/follower state
  outside the small body callback. If that later stage samples restored
  `unk88[1]`, it may lift/suppress the floor effect after the one valid terrain
  crossing frame.
- Keep `posVec[1]` on the floor and keep the body arc in `faceVec[1]`, but
  stop storing the arc in `unk88[1]` during active long-hop frames. Landing
  already clears both values.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`

Expected success signal:

- Grass/canopy-to-land long hops keep a stable floor shadow for the airborne
  duration, with the Pokemon body still arcing through `faceVec[1]`.

Expected failure signal:

- Shadow still only blinks, proving the shadow owner does not care about
  persistent `unk88[1]`, or shadow attaches to the body, proving this field
  split is still not the right floor/air contract.

Runtime result:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1494.nds`.
- User verified this was a regression: Pokemon no longer hopped at all.
- Reverted the code path to the prior carrier contract where
  `unk88[1]` stores the arc and `faceVec[1]` mirrors it.

Conclusion:

- `unk88[1]` is still required by the current visible long-hop presentation.
  Do not keep it floor-zero unless the hop presentation is rebuilt around a
  different stock movement lifecycle.

### S31 - Restore Stock Internal Jump Lifecycle For Long-Hop Carrier

Hypothesis:

- S28-S30 show the shadow is not fixed by draw-wrapper flags, logical movement
  history, or changing the `faceVec[1]`/`unk88[1]` split.
- Prior canopy long-hop Attempt 190 found the stable carrier: partner prep,
  one `MapObject_StartMovementCommandInternal` plus
  `MapObject_StartJumpMovementInternal`, then `Freeze -> 0x4A` restore.
- Current production code has drifted into partner prep plus a `Freeze`
  movement command while manually driving X/Z and arc. That bypasses the stock
  jump scratch/lifecycle likely used by the async shadow/effect owner.
- Rebuild the active carrier around stock internal jump state again:
  - Start a direction-specific internal jump command instead of a freeze command.
  - Let stock movement own primary-axis travel and vertical arc.
  - Preserve dynamic hop time by deriving `deltaFx32` from distance and
    `frameCount`.
  - Keep the existing custom secondary-axis interpolation only for diagonal
    jumps.
  - Keep final landing/restore bookkeeping unchanged.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `MapObject_StartMovementCommandInternal`
- `MapObject_StartJumpMovementInternal`

Expected success signal:

- Grass/canopy-to-land long hops keep a stable floor shadow while the Pokemon
  still visibly hops and diagonal/cardinal landings remain correct.

Expected failure signal:

- Overlay 149 overflows, hop timing/distance regresses, diagonal hops become
  visually/logically inconsistent, or the shadow still only blinks. A remaining
  blink after stock lifecycle restoration would point away from movement state
  and back to terrain/effect resource ownership.

Runtime result:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1496.nds`.
- User verified this was a regression: Pokemon no longer jumped.
- The first S31 build had kept the manual-carrier timing formula where extra
  tiles get slightly faster. That formula feeds unsafe per-frame values into
  `MapObject_StartJumpMovementInternal`.
- Adjusted S31 to use the previously proven internal-jump timing contract:
  `frameCount = distance * hopTime`, with `deltaFx32` derived from total
  distance over that frame count.
- Rebuild after the timing repair succeeded through the Overworld Behavior
  Profile Viewer server. `test.nds` opened successfully and was copied to Delta
  as `test1497.nds`.
- The old `scripts/verify-diagonal-canopy-ram.py` helper referenced by earlier
  canopy docs is no longer present, and the diagonal RAM probe is compiled off,
  so no headless runtime movement proof was recorded for this build.
- User verified `test1497.nds` still had broken Pokemon hopping.
- Reverted S31 back to the pre-S31 manual long-hop carrier: partner prep,
  freeze command, custom X/Z interpolation, and custom `unk88[1]`/`faceVec[1]`
  arc. Kept S29's logical tile history sync.

Conclusion:

- S31 is rejected as a production path. The stock internal jump carrier breaks
  the current long-hop presentation and must not be retried in-place without a
  separate diagnostic path that proves visible hopping still works first.

### S32 - Remove Draw-Scoped Follower ID Spoof And Stop Re-Seeding Move-Start

Hypothesis:

- S27 proved that draw-scoped spoofing of the wild object ID to follower ID
  `0xFD` does not keep the floor shadow alive. Keeping that failed probe in the
  production wrapper only broadens side effects and makes future observations
  harder to reason about.
- The active manual long-hop path currently sets `BIT_MOVE_START` every frame
  together with `BIT_JUMP_START` and `MAPOBJECTFLAG_UNK13`.
- `BIT_MOVE_START` is movement lifecycle state, not just render/shadow state.
  Re-seeding it every frame may make stock render/effect code repeatedly see a
  fresh movement start instead of a stable airborne jump, which matches the
  "shadow blinks once when crossing grass/canopy to land" symptom.
- Keep the working manual carrier and visible arc untouched. Only advertise
  jump visibility (`BIT_JUMP_START | MAPOBJECTFLAG_UNK13`) during active long
  hops and remove the already-failed follower-ID draw spoof.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`

Expected success signal:

- Grass/canopy-to-land long hops keep a stable ground shadow under the airborne
  Pokemon, with the body still hopping/arcing normally.

Expected failure signal:

- Shadow still only blinks, proving the persistent shadow invalidation is not
  caused by the failed ID spoof or repeated `BIT_MOVE_START` seeding.

Runtime result:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1499.nds`.
- User verified this was a regression: the canopy long-hop shadow never
  appeared at all.

Conclusion:

- Removing `BIT_MOVE_START` from the active manual long-hop render contract
  removes even the prior one-frame shadow blink. The bit is not sufficient to
  fix the midair shadow, but it is still required for the current shadow owner
  to produce any visible floor shadow during this custom hop.
- Keep the failed S27 draw-scoped follower-ID spoof removed unless a new
  diagnostic changes the variable under test.

### S33 - Restore Move-Start After No-Shadow Regression

Hypothesis:

- S32 changed two variables at once: it removed the already-failed
  draw-scoped follower-ID spoof and stopped re-seeding `BIT_MOVE_START`.
- S27 already proved the follower-ID spoof was not a working fix.
- The new "never shadow" runtime result is therefore most likely from removing
  `BIT_MOVE_START`.
- Restore `BIT_MOVE_START` as part of the active long-hop flag contract while
  leaving the failed follower-ID spoof out. This should return runtime behavior
  to the pre-S32 baseline, where the shadow could at least blink on
  grass/canopy-to-land transitions.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_CANOPY_LONG_JUMP_VISIBLE_FLAGS`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`

Expected success signal:

- Canopy long-hop shadows are no longer completely absent; behavior returns to
  the previous partial baseline where grass/canopy-to-land jumps can produce a
  one-frame floor-shadow blink.

Expected failure signal:

- Shadow remains completely absent, proving the removed draw-scoped ID spoof or
  another recent variable was part of the previous baseline.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1500.nds`.

Runtime result:

- Needs user verification. This build is expected to restore the pre-S32
  partial baseline, not solve the full midair shadow issue.

### S34 - Seed Stock Auxiliary Resource For Active Long-Hop

Hypothesis:

- The stock small-Pokemon draw callback calls the auxiliary/effect resource
  constructor at `0x0220589C` only when helper `0x02205564` accepts the map
  object before render-data byte `+0x17` bit 0 is set.
- Disassembly shows `0x02205564` checks a narrow stock sprite/gfx range
  (`0x019F..0x01A4`), so normal wild overworld Pokemon can take the
  primary-only terrain update path and never seed the `unk108[4]` auxiliary
  owner used by secondary/floor-shadow helpers.
- S7-S11 proved calling secondary draw helpers alone does not create this owner.
- During active canopy long-hop only, call the same stock constructor
  (`0x0220589D` as a Thumb function pointer) once per current wild slot primary
  sprite when `renderData->primarySprite` exists and `renderData->secondarySprite`
  is still null. This does not add a new custom shadow actor; it asks stock to
  create the missing auxiliary owner.

Files/symbols:

- `armips/asm/overworlds.s`
- `OverworldWildSpawns_IsPokemonPaletteObjectId`
- `0x02205564`
- `LocalMapObject::unk108[0]`
- `LocalMapObject::unk108[4]`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the airborne
  duration because the stock auxiliary owner now exists while the custom body
  arc remains in the existing wrapper.

Expected failure signal:

- Shadow still only blinks/disappears, proving the missing state is not just
  the absence of the `unk108[4]` auxiliary owner; or the ROM crashes/duplicates
  an effect, proving this constructor is unsafe outside the stock init gate.

Build:

- First ARM9 wrapper form called `0x0220589D` directly from
  `OverworldWildSpawns_CanopyLongJumpDrawWrapper` and guarded by the current
  primary sprite pointer. It failed to link because base ARM9 overflowed by
  68 bytes.
- A shrunk ARM9 wrapper form using a slot bitmask still failed to link because
  base ARM9 overflowed by 40 bytes.
- Reworked S34 to avoid adding ARM9 code: patch the stock helper at
  `0x02205564` so it branches to the existing wild-ID-aware
  `OverworldWildSpawns_IsPokemonPaletteObjectId` helper. This lets wild object
  IDs use the stock one-shot aux init path when render-data bit `+0x17` bit 0
  is clear.
- Build through the Overworld Behavior Profile Viewer server succeeded after
  the overlay-only rewrite. `test.nds` opened successfully and was copied to
  Delta as `test1501.nds`.

Runtime result:

- User verified this was a regression: Pokemon disappeared, including the
  follower Pokemon, and the midair shadow issue remained.

Conclusion:

- Replacing helper `0x02205564` globally is not safe. That helper is not only a
  "wild IDs may create aux owner" gate; it participates in normal
  small-Pokemon/follower render setup. Do not patch it globally.
- The missing shadow is not fixed by giving all wild IDs the stock aux-init
  predicate at this address.

Rollback:

- Removed the global `0x02205564` patch and rebuilt through the Overworld
  Behavior Profile Viewer server. `test.nds` opened successfully and was copied
  to Delta as `test1502.nds`.

### S35 - One-Shot Aux Init Through Draw-Scoped Gfx Spoof

Hypothesis:

- S34 proved that globally changing `0x02205564` is unsafe because the helper is
  used outside the stock one-shot aux init gate.
- The safer version is to leave `0x02205564` intact and only influence the one
  stock draw where the long-hop object deliberately asks render setup to rerun.
- At long-hop start, clear render-data byte `+0x17` bit 0 once so the normal
  small-Pokemon callback re-enters its setup gate.
- In the long-hop draw wrapper only while that bit is still clear, temporarily
  spoof `gfxId` into the stock `0x019F..0x01A4` range, call the normal callback,
  then restore the real `gfxId`. This should call the stock aux constructor
  once without making every frame or every caller treat wild objects as stock
  follower/Pokemon gfx.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::gfxId`
- `LocalMapObject::unk108[0x17]`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`

Expected success signal:

- Pokemon and follower visibility remain normal, and grass/canopy-origin long
  hops keep a stable floor shadow because the stock auxiliary owner is seeded
  only for the committed long hop.

Expected failure signal:

- Shadow still only blinks, proving the missing state is not just the stock
  aux constructor; or the one setup frame visibly flickers because gfx spoofing
  affects too much of the stock body draw.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1503.nds`.

Runtime result:

- User verified this did not solve the issue. The shadow behavior remained the
  same: it only blinked briefly midair on grass/canopy-to-land transitions.

Conclusion:

- One-shot stock-eligible aux setup is not enough. Either the stock
  terrain/effect owner invalidates the state after setup, or the missing floor
  shadow state is not created by this setup gate alone.
- Keep the S35 shape as useful evidence, but do not leave it as a claimed fix.

### S36 - Active-Frame Stock Setup Rerun With Draw-Scoped Gfx Spoof

Hypothesis:

- S4 only cleared the render setup latch, while S35 only spoofed a stock
  aux-owning gfx ID for the single setup rerun requested at long-hop start.
- If the shadow owner is being invalidated immediately after the setup frame,
  the long-hop draw wrapper should request stock setup again for every active
  airborne frame and spoof the stock gfx ID during each rerun.
- This keeps the experiment inside the existing stock small-Pokemon draw
  callback. It does not add a custom shadow actor and does not globally patch
  follower/Pokemon identity helpers.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::gfxId`
- `LocalMapObject::unk108[0x17]`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the
  airborne duration because the stock terrain/effect setup is refreshed every
  active frame while the object is presented as a stock aux-owning gfx.

Expected failure signal:

- Shadow still only blinks, proving the missing owner is outside the small
  Pokemon setup gate; or the Pokemon visibly flickers because per-frame setup
  churn is too invasive.

Runtime result:

- Superseded before build by S37 after a focused disassembly pass identified
  the exact terrain-suppression call inside stock primary draw. S36 was removed
  from the code before building so the next ROM has only one new shadow
  variable.

Conclusion:

- Do not test S36 before the terrain gate. It is still another setup-lifecycle
  probe, while S37 directly targets the branch that writes the terrain
  suppression latch.

### S37 - Force Stock Terrain Suppression Gate False

Hypothesis:

- Stock primary draw `0x021F8D80` calls normal sprite/shadow setup
  `sub_02023F04(sprite, 0x1000)` and then calls terrain gate `0x021F8FC0`.
- If that terrain gate returns nonzero, stock primary draw subtracts `0x2000`
  from draw Y and writes render-data byte `+0x15 = 1`. If it returns zero, it
  writes `+0x15 = 0`.
- S15 skipped too much by bypassing the whole block through
  `MAPOBJECTFLAG_UNK4`, and S17/S18 only cleared byte `+0x15` before/after
  stock draw. This probe keeps the stock setup block but forces only the
  terrain-gate return to false.
- This is a global diagnostic patch for overlay 1. If it works, replace it
  with a conditional wild-long-hop-only thunk instead of shipping the global
  terrain change.

Files/symbols:

- `armips/asm/overworlds.s`
- `0x021F8E3A`
- `0x021F8FC0`
- `LocalMapObject::unk108[0x15]`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow, proving the
  terrain-suppression gate is the source of the midair blink.

Expected failure signal:

- Shadow still only blinks or disappears, proving the missing state is not the
  primary terrain gate result; or other overworld Pokemon/follower terrain
  rendering looks wrong because this diagnostic patch is intentionally global.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1504.nds`.

Runtime result:

- User verified S37 did not solve the issue. The shadow still only blinked
  briefly midair on grass/canopy-to-land jumps.

Conclusion:

- The stock primary draw terrain-suppression gate at `0x021F8E3A` /
  `0x021F8FC0` is not the missing floor-shadow owner.
- Removed the global ARMIPS patch before the next probe so later results are
  not masked by a failed terrain-gate diagnostic.

### S38 - Active-Frame Stock Setup Rerun After S37 Rollback

Hypothesis:

- S35 proved that seeding stock aux setup once at long-hop start is not enough.
- S37 proved that forcing the primary terrain suppression gate false is also
  not enough.
- The remaining cheap setup-lifecycle probe is the deferred S36 shape: while a
  canopy long hop is actively airborne, clear render-data byte `+0x17` bit 0 on
  every draw frame and temporarily spoof `gfxId` into the stock aux-owning range
  only for the normal small-Pokemon callback.
- This tests whether the stock aux/effect owner at `0x0220589C` has to be
  refreshed continuously during the manual long-hop carrier.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::gfxId`
- `LocalMapObject::unk108[0x17]`
- `armips/asm/overworlds.s`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the airborne
  duration because the stock aux/effect setup is kept alive for every active
  long-hop draw frame.

Expected failure signal:

- Shadow still only blinks, proving the missing floor-shadow state is outside
  the stock setup latch/aux-gfx path; or Pokemon rendering flickers because
  per-frame setup churn is too invasive.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1506.nds`.

Runtime result:

- User verified the issue remained. The shadow still did not stay visible
  midair.

Conclusion:

- Draw-scoped `gfxId` spoofing plus per-frame setup-latch clearing is not
  enough.
- This suggests the missing state is owned by an async stock aux/shadow
  lifecycle that outlives `OverworldWildSpawns_CanopyLongJumpDrawWrapper`, so
  restoring `gfxId` immediately after the stock draw can still starve later
  update/render work.

### S39 - Keep Stock Shadow-Capable Gfx Identity For Full Airborne Span

Hypothesis:

- S38 only spoofed `LocalMapObject::gfxId` during the stock draw callback.
- Disassembly shows the stock aux/effect constructor at `0x0220589C` creates
  persistent task/effect state, and later callbacks can run after the wrapper
  has restored the real Pokemon `gfxId`.
- While the custom long-hop carrier is active, keep the object metadata
  `gfxId` in the stock shadow-capable range (`0x019F`) for the whole airborne
  span, then restore the real species sprite id when the hop lands or is
  cancelled.
- Keep the real loaded primary sprite and the existing custom arc path; this
  tests only async shadow-owner identity lifetime, not a new jump system.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_ClearCanopyLongJumpDiagonal`
- `LocalMapObject::gfxId`
- `LocalMapObject::unk108[0x17]`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the airborne
  duration because stock aux/shadow update callbacks continue to see a
  stock-shadow-capable object identity between draw frames.

Expected failure signal:

- Shadow still only blinks or disappears, proving `gfxId` identity lifetime is
  not the remaining gate and the next fix should stop probing stock identity
  and move to an owned floor-shadow payload.

Build:

- Superseded before build by S40 after a second helper-agent disassembly pass
  identified a distinct async follower/effect object-ID gate at `0x022055DC`.

Runtime result:

- Not tested.

Conclusion:

- Do not test S39 first. It still probes `gfxId` / setup identity, while S40
  targets the remaining hard follower-ID gate that draw-scoped probes would not
  cover.

### S40 - Admit Wild IDs Through Async Effect Shadow Nibble Gate

Hypothesis:

- The stock async effect path has a separate helper at `0x022055DC` that reads
  `(MapObject_GetParam(object, 1) >> 8) & 0xF`, but first hard-gates the object
  ID to follower ID `0xFD`.
- Disassembly identified callers at `0x022036FA` and `0x022038D8`, which are
  outside the map-object draw callback. That means S27 draw-scoped follower-ID
  spoofing and S38 draw-scoped `gfxId` spoofing can miss this gate.
- Patch only the gate inside `0x022055DC` to call the existing
  wild-ID-aware `OverworldWildSpawns_IsPokemonPaletteObjectId`, then leave the
  original nibble return path at `0x022055F8` unchanged.

Files/symbols:

- `armips/asm/overworlds.s`
- `OverworldWildSpawns_IsPokemonPaletteObjectId`
- `0x022055DC`
- `0x022055EC`
- `0x022055F8`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the airborne
  duration because the async follower/effect shadow helper now treats wild
  spawn object IDs `0xE0..0xE9` like the follower object.

Expected failure signal:

- Shadow still only blinks or disappears, proving the remaining issue is not
  the async `0x022055DC` follower-ID gate.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1507.nds`.

Runtime result:

- User verified the issue remained.

Conclusion:

- The async `0x022055DC` follower-ID gate is not the missing owner for the
  long-hop midair shadow.
- Stop probing stock follower/shadow gates without a new concrete disassembly
  signal; the next attempt should make the long-hop path own the shadow
  explicitly or hook a proven floor-shadow payload directly.

### S41 - Long-Hop-Owned Dark Ground Effect Canary

Hypothesis:

- S40 and the earlier stock draw/gate probes show the existing Pokemon shadow
  owner is not being kept alive by custom canopy long-hop movement.
- The next cheapest non-repeated test is to let the long-hop movement state own
  a floor presentation, while keeping the current single jump/movement carrier.
- `ov01_0220329C(LocalMapObject *, int)` is already imported, previously
  stable, and was observed to produce a small dark ground/blob effect. It is
  not an exact Pokemon shadow, but it is a stock effect-layer payload that can
  test whether an owned floor visual survives grass/canopy-origin hops.
- During active long-hop frames, periodically launch that dark-ground effect
  from the existing object floor position. Do not touch `faceVec[1]` or
  `unk88[1]`; those remain body arc state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `ov01_0220329C`
- `movementCanopyLongJumpDiagonalElapsedFrames`

Expected success signal:

- Grass/canopy-origin long hops have a visible ground-following dark mark for
  the airborne duration, proving the presentation must be owned by the long-hop
  state rather than the stock Pokemon shadow gates.

Expected failure signal:

- No visible improvement, proving `ov01_0220329C` is not a usable floor-shadow
  payload in this context; or visible trailing/blobs that confirm the owned
  effect route works but needs a custom exact shadow sprite instead.

Build:

- First shape with a separate helper overflowed overlay 149:
  `build/overworld_wild_spawns_overlay_linked.o section .text will not fit in
  region rom`.
- Shrunk the probe to a direct odd-frame call inside
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`.
- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1508.nds`.

Runtime result:

- User verified this produced a shiny-style effect on the Pokemon, not a floor
  shadow.

Conclusion:

- `ov01_0220329C` is not a usable shadow payload.
- The effect is useful enough to preserve separately as a future shiny
  overworld Pokemon visual candidate; see
  `documentation/shiny_overworld_pokemon_effect.md`.
- Remove the active long-hop call before the next shadow attempt.

### S42 - Leave `unk88[1]` Floor-Zero After Stock Draw

Hypothesis:

- S30 failed because it stopped storing the arc in `unk88[1]` during the
  movement update path, which also starved the visible hop presentation.
- The active draw wrapper already proves a narrower split works for the body:
  movement writes the arc to both `faceVec[1]` and `unk88[1]`, then the wrapper
  zeroes `unk88[1]` while stock draw positions the Pokemon body from
  `faceVec[1]`.
- The wrapper currently restores `unk88[1]` immediately after stock draw. If
  the async shadow/effect phase runs later in the frame, it may still see the
  restored airborne offset and drop the floor shadow after the one-frame
  grass/canopy-to-land blink.
- Do not change movement update or body arc calculation. Only stop restoring
  `unk88[1]` after the stock draw callback, letting the next movement update
  recalculate it before the next draw.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`

Expected success signal:

- Pokemon still visibly hop because `faceVec[1]` carries the body arc, while
  grass/canopy-origin long hops keep a stable floor shadow because later
  shadow/effect phases see `unk88[1] == 0`.

Expected failure signal:

- Pokemon hop presentation regresses, or shadow still only blinks, proving
  post-draw `unk88[1]` lifetime is not the missing floor-shadow state.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1509.nds`.

Runtime result:

- Superseded before user runtime verification. A helper-agent disassembly pass
  found that this likely targets the wrong carrier: `unk88[1]` affects the
  primary body position path, while the terrain-dependent floor shadow appears
  to depend on follower/Pokemon terrain nibble helpers around `0x02205584` and
  `0x022055B0`.

Conclusion:

- Restore the pre-S42 wrapper behavior before the next probe so the next ROM
  tests one variable: wild-ID admission through the terrain nibble helpers.

### S43 - Admit Wild IDs Through Terrain Nibble Helpers

Hypothesis:

- S40 patched only the async helper at `0x022055DC`, which reads a higher
  param-1 nibble and did not fix the shadow.
- Disassembly shows the stock terrain primary gate reaches `0x021F8FC0`, which
  calls `0x022055B0`; sibling helper `0x02205584` reads the high nibble of the
  low param-1 byte.
- Both helpers hard-gate on follower object ID `0xFD` before reading
  `MapObject_GetParam(object, 1)`.
- Patch only those helper gates to call the existing
  `OverworldWildSpawns_IsPokemonPaletteObjectId`, while leaving each helper's
  original nibble extraction unchanged. This admits wild spawn IDs `0xE0..0xE9`
  to the stock terrain data path without touching the broader `0x02205564`
  helper that caused the S34 visibility regression.

Files/symbols:

- `armips/asm/overworlds.s`
- `OverworldWildSpawns_IsPokemonPaletteObjectId`
- `0x02205584`
- `0x022055B0`
- `MapObject_GetParam(object, 1)`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow through the
  airborne duration because the stock terrain-effect path can read the wild
  object's param-1 nibbles just like a follower Pokemon.

Expected failure signal:

- Shadow still only blinks or disappears, proving these terrain nibble gates
  are not the missing floor-shadow owner.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1510.nds`.
- Binary sanity check of `base/overlay/overlay_0001.bin` confirmed both
  patched helpers branch to `OverworldWildSpawns_IsPokemonPaletteObjectId`
  before keeping their original high/low nibble extraction.

Runtime result:

- User verified the issue remained.

Conclusion:

- The `0x02205584` / `0x022055B0` terrain nibble gates are not the missing
  owner for the long-hop floor shadow.
- Remove the S43 helper patch before the next probe so failed stock terrain
  gate state does not stack with a distinct owned-floor effect test.

Rollback:

- Removed the S43 `0x02205584` and `0x022055B0` ARMIPS patches before S44.

### S44 - Owned Floor-Coordinate Effect Probe

Hypothesis:

- S40-S43 strongly suggest the stock follower/Pokemon terrain gates are not
  keeping the floor shadow alive for custom long hops.
- The next distinct cheap probe is to let the active long-hop state own a
  floor-positioned visual through a stock constructor that accepts explicit
  floor coordinates, rather than anchoring to the airborne object.
- `ov01_021FECA0(LocalMapObject *, int x, int height, int y)` creates effect
  id `6` using explicit x/y floor coordinates. This is different from S41's
  `ov01_0220329C`, which was object-anchored and produced a shiny-style effect.
- During active long-hop frames, call `ov01_021FECA0` from the interpolated
  logical tile every four frames with height `0`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::xCurr`
- `LocalMapObject::yCurr`
- `ov01_021FECA0`

Expected success signal:

- Grass/canopy-origin long hops show a stable floor-positioned mark through
  the airborne duration, proving the long-hop state can own a floor visual
  independent of terrain gates.

Expected failure signal:

- No visible floor mark, the wrong non-shadow effect appears, or the mark still
  blinks/disappears with terrain, proving this stock effect is not a usable
  owned shadow payload.

Build:

- First shape with both a frame-modulo guard and an explicit `elapsed < total`
  guard overflowed overlay 149:
  `build/overworld_wild_spawns_overlay_linked.o section .text will not fit in
  region rom`.
- Shrunk the probe by dropping the redundant end-frame guard and keeping only
  the every-fourth-frame check.
- The shrunk direct overlay call still overflowed overlay 149.
- Moved the expensive coordinate/effect call into base ARM9 helper
  `OverworldWildSpawns_CanopyLongJumpFloorProbe`, leaving overlay 149 with
  only the every-fourth-frame helper call.
- Build through the Overworld Behavior Profile Viewer server succeeded after
  the helper split. `test.nds` opened successfully and was copied to Delta as
  `test1511.nds`.

Runtime result:

- User verified the issue remained, and the ROM crashed immediately when a
  Pokemon spawned.

Conclusion:

- `ov01_021FECA0` is not safe as a long-hop-owned floor shadow payload in this
  path. Remove it immediately; do not retry this constructor from spawn or
  movement update without a separate crash-isolated harness.

Rollback:

- Removed `OverworldWildSpawns_CanopyLongJumpFloorProbe` and the active
  long-hop call before rebuilding.
- Rollback build through the Overworld Behavior Profile Viewer server
  succeeded. `test.nds` opened successfully and was copied to Delta as
  `test1513.nds`.

### S45 - Carry Body Arc In `unk94[1]`

Hypothesis:

- The repeated one-frame grass/canopy-to-land shadow blink suggests the stock
  shadow owner can briefly draw the floor shadow, but one of the live vertical
  offset channels makes it hide the shadow again on the next frame.
- Earlier attempts either carried the arc in `faceVec[1]` / `unk88[1]`, or
  zeroed `unk88[1]` without providing a separate visible-hop carrier.
- Disassembly notes indicate final sprite positioning sums
  `posVec + faceVec + unk88 + unk94`. Test whether `unk94[1]` can carry the
  visible Pokemon body arc while `faceVec[1]` and `unk88[1]` stay floor-zero
  for the stock shadow/effect owners.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_SetObjectLandingTile`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`
- `LocalMapObject::unk94[1]`

Expected success signal:

- The Pokemon body still follows the long-hop arc, and grass/canopy-origin
  long hops keep a stable floor shadow because shadow-sensitive channels remain
  floor-zero for the full frame.

Expected failure signal:

- No visible hop means `unk94[1]` is not a usable body-arc carrier in this draw
  path.
- A shadow attached to the airborne body means the stock shadow owner also
  consumes `unk94[1]`.
- The same one-frame blink means the missing owner is outside these vector
  channels.

Build:

- Build through the Overworld Behavior Profile Viewer server succeeded.
  `test.nds` opened successfully and was copied to Delta as `test1514.nds`.
- Build warning: existing unused `bsys` parameter in
  `src/battle/battle_script_commands.c`.

Runtime result:

- User verified the Pokemon no longer hopped.

Conclusion:

- `unk94[1]` is not a usable visible body-arc carrier for the current
  long-hop draw path.
- S46 must restore the visible arc to the known working `faceVec[1]` /
  `unk88[1]` path before testing a new shadow-specific idea.

### S46 - Keep Stock Shadow-Capable `gfxId` During Airborne Span

Hypothesis:

- S35 and S38 only spoofed `LocalMapObject::gfxId` during the draw wrapper.
  If the async terrain/follower shadow owner runs after the wrapper returns,
  it still sees the real wild Pokemon sprite id and can discard the shadow
  owner between frames.
- S40 and S43 patched object-ID/nibble gates, but did not test the full
  airborne lifetime of the stock shadow-capable `gfxId` predicate at
  `0x02205564`.
- Restore the working S44/S45 body carrier: `faceVec[1]` and `unk88[1]` both
  receive the arc, and the wrapper zeroes `unk88[1]` only during stock draw.
- While a canopy long hop is active, try making `object->gfxId` stock
  shadow-capable (`0x019F`) for the airborne span.
- A fuller version would also restore the real species sprite id on cleanup and
  clear render-data byte `+0x17` bit 0 once at long-hop start, but those pieces
  overflowed overlay 149 and were trimmed from the buildable S46 patch.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_ClearCanopyLongJumpDiagonal`
- `LocalMapObject::gfxId`
- `LocalMapObject::unk108[0x17]`
- `0x02205564`

Expected success signal:

- Pokemon visibly hop again, and grass/canopy-origin long hops keep a stable
  floor shadow because async shadow/effect code sees stock-eligible `gfxId`
  outside the draw wrapper.

Expected failure signal:

- Shadow still only blinks, proving `gfxId` lifetime is not the missing async
  owner predicate.
- Pokemon flickers or renders with the wrong stock metadata, proving full-span
  `gfxId` spoofing is too invasive even as a diagnostic.

Patch applied:

- Restored the visible long-hop arc to the pre-S45 carrier: both
  `faceVec[1]` and `unk88[1]` receive
  `OverworldWildSpawns_GetCanopyLongJumpArcHeight(...)`; `unk94[1]` is reset to
  zero again.
- The buildable S46 probe set `LocalMapObject::gfxId` to `0x019F` at canopy
  long-hop start; after the runtime crash result, that write was removed.
- The render-data `+0x17` latch clear was removed after repeated overlay 149
  `.text` overflows.
- The explicit `gfxId` restore was removed after overlay 149 overflowed. This
  became irrelevant after the crash result because the unsafe `gfxId` write was
  removed entirely. The current branch keeps only the visible-hop carrier
  restoration from this investigation.

Build result:

- First S46 build with start-time `gfxId`, render-data latch clear, and explicit
  landing/cleanup restore failed: overlay 149 `.text` would not fit.
- Second S46 build without duplicate landing restore still failed the same
  overlay 149 `.text` limit.
- Third S46 build without explicit restore still failed the same overlay 149
  `.text` limit.
- Fourth S46 build, reduced to restored hop carrier plus start-time `gfxId`
  seed only, succeeded through the UI build path and copied/opened
  `test1515.nds`.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- User verified the buildable S46 still crashes.

Conclusion:

- Full-span stock-shadow `gfxId` spoofing is rejected. Even the minimal
  start-time `object->gfxId = 0x019F` probe is not safe.
- The S46 `gfxId` write was removed. The S45 rollback that restores visible hop
  through `faceVec[1]` / `unk88[1]` remains.
- S47 should not pursue `gfxId` spoofing or render-data latch resets inside
  overlay 149. Prefer a floor-sampled stock aux setup hook or an owned custom
  shadow path outside this tight movement overlay.

Rollback build:

- After removing the S46 `gfxId` write, the UI build succeeded and copied/opened
  `test1516.nds`.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

### S47 - Floor-Sample Wild Terrain/Aux Update

Hypothesis:

- S46 proved `gfxId` spoofing is unsafe and should stay rejected.
- With real wild Pokemon `gfxId`, the stock constructor branch at `0x0220589C`
  is usually not reached. The wild-ID-aware branch that is reached calls the
  terrain/aux update helper at `0x02205808`.
- During a custom long hop, `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
  already zeroes `unk88[1]` for the whole stock draw callback, but leaves
  `faceVec[1]` live so the body hop still renders.
- S47 patches only the `0x021F78E6 -> 0x02205808` call. The wrapper saves
  `faceVec[1]`, zeroes it for that tiny terrain/aux update call, restores it,
  then returns before the stock primary body draw runs.

Files/symbols:

- `armips/asm/overworlds.s`
- `0x021F78E6`
- `0x02205808`
- `LocalMapObject::faceVec[1]`

Expected success signal:

- Grass/canopy-origin long hops keep a stable floor shadow while the Pokemon
  body still visibly hops through `faceVec[1]`.

Expected failure signal:

- Shadow still only blinks/disappears, proving the helper is not the owner of
  the persistent midair shadow state; or a render regression appears because
  this terrain/aux path expected airborne `faceVec[1]`.

Build result:

- The UI build succeeded and copied/opened `test1517.nds`.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- User verified S47 did not fix the midair shadow issue.

Conclusion:

- The wild terrain/aux update at `0x02205808` is not the missing persistent
  midair shadow owner, or zeroing `faceVec[1]` only during that call is too
  narrow to affect the state that hides shadows after grass/canopy-origin
  hops.
- Do not repeat narrow floor-sampling around this helper unless new evidence
  shows a different state is being sampled there.

### S48 - Manually Floor-Position Secondary Sprite After Body Draw

Hypothesis:

- The stock secondary callback attempts failed, but they still asked the stock
  callback path to own both state and positioning.
- The long-hop wrapper already has the exact frame window where the body is
  drawn airborne and `unk88[1]` is temporarily floor-zero.
- Reuse the existing `renderData->secondarySprite` only as a payload: after the
  normal body draw, temporarily zero `faceVec[1]`, `unk88[1]`, and `unk94[1]`,
  then call the known stock sprite position and visibility helpers directly
  for the secondary sprite.
- This does not create effects, does not touch `gfxId`, and does not add code
  to overlay 149.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_DrawCanopyLongJumpFloorSecondary`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`
- `LocalMapObject::unk94[1]`
- `renderData->secondarySprite`
- `0x021FA3E8`
- `0x021F8C88`

Patch applied:

- Removed the S47 terrain/aux floor-sampling hook from `armips/asm/overworlds.s`.
- First tried direct calls to the sprite position helper `0x021FA3E8` and
  visibility helper `0x021F8C88` for the secondary sprite after the active
  long-hop body draw, with all vertical offset channels temporarily zeroed.
- The direct-helper shape overflowed base ARM9 by 36 bytes.
- Shrunk the patch to call the stock secondary helper `0x021F77A5` after
  temporarily zeroing `faceVec[1]`, `unk88[1]`, and `unk94[1]`. This still
  tests the missing difference from S5/S8: every vertical channel is floor-zero
  during the secondary pass, not only `unk88[1]`.
- Restored the saved vertical channels immediately afterward, then restored
  the normal long-hop `unk88[1]` arc as before.

Expected success signal:

- Grass/canopy-origin long hops keep a floor-anchored shadow or floor mark
  during the airborne span while the Pokemon body still follows the hop arc.

Expected failure signal:

- No visible shadow means the wild Pokemon `secondarySprite` slot is null or
  not a usable floor-shadow payload in this context.
- An airborne/attached shadow means the stock helper consumes a different
  vertical channel or the secondary payload itself is not independent enough.

Build:

- The first direct-helper S48 shape failed before producing a ROM:
  base ARM9 region `rom` overflowed by 36 bytes.
- The reduced all-vertical-zero secondary-helper shape built successfully
  through the UI build path.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1518.nds`.
- The UI opened `test.nds` after the build.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- User verified the shadow still has the same midair grass-to-land transition:
  it flickers for one frame and then disappears.

Conclusion:

- Even when every known vertical offset channel is floor-zeroed, the stock
  secondary path still does not own a persistent midair floor shadow.
- Do not keep probing stock secondary sprite helpers for this issue without
  new disassembly evidence. The next useful path must provide its own floor
  visual.

### S49 - Field-Overlay-Owned Raw Floor Shadow Canary

Hypothesis:

- S48 proved the stock secondary shadow payload is not reliable for custom
  long hops.
- The base ARM9 insert region and overlay 149 are too tight for a custom raw
  renderer, but the field extension overlay is loaded with the field overlay
  and has substantial free space.
- Expose a tiny fixed field-visual entry from the field extension overlay and
  have the base long-hop draw wrapper call it only during active long-hop
  frames.
- The field overlay function draws a simple untextured black floor quad at
  `LocalMapObject::posVec` using raw G3 commands. This is a canary, not final
  polish: the first goal is proving an owned floor visual can persist through
  grass/canopy-to-land hops.

Files/symbols:

- `include/overworld_wild_field_visuals.h`
- `src/field/overworld_wild_field_visuals.c`
- `src/field/linker.ld`
- `src/overworld_wild_spawns.c`
- `OVERWORLD_WILD_FIELD_VISUAL_ENTRY_ADDR`
- `OverworldWildFieldVisual_DrawCanopyLongJumpShadow`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `reg_G3_MTX_TRANS`
- `reg_G3_POLYGON_ATTR`
- `reg_G3_VTX_16`

Patch applied:

- Added a field-visual entry at `0x023C8048`, after the existing map-teleport
  field-extension entries.
- Replaced the failed S48 stock-secondary pass with a guarded call through
  that field-visual entry.
- Added a field-overlay raw-G3 shadow canary: matrix push, translate to the
  object's floor position, draw a small flattened quad, then pop.

Expected success signal:

- A dark floor mark stays visible through the whole airborne span, including
  grass/canopy-origin jumps to land.

Expected failure signal:

- No mark appears, meaning the draw timing or matrix context is wrong.
- The mark appears in the wrong place, meaning the raw-G3 coordinates need a
  field-space conversion or a descriptor render callback instead of direct
  wrapper drawing.

Build:

- The UI build succeeded and copied/opened `test1519.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1519.nds`.
- Symbol check confirmed `gOverworldWildFieldVisualEntry` landed at
  `0x023C8048`, matching `OVERWORLD_WILD_FIELD_VISUAL_ENTRY_ADDR`.
- Base ARM9 remained at `31218` bytes; the raw draw helper lives in the field
  overlay and added `112` bytes there.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- Rejected. User verification on `test1519.nds` reported that overworld
  Pokemon no longer spawn.
- The probe was fully rolled back before any further shadow work. Treat this
  specific fixed field-visual entry/raw-G3 route as unsafe for the spawn path,
  even though it built and the symbol landed at the expected field-overlay
  address.

### S50 - Hold Stable `BIT_MOVE` During Manual Long-Hop

Hypothesis:

- S32 proved that removing `BIT_MOVE_START` removes even the one-frame shadow
  blink, so stock shadow/effect code needs the custom hop to look like a move
  has started.
- The active long-hop path currently re-seeds `BIT_MOVE_START` every frame but
  never sets `BIT_MOVE`.
- If the stock shadow/effect owner expects an in-progress movement bit after
  the start bit, the current state can look like repeated fresh starts rather
  than one continuous airborne movement. That fits the observed one-frame
  grass/canopy-to-land blink.
- Set `BIT_MOVE` alongside the existing active long-hop flags, but do not add
  it to the base draw-wrapper active predicate. Clear it on landing with the
  other temporary long-hop flags.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_SetObjectLandingTile`
- `BIT_MOVE`
- `BIT_MOVE_START`

Expected success signal:

- Grass/canopy-to-land long hops keep a floor shadow through the airborne span
  because stock code sees a continuous movement lifecycle.

Expected failure signal:

- Shadow still only blinks/disappears, proving the missing state is not the
  basic in-progress movement bit.

Patch applied:

- Added `BIT_MOVE` to the active canopy long-hop flag set in
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`.
- Added `BIT_MOVE` to the landing cleanup mask in
  `OverworldWildSpawns_SetObjectLandingTile`.
- Left the base draw-wrapper active predicate unchanged so body drawing does
  not depend on whether stock code clears `BIT_MOVE` before draw.

Build:

- UI build succeeded and copied/opened `test1521.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1521.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` remained `45032` bytes
  (`0xAFE8`), so the flag probe did not increase linked overlay 149 size.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- User verified the shadow issue still remained.

Conclusion:

- Holding `BIT_MOVE` during the active manual long-hop is not enough to keep the
  stock floor shadow alive.
- The S50 `BIT_MOVE` code was removed before the next probe so later results do
  not stack a failed movement-state variable.

### S51 - Pin Stock Shadow Sample To Landing Tile

Hypothesis:

- The active long-hop path interpolates `posVec[0]/[2]` and also syncs
  `xCurr/yCurr` from that interpolated position.
- S29 proved preserving `xPrev/yPrev -> xCurr/yCurr` movement history while
  following the interpolated tile did not fix the shadow.
- Zeno's read-only pass found the active path already updates logical tiles, so
  the next distinct tile-sampling question is whether stock shadow/terrain code
  needs a stable sample tile rather than a transient interpolated tile.
- During the active custom long-hop, pin `xPrev/yPrev` and `xCurr/yCurr` to the
  intended landing tile after the normal interpolation. Keep `posVec` and the
  body arc untouched, and let landing normalization restore the settled state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::xPrev`, `LocalMapObject::yPrev`
- `LocalMapObject::xCurr`, `LocalMapObject::yCurr`
- `movementCanopyLongJumpDiagonalTargetX/Y`

Expected success signal:

- Grass/canopy-to-land long hops keep a stable floor shadow, proving stock
  render/effect code needs a stable shadow sample tile separate from the
  collision/logical tile.

Expected failure signal:

- Shadow still only blinks/disappears, proving the missing state is deeper than
  the sampled logical tile.

Patch applied:

- Removed the failed S50 `BIT_MOVE` active/cleanup change.
- After the normal interpolated logical sync, overwrote `xPrev/yPrev` and
  `xCurr/yCurr` with the active long-hop target tile.
- Kept `posVec[0]/[2]`, floor `posVec[1]`, `faceVec[1]`, `unk88[1]`, and
  landing normalization unchanged.

Build:

- UI build succeeded and copied/opened `test1522.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1522.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `44968` bytes
  (`0xAFA8`), leaving more headroom than S50.
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- Rejected. User verification on `test1522.nds` reported that the shadow issue
  still remained and the ROM crashed.

Conclusion:

- Persistently pinning `xPrev/yPrev` and `xCurr/yCurr` to the landing tile is
  unsafe. It can corrupt normal object logic/collision while the hop is still
  active.
- Do not keep a persistent current-tile override. The next tile-sampling test
  must be draw-scoped and restore the real logical tile immediately.

### S52 - Draw-Scoped Landing Tile Sample

Hypothesis:

- S51 crashed because it changed the live logical/current tile for the whole
  active hop.
- The useful part of S51 was still the idea of a stable stock draw sample tile.
- Store the intended landing tile in `xInit/yInit` during active long-hop
  frames, then have the base draw wrapper temporarily replace only
  `xCurr/yCurr` with `xInit/yInit` while the stock small-Pokemon draw callback
  runs.
- Immediately restore the real `xCurr/yCurr` after stock draw. Keep
  `xPrev/yPrev`, `posVec`, and the body arc untouched.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::xInit`, `LocalMapObject::yInit`
- `LocalMapObject::xCurr`, `LocalMapObject::yCurr`

Expected success signal:

- Grass/canopy-to-land long hops keep a stable floor shadow while movement and
  collision remain stable, proving a draw-scoped sample tile is sufficient.

Expected failure signal:

- Shadow still only blinks/disappears, proving the stock shadow owner is not
  using the draw-window current tile as its missing stable input.

Patch applied:

- Removed the crashy S51 persistent `xPrev/yPrev` and `xCurr/yCurr` landing
  tile override.
- During active long-hop render updates, store the intended landing tile in
  `xInit/yInit`.
- In `OverworldWildSpawns_CanopyLongJumpDrawWrapper`, save `xCurr/yCurr`,
  temporarily set them to `xInit/yInit` only while
  `OW_WILD_MANKEY_TREE_TOP_DRAW_CALLBACK` runs, then restore the saved current
  tile.
- Kept the existing `unk88[1]` floor-zero window and restored `unk88[1]` after
  draw as before.

Build:

- UI build succeeded and copied/opened `test1525.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1525.nds`.
- `build/linked.o` measured `31210` bytes (`0x79EA`), still fitting the
  `0x7A00` base region but with little margin.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45036` bytes
  (`0xAFEC`).
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44940` bytes (`0xAF8C`).
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- Rejected. User verification on `test1525.nds` reported a crash when a
  Pokemon hops midair from grass to a land tile.

Correction:

- The first S52 edit had the base draw wrapper change, but missed the overlay
  assignment that keeps `xInit/yInit` pointed at the intended landing tile
  during active long-hop frames. Added that assignment before rebuilding.

Conclusion:

- Draw-scoped `xCurr/yCurr` tile sampling is unsafe. Even though it restores
  the fields immediately after the stock draw callback, the stock callback or
  a nested terrain/effect path can observe an inconsistent grass-to-land sample
  and crash.
- Do not retry tile-sample shadow probes through `xCurr/yCurr`,
  `xPrev/yPrev`, or `xInit/yInit` without new disassembly evidence.

### S53 - Remove Tile Sample And Keep `unk88[1]` Floor-Zero After Draw

Hypothesis:

- S52 shows tile-field sampling is crash-prone. Roll back that path entirely:
  no draw-scoped `xCurr/yCurr` swap and no active-frame `xInit/yInit` landing
  sample.
- S42 was superseded before user runtime verification. Re-test that narrower
  variable now: during active long-hop draw, zero `unk88[1]` before the stock
  small-Pokemon callback and do not restore it afterward.
- Movement update still recalculates `faceVec[1]` and `unk88[1]` on the next
  frame, so the visible body arc should continue to use the existing single
  long-hop presentation path. Any later shadow/effect phase in the same frame
  sees the floor-zero `unk88[1]` value instead of an airborne offset.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::unk88[1]`

Expected success signal:

- Pokemon still visibly hop, the S52 grass-to-land crash is gone, and the
  shadow remains floor-visible longer than the one-frame blink.

Expected failure signal:

- Pokemon hop presentation regresses, proving `unk88[1]` must be restored for
  the current body path; or the shadow still blinks, proving the post-draw
  `unk88[1]` lifetime is not the missing shadow owner.

Patch applied:

- Removed S52's draw-wrapper `xCurr/yCurr` save, landing-sample swap, and
  restore.
- Removed S52's active-frame `xInit/yInit` assignment to the long-hop target
  tile.
- Kept the existing active-frame logical sync and active visibility flags
  unchanged.
- Left `unk88[1]` as `0` after active long-hop stock draw instead of restoring
  the saved arc value.

Build:

- UI build succeeded and copied/opened `test1526.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1526.nds`.
- `build/linked.o` measured `31162` bytes (`0x79BA`), fitting the `0x7A00`
  base region with more room than S52.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45032` bytes
  (`0xAFE8`).
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44936` bytes (`0xAF88`).
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- Rejected as built in `test1528.nds`: user reported that no overworld Pokemon
  spawn.
- Likely cause is the linked overlay-load step. `HandleLoadOverlay` switches
  linked overlays to async load type, so overlay 150 can be marked active before
  its entry data is ready. Overlay 149 then reads the legacy encounter lookup
  entry immediately, which can make spawning fail.

Follow-up patch:

- Remove the overlay 149 -> 150 linked overlay row.
- Load overlay 150 synchronously from base `OverworldWildSpawns_GetOverlayEntry`
  after overlay 149 is resident. This keeps overlay-149 bytes low while ensuring
  behavior-data entry memory is ready before spawn lookup code runs.

### S54 - Owned Floor Shadow Quad In Canopy Long-Hop Draw Wrapper

Hypothesis:

- The repeated one-frame blink means the stock small-Pokemon shadow is still
  owned by terrain/current-tile gating somewhere below the object draw path.
- Stop trying to convince the stock shadow to survive grass/canopy tiles.
- During active canopy long-hop draw only, emit a tiny terrain-independent
  floor shadow owned by the long-hop draw wrapper itself.
- Anchor the quad to the already-interpolated floor position
  `posVec[0]/posVec[1]/posVec[2]`, never to the airborne body offset
  `faceVec[1]` or `unk88[1]`.
- Keep the stock body draw callback intact after the owned shadow so the
  visible Pokemon still uses the existing single long-hop presentation path.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `include/overworld_wild_spawns.h`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `reg_G3_MTX_MODE`
- `reg_G3_MTX_PUSH`
- `reg_G3_MTX_POP`
- `reg_G3_MTX_TRANS`
- `reg_G3_POLYGON_ATTR`
- `reg_G3_BEGIN_VTXS`
- `reg_G3_VTX_16`

Expected success signal:

- Grass/canopy-to-land long hops keep a visible midair floor shadow for the
  whole hop instead of blinking for only one frame.
- Normal Pokemon body rendering and hop movement remain intact.

Expected failure signal:

- No owned mark appears, meaning the draw-wrapper timing/matrix context is not
  valid for direct floor geometry.
- A crash or disappearing Pokemon means direct G3 writes in the object callback
  are unsafe and the next attempt should move the owned shadow to a proper
  field-effect render phase instead.

Patch applied:

- Added a tiny direct-G3 owned floor quad in
  `OverworldWildSpawns_CanopyLongJumpDrawWrapper` for active canopy long-hop
  frames.
- The owned quad is emitted before the stock small-Pokemon draw callback and is
  anchored to `mapObject->posVec[0]`, `mapObject->posVec[1] + 0x20`, and
  `mapObject->posVec[2]`.
- The wrapper still zeros `unk88[1]` for the stock callback window and still
  calls `OW_WILD_MANKEY_TREE_TOP_DRAW_CALLBACK` for the actual Pokemon body.
- Removed the unused Mankey tree-top depth wrapper/helper code from
  `src/overworld_wild_spawns.c` and dropped its public declaration from
  `include/overworld_wild_spawns.h` to recover base-space bytes.

Build:

- UI build succeeded and copied/opened `test1527.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1527.nds`.
- `build/output.bin` measured `31188` bytes (`0x79D4`), fitting the
  `0x7A00` base region with about 44 bytes left.
- `arm-none-eabi-size build/linked.o` reported `31186` bytes (`0x79D2`).
- `build/output_overworld_wild_spawns_overlay.bin` measured `45032` bytes
  (`0xAFE8`).
- `arm-none-eabi-size build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  still reported `44936` bytes (`0xAF88`).
- Existing unrelated warning remained:
  `src/battle/battle_script_commands.c:5516:54: unused parameter 'bsys'`.

Runtime result:

- Rejected. User verification on `test1527.nds` reported that the shadow issue
  remains.
- A crash also appeared after some time in-game. The exact cause is not
  confirmed, but S54 is suspicious because it writes raw G3 state from the
  map-object draw callback before the stock body callback.
- Treat direct raw-G3 floor geometry from
  `OverworldWildSpawns_CanopyLongJumpDrawWrapper` as unsafe unless later
  evidence proves the crash came from something else.

### S55 - Field-Effect-Owned Canopy Long-Hop Shadow

Hypothesis:

- S54 showed that direct raw-G3 writes inside the map-object draw callback are
  both ineffective for the midair grass-to-land blink and potentially unsafe.
- The owned shadow should live in the field-effect render phase instead, using
  the same effect allocator pattern already present for Mankey tree-top late
  draw experiments.
- The Pokemon body should still draw through the stock small-Pokemon callback;
  only the terrain-independent floor mark moves out to an owned field effect.
- The shadow effect lifetime should be tied to the active canopy long-hop state
  and explicitly cleared on long-hop end, slot deletion, or stale map context.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_ClearCanopyLongJumpDiagonal`
- `ov01_021F146C`
- `ov01_021F1620`
- `ov01_021F1640`

Expected success signal:

- Grass/canopy-to-land long hops keep a visible floor shadow through the full
  midair travel instead of blinking for only one frame.
- No delayed crash from stale shadow rendering after despawn or map transition.
- Normal Pokemon body drawing, hop arc, and landing behavior remain unchanged.

Expected failure signal:

- Build overflow in overlay 149, requiring size trimming before runtime
  verification.
- No owned mark appears, meaning this field-effect render callback is not using
  a suitable 3D state or matrix for direct floor geometry.
- Crash on spawn, hop, or delayed despawn/context change, meaning the effect
  lifetime or render primitive still touches unsafe state.

Patch applied:

- Removed the S54 direct raw-G3 floor quad from
  `OverworldWildSpawns_CanopyLongJumpDrawWrapper`; the wrapper now only keeps
  the stock long-hop body draw stable by zeroing `unk88[1]` during active
  canopy long-hop frames.
- Added a canopy long-hop shadow field-effect descriptor in
  `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- Added per-slot shadow effect handles, strict validity checks against the
  current field context/current spawn object, and explicit cleanup when the
  canopy long-hop state clears or a spawn slot is deleted.
- Created the field effect as soon as `OverworldWildSpawns_StartPreparedLongJumpCommand`
  marks the custom long-hop state active.
- The effect render callback emits the same tiny terrain-independent black quad
  from the field-effect phase instead of from the map-object draw callback.

Build:

- First S55 build failed at overlay 149 link:
  `section .text will not fit in region rom`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `45430` bytes of text (`0xB176`), up from the previous accepted
  `44936` bytes (`0xAF88`).
- A slimmer overlay-149-local effect version still failed. After moving the
  render callback and descriptor into overlay 150, overlay 149 still measured
  `45054` bytes of text, which is close but still too large after link
  overhead.

Revision:

- Keep the owned shadow render callback in overlay 150.
- Shrink the overlay-149 bridge to a create-only overlay-150 entry. Clearing
  uses the generic `ov01_021F1640` while overlay 150 is still resident, instead
  of validating and calling a second overlay-150 clear function pointer.
- Remove extra overlay-149 validation for the shadow entry because the entry is
  local generated code in the same ROM, not external data.
- Add a loader-side lifecycle guard: when a non-overworld-wild overlay cold
  unloads overlay 150/151, first run overlay 149's resident cleanup if overlay
  149 is resident. This clears live field-effect handles before the overlay-150
  callback code can disappear.
- The next build still failed overlay 149. The trimmed object measured `44958`
  bytes, roughly 22 bytes over the previous accepted object size. Trim the
  bridge further by relying on existing caller validation for `slot`/`object`
  and removing redundant guard code from the shadow-only helper functions.
- That still missed the overlay limit by a few bytes. Collapse the S55 probe to
  one global owned shadow effect handle instead of per-slot handles. This is a
  deliberate probe compromise: it proves or rejects the field-effect render
  phase without spending bytes on simultaneous multi-hop shadow ownership.
- The single-handle version was still about 8 bytes over once BSS was packed
  into the overlay region. Move that single live handle into overlay 150 too,
  so overlay 150 owns both the descriptor callbacks and the effect handle.
  Overlay 149 only loads/calls create and clears via the overlay-150 entry when
  that overlay is resident.
- The link still missed by roughly 12 bytes after overlay-150 handle ownership.
  Move normal landing cleanup into the overlay-150 effect update: after a short
  start grace, the effect self-destroys when the long-hop visibility flags are
  no longer present. Overlay 149 keeps only hard cleanup for slot deletion and
  resident overlay cleanup.
- Fold resident shadow cleanup into the existing overlay-150 unload branch
  instead of calling a separate clear-all helper. This preserves the hard
  cleanup invariant while saving the last few overlay-149 bytes.
- The linked overlay was still a few bytes over after `thumb_help`. Remove the
  slot-clear hard clear for this probe and rely on overlay-150 self-destroy for
  normal lifetime plus resident cleanup before overlay unload.
- Overlay 149 was finally under its own object budget, but `thumb_help` still
  tipped the linked overlay. Move the final resident clear out to base
  `overlay.c`, where there is room, and remove that cost from overlay 149.
- Link overlay 150 to overlay 149 in the base overlay loader so the shadow
  create hook can assume behavior-data overlay residency and drop its explicit
  `IsOverlayLoaded`/`HandleLoadOverlay` check from overlay 149.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1528.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `45040` bytes,
  fitting the `0xB000` overlay 149 region with 16 bytes left.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44830` text + `114` bss (`44944` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90` bytes.
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1032`
  bytes, well under overlay 150's `0x1000` region.
- `build/linked.o` measured `31162` bytes (`0x79BA`), fitting the base region.
- Warnings remain for older generated behavior profile initializers missing
  `hopTime`; these were non-fatal and unrelated to this shadow probe.

Runtime result:

- Pending user verification for the shadow visual.

Spawn-crash follow-up:

- Helper investigation found two cheaper non-shadow crash candidates in the
  immediate spawn path: invalid `HOP_FROM_OFF_SCREEN` start coordinates before
  `CreateSpecialFieldObjectWithParams`, and runtime behavior-class constants
  drifting from the generated behavior-data class indexes.
- Follow-up patch kept the S56 shadow bridge disabled, bumped
  `OVERWORLD_WILD_HELPER_OVERLAY_VERSION` so stale overlay 151 data is
  rejected, aligned the runtime class constants with `data/OverworldWildBehaviorData.c`,
  added a null/output guard to `OverworldWildSpawns_TryGetSpawnTerrain`, and
  made `OverworldWildSpawns_PrepareSpawnHopStart` fall back to
  `APPEAR_HOP` when the intended offscreen start tile cannot resolve terrain.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1534.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44790` text + `114` bss (`44904` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `build/linked.o` measured `31194` bytes.
- `git diff --check` passed.

### S63 - Deferred Owned Field-Effect Shadow With Object Identity Guard

Hypothesis:

- S62 proved the shared stock primary draw path is not a viable shadow route:
  the shadow still blinked and follower Pokemon disappeared.
- S58's owned field-effect shadow crashed because it was created directly from
  the hop-start path with only a raw `LocalMapObject *` lifetime.
- Keep the normal long-hop body path unchanged (`unk88[1] = arc`) and create
  the owned floor shadow only after the long-hop has entered its active frame
  update. Let overlay 150 own the effect lifetime and reject stale object
  pointers by checking the captured `FieldSystem`, map-object range, object id,
  active flag, and long-hop visible flags.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED`
- `OverworldWildSpawns_UpdateCanopyLongJumpDiagonalLanding`
- `OverworldWildSpawns_EnsureCanopyLongJumpShadowEffect`
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
- `OverworldWildBehavior_CanopyLongJumpShadowEffectWork`
- `OverworldWildBehavior_IsCurrentCanopyLongJumpShadowObject`

Expected success signal:

- Overworld Pokemon and follower Pokemon remain visible.
- Canopy long-hop movement remains visible.
- The owned floor shadow stays visible through grass/canopy-to-land midair
  transitions instead of blinking for one frame.

Expected failure signal:

- Crash or spawn/follower disappearance, meaning the field-effect bridge is
  still unsafe even when deferred and guarded.
- No owned shadow, meaning the field-effect render phase is not visible in the
  needed pass.
- Shadow still blinks, meaning the stock terrain-bound shadow is still the only
  visible one and the owned field-effect draw is ineffective.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1548.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `45028`
  bytes, under the `0xB000` overlay 149 limit by 28 bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44806` text + `114` bss (`44920` total).
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1168`
  bytes.
- `build/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.o`
  measured `962` text + `4` bss (`966` total).
- `build/output_overworld_wild_helper_overlay.bin` measured `4086`
  bytes.
- `build/output.bin` measured `31196` bytes.
- `git diff --check` passed.

### S62 - Let Active Wild Long-Hop Use `faceVec[1]` As Body Carrier

Hypothesis:

- S61 proved visible body hopping depends on `unk88[1]` during the stock draw
  path, because stock primary draw normally zeros the `faceVec` draw vector for
  this wild Pokemon path.
- Disassembly of stock primary draw `0x021F8D80` shows the zero-vector path at
  `0x021F8DC4 -> 0x021F8DD8`. If that branch is bypassed, the stock draw copies
  `faceVec`, zeros only X/Z, and keeps Y as a sprite-position carrier.
- `MAPOBJECTFLAG_UNK13` is only used by the custom canopy long-hop active flag
  set in this branch. Patch the stock zero-vector decision so active wild
  long-hop objects take the `faceVec`-Y path.
- Then keep `unk88[1]` floor-zero during active long-hop frames. If this works,
  the body arc comes from `faceVec[1]`, while shadow-sensitive `unk88[1]` no
  longer marks the object as airborne.

Files/symbols:

- `armips/asm/overworlds.s`
- `0x021F8DC4`
- `OverworldWildSpawns_CanopyLongJumpFaceVecGate`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::faceVec[1]`
- `LocalMapObject::unk88[1]`
- `MAPOBJECTFLAG_UNK13`

Expected success signal:

- Pokemon visibly hop again, unlike S61/S30.
- Grass/canopy-origin long hops keep a stable floor shadow because `unk88[1]`
  stays floor-zero while the visible body arc survives through `faceVec[1]`.

Expected failure signal:

- Pokemon still do not visibly hop, meaning this is not the zero-vector branch
  that removes `faceVec[1]`.
- Pokemon double-hop or arc looks wrong, meaning another carrier is still
  contributing.
- Shadow still only blinks, proving `unk88[1]` is not the shadow-sensitive
  state after all.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1544.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44790` text + `114` bss (`44904` total).
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1032`
  bytes.
- `build/output_overworld_wild_helper_overlay.bin` measured `4086`
  bytes.
- `build/output.bin` measured `31196` bytes.
- Binary check confirmed the hook at `0x021F8DC4` branches to the overlay 1
  helper in the free tail at `0x02209B44`.
- `git diff --check` passed.

Runtime result:

- Rejected. User verified the shadow issue remained, and follower Pokemon
  disappeared.
- This means the `0x021F8D80` zero-vector branch hook is too broad or clobbers
  state that the follower path needs, even though it was intended to key off
  the custom long-hop flag.
- Remove the overlay 1 `OverworldWildSpawns_CanopyLongJumpFaceVecGate` hook and
  restore active long-hop `unk88[1] = arc` before the next build.

Safe revert build:

- Removed the overlay 1 `0x021F8DC4` hook and the
  `OverworldWildSpawns_CanopyLongJumpFaceVecGate` helper.
- Restored active canopy long-hop rendering to carry the visible arc through
  `object->unk88[1] = arc`.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1546.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `44996`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44786` text + `114` bss (`44900` total).
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1032`
  bytes.
- `build/output_overworld_wild_helper_overlay.bin` measured `4086`
  bytes.
- `build/output.bin` measured `31196` bytes.
- `git diff --check` passed.

### S61 Application - Scoped Stock-Draw Wrapper

Patch plan:

- Add `OverworldWildSpawns_CanopyLongJumpStockDrawWrapper` to the free tail of
  overlay 1's `0x02209B18` ARMIPS patch area.
- The wrapper saves `LocalMapObject::unk88[1]`, clears it only while calling
  stock small-Pokemon draw at `0x021F7894`, then restores the saved value.
- Install the wrapper into `object->unkC8` when a canopy long-hop starts, and
  restore the stock small-Pokemon draw callback when the long-hop state clears.

Why this is different from S30:

- S30 kept `unk88[1]` floor-zero for the whole active frame and broke visible
  hopping.
- This attempt keeps the active movement frame unchanged; only the stock draw
  callback sees the floor-zero value.

Expected success signal:

- Pokemon still hop normally.
- Grass/canopy-origin long hops keep a floor-position shadow for more than the
  one-frame grass-to-land blink.

Expected failure signal:

- Pokemon no longer hop, crash on spawn/hop, or the shadow still only blinks.

Runtime result:

- Rejected. User verified `test1542.nds` makes Pokemon no longer visibly hop.
- This proves visible long-hop body height still depends on `unk88[1]` during
  stock draw. Clearing it only inside the draw wrapper is still too broad.
- Remove the draw-wrapper install before the next build; future attempts must
  preserve `unk88[1] = arc` for stock sprite draw and find a separate shadow
  gate/floor-position path.

Safe revert build:

- Removed the overlay 1 scoped draw wrapper and the overlay 149 `unkC8`
  install/restore hook.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1543.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1032`
  bytes.
- `build/output_overworld_wild_helper_overlay.bin` measured `4086`
  bytes.
- `build/output.bin` measured `31196` bytes.
- `git diff --check` passed.

Runtime result:

- User reported `test1534.nds` still has the shadow issue. The game no longer
  crashes, but the canopy long-hop shadow remains missing through most of the
  air time and only blinks briefly when travelling from grass/canopy onto land.

### S57 - Present Custom Long Hop As Jump Command During Render Frames

Hypothesis:

- The current custom long hop uses `OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND`
  as the real active movement command while manually updating the object's
  horizontal ground track and vertical arc.
- The stock renderer/shadow owner may use `object->movementCmd` as part of the
  jump lifecycle. This would explain the one-frame shadow blink: the renderer
  can briefly accept the terrain transition, then loses the persistent jump
  identity because the object reports a freeze command.
- S31 let stock jump movement own too much of the hop and broke hopping. This
  attempt does not let stock movement own travel. It only restores the freeze
  command before movement update, then presents the object as the stock long
  jump command between update ticks so the render side sees a jump.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `object->movementCmd`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_COMMAND`

Expected success signal:

- Canopy long-hop movement still works.
- The stock floor shadow persists through the whole midair hop, including
  grass/canopy-to-land transitions, without attaching to the Pokemon body.

Expected failure signal:

- Hopping regresses, the shadow still only blinks, or the command identity is
  not part of the stock shadow lifecycle.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1535.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45052`
  bytes, under the `0xB000` overlay 149 limit by 4 bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44842` text + `114` bss (`44956` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `build/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.o`
  measured `826` text + `4` bss (`830` total).
- `git diff --check` passed.

Runtime result:

- User reported the shadow issue remains. The command-identity shim did not
  make the stock floor shadow persist, so `object->movementCmd` is not the
  missing piece for the grass/canopy midair blink.
- Follow-up action: remove the S57 runtime shim before the next attempt so it
  does not consume overlay 149 space or risk the hop-start suppression side
  effect noted during review.

### S58 - Re-enable Owned Field-Effect Shadow After Loader Fixes

Hypothesis:

- S55's field-effect-owned shadow was disabled during spawn/no-spawn triage,
  but the later follow-ups found concrete non-shadow causes: async linked
  overlay 150 residency, broad taskman early returns, invalid offscreen spawn
  starts, and drifted behavior-class constants.
- With those isolated and the S57 command-identity shim removed, re-enable the
  smallest existing owned-shadow bridge: overlay 149 only calls the base
  `OverworldWildSpawns_CreateCanopyLongJumpShadowEffect`, while overlay 150
  owns the field-effect descriptor, render callback, and single live handle.
- This does not touch ordinary spawn setup. Overlay 150 is loaded synchronously
  by the base create helper only when a canopy long-hop starts.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_EnsureCanopyLongJumpShadowEffect`
- `src/overworld_wild_spawns.c`
- `OverworldWildSpawns_CreateCanopyLongJumpShadowEffect`
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`

Expected success signal:

- Overworld Pokemon still spawn and canopy long-hop movement still works.
- The owned field-effect floor shadow is visible through the whole midair hop,
  including grass/canopy-to-land transitions.

Expected failure signal:

- No shadow appears, proving the existing field-effect render payload/state is
  not visible in the needed phase.
- Spawn/no-spawn or crash regression, proving the bridge still has an unsafe
  overlay/effect lifetime despite the loader fixes.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1536.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45028`
  bytes, under the `0xB000` overlay 149 limit by 28 bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44810` text + `114` bss (`44924` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_behavior_data_overlay_linked.o` measured `1032`
  bytes, under the `0x1000` overlay 150 limit.
- `build/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.o`
  measured `826` text + `4` bss (`830` total).
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `git diff --check` passed.

Runtime result:

- Rejected. User verified `test1536.nds` crashes immediately when a Pokemon
  spawn is attempted.
- This confirms the overlay-150 field-effect shadow bridge is still unsafe in
  the spawn/hop path even after the loader fixes. Disable
  `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` again before the
  next build.

Safe revert build:

- Disabled `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` again.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1537.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44790` text + `114` bss (`44904` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_behavior_data_overlay_linked.o` measured `1032`
  bytes, under the `0x1000` overlay 150 limit.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.

### S59 - Force Shadow-Enabled Pokemon Render Param During Active Long-Hop

Hypothesis:

- `OVERWORLD_SIZE_SMALL` is `0x4E27`, while
  `OVERWORLD_SIZE_SMALL_NO_SHADOW` is `0x4E26`; the low bit is therefore a
  plausible stock "shadow allowed" render-param bit.
- Earlier stock-helper probes admitted wild IDs through terrain/effect helper
  gates but preserved the object's existing param value. This probe changes the
  param value itself while avoiding raw G3, field effects, draw callbacks, and
  movement-command spoofing.
- The user has said terrain-independent shadows are acceptable if that is what
  it takes, so leaving the bit set after the hop is acceptable for this probe.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::param[1]`
- `src/field/overworld_table.c`
- `OVERWORLD_SIZE_SMALL`
- `OVERWORLD_SIZE_SMALL_NO_SHADOW`

Expected success signal:

- Canopy long-hop movement still works.
- The stock shadow stays visible through grass/canopy-origin hops because the
  Pokemon is forced into the stock shadow-enabled render-param variant.

Expected failure signal:

- Shadow still only blinks/disappears, proving this low param bit is not the
  missing shadow gate for active long-hop terrain transitions.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1538.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45008`
  bytes, under the `0xB000` overlay 149 limit by 20 bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44798` text + `114` bss (`44912` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_behavior_data_overlay_linked.o` measured `1032`
  bytes, under the `0x1000` overlay 150 limit.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `git diff --check` passed.

Runtime result:

- Rejected. User verified this leads to an immediate crash when a Pokemon spawn
  is attempted.
- Removed the `object->param[1] |= 1` write before the next build. The low bit
  is not safe to force from the active long-hop render-offset path.

Safe revert build:

- Removed the `object->param[1] |= 1` write.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1539.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44790` text + `114` bss (`44904` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_behavior_data_overlay_linked.o` measured `1032`
  bytes, under the `0x1000` overlay 150 limit.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `git diff --check` passed.

### S60 - Clear Stock Setup Latch From The Active Long-Hop Update

Hypothesis:

- S4 cleared render-data byte `unk108[0x17]` bit 0 from the old
  `OverworldWildSpawns_CanopyLongJumpDrawWrapper`.
- The current source has `OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED`
  disabled, so that wrapper is not the live path anymore.
- Stock small-Pokemon draw at `0x021F7894` only reruns its auxiliary/shadow
  setup while `unk108[0x17]` bit 0 is clear, then sets the bit again before
  calling the body draw/update helpers.
- Clear only that setup latch during the active long-hop vector update, before
  stock draw sees the object. Do not mutate object params, object ID, current
  tile fields, field effects, or raw G3 state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `LocalMapObject::unk108[0x17]`
- Stock small-Pokemon draw callback `0x021F7894`

Expected success signal:

- The stock setup path refreshes on each active long-hop frame and keeps the
  grass/canopy-origin floor shadow visible through the airborne duration.

Expected failure signal:

- Shadow still only blinks/disappears, proving the missing owner is not the
  stock setup latch timing in the current no-wrapper path.

Patch applied:

- Added a single active-frame latch clear in
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`:
  `object->unk108[0x17] &= (u8)~1`.
- Kept all object params, object IDs, tile fields, field effects, and raw G3
  untouched.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1540.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45012`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44802` text + `114` bss (`44916` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_behavior_data_overlay_linked.o` measured `1032`
  bytes, under the `0x1000` overlay 150 limit.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `git diff --check` passed.

Runtime result:

- Rejected. User verified the shadow issue remained.
- This proves that clearing the stock setup latch from the current active
  long-hop update path is still not enough to keep grass/canopy-origin midair
  shadows alive.
- Remove the latch clear before the next build; it costs overlay 149 bytes and
  does not change the runtime result.

Safe revert build:

- Removed the active-frame `unk108[0x17]` latch clear.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1541.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44790` text + `114` bss (`44904` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_behavior_data_overlay_linked.o` measured `1032`
  bytes, under the `0x1000` overlay 150 limit.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `git diff --check` passed.

### S61 - Restore A Live Scoped Stock-Draw Wrapper For Long-Hop

Hypothesis:

- Curie's read-only pass found that the old long-hop/tree-top draw wrapper is
  not live in the current build: `OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED`
  is `0`, and the wrapper symbol is absent.
- This means current active long-hop frames leave `unk88[1] = arc` visible to
  the stock small-Pokemon draw callback for the whole draw, instead of only
  using it as movement/debug arc state.
- S30 proved that keeping `unk88[1]` floor-zero for the whole frame breaks the
  visible hop. The safer version is a true scoped wrapper: save `unk88[1]`,
  set it to zero only while calling stock small-Pokemon draw, then restore it.
- Put the wrapper in overlay 1's existing ARMIPS patch area rather than overlay
  149 or ARM9 base. Overlay 1 owns the stock map-object renderer and stays
  resident while map objects draw, avoiding field-effect lifetime issues and
  avoiding base-space pressure.

Files/symbols:

- `armips/asm/overworlds.s`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CanopyLongJumpStockDrawWrapper`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_ClearCanopyLongJumpDiagonal`
- `LocalMapObject::unkC8`
- `LocalMapObject::unk88[1]`
- Stock small-Pokemon draw callback `0x021F7895`

Expected success signal:

- Pokemon still visibly hop because `faceVec[1]` keeps carrying the body arc.
- Grass/canopy-origin long hops keep the floor shadow visible because stock
  draw samples `unk88[1] == 0` during the draw pass.

Expected failure signal:

- Pokemon hop height changes too much or no longer hops, proving the scoped
  wrapper still removes a required visible carrier.
- Shadow still only blinks/disappears, proving the missing owner is outside the
  stock draw window even when the wrapper is live again.

No-spawn regression follow-up:

- The `test1528.nds` build linked overlay 150 to overlay 149 so the long-hop
  shadow create hook could assume behavior-data residency.
- Runtime rejected that version because no overworld Pokemon spawned.
- Investigation found the linked-overlay loader switches linked overlays to
  async load type. `IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)` can
  therefore become true before overlay 150's fixed entry data at `0x023C3000`
  is ready.
- That is fatal to spawning because overlay 149 can immediately read the legacy
  encounter lookup entry from overlay 150 and see uninitialized lookup pointers
  or count data.

Follow-up patch:

- Removed the overlay 149 -> overlay 150 linked-overlay row.
- Restored explicit synchronous overlay 150 loading from base
  `OverworldWildSpawns_GetOverlayEntry` immediately after overlay 149 is
  resident.
- Kept the shadow create call cheap in overlay 149; overlay 150 is now prepared
  by the base entry path instead of a linked async dependency.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1529.nds`.
- `build/linked.o` measured `31194` bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44830` text + `114` bss (`44944` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90` bytes.
- `build/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.o`
  measured `826` text + `4` bss (`830` total).
- `git diff --check` passed.

Runtime result:

- User reported `test1529.nds` still had no overworld Pokemon spawning.

Second no-spawn follow-up:

- Found a separate spawn-entry regression from the transition-flicker cleanup:
  `OverworldWildSpawns_OnPlayerStep` and overlay 149's
  `OverworldWildSpawns_OverlayOnPlayerStep` both had a broad
  `fieldSystem->taskman != NULL` early return.
- That guard was too high in the pipeline. Since the spawn hook is called from
  the player-step/repel path, it could skip overlay loading, map-state update,
  and `OverworldWildSpawns_TryRefill` entirely.
- The field-ready grace task also no longer called
  `OverworldWildSpawns_OnPlayerStep` when its delay reached zero, removing the
  initial post-transition spawn pass.

Patch:

- Removed the broad taskman early returns from the base player-step hook and
  overlay 149 player-step hook.
- Restored the field-ready delayed `OverworldWildSpawns_OnPlayerStep` call.
- Kept the field-ready task's transition guard so map teleport polling still
  waits until field tasks are finished.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1530.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `45032` bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44822` text + `114` bss (`44936` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90` bytes.
- `build/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.o`
  measured `826` text + `4` bss (`830` total).
- `build/linked.o` measured `31194` bytes.
- `git diff --check` passed.

Runtime result:

- User reported `test1530.nds` still had no overworld Pokemon spawning.

Third no-spawn follow-up:

- Helper-agent/data pass found the generated `test.nds` contains OWBD member
  17 and OWED member 18, while the clean input `rom.nds` does not. If an
  emulator launches `rom.nds`, overworld spawns cannot work because the code
  addon data is absent.
- Source/data review found the OWED lookup blob valid for normal route maps, so
  the remaining source-level suspect was overlay residency during spawn prep.
- Moved the synchronous overlay 150 load out of the normal player-step entry.
  Normal spawn steps now load only overlay 149; overlay 150 is loaded
  synchronously only by the canopy long-hop shadow bridge immediately before
  invoking overlay 150's shadow effect create hook.
- This keeps the shadow fix away from ordinary map enablement, encounter
  lookup, and helper overlay 151 spawn preparation.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1531.nds`.
- `build/linked.o` measured `31226` bytes (`0x79FA`).
- `build/output_overworld_wild_spawns_overlay.bin` measured `45028` bytes.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44810` text + `114` bss (`44924` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90` bytes.
- `build/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.o`
  measured `826` text + `4` bss (`830` total).
- `git diff --check` passed.

Remaining suspect if `test1531.nds` still does not spawn:

- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` is still enabled. A helper pass noted
  that this can detach spawn state without deleting normal spawn map objects
  during context churn, potentially orphaning objects and blocking future spawn
  placement. This is less likely to explain a fresh route with no spawns, but
  it is the next source-level cleanup candidate.

### S56 - Disable Field-Effect Shadow Bridge For Spawn-Crash Isolation

Hypothesis:

- The S55 owned shadow field effect is still created immediately from
  `OverworldWildSpawns_StartPreparedLongJumpCommand`.
- If the game crashes immediately when attempting to spawn Pokemon, the most
  likely recent spawn-time risk is the overlay-150 field-effect shadow bridge,
  not the normal spawn table data.
- Disabling `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` should
  leave long-hop movement intact while preventing the custom shadow field
  effect from being allocated at object creation/hop start.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_EnsureCanopyLongJumpShadowEffect`

Expected success signal:

- Overworld Pokemon can spawn again without an immediate crash.
- Canopy long-hop Pokemon still move, but the midair shadow issue remains.

Expected failure signal:

- The game still crashes immediately on spawn, proving the crash is earlier
  than the custom canopy shadow effect allocation.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1533.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `44988`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44778` text + `114` bss (`44892` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/linked.o` measured `31194` bytes.
- `git diff --check` passed.

Runtime result:

- Pending user verification.

Spawn-crash follow-up:

- Helper investigation found two cheaper non-shadow crash candidates in the
  immediate spawn path: invalid `HOP_FROM_OFF_SCREEN` start coordinates before
  `CreateSpecialFieldObjectWithParams`, and runtime behavior-class constants
  drifting from the generated behavior-data class indexes.
- Follow-up patch kept the S56 shadow bridge disabled, bumped
  `OVERWORLD_WILD_HELPER_OVERLAY_VERSION` so stale overlay 151 data is
  rejected, aligned the runtime class constants with `data/OverworldWildBehaviorData.c`,
  added a null/output guard to `OverworldWildSpawns_TryGetSpawnTerrain`, and
  made `OverworldWildSpawns_PrepareSpawnHopStart` fall back to
  `APPEAR_HOP` when the intended offscreen start tile cannot resolve terrain.
- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1534.nds`.
- `build/overworld_wild_spawns_overlay_linked.o` measured `45000`
  bytes, under the `0xB000` overlay 149 limit.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `44790` text + `114` bss (`44904` total).
- `build/overworld_wild_spawns_overlay/thumb_help.o` measured `90`
  bytes.
- `build/overworld_wild_helper_overlay_linked.o` measured `4086`
  bytes, under the `0x1000` overlay 151 limit.
- `build/linked.o` measured `31194` bytes.
- `git diff --check` passed.
- Runtime crash result is pending user verification.

### S64 - Disable Deferred Field-Effect Shadow Bridge For S62/S63 Crash

Hypothesis:

- User identified the current crash as coming from the S62-family shadow
  implementation.
- The direct S62 `faceVec[1]` hook was already reverted, but the current ROM
  still had S63's deferred owned field-effect shadow bridge enabled.
- Disable the bridge again so the normal canopy long-hop path can run far
  enough for the Igglybuff grass-to-land repro.

Patch:

- Set `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` back to `0`.
- Left the normal active long-hop arc path alone: `object->unk88[1] = arc`
  remains intact.

Expected success signal:

- Igglybuff can spawn and continue past the scared/setup hop into the leftward
  grass-to-land jump without crashing.
- The midair shadow issue remains, because this only removes the crashy shadow
  bridge.

Expected failure signal:

- Crash/freeze still happens before the leftward hop, meaning another recent
  non-shadow path is responsible.

Build:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1549.nds`.
- `build/output_overworld_wild_spawns_overlay.bin` measured `44996`
  bytes, under the `0xB000` overlay 149 limit.
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1168`
  bytes.
- `build/output.bin` measured `31196` bytes.
- `git diff --check` passed.

Runtime result:

- Headless harness command:
  `scripts/headless-overworld-shadow-harness.py --prefix igglybuff_shadow_s64_crash_unblock --capture-frames 180 --contact-every 2 --target-igglybuff ledge-spawn`.
- DSV source:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Harness completed without crashing and captured through the ledge-spawned
  Igglybuff movement window.
- Harness detected `actual_left_hop_start_frame` /
  `second_left_jump_start_frame` at frame `27`.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s64_crash_unblock_contact.png`.
- This unblocks testing again; the midair shadow issue itself remains.

### S65 - Guardrail Review And Default Oracle Baseline

Hypothesis:

- After the S64 crash unblock, preserve the stable baseline:
  `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED == 0`,
  `object->unk88[1] = arc`, floor `posVec[1]`, and visible hopping intact.
- Re-check whether a new implementation path exists that does not repeat the
  documented failures and does not add risky overlay-150 field effects, raw G3
  drawing, broad stock draw hooks, identity/gfx spoofing, tile/param lifetime
  hacks, or another body-arc carrier change.

Patch:

- No source patch was made.
- No safe new implementation candidate was found under the current guardrails.
- The live source has no active `OverworldWildSpawns_CanopyLongJumpDrawWrapper`
  path for this issue; the historical draw-wrapper notes therefore should not
  be treated as a currently available low-risk insertion point.

Files/symbols inspected:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_spawns.c`
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
- `armips/asm/overworlds.s`
- `data/OverworldWildBehaviorData.c`
- `include/map_events_internal.h`
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
- `OverworldWildSpawns_UpdateCanopyLongJumpDiagonalLanding`
- `OverworldWildSpawns_StartPreparedLongJumpCommand`
- `OverworldWildSpawns_EnsureCanopyLongJumpShadowEffect`
- `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_OFFSET`

Build:

- Not run. No source code was changed, so there was no new ROM to validate.
- Existing ROM used by the harness:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/test.nds`.

Runtime result:

- Headless harness command:
  `scripts/headless-overworld-shadow-harness.py --prefix igglybuff_shadow_s65_guardrail_blocked_baseline --target-igglybuff ledge-spawn`.
- DSV source:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Harness exit code: `2`.
- Harness detected `actual_left_hop_start_frame` /
  `second_left_jump_start_frame` at frame `27`.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s65_guardrail_blocked_baseline_contact.png`.
- Summary JSON:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s65_guardrail_blocked_baseline_summary.json`.
- Default oracle result:
  `shadow_pass.passed == false`,
  `valid_body_frame_count == 105`,
  `tracked_percent == 100`,
  `present_frame_count == 0`,
  `present_percent == 0`,
  `missing_shadow_frame_count == 105`,
  `max_missing_run == 105`,
  with pass window `75..179`.

Conclusion:

- The S64 baseline remains stable enough to capture the repro: no crash,
  no no-spawn/body-track regression, and visible Igglybuff motion continues.
- The midair floor shadow still fails the default oracle.
- Under the current guardrails and overlay-size pressure, the remaining
  source-side options are the same unsafe or previously failed families:
  re-enabling the overlay-150 owned field-effect bridge, raw G3 drawing,
  stock draw/secondary helper hooks, identity/gfx spoofing, param/tile
  lifetime hacks, or moving the body arc away from the proven
  `faceVec[1]`/`unk88[1]` presentation.
- Stop here rather than forcing a risky patch.

### S66 - Guarded `unk88[1]` Zero Around `0x02205808` Call

Hypothesis:

- S47 zeroed `faceVec[1]` around the `0x021F78E6 -> 0x02205808`
  terrain/aux update call and failed.
- A narrower probe would leave `faceVec`, `posVec`, tile fields, params,
  `gfxId`, `unkC8`, overlay 150, raw G3 drawing, and the long-hop movement
  logic untouched, while only making `object->unk88[1]` look floor-zero to the
  `0x02205808` helper.
- Guard the probe to custom overworld wild objects only:
  `object->id` in `0xE0..0xE9` and `MAPOBJECTFLAG_UNK13` set.

Requested exact patch:

- In `armips/asm/overworlds.s`, patch only the `bl 0x02205808` call at
  `0x021F78E6` to an overlay-1 free-tail wrapper.
- Wrapper arguments would remain `r0=variant`,
  `r1=LocalMapObject *`, `r2=primarySprite`.
- Unguarded objects would call `0x02205808` unchanged.
- Guarded objects would save `LocalMapObject::unk88[1]` at offset `0x8C`,
  write zero, call `0x02205808`, then restore `unk88[1]`.

Feasibility result:

- Not patched.
- Current overlay-1 tail is:
  `base/overlay/overlay_0001.bin` loaded at `0x021E5900`, file size
  `148064`, end address `0x02209B60`.
- Existing ARMIPS tail patch starts at `0x02209B18`.
- Existing shiny-palette and transition-dispatch thunks occupy bytes
  `0x02209B18..0x02209B43`.
- The only clear final-tail padding left is `0x02209B44..0x02209B5F`
  (`28` bytes total).
- The smallest safe shape I found for the exact wrapper still needs roughly
  `46` bytes: range guard, `MAPOBJECTFLAG_UNK13` guard, save/restore of `lr`
  and `r4`, temporary zero of `[object + 0x8C]`, original helper call, restore
  of `[object + 0x8C]`, and a return path preserving the helper's `r0` return
  value.
- Fitting it would require one of the following, all outside the requested
  constraints:
  reclaiming or rewriting unrelated overlay-1 tail thunks, using a second
  non-tail code cave, relaxing the exact wild-ID guard, not preserving `r4`,
  clobbering the helper return value, or changing the hook site/helper itself.

Build:

- Not run. No ARMIPS/source patch was made.

Runtime result:

- Not run. There was no new ROM for the harness to verify.

Conclusion:

- The S66 probe is conceptually distinct from S47 because it scopes only
  `unk88[1]`, not `faceVec[1]`.
- The exact requested implementation is not safely encodable in the remaining
  overlay-1 final-tail padding in the current worktree.
- Preserve the S64/S65 stable baseline and do not force this through a broader
  ARMIPS/code-cave change without explicit approval.

### S67 - ARM9-Resident Guarded `unk88[1]` Aux Wrapper

Hypothesis:

- S66's behavior can be implemented safely by keeping the hook at the exact
  small-Pokemon draw-path callsite `0x021F78E6`, but placing the guarded wrapper
  in resident ARM9 fairy padding instead of overlay-1 tail space.
- The wrapper should only affect custom overworld wild objects while the custom
  long-hop active flag is present: `object->id` in `0xE0..0xE9` and
  `MAPOBJECTFLAG_UNK13` set.
- Guarded calls temporarily present `LocalMapObject::unk88[1]` offset `0x8C`
  as floor-zero only to `0x02205808`; all other render/movement state remains
  untouched, including the live long-hop body carrier `object->unk88[1] = arc`.

Patch plan:

- `armips/asm/overworlds.s`
  - Patch only `0x021F78E6`, replacing the stock `bl 0x02205808` with
    `bl OverworldWildSpawns_GuardedUnk88AuxUpdate`.
- `armips/asm/fairy.s`
  - Add `OverworldWildSpawns_GuardedUnk88AuxUpdate` inside the existing
    resident ARM9 `.area 0x02071CA0-.` after `plate_to_type_table` and before
    `.endarea`.
  - The wrapper saves/restores `r3`, `r4`, `r7`, and `lr`, checks the wild ID
    range and `MAPOBJECTFLAG_UNK13`, clears/restores `[object + 0x8C]` only for
    guarded calls, and then returns with the original helper's `r0`.

Expected success signal:

- Build succeeds without changing overlay 149 size.
- Harness exits `0` with `shadow_pass.passed == true`.
- Igglybuff remains trackable and visibly hops, with no crash/no-spawn/no-hop
  regression.

Expected failure signal:

- Build fails because the ARM9 area overflows or the forward ARMIPS symbol is
  not resolvable.
- Harness exits nonzero due to crash, no spawn, no hop/body tracking failure,
  or `shadow_pass.passed == false`.

Patch:

- `armips/asm/overworlds.s`
  - Patched only the small-Pokemon draw-path callsite at `0x021F78E6`:
    `bl 0x02205808` -> `bl OverworldWildSpawns_GuardedUnk88AuxUpdate`.
- `armips/asm/fairy.s`
  - Added `OverworldWildSpawns_GuardedUnk88AuxUpdate` inside the existing
    resident ARM9 fairy area `0x02071C28..0x02071CA0`, after
    `plate_to_type_table` and before `.endarea`.
  - The wrapper checks `object->id` in `0xE0..0xE9`, checks
    `MAPOBJECTFLAG_UNK13`, saves `[object + 0x8C]`, writes zero, calls
    `0x02205808`, restores `[object + 0x8C]`, and returns the helper result.
- No changes were made to `faceVec`, `posVec`, tile fields, params, `gfxId`,
  `unkC8`, overlay 150, raw G3 drawing, or overlay 149 long-hop arc logic.

Build:

- UI build endpoint succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1550.nds`.
- `test.nds` size: `184792544` bytes.
- `build/output_overworld_wild_spawns_overlay.bin` measured `44996`
  bytes, unchanged from S64/S65 and still under the `0xB000` overlay 149 limit.
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1168`
  bytes.
- `build/output_overworld_wild_helper_overlay.bin` measured `4086`
  bytes.
- `build/output.bin` measured `31196` bytes.
- Binary spot check:
  - `base/overlay/overlay_0001.bin` at `0x021F78E6` starts with
    `7a f6 b5 f9`, confirming the patched callsite.
  - `base/arm9.bin` at `0x02071C28` contains the fairy routine followed by
    the S67 wrapper inside the existing padding.
- `git diff --check` passed.

Runtime result:

- Headless harness command:
  `scripts/headless-overworld-shadow-harness.py --prefix igglybuff_shadow_s67_unk88_floor_sample --capture-frames 360 --contact-every 4 --target-igglybuff ledge-spawn`.
- DSV source:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Harness exit code: `2`.
- Harness detected `actual_left_hop_start_frame` /
  `second_left_jump_start_frame` at frame `27`.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s67_unk88_floor_sample_contact.png`.
- Summary JSON:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s67_unk88_floor_sample_summary.json`.
- Default oracle result:
  `shadow_pass.passed == false`,
  `valid_body_frame_count == 105`,
  `tracked_percent == 100`,
  `present_frame_count == 0`,
  `present_percent == 0`,
  `missing_shadow_frame_count == 105`,
  `max_missing_run == 105`,
  with pass window `75..179`.

Conclusion:

- S67 builds and does not regress spawn/hop/body tracking.
- This S67 run was not instrumented, so it did not prove whether the guarded
  call path actually fired during the harness hop; S68 later found the guarded
  hit counter stayed at `0`.
- S67 as implemented is not a fix for the Igglybuff grass-to-non-grass midair
  floor shadow. Because S68 showed the guarded path did not pass both guards,
  do not use S67 alone as proof that `0x02205808` / `unk88[1]` is or is not the
  missing persistent shadow owner.

### S68 - Instrumented S67 Guard Hit Counter

Purpose:

- S68 was instrumentation-only, not a proposed shadow fix.
- The goal was to keep the S67 hook/wrapper active for one harness run and
  prove whether the guarded branch actually passed during the Igglybuff
  grass-to-non-grass hop before retiring or redirecting this path.

Patch:

- `armips/asm/overworlds.s`
  - Temporarily kept the S67 callsite patch at `0x021F78E6`:
    `bl 0x02205808` -> `bl OverworldWildSpawns_GuardedUnk88AuxUpdate`.
- `armips/asm/fairy.s`
  - Temporarily revised `OverworldWildSpawns_GuardedUnk88AuxUpdate` inside
    the existing ARM9 fairy padding `0x02071C28..0x02071CA0`.
  - Added a resident counter label
    `OverworldWildSpawns_GuardedUnk88AuxUpdateHitCount`.
  - Incremented the counter only after both guards passed and before zeroing
    `[object + 0x8C]`.
  - The built counter address was `0x02071C88`; the literal pool word at
    `0x02071C84` pointed to that address.
- `scripts/headless-overworld-shadow-harness.py`
  - Added optional `--memory-read label:type:address` support, reusing the
    existing parser and memory reader from `scripts/headless-overworld-test.py`.
  - The harness now writes post-capture memory reads into `memory_reads` in the
    summary JSON.

Instrumented build:

- UI build endpoint succeeded with `runAfter:true` and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1551.nds`.
- `test.nds` size: `184792544` bytes.
- `build/output_overworld_wild_spawns_overlay.bin` measured `44996` bytes.
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1168`
  bytes.
- `build/output_overworld_wild_helper_overlay.bin` measured `4086` bytes.
- `build/output.bin` measured `31196` bytes.
- Binary spot check for the instrumented ROM:
  - `base/overlay/overlay_0001.bin` at `0x021F78E6` started with
    `7a f6 b5 f9`, confirming the temporary S67/S68 callsite hook.
  - `base/arm9.bin` showed the counter literal/counter pair at
    `0x02071C84` / `0x02071C88`.

Runtime result:

- Headless harness command:
  `scripts/headless-overworld-shadow-harness.py --prefix igglybuff_shadow_s68_unk88_floor_sample_hit_counter --capture-frames 360 --contact-every 4 --target-igglybuff ledge-spawn --memory-read s67_hits:u32:0x02071C88`.
- DSV source:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Harness exit code: `2`.
- Harness detected `actual_left_hop_start_frame` /
  `second_left_jump_start_frame` at frame `27`.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s68_unk88_floor_sample_hit_counter_contact.png`.
- Summary JSON:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s68_unk88_floor_sample_hit_counter_summary.json`.
- Memory read result:
  `s67_hits` at `0x02071C88` was `0x00000000` / `0`.
- Default oracle result:
  `shadow_pass.passed == false`,
  `valid_body_frame_count == 105`,
  `tracked_percent == 100`,
  `present_frame_count == 0`,
  `present_percent == 0`,
  `missing_shadow_frame_count == 105`,
  `max_missing_run == 105`,
  with pass window `75..179`.

Conclusion:

- The counter was not positive. The guarded S67 branch did not pass both guards
  during the harness repro/capture window.
- Because the guarded path did not fire, this run does not prove that
  `0x02205808` / `unk88[1]` floor sampling is not the missing persistent shadow
  owner. It only proves the specific S67 hook/guard combination did not engage
  for the harness hop.
- The temporary S67/S68 runtime hook was removed after the diagnostic run; the
  harness `--memory-read` support and this documentation were kept.

Post-run baseline restore:

- Removed the temporary `0x021F78E6` callsite patch from
  `armips/asm/overworlds.s`.
- Removed the temporary wrapper/counter block from `armips/asm/fairy.s`.
- UI build endpoint succeeded again with `runAfter:true` and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1552.nds`.
- Restored-baseline `test.nds` size: `184792544` bytes.
- Restored-baseline `build/output_overworld_wild_spawns_overlay.bin` measured
  `44996` bytes.
- Binary spot check after restore:
  - `base/overlay/overlay_0001.bin` at `0x021F78E6` was `0d f0 8f ff`, so the
    S67/S68 callsite hook is no longer present.
  - `base/arm9.bin` fairy padding after `plate_to_type_table` is back to
    `0xFF` fill; the temporary wrapper/counter bytes are no longer present.

### S69 - Auxiliary Gate Status Instrumentation

Purpose:

- S69 is instrumentation-only, not a proposed visual fix.
- S68 showed the guarded hit counter stayed at `0`, but it did not identify
  whether the `0x021F78E6` callsite never ran, the wild-ID guard failed, the
  `MAPOBJECTFLAG_UNK13` guard failed, or the guarded hit counter itself was
  faulty.
- This probe records which gates are seen by the exact S67/S68 callsite while
  preserving the original `0x02205808` behavior and leaving `unk88[1]`
  unchanged.

Status bits:

- `0x1`: wrapper entered.
- `0x2`: `object->id` was in `0xE0..0xE9`.
- `0x4`: `object->flags & MAPOBJECTFLAG_UNK13` was set.
- `0x8`: wild ID and `MAPOBJECTFLAG_UNK13` were both true in the same
  invocation.

Patch plan:

- `armips/asm/overworlds.s`
  - Temporarily patch only the small-Pokemon draw-path callsite at
    `0x021F78E6`:
    `bl 0x02205808` -> `bl OverworldWildSpawns_AuxGateStatusProbe`.
- `armips/asm/fairy.s`
  - Add `OverworldWildSpawns_AuxGateStatusProbe` inside the existing ARM9
    fairy padding `0x02071C28..0x02071CA0`.
  - Add a resident `u32` status word after the wrapper.
  - OR the status bits above into the word, call `0x02205808` unchanged, and
    return the original helper result.

Expected interpretation:

- `0x0`: hook did not run or was not installed.
- `0x1`: callsite ran, but not for a wild/active-hop object.
- `0x3`: wild ID reached, but `MAPOBJECTFLAG_UNK13` timing failed.
- `0x5`: `MAPOBJECTFLAG_UNK13` appeared somewhere, but not with wild ID.
- `0xF`: both guards passed; recheck S68 counter placement/implementation.

Patch:

- `armips/asm/overworlds.s`
  - Temporarily patched only the small-Pokemon draw-path callsite at
    `0x021F78E6`:
    `bl 0x02205808` -> `bl OverworldWildSpawns_AuxGateStatusProbe`.
- `armips/asm/fairy.s`
  - Temporarily added `OverworldWildSpawns_AuxGateStatusProbe` inside the
    existing ARM9 fairy padding `0x02071C28..0x02071CA0`.
  - Added a resident status word after the wrapper.
  - The wrapper only ORed diagnostic bits into the status word and then called
    `0x02205808` unchanged; it did not touch `unk88[1]`, `faceVec`, `posVec`,
    tile fields, params, `gfxId`, `unkC8`, overlay 150, raw G3 drawing, or
    overlay 149 long-hop logic.

Instrumented build:

- UI build endpoint succeeded with `runAfter:true` and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1553.nds`.
- `test.nds` size: `184792544` bytes.
- `build/output_overworld_wild_spawns_overlay.bin` measured `44996` bytes.
- `build/output_overworld_wild_behavior_data_overlay.bin` measured `1168`
  bytes.
- `build/output_overworld_wild_helper_overlay.bin` measured `4086` bytes.
- `build/output.bin` measured `31196` bytes.
- Binary spot check for the instrumented ROM:
  - `base/overlay/overlay_0001.bin` at `0x021F78E6` started with
    `7a f6 b5 f9`, confirming the temporary S69 callsite hook.
  - `base/arm9.bin` showed the literal/status pair at
    `0x02071C8C` / `0x02071C90`.
- Built status word address: `0x02071C90`.

Runtime result:

- Headless harness command:
  `scripts/headless-overworld-shadow-harness.py --prefix igglybuff_shadow_s69_aux_gate_status --capture-frames 360 --contact-every 4 --target-igglybuff ledge-spawn --no-fail-on-shadow-pass --memory-read aux_status:u32:0x02071C90`.
- DSV source:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Harness exit code: `0` due to `--no-fail-on-shadow-pass`.
- Harness detected `actual_left_hop_start_frame` /
  `second_left_jump_start_frame` at frame `27`.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s69_aux_gate_status_contact.png`.
- Summary JSON:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s69_aux_gate_status_summary.json`.
- Memory read result:
  `aux_status` at `0x02071C90` was `0x00000000` / `0`.
- Default oracle result, recorded but not used for process failure:
  `shadow_pass.passed == false`,
  `valid_body_frame_count == 105`,
  `tracked_percent == 100`,
  `present_frame_count == 0`,
  `present_percent == 0`,
  `missing_shadow_frame_count == 105`,
  `max_missing_run == 105`,
  with pass window `75..179`.

Interpretation:

- The S69 hook was installed in the built overlay, but `aux_status` stayed
  `0x0`.
- Given the confirmed callsite patch, this means the `0x021F78E6` auxiliary
  update callsite did not run during the harness repro/capture window.
- S68's zero hit counter was therefore not caused by wild-ID or
  `MAPOBJECTFLAG_UNK13` guard timing at this callsite; the callsite itself was
  not reached for the Igglybuff hop path under the harness.

Post-run baseline restore:

- Removed the temporary `0x021F78E6` callsite patch from
  `armips/asm/overworlds.s`.
- Removed the temporary wrapper/status word block from `armips/asm/fairy.s`.
- UI build endpoint succeeded again with `runAfter:true` and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1554.nds`.
- Restored-baseline `test.nds` size: `184792544` bytes.
- Restored-baseline `build/output_overworld_wild_spawns_overlay.bin` measured
  `44996` bytes.
- Binary spot check after restore:
  - `base/overlay/overlay_0001.bin` at `0x021F78E6` was `0d f0 8f ff`, so the
    S69 callsite hook is no longer present.
  - `base/arm9.bin` fairy padding after `plate_to_type_table` is back to
    `0xFF` fill; the temporary wrapper/status bytes are no longer present.

### S70 - Primary Draw Phase Probe

Purpose:

- S70 is instrumentation-only, not a proposed visual fix.
- S69 proved the auxiliary `0x021F78E6 -> 0x02205808` init callsite did not run
  during the harness repro/capture window.
- The next candidate is the always-running primary draw phase at
  `0x021F78FE -> 0x021F8D80`, which is closer to the visible body draw.

Status bits:

- `0x1`: primary wrapper entered.
- `0x2`: `object->id` was in `0xE0..0xE9`.
- `0x20`: wild ID plus required active-hop flags were observed in the same
  invocation. The flag mask is `BIT_JUMP_START | BIT_MOVE_START |
  MAPOBJECTFLAG_UNK13` (`0x00012004`).

Patch plan:

- `armips/asm/overworlds.s`
  - Temporarily patch only the primary draw callsite at `0x021F78FE`:
    `bl 0x021F8D80` -> `bl OverworldWildSpawns_PrimaryDrawProbe`.
- `armips/asm/fairy.s`
  - Add `OverworldWildSpawns_PrimaryDrawProbe` inside the existing ARM9 fairy
    padding `0x02071C28..0x02071CA0`.
  - Add resident diagnostics after the wrapper:
    `OverworldWildSpawns_PrimaryEnterCount` and
    `OverworldWildSpawns_PrimaryStatus`.
  - The primary draw call has a stack argument at `[sp]`; the wrapper must not
    call `0x021F8D80` with a shifted stack. To preserve behavior, save low
    registers temporarily, record diagnostics, restore the original registers
    and stack layout, then tail-branch to `0x021F8D80` so the original callee
    returns directly to the stock caller.
  - The separate active counter, renderData byte pack, and larger field
    sampling are omitted if the area is too tight; do not spill this probe into
    overlay 149 or broader hooks.

Instrumented patch details:

- `armips/asm/overworlds.s`
  - Patched only `0x021F78FE` for the instrumentation run.
  - Instrumented built bytes at `base/overlay/overlay_0001.bin + 0x11FFE`
    were `7a f6 a9 f9`.
- `armips/asm/fairy.s`
  - Wrapper built at `0x02071C54`.
  - `OverworldWildSpawns_PrimaryEnterCount` built at `0x02071C94`.
  - `OverworldWildSpawns_PrimaryStatus` built at `0x02071C98`.
  - Literal pool entries used `0x02071C94`, `0x00012004`, and
    `0x021F8D81`.

Instrumented build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success, exit code `0`, elapsed `0:37`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1555.nds`
- Sizes:
  - `test.nds`: `184792544`
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996`
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `1168`
  - `build/output_overworld_wild_helper_overlay.bin`: `4086`
  - `build/output.bin`: `31196`
- Build warning observed: pre-existing `unused parameter 'bsys'` in
  `src/battle/battle_script_commands.c`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s70_primary_draw_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-read primary_enter:u32:0x02071C94 \
  --memory-read primary_status:u32:0x02071C98
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- `contact_start_frame`: `27`.
- Memory reads:
  - `primary_enter`: `0x000005B0` / `1456`.
  - `primary_status`: `0x00000003`.
- Shadow oracle still failed:
  - `shadow_pass.passed`: `false`
  - `tracked_percent`: `100`
  - `present_frame_count`: `0` / `105`
  - `present_percent`: `0`
  - `missing_shadow_frame_count`: `105`
  - `max_missing_run`: `105`
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s70_primary_draw_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s70_primary_draw_probe_contact.png`
  - Ready screenshot:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s70_primary_draw_probe_00_ready.png`
  - After-left screenshot:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s70_primary_draw_probe_01_after_left_spawn.png`
  - DSV:
    `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`

Interpretation:

- The primary draw hook is definitely reached during the repro
  (`primary_enter=1456`).
- The hook observes overworld wild object IDs (`primary_status & 0x2`).
- The tested active-hop flag combo (`0x00012004`) was not observed in the same
  invocation (`primary_status & 0x20` is clear).
- Therefore this probe shows that `0x021F78FE -> 0x021F8D80` is live for the
  repro and wild IDs, but does not by itself identify a persistent shadow owner
  or a safe state mutation. S70 remains instrumentation-only.

Restoration:

- Removed the temporary `0x021F78FE` hook and the fairy wrapper/status words
  after collecting the harness result.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Restored-baseline build result: success, exit code `0`, elapsed `0:28`; UI
  opened `test.nds`.
- Restored-baseline copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1556.nds`
- Restored-baseline sizes:
  - `test.nds`: `184792544`
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996`
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `1168`
  - `build/output_overworld_wild_helper_overlay.bin`: `4086`
  - `build/output.bin`: `31196`
- Binary spot check after restore:
  - `base/overlay/overlay_0001.bin` at `0x021F78FE` is back to stock
    `01 f0 3f fa`.
  - `base/arm9.bin` fairy padding after `plate_to_type_table` is back to
    `0xFF` fill; the S70 wrapper/status bytes are no longer present.

### S71 - Active Object RAM Mirror Probe

Purpose:

- S71 was intended as instrumentation only, not a visual fix.
- S70 proved the primary draw path runs and sees wild IDs, but not whether it
  sees the exact active long-hop object or the active-hop flags at draw time.
- S71 therefore targeted
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset` so the actual
  overlay-149 long-hop object could be mirrored immediately around the existing
  flag write:
  `object->flags |= (BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13)`.

Planned fields and status bits:

- Planned fields:
  - `s71_apply_count`
  - `s71_status`
  - `s71_object_ptr`
  - `s71_object_id`
  - `s71_slot`
  - `s71_elapsed_total`
  - `s71_max_arc`
  - `s71_pre_flags_or`
  - `s71_post_flags_or`
  - `s71_face_y_or`
  - `s71_unk88_y_or`
  - `s71_unk94_y_or`
  - `s71_pos_y_last`
- Planned status bits:
  - `0x1`: entered the apply probe.
  - `0x2`: object ID was in `0xE0..0xE9`.
  - `0x4`: runtime long-hop active for the slot.
  - `0x8`: arc was nonzero.
  - `0x10`: all active-hop flags were already set before the OR.
  - `0x20`: all active-hop flags were set after the OR.
  - `0x40`: `elapsed >= 2`.
  - `0x80`: `total != 0`.

Implementation attempt A:

- Added temporary diagnostic words in resident ARM9 fairy padding, starting at
  `0x02071C54`.
- Added a C recorder function near
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset` and called it
  immediately after the flag OR.
- This used fairy padding only as diagnostic storage, not as a hook.
- Build result: failed before ROM generation.
- UI build command:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Failure:
  `arm-none-eabi-ld: build/overworld_wild_spawns_overlay_linked.o section '.text' will not fit in region 'rom'`
- Exit code: `2`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `.text=44660`, `.bss=114`, `.rodata=350`,
  `.overworld_wild_spawns_entry=12`, total `45230`.

Implementation attempt B:

- Removed the helper function and reduced the C probe to a single inline block
  after the flag OR.
- Kept only the decisive writes:
  `apply_count`, `status`, `object_ptr`, `object_id`, `slot`,
  `elapsed_total`, `max_arc`, `pre_flags_or`, and `post_flags_or`.
- Build result: still failed before ROM generation.
- UI build command:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Failure:
  `arm-none-eabi-ld: build/overworld_wild_spawns_overlay_linked.o section '.text' will not fit in region 'rom'`
- Exit code: `2`.
- `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`
  measured `.text=44580`, `.bss=114`, `.rodata=350`,
  `.overworld_wild_spawns_entry=12`, total `45150`.

Result:

- No S71 harness command was run because no instrumented ROM was produced.
- No S71 contact sheet, summary JSON, or memory-read values exist.
- Conclusion: with the current dirty overlay-149 baseline, even a reduced
  source-level RAM mirror inside
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset` exceeds the
  overlay's remaining space. Future S71-style diagnostics should avoid adding
  linked C in overlay 149 unless space is first recovered or the probe is moved
  to a replacement-style ARMIPS patch that does not grow the overlay.

Restoration:

- Removed the temporary C probe and fairy diagnostic words.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Restored-baseline build result: success, exit code `0`, elapsed `0:32`; UI
  opened `test.nds`.
- Restored-baseline copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1557.nds`
- Restored-baseline sizes:
  - `test.nds`: `184792544`
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996`
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `1168`
  - `build/output_overworld_wild_helper_overlay.bin`: `4086`
  - `build/output.bin`: `31196`
- Restored overlay-149 linked section:
  - `build/overworld_wild_spawns_overlay_linked.o` `.text`: `44996`.
- Binary spot check after restore:
  - `base/arm9.bin` fairy padding after `plate_to_type_table` is back to
    `0xFF` fill; the S71 diagnostic words are no longer present.

### S72 - Apply Flag Mirror ARMIPS Probe

Purpose:

- S72 was instrumentation only, not a visual fix.
- S71 could not be built as overlay-149 C because the overlay is size-tight.
- This probe therefore tested the same active-object flag-write point with a
  raw ARMIPS replacement that did not grow overlay 149 C.
- Targeted the existing flag-write block inside
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset` around
  `0x023CF744`.

Stock bytes and disassembly before the probe:

- `base/overlay/overlay_0149.bin + 0x2730..0x2760` confirmed the stock block:

```text
023cf730: 6ee3       ldr r3, [r4, #108]
023cf732: 1428       asrs r0, r5, #16
023cf734: 42b1       cmp r1, r6
023cf736: d101       bne.n 0x23cf73c
023cf738: 4283       cmp r3, r0
023cf73a: d003       beq.n 0x23cf744
023cf73c: 65a1       str r1, [r4, #88]
023cf73e: 6623       str r3, [r4, #96]
023cf740: 6666       str r6, [r4, #100]
023cf742: 66e0       str r0, [r4, #108]
023cf744: 6826       ldr r6, [r4, #0]
023cf746: 4f14       ldr r7, [pc, #80]
023cf748: 4337       orrs r7, r6
023cf74a: 0020       movs r0, r4
023cf74c: 6027       str r7, [r4, #0]
023cf74e: 4913       ldr r1, [pc, #76]
023cf750: 4c13       ldr r4, [pc, #76]
023cf752: f008 fb1b  bl 0x23d7d8c
023cf756: b007       add sp, #28
023cf758: bdf0       pop {r4, r5, r6, r7, pc}
```

- Raw target bytes at `0x023CF744` were `26 68 14 4f`.

Temporary patch:

- `armips/asm/fairy.s`
  - Added `OverworldWildSpawns_S72ApplyFlagMirror` in ARM9 fairy padding after
    `plate_to_type_table`.
  - The helper recreated the two overwritten instructions:
    `ldr r6, [r4, #0]` and `ldr r7, =0x00012004`.
  - The helper used `bx lr` so the stock caller resumed at `0x023CF748`, where
    the original `orrs r7, r6` and `str r7, [r4, #0]` still executed.
  - The helper did not touch faceVec, posVec, tile fields, params, gfxId,
    `unkC8`, overlay 150, raw G3 draw, or the long-hop arc carrier.
- `armips/asm/fairy.s`
  - Temporarily patched `base/overlay/overlay_0149.bin` at `0x023CF744`:
    `bl OverworldWildSpawns_S72ApplyFlagMirror`.
  - Instrumented built bytes at `base/overlay/overlay_0149.bin + 0x2744`
    were `a2 f4 86 fa`.
- Diagnostic words:
  - `s72_count`: `0x02071C88`
  - `s72_status`: `0x02071C8C`
  - `s72_object`: `0x02071C90`
  - `s72_id`: `0x02071C94`
  - `s72_pre_flags`: `0x02071C98`
  - `s72_post_flags`: `0x02071C9C`
- Status bits:
  - `0x01`: helper entered.
  - `0x02`: object ID was in `0xE0..0xE9`.
  - `0x20`: mirrored post flags contain `0x00012004`.

Instrumented build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success, exit code `0`, elapsed `0:34`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1558.nds`
- Sizes:
  - `test.nds`: `184792544`
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996`
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `1168`
  - `build/output_overworld_wild_helper_overlay.bin`: `4086`
  - `build/output.bin`: `31196`
- Build warning observed: pre-existing `unused parameter 'bsys'` in
  `src/battle/battle_script_commands.c`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s72_apply_flag_mirror \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-read s72_count:u32:0x02071C88 \
  --memory-read s72_status:u32:0x02071C8C \
  --memory-read s72_object:u32:0x02071C90 \
  --memory-read s72_id:u32:0x02071C94 \
  --memory-read s72_pre_flags:u32:0x02071C98 \
  --memory-read s72_post_flags:u32:0x02071C9C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- `contact_start_frame`: `27`.
- Memory reads:
  - `s72_count`: `0x000000B8` / `184`.
  - `s72_status`: `0x00000023` / `35`.
  - `s72_object`: `0x022AEF44`.
  - `s72_id`: `0x000000E1` / `225`.
  - `s72_pre_flags`: `0x0010C801`.
  - `s72_post_flags`: `0x0011E805`.
- Shadow oracle still failed:
  - `shadow_pass.passed`: `false`
  - `tracked_percent`: `100`
  - `present_frame_count`: `0` / `105`
  - `present_percent`: `0`
  - `missing_shadow_frame_count`: `105`
  - `max_missing_run`: `105`
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s72_apply_flag_mirror_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s72_apply_flag_mirror_contact.png`
  - Ready screenshot:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s72_apply_flag_mirror_00_ready.png`
  - After-left screenshot:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s72_apply_flag_mirror_01_after_left_spawn.png`
  - DSV:
    `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`

Interpretation:

- The exact flag-write block at `0x023CF744` executes during the harness repro
  (`s72_count=184`).
- The helper saw an overworld wild object ID in the target range
  (`s72_status & 0x2`, `s72_id=0xE1`).
- The mirrored stock post flags contain the expected active-hop mask:
  `0x0011E805 & 0x00012004 == 0x00012004`.
- Since the shadow oracle still had no present frames in the pass window,
  absence of the overlay-149 flag OR is not the missing persistent shadow
  owner. The next target should be downstream shadow ownership/lifecycle after
  this flag write rather than another proof that overlay 149 sets the active
  flags.

Restoration:

- Removed the temporary `0x023CF744` hook, fairy helper, and diagnostic words
  after collecting the harness result.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Restored-baseline build result: success, exit code `0`, elapsed `0:25`; UI
  opened `test.nds`.
- Restored-baseline copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1559.nds`
- Restored-baseline sizes:
  - `test.nds`: `184792544`
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996`
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `1168`
  - `build/output_overworld_wild_helper_overlay.bin`: `4086`
  - `build/output.bin`: `31196`
- Binary spot check after restore:
  - `base/overlay/overlay_0149.bin` at `0x023CF744` is back to stock
    `26 68 14 4f`.
  - `base/arm9.bin` fairy padding after `plate_to_type_table` is back to
    `0xFF` fill; the S72 helper and diagnostic words are no longer present.

### S73 - Primary Draw E1 Correlation Probe

Purpose:

- S73 was instrumentation only, not a proposed visual fix.
- S72 proved the overlay-149 flag write executes for wild object ID `0xE1`
  and writes flags containing `0x00012004`, but S70's primary-draw probe was
  too broad to prove whether that exact active wild object reaches primary draw
  with the same active-hop flags.
- S73 therefore correlated the normal small-Pokemon primary draw callsite with
  object ID `0xE1` and draw-time flags/render bytes.

Implementation notes:

- The initial S73 proposal included faceVec and stack-argument status bits, but
  the safe resident padding budget is exact. This built probe kept the
  decisive fields instead: enter count, `0xE1` draw count, object pointer,
  flags, render-data pack, and `unk88[1]`.
- Because of that compression, S73 does not answer draw-time `faceVec` state
  and does not independently runtime-verify stack-argument preservation. It
  only verifies that the wrapper could tail-call stock primary draw without an
  immediate crash in the harness.
- `armips/asm/fairy.s`
  - Temporarily patched only the primary draw callsite at
    `0x021F78FE`: `bl 0x021F8D80` -> `bl
    OverworldWildSpawns_S73PrimaryE1Probe`.
  - Added the first helper chunk in ARM9 padding
    `0x02110258..0x021102A4`.
  - Added the tail helper chunk in the existing fairy padding
    `0x02071C54..0x02071CA0`.
  - The helper saved the original call registers, recorded diagnostics, then
    tail-branched to `0x021F8D81` so stock primary draw saw the original stack
    layout.
  - Added seven diagnostic words in overlay-1 tail padding
    `0x02209B44..0x02209B5F`.
- Instrumented built bytes:
  - `base/overlay/overlay_0001.bin` at `0x021F78FE` was `18 f7 ab fc`.
  - Diagnostic words at `0x02209B44..0x02209B5F` were zero-initialized.

Diagnostic words:

- `s73_status`: `0x02209B44`
- `s73_enter`: `0x02209B48`
- `s73_e1_count`: `0x02209B4C`
- `s73_e1_object`: `0x02209B50`
- `s73_e1_flags`: `0x02209B54`
- `s73_e1_render_pack`: `0x02209B58`
- `s73_e1_unk88_y`: `0x02209B5C`

Status bits:

- `0x01`: wrapper entered.
- `0x02`: saw object ID `0xE1`.
- `0x04`: draw-time flags contained all of `0x00012004`.
- `0x10`: `unk88[1]` was nonzero on at least one `0xE1` draw.
- `0x20`: render-data byte `+0x15` was nonzero on at least one `0xE1` draw.
- `0x40`: render-data byte `+0x17` bit 0 was set on at least one `0xE1`
  draw.

Instrumented build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1560.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s73_primary_e1_correlate \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-read s73_status:u32:0x02209B44 \
  --memory-read s73_enter:u32:0x02209B48 \
  --memory-read s73_e1_count:u32:0x02209B4C \
  --memory-read s73_e1_object:u32:0x02209B50 \
  --memory-read s73_e1_flags:u32:0x02209B54 \
  --memory-read s73_e1_render_pack:u32:0x02209B58 \
  --memory-read s73_e1_unk88_y:u32:0x02209B5C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- `contact_start_frame`: `27`.
- Memory reads:
  - `s73_status`: `0x00000073` / `115`.
  - `s73_enter`: `0x000005B0` / `1456`.
  - `s73_e1_count`: `0x000001BA` / `442`.
  - `s73_e1_object`: `0x022AEED0`.
  - `s73_e1_flags`: `0x0010C801`.
  - `s73_e1_render_pack`: `0x00030100`.
  - `s73_e1_unk88_y`: `0x00000000`.
- Shadow oracle still failed:
  - `shadow_pass.passed`: `false`
  - `tracked_percent`: `100`
  - `present_frame_count`: `0` / `105`
  - `present_percent`: `0`
  - `missing_shadow_frame_count`: `105`
  - `max_missing_run`: `105`
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s73_primary_e1_correlate_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s73_primary_e1_correlate_contact.png`

Interpretation:

- Primary draw definitely sees object ID `0xE1` during the repro
  (`s73_e1_count=442`), so S70's broad wild-ID observation did include this
  object identity class.
- No `0xE1` primary draw observed the full active-hop mask
  (`s73_status & 0x04 == 0`).
- The last recorded draw-time flags were `0x0010C801`, while S72's last
  recorded post-OR flags were `0x0011E805`; the difference is exactly
  `0x00012004`.
- `s73_status` is an aggregate OR across the run. `s73_e1_flags` and
  `s73_e1_unk88_y` are last-recorded values, so `s73_status & 0x10` means
  `unk88[1]` was nonzero at least once even though the final recorded value was
  `0`.
- The object pointer differs from S72 because this was a separate run; S73 keys
  the correlation by object ID, not by stable heap address.
- Therefore S72 and S73 together strongly indicate that overlay 149 sets
  `BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13`, but those bits are
  gone by the time the normal primary draw consumes object ID `0xE1`. They do
  not prove the same object/frame transition inside one run. The next probe
  should identify where that active-hop mask is cleared between the overlay-149
  apply path and the overlay-1 primary draw callsite.

Restoration:

- Removed the temporary `0x021F78FE` hook, split ARM9 helper chunks, and
  diagnostic words after collecting the harness result.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Restored-baseline build result: success, exit code `0`, elapsed `0:25`; UI
  opened `test.nds`.
- Restored-baseline copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1561.nds`
- Binary spot check after restore:
  - `base/overlay/overlay_0001.bin` at `0x021F78FE` is back to stock
    `01 f0 3f fa`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..` is back to tail padding
    (`0xFF` fill followed by final zero bytes), not diagnostic words.
  - `base/arm9.bin` helper ranges `0x02071C54..0x02071CA0` and
    `0x02110258..0x021102A4` are back to `0xFF` fill.

### S74 - Landing Clear Callsite Probe

Purpose:

- S74 was instrumentation only, not a proposed visual fix.
- S73 showed that object ID `0xE1` reached primary draw without the active-hop
  mask `0x00012004`. A likely clearer was the landing normalizer at
  `OverworldWildSpawns_SetObjectLandingTile`, which calls `MapObject_ClearBits`
  with mask `0x00012314`.

Implementation notes:

- `armips/asm/fairy.s`
  - Temporarily patched overlay 149 at `0x023CE2FE`, replacing the
    `SetObjectLandingTile -> MapObject_ClearBits` call with an ARM9-resident
    probe in fairy padding.
  - The helper inlined stock `MapObject_ClearBits` behavior
    (`object->flags &= ~mask`) and logged wild object IDs `0xE0..0xE9`.
  - Diagnostic words were stored at `0x02209B44..0x02209B5F`.
- `scripts/headless-overworld-shadow-harness.py`
  - Added optional `--memory-sample-every N`; default remains disabled. This
    samples the requested memory reads during the capture window so diagnostic
    events can be compared to the f075-f179 shadow oracle window. The pass rule
    itself remains unchanged and time-of-day-safe.

Instrumented build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1562.nds`

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s74_landing_clear_probe_sampled \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s74_status:u32:0x02209B44 \
  --memory-read s74_landing_enter:u32:0x02209B48 \
  --memory-read s74_landing_hit:u32:0x02209B4C \
  --memory-read s74_landing_object:u32:0x02209B50 \
  --memory-read s74_landing_id:u32:0x02209B54 \
  --memory-read s74_landing_pre_flags:u32:0x02209B58 \
  --memory-read s74_landing_post_flags:u32:0x02209B5C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- Shadow oracle still failed:
  - `shadow_pass.passed`: `false`
  - `tracked_percent`: `100`
  - `present_frame_count`: `0` / `105`
  - `max_missing_run`: `105`
- Final memory reads:
  - `s74_status`: `0x0000001F`.
  - `s74_landing_enter`: `11`.
  - `s74_landing_hit`: `11`.
  - `s74_landing_id`: `0xE1`.
  - `s74_landing_pre_flags`: `0x0010C801`.
  - `s74_landing_post_flags`: `0x0010C801`.
- Sampled memory transition summary:
  - Frame `118`: first broad wild landing-clear hit; status already showed an
    active-mask clear, but the latched object ID was `0xE0`, not the selected
    Igglybuff.
  - Frame `203`: first `0xE1` hit in the sample stream.
  - Frame `299`: later `0xE1` hit with active pre-flags.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s74_landing_clear_probe_sampled_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s74_landing_clear_probe_sampled_contact.png`

Interpretation:

- The landing normalizer can remove `0x00012004`, but the broad S74 probe
  mixed multiple wild objects. The first in-window active clear was not the
  selected ledge-spawned Igglybuff. This needed an exact-ID latch before any
  landing-cleanup fix could be justified.

### S75 - Exact `0xE1` Landing Clear Latch

Purpose:

- S75 narrowed S74 to the selected Igglybuff object ID `0xE1` and latched only
  the first `0xE1` landing clear whose pre-flags contained `0x00012004`.

Implementation notes:

- `armips/asm/fairy.s`
  - Kept the same temporary `0x023CE2FE` landing-clear hook.
  - Filtered logging to object ID `0xE1`.
  - Diagnostic layout:
    - `0x02209B44`: `s75_status`.
    - `0x02209B48`: landing-clear enter count.
    - `0x02209B4C`: `0xE1` hit count.
    - `0x02209B50`: first active-mask clear hit count.
    - `0x02209B54`: `0xE1` object pointer.
    - `0x02209B58`: first active-mask pre-clear flags.
    - `0x02209B5C`: first active-mask post-clear flags.
- An initial S75 build overflowed the `0x02110258..0x021102A4` helper padding by
  4 bytes. The logger was trimmed, then rebuilt successfully.

Instrumented build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success, exit code `0`, elapsed `0:28`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1563.nds`

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s75_exact_e1_landing_latch \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s75_status:u32:0x02209B44 \
  --memory-read s75_landing_enter:u32:0x02209B48 \
  --memory-read s75_e1_hit:u32:0x02209B4C \
  --memory-read s75_first_active_hit:u32:0x02209B50 \
  --memory-read s75_e1_object:u32:0x02209B54 \
  --memory-read s75_first_pre_flags:u32:0x02209B58 \
  --memory-read s75_first_post_flags:u32:0x02209B5C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- Shadow oracle still failed:
  - `shadow_pass.passed`: `false`
  - `tracked_percent`: `100`
  - `present_frame_count`: `0` / `105`
  - `max_missing_run`: `105`
- Final memory reads:
  - `s75_status`: `0x0000001F`.
  - `s75_landing_enter`: `11`.
  - `s75_e1_hit`: `8`.
  - `s75_first_active_hit`: `1`.
  - `s75_first_pre_flags`: `0x0011E005`.
  - `s75_first_post_flags`: `0x0010C001`.
- Sampled memory transition summary:
  - Frame `118`: landing-clear hook entered for other object(s), but
    `s75_e1_hit` was still `0`.
  - Frame `203`: first `0xE1` active-mask clear latched.
  - The shadow oracle pass window is frames `75..179`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s75_exact_e1_landing_latch_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s75_exact_e1_landing_latch_contact.png`

Interpretation:

- For the selected ledge-spawned Igglybuff, landing cleanup removes the
  active-hop mask after the failing f075-f179 window. This rules out the
  landing normalizer as the cause of the midair shadow absence.
- The next cheap probe should hook `MapObject_ClearBits` globally, filtered to
  object ID `0xE1` and masks intersecting `0x00012004`, to prove whether any
  other clearer removes the active-hop mask inside the pass window. If no
  clearer appears in-window, the issue is below flag lifetime: native shadow
  render eligibility or terrain/logical-tile shadow state.

### S76 - Global `MapObject_ClearBits` Probe

Purpose:

- S76 checked whether any non-landing path clears the selected Igglybuff's
  active-hop-related bits during the harness pass window.
- This was instrumentation only, not a proposed visual fix.

Implementation notes:

- `armips/asm/fairy.s`
  - Temporarily patched `MapObject_ClearBits` at ARM9 address `0x0205F214`.
  - Inlined the stock `object->flags &= ~mask` behavior and logged calls for
    object ID `0xE1` when the clear mask intersected `0x00012004`.
  - Diagnostic words were stored at `0x02209B44..0x02209B5F`.
  - The overlay 149 landing hook from S75 was restored to stock before this
    probe.

Instrumented build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1564.nds`

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s76_global_clearbits_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s76_status:u32:0x02209B44 \
  --memory-read s76_match_count:u32:0x02209B48 \
  --memory-read s76_object:u32:0x02209B4C \
  --memory-read s76_mask:u32:0x02209B50 \
  --memory-read s76_lr:u32:0x02209B54 \
  --memory-read s76_pre_flags:u32:0x02209B58 \
  --memory-read s76_post_flags:u32:0x02209B5C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- Shadow oracle still failed:
  - `shadow_pass.passed`: `false`.
  - `tracked_percent`: `100`.
  - `present_frame_count`: `0` / `105`.
  - `max_missing_run`: `105`.
- Final memory reads:
  - `s76_status`: `0x00000003`.
  - `s76_match_count`: `888`.
  - `s76_object`: `0x022AEB1C`.
  - `s76_mask`: `0x00010004`.
  - `s76_lr`: `0x0205FE65`.
  - `s76_pre_flags`: `0x0000E825`.
  - `s76_post_flags`: `0x0000E821`.
- Sampled memory transition summary:
  - The matching clear count was already `156` at capture frame `0`.
  - The count increased by `208` inside the f075-f179 pass window.
  - The first latched caller was the stock movement cleanup path around
    `0x0205FE48`, which calls `MapObject_ClearBits(object, 0x00010004)`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s76_global_clearbits_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s76_global_clearbits_probe_contact.png`

Interpretation:

- Native active-hop flags are not stable during the midair pass window. The
  stock movement cleanup path repeatedly clears a mask that includes
  `BIT_MOVE_START | BIT_JUMP_START` while the selected Igglybuff is still in
  the harness window.
- This makes fixes that depend on `(flags & 0x00012004) == 0x00012004`
  fragile. The next implementation should use the owned canopy-long-jump shadow
  effect or an equivalent floor-shadow path whose lifetime is based on object
  identity plus long-hop state/arc liveness instead of those native active bits.

### S77 - Owned Field-Effect Shadow With Arc Lifetime

Purpose:

- S77 tested the owned canopy-long-jump field-effect shadow path again, but
  without depending on the unstable active-hop flag mask from S76.
- The effect lifetime was changed to object identity plus arc liveness
  (`faceVec[1] | unk88[1]`), and the effect was made per wild object ID
  (`0xE0..0xE9`) instead of a single global instance.

Implementation notes:

- `armips/asm/fairy.s`
  - Removed the temporary S76 global `MapObject_ClearBits` hook, helper, and
    diagnostic data.
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - Set `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` to `1`.
  - Kept overlay 149's call small: it only requests the behavior-data overlay
    shadow effect during the active long-hop update.
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
  - Added the field-effect descriptor, floor-shadow draw callback, and a
    10-slot effect pointer table keyed by wild object IDs.
  - The render path uses `object->posVec[1] + 0x20`, while the visible body arc
    remains in `faceVec[1]` / `unk88[1]`.
- `scripts/headless-overworld-shadow-harness.py`
  - Hardened Igglybuff target detection after the first S77 run selected flower
    pixels instead of the ledge-spawned body. The harness now uses a brighter
    palette-safe pink predicate and, for `--target-igglybuff ledge-spawn`, an
    initial ledge-band target pick. The same shadow pass window and
    time-of-day-safe shadow contrast rules were left unchanged.

Review:

- Implementation review found the single-instance effect risk; the follow-up
  converted the effect storage to per-object slots.
- Second review found no blocking code issue but called out the tiny overlay
  149 margin and required build/harness verification.

Build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1565.nds`
- Size checks:
  - `build/output_overworld_wild_spawns_overlay.bin`: `45028` / `45056`
    bytes, leaving `28` bytes.
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `1276` / `4096`
    bytes, leaving `2820` bytes.
  - `build/output.bin`: `31196` bytes.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_owned_effect_arc_lifetime_s77_target_fixed \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- `actual_left_hop_start_frame`: `27`.
- The corrected target detector selected the intended ledge-spawned Igglybuff:
  initial bbox `[105, 84, 118, 95]`.
- The shadow signal became strong in the old f075-f179 window, but the visual
  movement regressed:
  - S77 frame `75`: bbox `[73, 84, 84, 95]`, `shadow_present=true`.
  - Baseline S76 frame `75`: bbox `[56, 75, 67, 88]`.
  - Baseline S76 frame `100`: bbox `[32, 74, 43, 87]`.
  - Baseline S76 frame `150`: bbox `[11, 85, 22, 98]`.
- In S77 the Igglybuff visually stops around frame `39` instead of continuing
  left through the long-hop path. The angry/scared bubble remains visible above
  it, making the field-effect bridge a movement/lifecycle regression rather
  than a valid shadow fix.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_owned_effect_arc_lifetime_s77_target_fixed_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_owned_effect_arc_lifetime_s77_target_fixed_contact.png`
  - Regressed frame:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_owned_effect_arc_lifetime_s77_target_fixed_frames/igglybuff_shadow_owned_effect_arc_lifetime_s77_target_fixed_f075.png`
  - Baseline comparison frame:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s76_global_clearbits_probe_frames/igglybuff_shadow_s76_global_clearbits_probe_f075.png`

Interpretation:

- S77 proves that an owned field-effect shadow can make a terrain-independent
  dark mark visible, but the bridge is still unsafe for the long-hop movement
  lifecycle. This aligns with earlier S55/S58/S63/S64 history where the
  behavior-data field-effect bridge caused spawn/crash regressions.
- Reject this approach for now. The next attempt should disable/remove the
  field-effect bridge again and avoid creating `ov01_021F1620` effects during
  the canopy long-hop update.

### S78 - Preserve Native Start Bits In `MapObject_ClearBits` During Arc

Purpose:

- S78 tried to keep the stock shadow path alive without the unsafe field-effect
  bridge from S77.
- S76 showed that stock movement cleanup repeatedly clears `0x00010004`
  (`BIT_MOVE_START | BIT_JUMP_START`) while the custom long-hop arc is still
  active, so S78 hooked `MapObject_ClearBits` and restored those two bits for
  wild object IDs while `faceVec[1] | unk88[1]` was nonzero.

Implementation notes:

- `armips/asm/fairy.s`
  - Patched `MapObject_ClearBits` at `0x0205F214`.
  - The helper first reproduced stock behavior (`object->flags &= ~mask`).
  - If the object ID was in `0xE0..0xE9`, the clear mask intersected
    `0x00010004`, and `faceVec[1] | unk88[1]` was nonzero, it ORed
    `0x00010004` back into the stored flags.
  - The first review caught that the helper label started after a 21-byte table
    and needed alignment. A follow-up added `.align 2` before the helper.
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - Set `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` back to `0`.
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
  - Replaced the S77 field-effect implementation with no-op create/clear
    stubs so the behavior-data overlay entry layout remains valid without
    creating `ov01_021F1620` effects.

Build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1566.nds`
- Size checks:
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996` / `45056`
    bytes, leaving `60` bytes.
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `678` / `4096`
    bytes, leaving `3418` bytes.
  - `build/output.bin`: `31196` bytes.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s78_clearbits_preserve_arc \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `0`.
- `actual_left_hop_start_frame`: `27`.
- `shadow_pass.passed`: `true`.
- `shadow_pass.present_frame_count`: `105` / `105`.
- `shadow_pass.tracked_percent`: `100`.
- This is a false positive for gameplay correctness. The shadow oracle only
  checks the target body and shadow in frames f075-f179; it does not require the
  Pokemon to continue traveling left like the baseline.

Movement regression:

- Baseline S76 continued moving left:
  - f075 bbox `[56, 75, 67, 88]`.
  - f099 bbox `[32, 74, 43, 87]`.
  - f127 bbox `[11, 85, 22, 98]`.
- S78 stopped around the ledge:
  - f075 bbox `[72, 81, 83, 95]`.
  - f099 bbox `[72, 81, 83, 95]`.
  - f127 bbox `[72, 81, 83, 95]`.
  - f179 bbox `[72, 81, 83, 95]`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s78_clearbits_preserve_arc_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s78_clearbits_preserve_arc_contact.png`

Interpretation:

- S78 proves that restoring the stock start bits can make the native shadow
  path pass the shadow oracle, but keeping those bits alive globally changes
  the movement lifecycle and stalls the manual long-hop.
- Reject this state-scoped `MapObject_ClearBits` preservation. The next
  candidate should be draw/render-scoped: present the needed flags only while
  the stock draw/shadow path is consuming the object, then restore the original
  flags immediately so movement cleanup remains baseline-compatible.

### S79 - Draw-Scoped Native Start Bits At Primary Sprite Draw Call

Purpose:

- S79 tried the render-scoped version suggested after S78: avoid changing
  movement state globally, and instead expose the native start bits only while
  overlay 1's primary map-object draw path consumes the object.
- This was intended to preserve the stock shadow path without repeating S78's
  movement freeze.

Implementation notes:

- `armips/asm/overworlds.s`
  - Patched the overlay 1 primary draw callsite at `0x021F78FE` from stock
    `bl 0x021F8D80` to
    `bl OverworldWildSpawns_PrimaryDrawLongHopShadowWrapper`.
- `armips/asm/fairy.s`
  - Restored `MapObject_ClearBits` at `0x0205F214` to stock behavior so S78's
    state-scoped preservation is no longer active.
  - Added `OverworldWildSpawns_PrimaryDrawLongHopShadowWrapper` in ARM9 padding
    `0x02110258..0x021102A4`.
  - The wrapper checks wild object IDs `0xE0..0xE9` and treats
    `object->faceVec[1] | object->unk88[1]` as the long-hop-in-progress signal.
  - During that draw call only, it ORs `0x00010004` into `object->flags`, calls
    stock `0x021F8D80` with the original stack argument copied into the stock
    call's `[sp]` slot, then restores the exact original flag word.
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - Kept `OW_WILD_SPAWNER_CANOPY_LONG_JUMP_SHADOW_EFFECT_ENABLED` disabled.
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
  - Kept the behavior-data shadow-effect entry as no-op stubs.

Build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1567.nds`
- Size checks:
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996` / `45056`
    bytes, leaving `60` bytes.
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `678` / `4096`
    bytes, leaving `3418` bytes.
  - `build/output.bin`: `31196` bytes.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s79_draw_scoped_flags \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- `actual_left_hop_start_frame`: `27`.
- `target_origin`: bbox `[105, 84, 118, 95]`, `pixel_count` `75`.
- `shadow_pass.passed`: `false`.
- `shadow_pass.present_frame_count`: `0` / `105`.
- `shadow_pass.missing_shadow_frame_count`: `105`.
- `shadow_pass.tracked_percent`: `100`.
- Movement did not regress:
  - f075 bbox `[56, 75, 67, 89]`.
  - f099 bbox `[32, 74, 43, 88]`.
  - f127 bbox `[11, 85, 22, 99]`.
  - f179 bbox `[10, 84, 22, 98]`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s79_draw_scoped_flags_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s79_draw_scoped_flags_contact.png`

Interpretation:

- S79 confirms that the draw-scoped primary sprite call wrapper is movement-safe
  for this repro, unlike S78.
- It does not fix the midair shadow. The stock shadow decision for this bug is
  not controlled by exposing `0x00010004` only around the primary sprite draw
  call at `0x021F78FE`, or that call is not the shadow-consuming path.
- Reject this exact callsite-only approach. The next attempt should locate the
  lower native shadow draw/suppression gate or another draw callsite that
  actually owns the shadow, while keeping any state changes render-scoped and
  preserving the S79 movement behavior.

### S80 - Draw-Scoped Full Native Start Bits At Final Visibility Call

Purpose:

- S80 followed up on S79 by moving the render-scoped flag exposure to the final
  small-Pokemon visibility call, `0x021F7910 -> 0x021F8C88`, and using the full
  missing draw-time flag delta `0x00012004`.
- The hypothesis was that `0x021F8C88` was the consumer hiding the shadow or
  shadow-bearing sprite when the native movement bits were absent.

Implementation notes:

- `armips/asm/overworlds.s`
  - Replaced the original `0x021F78FE..0x021F7914` region with the same
    instruction sequence except the final `bl 0x021F8C88` now calls
    `OverworldWildSpawns_LongHopShadowVisibilityWrapper`.
  - The primary draw call `0x021F8D80`, final position call `0x021FA3E8`, and
    `strb r7, [r4, #16]` remain in their original order.
- `armips/asm/fairy.s`
  - Added `OverworldWildSpawns_LongHopShadowVisibilityWrapper` in ARM9 padding
    `0x02110258..0x021102A4`.
  - The wrapper checks wild object IDs `0xE0..0xE9`, treats
    `object->faceVec[1] | object->unk88[1]` as the long-hop-in-progress signal,
    ORs `0x00012004` into `object->flags` only while calling stock
    `0x021F8C88(object, primarySprite)`, then restores the exact original flag
    word.
  - After review, the stale S78/S79 `MapObject_ClearBits` stock-restoration hunk
    was removed so S80 no longer patches that global helper.
- `scripts/headless-overworld-shadow-harness.py`
  - Added an explicit `movement_pass` to prevent S78-style false positives.
  - The movement pass requires at least `90%` valid target tracking in
    f075-f179, at least `60` px leftward movement from the after-LEFT origin,
    and at least `24` px leftward movement within the pass window.
  - Shadow and movement failure suppression now use separate CLI flags:
    `--no-fail-on-shadow-pass` and `--no-fail-on-movement-pass`.

Review:

- Static review found the assembly layout sound: branch reach, Thumb encoding,
  stack balance, register preservation, mask construction, and exact flag
  restore were all acceptable.
- The reviewer recommended cleanup only: remove the stale
  `MapObject_ClearBits` hunk and tighten the harness movement-pass semantics.
  Both cleanup items were applied after the S80 harness run.

Build:

- Command route:
  `curl -sS -X POST http://127.0.0.1:8765/build -H 'Content-Type: application/json' -d '{"runAfter":true}'`
- Result: success; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1568.nds`
- Size checks:
  - `build/output_overworld_wild_spawns_overlay.bin`: `44996` / `45056`
    bytes, leaving `60` bytes.
  - `build/output_overworld_wild_behavior_data_overlay.bin`: `678` / `4096`
    bytes, leaving `3418` bytes.
  - `build/output.bin`: `31196` bytes.
- Built-byte sanity:
  - `0x021F7910` now branches to `0x02110258`.
  - The wrapper constructs `0x00012004` as `0x12 << 12` plus `4`, calls
    `0x021F8C88`, and restores the original flag word when it changed flags.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s80_visibility_fullmask \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- `actual_left_hop_start_frame`: `27`.
- `shadow_pass.passed`: `false`.
- `shadow_pass.present_frame_count`: `0` / `105`.
- `shadow_pass.tracked_percent`: `100`.
- `movement_pass.passed`: `true`.
- Movement details:
  - `origin_center_x`: `111`.
  - `first_window_center_x`: `61`.
  - `min_center_x`: `16`.
  - `origin_left_delta`: `95`.
  - `window_left_delta`: `45`.
  - f075 bbox `[56, 75, 67, 89]`.
  - f099 bbox `[32, 74, 43, 88]`.
  - f127 bbox `[11, 85, 22, 99]`.
  - f179 bbox `[10, 84, 22, 98]`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s80_visibility_fullmask_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s80_visibility_fullmask_contact.png`

Interpretation:

- S80 proves that render-scoped full `0x00012004` exposure at the final
  visibility call is safe for movement but still does not restore the midair
  floor shadow.
- `0x021F8C88` controls sprite visibility, not the missing floor shadow. The
  next attempt should stop targeting this visibility helper and instead locate
  the actual shadow sprite/draw creation path or the shadow tile/terrain
  suppression path.

### S81 - Preserve Only `BIT_JUMP_START` In `MapObject_ClearBits` During Arc

Purpose:

- S81 tested a smaller version of S78's state-scoped flag preservation.
- S78 restored both `BIT_MOVE_START | BIT_JUMP_START` and produced a shadow
  false positive by freezing/stalling the long hop. S81 restored only
  `BIT_JUMP_START` (`0x00010000`) for wild object IDs while the custom arc
  channels were active, leaving `BIT_MOVE_START` cleared by the stock movement
  lifecycle.

Implementation notes:

- `armips/asm/fairy.s`
  - Temporarily patched `MapObject_ClearBits` at ARM9 address `0x0205F214`.
  - The wrapper inlined stock behavior (`object->flags &= ~mask`).
  - If the clear mask included `0x00010000`, the object ID was in `0xE0..0xE9`,
    and `object->faceVec[1] | object->unk88[1]` was nonzero, the wrapper ORed
    `0x00010000` back into `object->flags`.
- This was intentionally narrower than S78 and did not touch overlay 149 or the
  overlay 1 draw callbacks.

Build:

- Two initial UI build attempts failed before assembly because Docker Desktop
  was wedged before container creation:
  `Docker produced no terminal output for 45s`.
- A direct `docker run` smoke probe also hung before any container appeared.
- Docker Desktop was restarted after its logs showed lifecycle-server failures
  and a `com.docker.virtualization: Process terminated unexpectedly` dialog.
- After restart, `docker run --rm hg-engine /bin/bash -lc 'echo docker-smoke-ok'`
  succeeded.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:30`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1569.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s81_clearbits_jump_only \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- `actual_left_hop_start_frame`: `27`.
- `shadow_pass.passed`: `false`.
- `shadow_pass.present_frame_count`: `0` / `105`.
- `shadow_pass.tracked_percent`: `100`.
- `shadow_pass.max_missing_run`: `105`.
- `movement_pass.passed`: `true`.
- Movement details:
  - `origin_center_x`: `111`.
  - `first_window_center_x`: `61`.
  - `min_center_x`: `16`.
  - `origin_left_delta`: `95`.
  - `window_left_delta`: `45`.
  - f075 bbox `[56, 75, 67, 89]`.
  - f099 bbox `[32, 74, 43, 88]`.
  - f179 bbox `[10, 84, 22, 98]`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s81_clearbits_jump_only_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s81_clearbits_jump_only_contact.png`

Interpretation:

- Preserving only `BIT_JUMP_START` avoids the S78 movement freeze, but it does
  not restore the midair shadow.
- This rejects the remaining cheap state-scoped `MapObject_ClearBits` flag
  preservation variant. Do not retry global clearbits preservation without new
  evidence.
- The next attempt should follow the lower shadow/secondary-render path
  identified around `0x021FA61C`, `0x021FA6E0`, and `0x021FA71C`, or identify a
  terrain-agnostic shadow draw/suppression gate directly.
- The temporary S81 hook was removed from source after this failed harness run.

### S82 - Lower Lifecycle Registration And Activation Probes

Purpose:

- S82 followed S81's rejection of movement-flag preservation by probing the
  lower overlay-1 lifecycle path around `0x021FA61C`, `0x021FA6E0`, and
  `0x021FA71C`.
- The goal was to determine whether the native lower shadow/secondary-resource
  layer is created, activated, deactivated, or toggled during the user-confirmed
  missing-shadow window, frames f075-f179.

#### S82a - Bad Entry Hook Placement

Implementation notes:

- Temporarily hooked `0x021FA61C` at the first instruction and branched through
  an ARM9 helper at `0x02110258`.
- The hook used `r4` before the stock function prologue saved it.

Build:

- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:34`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1570.nds`.
- Build emitted a padding-overlap warning for the diagnostic words because the
  shiny-helper padding area still filled through `0x02209B58`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s82_lower_lifecycle_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s82_entry_count:u32:0x02209B44 \
  --memory-read s82_mode0_count:u32:0x02209B48 \
  --memory-read s82_mode_nonzero_count:u32:0x02209B4C \
  --memory-read s82_last_key:u32:0x02209B50 \
  --memory-read s82_last_handle:u32:0x02209B54 \
  --memory-read s82_last_mode:u32:0x02209B58 \
  --memory-read s82_last_manager:u32:0x02209B5C
```

Harness result:

- Exit code: `2`.
- Ready and after-LEFT screenshots were fully black (`getbbox=None`).
- `target_origin`: `null`.
- `actual_left_hop_start_frame`: `null`.
- Final diagnostics showed one lower lifecycle entry hit, but the visual repro
  was invalid.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s82_lower_lifecycle_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s82_lower_lifecycle_probe_contact.png`

Interpretation:

- Reject S82a. Hooking before the callee saved `r4` clobbered caller state and
  invalidated the repro.

#### S82b - Registration Probe After The Stock Prologue

Implementation notes:

- Moved the `0x021FA61C` hook to `0x021FA620`, after the stock
  `push {r3,r4,r5,r6,lr}; sub sp,#4` prologue.
- The helper logged registration count, mode counts, last key, last handle,
  last mode, and last manager to `0x02209B44..0x02209B5F`.
- The shiny-helper padding fill was shortened to end at `0x02209B44`, removing
  the overlap warning.

Build:

- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:24`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1571.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s82b_lower_lifecycle_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s82_entry_count:u32:0x02209B44 \
  --memory-read s82_mode0_count:u32:0x02209B48 \
  --memory-read s82_mode_nonzero_count:u32:0x02209B4C \
  --memory-read s82_last_key:u32:0x02209B50 \
  --memory-read s82_last_handle:u32:0x02209B54 \
  --memory-read s82_last_mode:u32:0x02209B58 \
  --memory-read s82_last_manager:u32:0x02209B5C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- `shadow_pass.passed`: `false`.
- `shadow_pass.present_frame_count`: `0` / `105`.
- `shadow_pass.tracked_percent`: `100`.
- `movement_pass.passed`: `true`.
- Final diagnostics:
  - `s82_entry_count`: `9`.
  - `s82_mode0_count`: `0`.
  - `s82_mode_nonzero_count`: `9`.
  - `s82_last_key`: `658` (`0x292`, Igglybuff overworld tag).
  - `s82_last_handle`: `0x02384DA0`.
  - `s82_last_mode`: `1`.
  - `s82_last_manager`: `0x022ADEB0`.
- Sampled diagnostics:
  - Only one sampled value state, already present at capture frame `0`.
  - No registration count or value changed during frames `0..360`, including
    the f075-f179 failure window.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s82b_lower_lifecycle_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s82b_lower_lifecycle_probe_contact.png`

Interpretation:

- The lower registration path does create/register entries for key `658`, but
  that registration happens before the captured hop. It is not changing during
  the missing-shadow window.
- Registration alone is not the per-frame shadow suppression toggle.

#### S82c - Activation And Deactivation Probe

Implementation notes:

- Removed the registration hook and instead wrapped the inner lower lifecycle
  calls:
  - `0x021FA708 -> 0x020259E0` activation call.
  - `0x021FA742 -> 0x02025A48` deactivation call.
- Logged activation count, deactivation count, last activation key/handle, last
  deactivation key/handle, and last event to `0x02209B44..0x02209B5F`.

Build:

- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:29`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1572.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s82c_lower_activation_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s82_activation_count:u32:0x02209B44 \
  --memory-read s82_deactivation_count:u32:0x02209B48 \
  --memory-read s82_last_activation_key:u32:0x02209B4C \
  --memory-read s82_last_activation_handle:u32:0x02209B50 \
  --memory-read s82_last_deactivation_key:u32:0x02209B54 \
  --memory-read s82_last_deactivation_handle:u32:0x02209B58 \
  --memory-read s82_last_event:u32:0x02209B5C
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- `actual_left_hop_start_frame`: `27`.
- `shadow_pass.passed`: `false`.
- `shadow_pass.present_frame_count`: `0` / `105`.
- `shadow_pass.tracked_percent`: `100`.
- `movement_pass.passed`: `true`.
- Final diagnostics:
  - `s82_activation_count`: `9`.
  - `s82_deactivation_count`: `9`.
  - `s82_last_activation_key`: `658`.
  - `s82_last_activation_handle`: `0x02355E58`.
  - `s82_last_deactivation_key`: `658`.
  - `s82_last_deactivation_handle`: `0x02355E58`.
  - `s82_last_event`: `2` (deactivation).
- Sampled diagnostics:
  - Only one sampled value state, already present at capture frame `0`.
  - No activation or deactivation count changed during frames `0..360`,
    including the f075-f179 failure window.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s82c_lower_activation_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s82c_lower_activation_probe_contact.png`

Interpretation:

- The lower lifecycle queue activates and deactivates key `658` before the
  captured hop. It does not toggle during the actual missing-shadow window.
- This path appears to be resource/lifecycle setup, not the per-frame floor
  shadow visibility owner.
- Do not keep probing `0x021FA61C`, `0x021FA6E0`, or `0x021FA71C` unless a new
  correlation to the actual floor shadow is found.
- The next attempt should return to the per-object render data and native sprite
  shadow state around `0x021F8D80` / `0x02023F04`, but with diagnostics that
  compare the primary sprite's shadow state between a normal land jump and the
  grass-to-land long hop instead of only forcing flags.

#### Harness Repair - Strict Upper Ledge Target Selection

The ledge-spawn harness target selection was repaired after a read-only
explorer found that the current `ledge-spawn` mode could seed from the lower
false pink/terrain component at `[110, 163, 131, 185]`.

This invalidates the current S83 artifacts. The S83 primary-snapshot probe was
built and run while the harness still selected that lower component, so its
summaries have `actual_left_hop_start_frame=null`, failed movement, and no valid
evidence from the user-confirmed upper ledge hop. S83 must be rerun under the
strict upper ledge selector before any conclusions from it are used.

Implementation notes:

- `ledge-spawn` now seeds only from the upper ledge repro ROI, `x=70..145` and
  `y=70..115`.
- The seed is scored by ready-vs-after-left newly pink pixels so the object
  appearing after LEFT is preferred.
- If the upper ROI seed is missing, `target_selection.passed=false` and the
  harness exits with status `2`; it no longer falls back to a global/lower
  component.
- Continuity tracking for `ledge-spawn` is restricted to the upper hop band,
  `center_y <= 125`.
- The pink predicate was widened for the current light-pink overworld palette
  so the upper Igglybuff body is detected as `[105, 84, 118, 95]` again.

Verification command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_harness_repair_20260703 \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass
```

Harness result:

- Exit code: `0` with `--no-fail-on-shadow-pass`.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- `target_origin`: bbox `[105, 84, 118, 95]`, `new_pink_pixels`: `75`.
- `target_selection.passed`: `true`.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
- `shadow_pass.passed`: `false`, still matching the known midair shadow bug.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_harness_repair_20260703_summary.json`.
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_harness_repair_20260703_contact.png`.

### S84 - Full Small-Draw Scoped Native Flags

Purpose:

- S84 tests the smallest production version of the S78/S79/S80 flag idea after
  the ledge-spawn harness repair.
- Unlike S79 and S80, this wraps the full stock small-Pokemon draw callback
  entry (`0x021F7895`) instead of only the primary draw call or final visibility
  helper. The hypothesis is that an earlier or later part of the full callback
  consumes the native jump/move flags for floor-shadow setup.

Implementation plan:

- Patch only overlay 1 stock small-Pokemon draw callback entry
  `0x021F7894`.
- Use an ARM9 trampoline in the existing padding window
  `0x02110258..0x021102A4`.
- If the object ID is in the overworld wild range `0xE0..0xE9` and
  `faceVec[1] | unk88[1]` is nonzero, temporarily OR `0x00012004`
  (`BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13`) into
  `object->flags`, call the stock callback body, then restore the exact
  original flags.
- Do not touch `unk88`, `faceVec`, tile fields, gfx id, field effects, raw G3,
  secondary helpers, overlay 149, or movement code.

Expected result:

- If the full stock callback owns the missing floor-shadow decision, the
  repaired ledge-spawn harness should pass both movement and shadow checks.
- If the result matches S79/S80, movement should still pass and shadow should
  remain absent, proving the full small-Pokemon callback's temporary flags are
  not enough.

Build:

- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1578.nds`.
- Built-byte sanity:
  - `0x021F7894` now loads and branches to
    `OverworldWildSpawns_FullDrawScopedFlagsWrapper|1` (`0x02110259`).
  - The ARM9 wrapper at `0x02110258` checks wild object IDs, checks
    `faceVec[1] | unk88[1]`, builds `0x00012004`, calls the stock body
    trampoline, and restores the saved flag word.
  - The stock body trampoline copies the overwritten callback prologue and
    resumes at `0x021F789D`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s84_full_draw_scoped_flags \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- `target_origin`: bbox `[105, 84, 118, 95]`, `new_pink_pixels`: `75`.
- `target_selection.passed`: `true`.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - `origin_left_delta`: `95`.
  - `window_left_delta`: `45`.
  - `tracked_percent`: `100`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Visual inspection of the contact sheet matches the JSON: the upper
  ledge-spawn Igglybuff moves left correctly, but the accepted midair floor
  shadow core is absent throughout frames f075-f179.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s84_full_draw_scoped_flags_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s84_full_draw_scoped_flags_contact.png`

Interpretation:

- S84 is movement-safe but does not fix the midair floor shadow.
- A full stock small-Pokemon draw-callback scoped exposure of
  `BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13` is not enough to
  restore the missing floor shadow on the repaired ledge-spawn repro.
- Do not keep this patch for production; it should be reverted unless it is
  needed temporarily for follow-up instrumentation.

### S85 - Primary Draw Post-Stock Snapshot

Purpose:

- S85 is instrumentation-only, not a proposed visual fix.
- The pre-step rebuild refreshed `base/overlay/overlay_0001.bin` after S84 was
  reverted in source, so stale generated overlay bytes could not masquerade as
  current source behavior.
- The probe targets the selected upper ledge Igglybuff's primary draw call at
  `0x021F78FE -> 0x021F8D80` and records the post-stock state for object ID
  `0xE1` during the repaired harness window.

Pre-S85 baseline checks:

- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:34`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1579.nds`.
- Source spot check:
  - `armips/asm/overworlds.s`, `armips/asm/fairy.s`, and
    `armips/global.s` contain no S84 full-draw hook labels.
- Built-byte spot check:
  - `base/overlay/overlay_0001.bin` at `0x021F7894` starts with the stock
    small-draw prologue bytes `f8 b5 05 1c ...`, not the S84 trampoline.
  - `base/arm9.bin` at `0x02110258..0x021102A3` is back to `0xFF` fill.
  - `base/overlay/overlay_0001.bin` at `0x021F78FE` is stock
    `01 f0 3f fa`.

Implementation plan:

- Patch only overlay 1 primary draw callsite `0x021F78FE`:
  `bl 0x021F8D80` -> `bl OverworldWildSpawns_S85PrimaryDrawSnapshot`.
- Preserve the original behavior by copying the caller's stack argument into
  the stock call's `[sp]` slot, calling `0x021F8D81`, preserving the stock
  return value, and then logging post-stock state.
- Store diagnostic words in `0x02209B44..0x02209B5F`, shortening the existing
  overlay-1 tail fill so those words do not collide with the shiny helper.
- Use the known ARM9 padding windows for helper code:
  `0x02071C54..0x02071C9F` and `0x02110258..0x021102A3`.
- The requested internal hooks at `0x021F8E2E` and `0x021F8E3A` are deferred
  unless the primary snapshot leaves enough safe padding after assembly. The
  primary post-stock snapshot is the required minimum.

Diagnostic words:

- `0x02209B44 s85_status`
- `0x02209B48 s85_primary_entry_count`
- `0x02209B4C s85_e1_draw_count`
- `0x02209B50 s85_object_flags`
- `0x02209B54 s85_vertical_pack`
- `0x02209B58 s85_render_pack`
- `0x02209B5C s85_sprite_word_b8`

Status bits:

- `0x0001`: primary wrapper entered.
- `0x0002`: saw object ID `0xE1`.
- `0x0004`: post-stock flags include `0x00012004`.
- `0x0008`: primary sprite pointer nonzero.
- `0x0010`: `sub_02023F04(primarySprite, 0x1000)` observed for `0xE1`, if
  hooked.
- `0x0020`: terrain gate `0x021F8FC0` called for `0xE1`, if hooked.
- `0x0040`: terrain gate returned nonzero for `0xE1`, if hooked.
- `0x0080`: post-stock `renderData[0x15]` nonzero.
- `0x0100`: post-stock `renderData[0x17] & 1`.

Implementation result:

- Patched only the overlay 1 primary draw callsite at `0x021F78FE`.
- The wrapper called the stock `0x021F8D80` first, preserved behavior, then
  logged the post-stock state for object ID `0xE1`.
- Diagnostic words were stored at `0x02209B44..0x02209B5F`.
- The internal `0x021F8E2E -> 0x02023F04(sprite, 0x1000)` and
  `0x021F8E3A -> 0x021F8FC0(variant, object, sprite)` hooks were not added.
  The safe padding budget was consumed by the primary post-stock snapshot, so
  S85 leaves bits `0x0010`, `0x0020`, and `0x0040` clear by design.
- The first assembly pass overflowed the small ARM9 fairy padding area by four
  bytes. Removing the redundant saved-variant move kept the stock call state
  intact and let the diagnostic assemble.

Instrumented build:

- Built through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:28`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1580.nds`.
- Built-byte spot check:
  - `base/overlay/overlay_0001.bin` at `0x021F78FE` was patched to
    `7a f6 a9 f9`, a branch to the S85 wrapper at `0x02071C54`.
  - Diagnostic words at `0x02209B44..0x02209B5F` were zero-initialized before
    the harness.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s85_primary_terrain_snapshot \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s85_status:u32:0x02209B44 \
  --memory-read s85_primary_entry_count:u32:0x02209B48 \
  --memory-read s85_e1_draw_count:u32:0x02209B4C \
  --memory-read s85_object_flags:u32:0x02209B50 \
  --memory-read s85_vertical_pack:u32:0x02209B54 \
  --memory-read s85_render_pack:u32:0x02209B58 \
  --memory-read s85_sprite_word_b8:u32:0x02209B5C
```

Harness result:

- Exit code: `0` because `--no-fail-on-shadow-pass` was set.
- `target_selection.passed`: `true`.
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `27`.
- `contact_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `45`.
  - First window bboxes include f075 `[56,75,67,89]`,
    f077 `[54,74,65,89]`, f079 `[52,74,63,88]`.
  - Last window bboxes include f174-f175 `[11,85,22,99]` and
    f176-f179 `[10,84,22,98]`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s85_primary_terrain_snapshot_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s85_primary_terrain_snapshot_contact.png`

Final diagnostics:

- `s85_status`: `0x0000018B`.
  - Set: `0x0001` primary wrapper entered.
  - Set: `0x0002` object ID `0xE1` observed.
  - Set: `0x0008` primary sprite pointer was nonzero.
  - Set: `0x0080` post-stock `renderData[0x15]` was nonzero at least once.
  - Set: `0x0100` post-stock `renderData[0x17] & 1`.
  - Clear: `0x0004` full post-stock flag mask `0x00012004` was never present.
  - Clear by design: `0x0010`, `0x0020`, `0x0040`, because the internal hooks
    were not installed.
- `s85_primary_entry_count`: `0x000005B0` (`1456`).
- `s85_e1_draw_count`: `0x000001BA` (`442`).
- `s85_object_flags`: `0x0010C801`.
- `s85_vertical_pack`: `0x00000000`.
- `s85_render_pack`: `0x01000003`.
- `s85_sprite_word_b8`: `0x0004A000`.

Key f075-f179 sampled transitions:

- Counters advanced continuously in the repaired harness window:
  `s85_primary_entry_count` `526 -> 838` (`+312`) and
  `s85_e1_draw_count` `132 -> 236` (`+104`).
- `s85_status` stayed `0x0000018B` throughout f075-f179.
- Flag/render phases:
  - f075-f081: flags `0x00106003`, render pack `0x01000003`.
  - f082-f091: flags `0x00106001`, render pack `0x01010003`.
  - f092-f101: flags `0x00106001`, render pack `0x01000003`.
  - f102-f111: flags `0x00106001`, render pack `0x01010003`.
  - f114-f122: flags `0x0010E001`, render pack `0x01000003`.
  - f123-f132: flags `0x0010E001`, render pack `0x01010003`.
  - f133-f142: flags `0x0010E001`, render pack `0x01000003`.
  - f143-f152: flags `0x0010E001`, render pack `0x01010003`.
  - f153-f162: flags `0x0010E001`, render pack `0x01000003`.
  - f163-f172: flags `0x0010E001`, render pack `0x01010003`.
  - f173-f179: flags `0x0010E001`, render pack `0x01000003`.
- `renderData[0x15]` was nonzero in `50` frames in f075-f179, first at f082
  and last at f172.
- The flag word moved to `0x0010E001` at f114 and stayed there through f179,
  but it still never contained the full `0x00012004` mask.
- `s85_vertical_pack` ranged from `0x00000000` to `0xFC1FE000`; low 16 bits
  alternated between `0x0000` and `0xE000` in the sampled window.
- `s85_sprite_word_b8` ranged from `0x0003C000` to `0x0004F000`.

Interpretation:

- S85 proves the selected ledge-spawn Igglybuff reaches the primary draw path at
  `0x021F78FE -> 0x021F8D80`; the hook entered `1456` times and logged object
  ID `0xE1` `442` times.
- S85 also proves the primary sprite pointer was observed for that object; the
  continuously changing sampled sprite `+0xB8` value makes it likely the
  primary sprite stayed live through the failed shadow window, but the status
  bit itself is sticky and is not per-frame proof.
- The accepted midair floor shadow is still absent for every frame f075-f179
  even while the primary draw path is active and the body moves correctly.
- The full post-stock flag mask `0x00012004` is not present on object `0xE1` at
  the primary post-stock snapshot. That makes the missing mask a real observed
  state at this draw path, not stale S84 residue.
- Because the internal terrain/sprite helper hooks were skipped, S85 does not
  prove whether `0x02023F04(sprite, 0x1000)` or `0x021F8FC0` is called for E1.

Restoration:

- Removed the temporary `0x021F78FE` hook, the `0x02209B44..0x02209B5F`
  diagnostic words, and the split ARM9 helper chunks after the harness run.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:34`; UI opened `test.nds`.
- Copied clean ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1581.nds`.
- Clean built-byte spot checks:
  - `base/overlay/overlay_0001.bin` at `0x021F78FE` is back to stock
    `01 f0 3f fa`.
  - `base/overlay/overlay_0001.bin` at `0x021F7894` starts with the stock
    small-draw prologue bytes `f8 b5 05 1c ...`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B57` is back to
    `0xFF` tail fill.
  - `base/arm9.bin` at `0x02071C54..0x02071C9F`,
    `0x02110258..0x021102A3`, `0x021102D4..0x021102F7`, and
    `0x021103A0..0x021103B7` is back to fill/non-S85 data.

### S86 - Internal Terrain Gate Return Probe

Purpose:

- S86 is instrumentation-only, not a proposed visual fix.
- S85 proved the selected upper ledge-spawn Igglybuff reaches primary draw with
  movement passing and shadow failing, but did not hook the internal terrain
  gate because the earlier probe used the safe padding budget.
- This probe wraps only the stock primary draw internal call
  `0x021F8E3A -> 0x021F8FC0(variant, object, sprite)` and records whether that
  call happens for object ID `0xE1`, plus whether stock returns zero or nonzero.

Implementation plan:

- Patch only overlay 1 callsite `0x021F8E3A`:
  `bl 0x021F8FC0` -> `bl OverworldWildSpawns_S86TerrainGateProbe`.
- The wrapper preserves the stock call state, calls the stock Thumb entry
  `0x021F8FC1`, and returns exactly the stock return value to the caller.
- Log only when `object->id == 0xE1`.
- Do not add renderData plumbing at this internal callsite; record
  `object->flags` and `sprite + 0xB8` as the cheap auxiliary state.
- Store diagnostic words in `0x02209B44..0x02209B5F`, shortening the existing
  overlay-1 tail fill only for the diagnostic run.

Diagnostic words:

- `0x02209B44 s86_status`
- `0x02209B48 s86_gate_call_count`
- `0x02209B4C s86_return_zero_count`
- `0x02209B50 s86_return_nonzero_count`
- `0x02209B54 s86_last_flags`
- `0x02209B58 s86_last_aux`
- `0x02209B5C s86_last_variant_return`

Status bits:

- `0x0001`: wrapper entered for object ID `0xE1`.
- `0x0002`: saw object ID `0xE1`.
- `0x0004`: stock returned zero for object ID `0xE1`.
- `0x0008`: stock returned nonzero for object ID `0xE1`.

Packing notes:

- `s86_last_aux` stores `sprite + 0xB8`, or `0` if the sprite pointer is null.
- `s86_last_variant_return` packs low byte `variant`, next byte stock return.

Planned harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s86_terrain_gate_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s86_status:u32:0x02209B44 \
  --memory-read s86_gate_call_count:u32:0x02209B48 \
  --memory-read s86_return_zero_count:u32:0x02209B4C \
  --memory-read s86_return_nonzero_count:u32:0x02209B50 \
  --memory-read s86_last_flags:u32:0x02209B54 \
  --memory-read s86_last_aux:u32:0x02209B58 \
  --memory-read s86_last_variant_return:u32:0x02209B5C
```

Implementation result:

- Patched only the overlay 1 internal terrain-gate callsite at `0x021F8E3A`.
- The corrected diagnostic callsite built as `17 f7 4b fa`, a branch to the
  wrapper at `0x021102D4`.
- The wrapper saved `variant`, `object`, and `sprite`, called stock
  `0x021F8FC0` / Thumb `0x021F8FC1`, logged only object ID `0xE1`, restored the
  stock return value into `r0`, and returned to the stock caller.
- The logger occupied existing ARM9 helper padding at
  `0x02110258..0x02110297`; the remaining bytes through `0x021102A3` were
  padding headroom.
- Diagnostic words at `0x02209B44..0x02209B5F` were zero-initialized before
  the harness.
- The first instrumented run copied `test1585.nds` and proved the hook was
  active, but exposed a diagnostic bug: return counts advanced while
  `s86_gate_call_count` stayed `0`. That run is superseded by the counter-fixed
  run below.

Instrumented build:

- Built through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:25`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1586.nds`.

Harness result:

- Exit code: `0` because `--no-fail-on-shadow-pass` was set.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- `target_selection.passed`: `true`.
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `45`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s86_terrain_gate_probe_counterfix_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s86_terrain_gate_probe_counterfix_contact.png`

Final diagnostics:

- `s86_status`: `0x0000000F`.
  - Set: wrapper entered for object ID `0xE1`.
  - Set: object ID `0xE1` observed.
  - Set: stock returned nonzero for object ID `0xE1`.
  - Set: stock returned zero for object ID `0xE1`.
- `s86_gate_call_count`: `0x000001A8` (`424`).
- `s86_return_zero_count`: `0x000000D7` (`215`).
- `s86_return_nonzero_count`: `0x000000D1` (`209`).
- `s86_last_flags`: `0x0010C801`.
- `s86_last_aux` (`sprite + 0xB8`): `0x0004A000`.
- `s86_last_variant_return`: `0x00000003`.

Key f075-f179 sampled transitions:

- The terrain-gate call was active throughout the missing-shadow window:
  `s86_gate_call_count` `116 -> 220` (`+104`).
- Both return paths happened while the accepted floor shadow was absent:
  `s86_return_zero_count` `61 -> 114` (`+53`) and
  `s86_return_nonzero_count` `55 -> 106` (`+51`).
- `s86_status` stayed `0x0000000F` throughout f075-f179.
- `s86_last_flags` values in the window were `0x00106003`,
  `0x00106001`, and `0x0010E001`.
- `s86_last_variant_return` values in the window were `0x00000003`
  (variant `3`, return `0`) and `0x00000103` (variant `3`, return `1`).

Interpretation:

- S86 proves the selected ledge-spawn Igglybuff reaches the internal
  `0x021F8E3A -> 0x021F8FC0` terrain gate during the same f075-f179 frames
  where movement passes and the accepted floor shadow is missing.
- The terrain gate is not simply skipped for object ID `0xE1`; it returns both
  zero and nonzero during the missing-shadow window.
- Because the shadow still fails `0` / `105` while nonzero returns occur, S86
  rules out only this single primary-draw internal terrain-gate return as the
  floor-shadow visibility owner. It does not rule out broader terrain-derived
  state, tile sampling, auxiliary/shadow sprite setup, or another lower shadow
  owner.

Restoration:

- Removed the temporary `0x021F8E3A` hook, the `0x02209B44..0x02209B5F`
  diagnostic words, and the temporary ARM9 wrapper/logger chunks.
- `armips/asm/overworlds.s` and `armips/asm/fairy.s` are clean of S86 hook
  labels after cleanup.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:29`; UI opened `test.nds`.
- Copied clean ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1587.nds`.
- Clean built-byte spot checks:
  - `base/overlay/overlay_0001.bin` at `0x021F8E3A` is back to stock
    `00 f0 c1 f8`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B57` is back to
    `0xFF` tail fill; `0x02209B58..0x02209B5F` is back to the original zero
    bytes.
  - `base/arm9.bin` at `0x02110258..0x02110297` is back to `0xFF` fill.
  - `base/arm9.bin` at `0x021102D4..0x021102F7` is back to the original fill
    and nearby non-S86 literal data.

### S87 - Primary Depth Helper State Probe

Purpose:

- S87 is instrumentation-only, not a proposed visual fix.
- S86 proved the selected ledge-spawn Igglybuff reaches the internal terrain
  gate during the missing-shadow window, but the floor shadow still fails.
- This probe wraps only the stock primary draw depth/state helper call
  `0x021F8E2E -> 0x02023F04(sprite, 0x1000)` to test whether the helper is
  reached for object ID `0xE1`, whether `sprite + 0xB8` changes across it, and
  whether object flags gain or lose the full `0x00012004` mask.

Implementation plan:

- Patch overlay 1 callsite `0x021F8E2E`, stock bytes `2B F6 69 F8`
  (`bl 0x02023F04`), to call an ARM9 Thumb wrapper.
- At that callsite: `r0 = primarySprite`, `r1 = 0x1000`, and
  `r5 = LocalMapObject *object`.
- The wrapper must preserve stock behavior: call stock `0x02023F05` with the
  original `r0/r1`, return normally, and preserve caller-expected registers
  even though the stock return value is ignored.
- Filter and log only when `[r5,#8] == 0xE1`.
- Store diagnostic words in `0x02209B44..0x02209B5F`, shortening the existing
  overlay-1 tail fill only for the diagnostic run. Do not place helper code in
  these diagnostic data words.

Diagnostic words:

- `0x02209B44 s87_status`
- `0x02209B48 s87_e1_depth_call_count`
- `0x02209B4C s87_sprite_ptr`
- `0x02209B50 s87_flags_before`
- `0x02209B54 s87_flags_after`
- `0x02209B58 s87_sprite_b8_before`
- `0x02209B5C s87_sprite_b8_after`

Status bits:

- `0x0001`: E1 wrapper logged.
- `0x0002`: depth `r1` was `0x1000`.
- `0x0004`: primarySprite non-null.
- `0x0008`: sprite `+0xB8` changed across stock call.
- `0x0010`: sprite `+0xB8` after equals `0x1000`.
- `0x0020`: object flags changed across stock call.
- `0x0040`: `flags_before` had `0x00012004`.
- `0x0080`: `flags_after` had `0x00012004`.

Planned harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s87_depth_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s87_status:u32:0x02209B44 \
  --memory-read s87_e1_depth_call_count:u32:0x02209B48 \
  --memory-read s87_sprite_ptr:u32:0x02209B4C \
  --memory-read s87_flags_before:u32:0x02209B50 \
  --memory-read s87_flags_after:u32:0x02209B54 \
  --memory-read s87_sprite_b8_before:u32:0x02209B58 \
  --memory-read s87_sprite_b8_after:u32:0x02209B5C
```

Implementation and build notes:

- Added a temporary overlay-1 hook at `0x021F8E2E`, replacing stock bytes
  `2B F6 69 F8` with a call to an ARM9 Thumb wrapper.
- The wrapper preserved stock behavior by calling `0x02023F04` with the
  original `r0/r1`, then returning normally. Logging was filtered to object ID
  `0xE1` via `[r5,#8]`.
- Diagnostic words were stored at `0x02209B44..0x02209B5F`; no helper code was
  placed in that diagnostic-data range.
- The first instrumented build failed because a direct branch from
  `0x021102D4` to `0x02108FC8` was out of range. The probe was adjusted to use
  a Thumb literal-loaded `bx` into the store helper.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:26`; UI opened `test.nds`.
- Copied instrumented ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1588.nds`.

Instrumented built-byte spot checks:

- `base/overlay/overlay_0001.bin` at `0x021F8E2E` was patched away from stock
  `2B F6 69 F8`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.
- ARM9 helper code was placed in padding at `0x02071C54..`, `0x02110258..`,
  `0x021102D4..`, and `0x02108FC8..`.

Harness result:

- Command: the planned `igglybuff_shadow_s87_depth_probe` harness command
  above.
- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- `target_selection.passed`: `true`.
  - Target bbox: `[105,84,118,95]`; center: `[111,89]`.
  - `new_pink_pixels`: `75`.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `45`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s87_depth_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s87_depth_probe_contact.png`

Final diagnostics:

- `s87_status`: `0x0000000F`.
  - Set: E1 wrapper logged.
  - Set: depth `r1` was `0x1000`.
  - Set: primarySprite was non-null.
  - Set: sprite `+0xB8` changed across the stock call.
  - Clear: sprite `+0xB8` after equals literal `0x1000`.
  - Clear: object flags changed across the stock call.
  - Clear: `flags_before` had full mask `0x00012004`.
  - Clear: `flags_after` had full mask `0x00012004`.
- `s87_e1_depth_call_count`: `0x000001A8` (`424`).
- `s87_sprite_ptr`: `0x0234A0DC`.
- `s87_flags_before`: `0x0010C801`.
- `s87_flags_after`: `0x0010C801`.
- `s87_sprite_b8_before`: `0x00049000`.
- `s87_sprite_b8_after`: `0x0004A000`.

Key f075-f179 sampled transitions:

- `s87_status` stayed `0x0000000F`.
- `s87_e1_depth_call_count` went from `0x00000074` to `0x000000DC`
  (`116 -> 220`, `+104`) during the missing-shadow window.
- `s87_sprite_ptr` stayed `0x0234A0DC`.
- `s87_flags_before` and `s87_flags_after` were identical at every sampled
  call. Values seen in the window included:
  - f075: `0x00106003`.
  - f082: `0x00106001`.
  - f114: `0x0010E001`.
  - f179: `0x0010E001`.
- `s87_sprite_b8_before` cycled in `0x1000` steps through
  `0x0003C000..0x0004F000`, wrapping back to `0x0003C000` at f114.
- `s87_sprite_b8_after` was consistently one `0x1000` step ahead of the
  before value at the sampled calls, for example f075
  `0x0003C000 -> 0x0003D000`, f112 `0x0004F000 -> 0x0003C000`, and f179
  `0x00048000 -> 0x00049000`.

Interpretation:

- S87 proves the selected object ID `0xE1` reaches the exact primary depth
  helper call `0x021F8E2E -> 0x02023F04(sprite, 0x1000)` during the same
  f075-f179 window where movement passes and the accepted floor shadow is
  missing.
- The helper receives depth `0x1000`, receives a live primary sprite, and
  mutates sprite `+0xB8` across the stock call.
- The resulting sprite `+0xB8` values are large cycling values, not literal
  `0x1000`, so status bit `0x0010` correctly remains clear.
- Object flags do not change across this stock helper call, and neither the
  before nor after flags contain the full `0x00012004` mask.
- Therefore the missing midair floor shadow is not caused by skipping this
  helper or passing the wrong depth constant into this helper. The next probe
  should move downstream toward the actual shadow/OAM owner after
  `sub_02023F04`, rather than continuing to chase this `0x1000` call or object
  flags alone.

Restoration:

- Removed the temporary `0x021F8E2E` hook, the `0x02209B44..0x02209B5F`
  diagnostic words, and the temporary ARM9 wrapper/logger chunks.
- `armips/asm/overworlds.s` and `armips/asm/fairy.s` are clean of S87 hook
  labels after cleanup.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:41`; UI opened `test.nds`.
- Copied clean ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1589.nds`.
- Clean built-byte spot checks:
  - `base/overlay/overlay_0001.bin` at `0x021F8E2E` is back to stock
    `2B F6 69 F8`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B57` is back to
    `0xFF` tail fill; `0x02209B58..0x02209B5F` is back to the original zero
    bytes.
  - `base/arm9.bin` at `0x02071C54..0x02071C9F`,
    `0x02110258..0x021102A3`, `0x021102D4..0x021102F7`, and
    `0x02108FC8..0x02108FE8` is back to `0xFF` fill.

### S88 - Final Vector Writeback Probe

Purpose:

- S88 is instrumentation-only, not a proposed visual fix.
- S86 proved object `0xE1` reaches
  `0x021F8E3A -> 0x021F8FC0` during the missing-shadow window, but that
  terrain gate alone is not sufficient for the floor shadow.
- S87 proved object `0xE1` reaches
  `0x021F8E2E -> 0x02023F04(sprite, 0x1000)` and `sprite + 0xB8` mutates, but
  that depth helper alone is not sufficient for the floor shadow.
- This probe moves one step downstream to the final vector writeback call
  `0x021F8E68 -> 0x0205F97C(object, &finalVec)`.

Implementation plan:

- Patch overlay 1 callsite `0x021F8E68`, stock bytes `66 F6 88 FD`
  (`bl 0x0205F97C`), to call an ARM9 Thumb wrapper.
- At the callsite, expected state is:
  - `r0 = object`.
  - `r1 = &finalVec` / `sp+8`.
  - `r4 = renderData`.
  - `r5 = object`.
  - `r6 = variant`.
  - `r7 = sub_0205F888(object)` result.
  - `[sp] = primarySprite`.
  - `[sp+4] = 0x021F9344(object)` result.
  - `[sp+8..0x10] = final vec x/y/z`.
- The wrapper preserves stock behavior by calling stock Thumb
  `0x0205F97D` with the original `r0/r1`, returning normally, and preserving
  caller-expected `r4-r7`.
- Log only when `[r5,#8] == 0xE1`.
- Store exactly seven diagnostic words at `0x02209B44..0x02209B5F`. Do not put
  code in these diagnostic-data words.

Diagnostic words:

- `0x02209B44 s88_status`
- `0x02209B48 s88_e1_writeback_count`
- `0x02209B4C s88_sprite_ptr` (`[sp]` at wrapper entry)
- `0x02209B50 s88_flags` (`object->flags`)
- `0x02209B54 s88_final_vec_y` (`[finalVec + 4]` before stock call)
- `0x02209B58 s88_render_pack`
- `0x02209B5C s88_sprite_b8` (`primarySprite + 0xB8`, or `0` if null)

Status bits:

- `0x0001`: wrapper entered for object ID `0xE1`.
- `0x0002`: saw object ID `0xE1`.
- `0x0004`: sprite pointer non-null.
- `0x0008`: `r7 != 0`.
- `0x0010`: special predicate `[sp+4]` nonzero.
- `0x0020`: `renderData[0x15]` nonzero.
- `0x0040`: `renderData[0x17] & 1`.
- `0x0080`: final vec.y nonzero.

Packing notes:

- `s88_render_pack` packs `renderData[0x15]` in bits `0..7` and
  `renderData[0x17]` in bits `8..15`; upper bits remain zero.

Planned harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s88_final_vec_writeback_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s88_status:u32:0x02209B44 \
  --memory-read s88_e1_writeback_count:u32:0x02209B48 \
  --memory-read s88_sprite_ptr:u32:0x02209B4C \
  --memory-read s88_flags:u32:0x02209B50 \
  --memory-read s88_final_vec_y:u32:0x02209B54 \
  --memory-read s88_render_pack:u32:0x02209B58 \
  --memory-read s88_sprite_b8:u32:0x02209B5C
```

Implementation and build notes:

- Added a temporary overlay-1 hook at `0x021F8E68`, replacing stock bytes
  `66 F6 88 FD` with a call to an ARM9 Thumb wrapper.
- The wrapper preserved stock behavior by calling `0x0205F97C` with the
  original `r0/r1`, then returning normally. Logging was filtered to object ID
  `0xE1` via `[r5,#8]`, and the wrapper/log preserved `r4-r7`.
- Diagnostic words were stored at `0x02209B44..0x02209B5F`; no helper code was
  placed in that diagnostic-data range.
- `s88_render_pack` uses byte 0 for `renderData[0x15]` and byte 1 for
  `renderData[0x17]`.
- Helper code occupied existing ARM9 padding at `0x02071C54..0x02071C73`,
  `0x02110258..0x0211028F`, `0x021102D4..0x021102EF`, and
  `0x021103A0..0x021103B1`.

Instrumented build:

- Built through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
- Copied instrumented ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1590.nds`.

Instrumented built-byte spot checks:

- `base/overlay/overlay_0001.bin` at `0x021F8E68` was patched from stock
  `66 f6 88 fd` to `78 f6 f4 fe`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.
- ARM9 helper code was present only in the planned helper pads listed above.

Harness result:

- Command: the planned `igglybuff_shadow_s88_final_vec_writeback_probe`
  harness command above.
- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- `target_selection.passed`: `true`.
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `45`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s88_final_vec_writeback_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s88_final_vec_writeback_probe_contact.png`

Final diagnostics:

- `s88_status`: `0x00000047`.
  - Set: wrapper entered for object ID `0xE1`.
  - Set: object ID `0xE1` observed.
  - Set: primary sprite pointer non-null.
  - Clear: `r7 != 0`.
  - Clear: special predicate `[sp+4]` nonzero.
  - Clear in the final read: `renderData[0x15]` nonzero.
  - Set: `renderData[0x17] & 1`.
  - Clear in the final read: final vec.y nonzero.
- `s88_e1_writeback_count`: `0x000001BA` (`442`).
- `s88_sprite_ptr`: `0x0234A11C`.
- `s88_flags`: `0x0010C801`.
- `s88_final_vec_y`: `0x00000000`.
- `s88_render_pack`: `0x00000100`
  (`renderData[0x15] = 0x00`, `renderData[0x17] = 0x01`).
- `s88_sprite_b8`: `0x0004A000`.

Key f075-f179 sampled transitions:

- The final-vector writeback call was active throughout the missing-shadow
  window: `s88_e1_writeback_count` `132 -> 236` (`+104`).
- `s88_status` alternated between `0x00000047` and `0x000000E7`.
  - The common bits prove E1 entry, E1 observation, non-null sprite, and
    `renderData[0x17] & 1`.
  - The `0x000000E7` frames additionally had `renderData[0x15] != 0` and
    `finalVec.y != 0`.
  - `r7 != 0` and special predicate `[sp+4] != 0` stayed clear in the sampled
    window.
- `s88_sprite_ptr` stayed `0x0234A11C`.
- `s88_flags` values in the window were `0x00106003`, `0x00106001`, and
  `0x0010E001`.
- `s88_final_vec_y` toggled between `0x00000000` and `0xFFFFE000`.
- `s88_render_pack` toggled with final vec.y:
  - `0x00000100`: `renderData[0x15] = 0`, `renderData[0x17] = 1`.
  - `0x00000101`: `renderData[0x15] = 1`, `renderData[0x17] = 1`.
- `s88_sprite_b8` cycled through `0x0003C000..0x0004F000` in `0x1000`
  steps; f075 was `0x0003D000`, f179 was `0x00049000`.

Interpretation:

- S88 proves the selected object ID `0xE1` reaches the final vector writeback
  call `0x021F8E68 -> 0x0205F97C(object, &finalVec)` during the same
  f075-f179 window where movement passes and the accepted floor shadow is
  missing.
- The writeback receives a live primary sprite and writes while
  `renderData[0x17] & 1` is set. `renderData[0x15]` and final vec.y toggle
  together, so the callsite sees both grounded-looking and lifted final-vector
  states during the missing-shadow window.
- Because the shadow still fails `0` / `105` while this writeback is active,
  the missing floor shadow is not explained by skipping the final vector
  writeback. The next probe should move farther downstream into the sprite/OAM
  or shadow-owner phase after `0x0205F97C` consumes the final vector.

Restoration:

- Removed the temporary `0x021F8E68` hook, the `0x02209B44..0x02209B5F`
  diagnostic words, and the temporary ARM9 wrapper/logger chunks.
- `armips/asm/overworlds.s` and `armips/asm/fairy.s` are clean of S88 hook
  labels after cleanup.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:25`; UI opened `test.nds`.
- Copied clean ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1591.nds`.
- Clean built-byte spot checks:
  - `base/overlay/overlay_0001.bin` at `0x021F8E68` is back to stock
    `66 f6 88 fd`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B57` is back to
    `0xFF` tail fill; `0x02209B58..0x02209B5F` is back to the original zero
    bytes.
  - `base/arm9.bin` at `0x02071C54..0x02071C9F`,
    `0x02110258..0x021102A3`, `0x021102D4..0x021102F7`, and
    `0x021103A0..0x021103B7` is back to fill/non-S88 data.

### S89 - Type-3 Sprite Actor Commit Probe

Purpose:

- S89 is instrumentation-only, not a proposed visual fix.
- S86/S87/S88 proved object `0xE1` reaches overlay primary draw internals,
  the primary depth helper, and final vector writeback during f075-f179 while
  the accepted floor shadow still fails.
- This probe moves materially later into the ARM9 sprite actor/OAM-ish commit
  path by wrapping the type-3 call `0x02023998 -> 0x02023FEC(sprite)`.

Implementation plan:

- Patch ARM9 callsite `0x02023998`, stock bytes `00 F0 28 FB`
  (`bl 0x02023FEC`), to call a Thumb wrapper.
- At the callsite, expected state is:
  - `r0 = r4 = sprite/actor pointer`.
  - `[r4 + 0x24] == 1` active actor gate already passed.
  - `[r4 + 0xB4] == 3` state gate selects `0x02023FEC`.
  - `[r4 + 0x1C]` callback/user arg; likely owner/context candidate, not
    guaranteed.
  - `[r4 + 0xB6]` and `[r4 + 0xB8]` are sprite state consumed by
    `0x02023FEC`.
  - `r5` and `r6` are live in the caller, so preserve `r4-r6/lr`.
- The wrapper preserves stock behavior by calling stock Thumb
  `0x02023FED` with the original `r0`, then returning normally.
- Count all type-3 commits, and separately count commits where
  `[sprite + 0x1C]` looks like a main-RAM pointer and `[owner_arg + 8] ==
  0xE1`. If the owner arg is not safely usable, leave the owner ID pack byte
  as zero rather than faking an `E1` match.
- Store exactly seven diagnostic words at `0x02209B44..0x02209B5F`,
  shortening the existing overlay-1 tail fill only for the diagnostic run.
  Do not place helper code in those diagnostic-data words.

Diagnostic words:

- `0x02209B44 s89_status`
- `0x02209B48 s89_type3_commit_count`
- `0x02209B4C s89_e1_commit_count`
- `0x02209B50 s89_last_sprite_ptr`
- `0x02209B54 s89_last_owner_arg`
- `0x02209B58 s89_last_sprite_b8`
- `0x02209B5C s89_last_pack`

Status bits:

- `0x0001`: wrapper entered.
- `0x0002`: stock `0x02023FEC` called.
- `0x0004`: `[sprite + 0x1C]` looked like main RAM.
- `0x0008`: `owner_arg->id == 0xE1`.
- `0x0010`: `sprite + 0xB4 == 3`.
- `0x0020`: `sprite + 0xB8` nonzero.
- `0x0040`: `sprite + 0xB8` in observed `0x0003C000..0x0004F000` band.

Packing notes:

- `s89_last_pack` packs `sprite[0xB4]` in bits `0..7`,
  `sprite[0xB6]` in bits `8..23`, and `owner_arg->id` in bits `24..31` if
  safely readable; otherwise the owner-ID byte remains zero.

Planned harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s89_oam_commit_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s89_status:u32:0x02209B44 \
  --memory-read s89_type3_commit_count:u32:0x02209B48 \
  --memory-read s89_e1_commit_count:u32:0x02209B4C \
  --memory-read s89_last_sprite_ptr:u32:0x02209B50 \
  --memory-read s89_last_owner_arg:u32:0x02209B54 \
  --memory-read s89_last_sprite_b8:u32:0x02209B58 \
  --memory-read s89_last_pack:u32:0x02209B5C
```

Implementation and build notes:

- Added a temporary ARM9 hook at `0x02023998`, replacing stock bytes
  `00 f0 28 fb` with a call to a Thumb wrapper at `0x02071C54`.
- The wrapper preserved stock behavior by logging with the original sprite
  pointer, restoring the caller's original `r5/r6` before the stock call, then
  calling `0x02023FEC` and returning normally.
- Diagnostic words were stored at `0x02209B44..0x02209B5F`; no helper code was
  placed in the diagnostic-data range.
- Helper code occupied existing ARM9 padding at `0x02071C54..0x02071C67`,
  `0x02110258..0x02110297`, `0x021102D4..0x021102F3`, and
  `0x021103A0..0x021103B5`.
- Built through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
- Copied instrumented ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1592.nds`.

Instrumented built-byte spot checks:

- `base/arm9.bin` at `0x02023998` changed from stock `00 f0 28 fb` to
  `4e f0 5c f9`, a branch to the S89 wrapper at `0x02071C54`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.
- ARM9 helper code was present only in the planned helper pads listed above.

Harness result:

- Command: the planned `igglybuff_shadow_s89_oam_commit_probe` harness command
  above.
- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- `target_selection.passed`: `true`.
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `45`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s89_oam_commit_probe_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s89_oam_commit_probe_contact.png`

Final diagnostics:

- `s89_status`: `0x00000073`.
  - Set: wrapper entered.
  - Set: stock `0x02023FEC` called.
  - Clear: `[sprite + 0x1C]` looked like main RAM.
  - Clear: `owner_arg->id == 0xE1`.
  - Set: `sprite + 0xB4 == 3`.
  - Set: `sprite + 0xB8` nonzero.
  - Set: `sprite + 0xB8` in observed `0x0003C000..0x0004F000` band.
- `s89_type3_commit_count`: `0x00000EEF` (`3823`).
- `s89_e1_commit_count`: `0x00000000` (`0`).
- `s89_last_sprite_ptr`: `0x0234A17C`.
- `s89_last_owner_arg`: `0x00000000`.
- `s89_last_sprite_b8`: `0x00049000`.
- `s89_last_pack`: `0x00000303`
  (`sprite[0xB4] = 3`, `sprite[0xB6] = 3`, owner ID byte `0`).

Key f075-f179 sampled transitions:

- The ARM9 type-3 commit path was active throughout the missing-shadow window:
  `s89_type3_commit_count` `1554 -> 2381` (`+827`).
- `s89_e1_commit_count` stayed `0` throughout the window.
- `s89_status` stayed `0x00000073` throughout the window.
- `s89_last_owner_arg` stayed `0x00000000`; status bit `0x0004` never set, so
  `[sprite + 0x1C]` was not a usable main-RAM owner pointer for this path.
- `s89_last_sprite_ptr` cycled among multiple type-3 sprite actors in the
  window: `0x02349C20`, `0x02349CE4`, `0x02349E6C`, `0x02349F30`,
  `0x02349FF4`, `0x0234A0B8`, and `0x0234A17C`.
- `s89_last_pack` values in the window were `0x00000003`, `0x00000203`, and
  `0x00000303`; the owner-ID byte remained zero.
- `s89_last_sprite_b8` included the familiar observed band
  `0x0003C000..0x0004F000`, for example f076 `0x0003D000`, f112
  `0x0004F000`, f114 `0x0003C000`, and f179 `0x00048000`.

Interpretation:

- S89 proves the later ARM9 type-3 sprite actor commit path
  `0x02023998 -> 0x02023FEC` is active during the same f075-f179 window where
  the selected ledge-spawn Igglybuff moves correctly and the accepted floor
  shadow is missing.
- This callsite is not directly attributable to object `0xE1` through
  `[sprite + 0x1C]`: that field was `0` for the logged commits, never looked
  like a main-RAM pointer, and never produced an owner ID match. Therefore the
  probe must be read as a broad type-3 sprite/OAM-ish commit-path confirmation,
  not as proof that E1 itself reached this exact callsite.
- The next useful probe should find a stronger owner mapping around the ARM9
  sprite actor list before or after `0x02023FEC`, likely by tracing where the
  sprite actor is attached to a map object or where the final OAM attributes are
  committed with a recoverable actor-to-object relationship.

Cleanup and clean rebuild:

- Removed the temporary S89 production hook at `0x02023998`, the seven
  diagnostic words at `0x02209B44..0x02209B5F`, and the ARM9 helper code in the
  pads at `0x02071C54..0x02071C67`, `0x02110258..0x02110297`,
  `0x021102D4..0x021102F3`, and `0x021103A0..0x021103B5`.
- Verified `armips/asm/overworlds.s` and `armips/asm/fairy.s` had no remaining
  S89 labels/hooks/data diffs.
- Rebuilt clean through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:31`; UI opened `test.nds`.
  - Copied clean ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1593.nds`.
  - Existing non-S89 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Clean built-byte restoration checks:
  - `base/arm9.bin` at `0x02023996..0x0202399D`:
    `20 1c 00 f0 28 fb 04 e0`, restoring the stock
    `bl 0x02023FEC` bytes at `0x02023998`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F`:
    `ff` fill for `0x02209B44..0x02209B57`, then zero bytes for
    `0x02209B58..0x02209B5F`; no S89 counter initializers remain.
  - ARM9 helper pads verified restored to `ff` fill over the S89-used spans:
    `0x02071C54..0x02071C9F`, `0x02110258..0x02110297`,
    `0x021102D4..0x021102F7`, and `0x021103A0..0x021103B7`.

### S90 - Render-to-Actor Mapping Probe

Purpose:

- S90 is instrumentation-only, not a proposed visual fix.
- S89 proved the later ARM9 type-3 commit path was active during the
  missing-shadow window, but did not have a recoverable owner pointer through
  `[sprite + 0x1C]`.
- This probe maps the overlay-1 object draw phase to the broader ARM9 actor
  commit by saving the selected `0xE1` draw object's primary/secondary sprite
  actors, then checking whether the later ARM9 actor commit sees the same
  actor.

Implementation plan:

- Patch overlay 1 callsite `0x021F7908`, stock bytes `02 F0 6E FD`
  (`bl 0x021FA3E8`), to a Thumb wrapper.
  - Entry state: `r0 = object`, `r1 = primarySprite`, `r4 = renderData`,
    `r5 = object`, `r7 = variant`.
  - Log only when `[r5 + 0x08] == 0xE1`.
  - Save object, primary, secondary `[r4 + 4]`, `renderData == object+0x108`,
    and render bytes `+0x10`, `+0x15`, `+0x17`.
  - Preserve behavior by calling stock `0x021FA3E8` with original `r0/r1`.
- Patch ARM9 callsite `0x020239BA`, stock bytes `FB F7 CB FD`
  (`bl 0x0201F554`), to a Thumb wrapper.
  - Entry state: `r0 = actor+0x30`, `r1 = actor`, `r2 = payload/scratch`,
    `r3 = actor+0x0C`, `r4 = actor`.
  - Compare actor against saved primary/secondary, and compare
    `[actor+0x24]`, `[actor+0x40]`, and `[actor+0xA0]` against saved primary.
  - On match, save the matched actor and pack matched actor `B4`.
  - Preserve behavior by calling stock `0x0201F554` with original `r0-r3`.
- Store exactly seven diagnostic words at `0x02209B44..0x02209B5F`, shortening
  the existing overlay-1 tail fill only for the diagnostic run.

Diagnostic words:

- `0x02209B44 s90_status`
- `0x02209B48 s90_e1_draw_count`
- `0x02209B4C s90_object`
- `0x02209B50 s90_primary`
- `0x02209B54 s90_secondary`
- `0x02209B58 s90_last_matched_actor`
- `0x02209B5C s90_pack`

Status bits:

- `0x0001`: draw logged.
- `0x0002`: `renderData == object + 0x108`.
- `0x0004`: primary non-null.
- `0x0008`: actor exact primary.
- `0x0010`: actor exact secondary.
- `0x0020`: `actor+0x24 == primary`.
- `0x0040`: `actor+0xA0 == primary`.
- `0x0080`: matched actor `B4 == 3`.

Packing notes:

- `s90_pack` packs `renderData[0x10]` in bits `0..7`,
  `renderData[0x15]` in bits `8..15`, `renderData[0x17]` in bits `16..23`,
  and matched actor `B4` in bits `24..31`.
- The actor `+0x40` comparison contributes to the match decision but has no
  dedicated status bit in the seven-word layout; a `+0x40`-only match would be
  visible as `s90_last_matched_actor` without one of the exact/`+0x24`/`+0xA0`
  status bits.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s90_render_actor_mapping \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s90_status:u32:0x02209B44 \
  --memory-read s90_e1_draw_count:u32:0x02209B48 \
  --memory-read s90_object:u32:0x02209B4C \
  --memory-read s90_primary:u32:0x02209B50 \
  --memory-read s90_secondary:u32:0x02209B54 \
  --memory-read s90_last_matched_actor:u32:0x02209B58 \
  --memory-read s90_pack:u32:0x02209B5C
```

Implementation and build notes:

- Added temporary source hooks only in `armips/asm/overworlds.s` and
  `armips/asm/fairy.s`.
- Diagnostic words were stored at `0x02209B44..0x02209B5F`; no helper code was
  placed in that diagnostic-data range.
- Helper code occupied existing ARM9 padding at `0x02071C54..0x02071C9F`,
  `0x0202990A..0x0202991B`, `0x02108FC8..0x02108FE8`,
  `0x021101B4..0x021101CB`, `0x02110258..0x021102A3`,
  `0x021102D4..0x021102F7`, `0x02110348..0x02110357`, and
  `0x021103A0..0x021103B7`.
- The first instrumented build failed because the initial helper layout
  overflowed three tiny pads by 4, 2, and 2 bytes. The final layout split the
  actor field checks and pack-preservation helper into separate small pads.
- Final instrumented build was through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:29`; UI opened `test.nds`.
  - Copied instrumented ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1596.nds`.
  - Existing non-S90 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.

Instrumented built-byte spot checks:

- `base/overlay/overlay_0001.bin` at `0x021F7908` changed from stock
  `02 f0 6e fd` to `7a f6 a4 f9`.
- `base/arm9.bin` at `0x020239BA` changed from stock `fb f7 cb fd` to
  `ec f0 8b fc`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.

Harness result:

- Command: the planned `igglybuff_shadow_s90_render_actor_mapping` harness
  command above.
- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- `target_selection.passed`: `true`.
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `45`.
- `movement_progress_pass.passed`: `true`.
  - `distinct_center_x_count`: `38`; `progress_left_delta`: `72`.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Artifacts:
  - Summary JSON:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s90_render_actor_mapping_summary.json`
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s90_render_actor_mapping_contact.png`

Final diagnostics:

- `s90_status`: `0x0000008F`.
  - Set: draw logged.
  - Set: `renderData == object + 0x108`.
  - Set: primary non-null.
  - Set: actor exact primary.
  - Clear: actor exact secondary.
  - Clear: `actor+0x24 == primary`.
  - Clear: `actor+0xA0 == primary`.
  - Set: matched actor `B4 == 3`.
- `s90_e1_draw_count`: `0x000001BA` (`442`).
- `s90_object`: `0x022AEF14`.
- `s90_primary`: `0x0234A15C`.
- `s90_secondary`: `0x00000000`.
- `s90_last_matched_actor`: `0x0234A15C`.
- `s90_pack`: `0x03010003`
  (`renderData[0x10] = 3`, `renderData[0x15] = 0`,
  `renderData[0x17] = 1`, matched actor `B4 = 3`).

Key f075-f179 sampled transitions:

- `s90_e1_draw_count` advanced `132 -> 236` (`+104`) during the missing-shadow
  window.
- `s90_status` stayed `0x0000008F` throughout the window.
- `s90_object` stayed `0x022AEF14`.
- `s90_primary` stayed `0x0234A15C`.
- `s90_secondary` stayed `0x00000000`.
- `s90_last_matched_actor` stayed `0x0234A15C`, exactly matching
  `s90_primary`.
- `s90_pack` alternated only between `0x03010003` and `0x03010103`.
  - In both values, matched actor `B4 = 3`, `renderData[0x10] = 3`, and
    `renderData[0x17] = 1`.
  - The `renderData[0x15]` byte toggled between `0` and `1`.

Interpretation:

- S90 proves that the selected object ID `0xE1` reaches the overlay draw call
  `0x021F7908 -> 0x021FA3E8` with `renderData == object + 0x108`, a non-null
  primary sprite actor, and no secondary actor.
- The later broad ARM9 actor commit call `0x020239BA -> 0x0201F554` sees the
  exact same actor pointer as the overlay draw primary: `s90_primary ==
  s90_last_matched_actor == 0x0234A15C`.
- The matched actor has `B4 == 3`, and this remains true during the full
  f075-f179 missing-shadow window.
- Therefore, unlike S89's broad type-3 commit probe, S90 provides a direct
  object-to-actor mapping: the missing-shadow `0xE1` draw primary is the same
  actor that later reaches the ARM9 commit hook.
- The secondary path is not involved for this repro (`s90_secondary == 0`), and
  the `actor+0x24`/`actor+0xA0` primary aliases did not match. The exact actor
  pointer identity is the decisive mapping.
- The next useful probe can move downstream from `0x020239BA -> 0x0201F554`
  while carrying this actor identity, rather than searching for another owner
  pointer.

Cleanup and clean rebuild:

- Removed the temporary overlay hook at `0x021F7908`, the temporary ARM9 hook
  at `0x020239BA`, the seven diagnostic words at `0x02209B44..0x02209B5F`,
  and all S90 helper code in the ARM9 pads listed above.
- Verified `armips/asm/overworlds.s` and `armips/asm/fairy.s` contain no
  remaining S90 labels/hooks/data and have no remaining S90 source diff.
- Rebuilt clean through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:25`; UI opened `test.nds`.
  - Copied clean ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1597.nds`.
  - Existing non-S90 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Clean built-byte restoration checks:
  - `base/overlay/overlay_0001.bin` at `0x021F7908` is back to stock
    `02 f0 6e fd`.
  - `base/arm9.bin` at `0x020239BA` is back to stock `fb f7 cb fd`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` is back to
    `ff` fill for `0x02209B44..0x02209B57`, then original zero bytes for
    `0x02209B58..0x02209B5F`.
  - S90 helper pads verified restored to `ff` fill:
    `0x02071C54..0x02071C9F`, `0x0202990A..0x0202991B`,
    `0x02108FC8..0x02108FE8`, `0x021101B4..0x021101CB`,
    `0x02110258..0x021102A3`, `0x021102D4..0x021102F7`,
    `0x02110348..0x02110357`, and `0x021103A0..0x021103B7`.

### S91 - Downstream Renderer Emit Probe

Purpose:

- S91 is instrumentation-only, not a proposed visual fix.
- S90 proved the selected object `0xE1` maps to the exact primary actor that
  reaches `0x0201F554`.
- This probe carries that actor identity farther downstream into the flush and
  command-packet enqueue path, to check whether the selected actor is dropped
  before the enqueue boundary.

Implementation plan:

- Reuse the S90 overlay mapper at `0x021F7908`, stock bytes `02 F0 6E FD`
  (`bl 0x021FA3E8`), only to save the selected `0xE1` object and primary actor.
- Patch ARM9 callsite `0x02023998`, stock bytes `00 F0 28 FB`
  (`bl 0x02023FEC`), to count/sample exact saved-actor type-3 hits.
- Patch ARM9 callsite `0x0201F580`, stock bytes `A0 F0 A2 EB`
  (`blx 0x020BFCC8` inside `0x0201F554`), to count exact saved-actor flushes
  and reset per-flush enqueue slots before calling stock.
- Patch ARM9 ARM callsite `0x020C0458`, stock bytes `32 08 00 EB`
  (`bl 0x020C2528`), to wrap the command-packet enqueue call. At this point
  `r7 = work`, `r5 = enqueue record`, and `[r7 + 4] == actor + 0x30`.
- Store exactly seven public diagnostic words at `0x02209B44..0x02209B5F`.
  Hidden saved-object/actor state and helper code live outside the public
  diagnostic words and are removed after the probe.

Diagnostic words:

- `0x02209B44 s91_status`
- `0x02209B48 s91_counts_a`
  (`low16 = flush count`, `high16 = exact type-3 count`)
- `0x02209B4C s91_counts_b`
  (`low16 = total emit count`, `bits16..23 = last-flush emit count`,
  `bits24..31 = actor payload flags low byte`)
- `0x02209B50 s91_actor_pack`
  (`B4 | B6 << 8 | ((B8 >> 12) & 0xFFFF) << 16`)
- `0x02209B54 s91_vertical_pack`
  (`low16 = posVec[1] >> 12`,
  `high16 = (faceVec[1] | unk88[1]) >> 12`)
- `0x02209B58 s91_emit0_attr01`
  (`first copied payload word | next sampled word << 16`)
- `0x02209B5C s91_emit1_attr01`
  (`second sampled enqueue payload, or last sampled enqueue if more than two`)

Status bits:

- `0x0001`: mapper saw selected object `0xE1`.
- `0x0002`: exact saved-actor type-3 hit.
- `0x0004`: exact saved-actor flush hit.
- `0x0008`: exact saved-actor emit hit.
- `0x0010`: last exact saved-actor flush enqueued zero command packets.
- `0x0020`: last exact saved-actor flush enqueued more than one command packet.
- `0x0040`: actor payload low byte had tested skip/hidden bits
  (`payload[0] & 0x18`).
- `0x0080`: first copied payload word had tested `0x0300` bits; this is a
  payload observation, not a proven final OAM hidden/disabled classification.

Implementation and build notes:

- Added temporary source hooks only in `armips/asm/fairy.s`.
- Helper code occupied temporary ARM9 pads at `0x02071C54..0x02071C9F`,
  `0x02110258..0x021102A3`, `0x02108D74..0x02108E9F`,
  `0x02108FC8..0x02108FE7`, and `0x021103A0..0x021103B7`.
- The first instrumented build (`test1598.nds`) sampled the enqueue record
  from `[r5 + 0]`, which the local setup showed was control/flag data. The
  final recorded run below uses `[r5 + 4]`, matching the first word copied into
  the `0x020C2528` payload.
- Final instrumented build was through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:25`; UI opened `test.nds`.
  - Copied instrumented ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1599.nds`.
  - Existing non-S91 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.

Instrumented built-byte spot checks:

- `base/overlay/overlay_0001.bin` at `0x021F7908` changed from stock
  `02 f0 6e fd` to `7a f6 a4 f9`.
- `base/arm9.bin` at `0x02023998` changed from stock `00 f0 28 fb` to
  `ec f0 5e fc`.
- `base/arm9.bin` at `0x0201F580` changed from stock `a0 f0 a2 eb` to
  `52 f0 79 fb`.
- `base/arm9.bin` at `0x020C0458` changed from stock `32 08 00 eb` to
  `da 22 01 eb`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s91_downstream_renderer_probe_attr \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s91_status:u32:0x02209B44 \
  --memory-read s91_counts_a:u32:0x02209B48 \
  --memory-read s91_counts_b:u32:0x02209B4C \
  --memory-read s91_actor_pack:u32:0x02209B50 \
  --memory-read s91_vertical_pack:u32:0x02209B54 \
  --memory-read s91_emit0_attr01:u32:0x02209B58 \
  --memory-read s91_emit1_attr01:u32:0x02209B5C
```

Harness result:

- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Target selection passed:
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `28`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `47`.
- `movement_progress_pass.passed`: `true`.
  - `distinct_center_x_count`: `38`; `progress_left_delta`: `72`.
  - `progress_window_end_frame`: `125`.
- Landing/stationary tail was detected from f125 through f179.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Contact sheet inspected:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s91_downstream_renderer_probe_attr_contact.png`
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s91_downstream_renderer_probe_attr_summary.json`

Final diagnostics:

- `s91_status`: `0x0000008F`.
  - Set: mapper saw selected object `0xE1`.
  - Set: exact saved-actor type-3 hit.
  - Set: exact saved-actor flush hit.
  - Set: exact saved-actor emit hit.
  - Clear: last exact saved-actor flush enqueued zero command packets.
  - Clear: last exact saved-actor flush enqueued more than one command packet.
  - Clear: actor payload low-byte skip/hidden bits (`0x18`) seen.
  - Set: first copied payload word had tested `0x0300` bits seen.
- `s91_counts_a`: `0x01080108`
  (`flush count = 264`, `exact type-3 count = 264`).
- `s91_counts_b`: `0x00010108`
  (`total emit count = 264`, `last-flush emit count = 1`,
  `actor payload flags low byte = 0x00`).
- `s91_actor_pack`: `0x00490303`
  (`B4 = 3`, `B6 = 3`, `(B8 >> 12) & 0xFFFF = 0x0049`).
- `s91_vertical_pack`: `0x00010010`
  (`posVec[1] >> 12 = 16`, active visual lift sample `= 1`).
- `s91_emit0_attr01`: `0x318AC210`
  (`first copied payload word = 0xC210`, `next sampled word = 0x318A`).
- `s91_emit1_attr01`: `0x00000000`
  (no second enqueue in the final exact saved-actor flush).

Active-hop f075-f124:

- `s91_status` stayed `0x0000008F`.
- `s91_counts_a` advanced from `0x006D006D` to `0x00850085`:
  `+24` flushes and `+24` exact type-3 hits.
- `s91_counts_b` advanced from `0x0001006D` to `0x00010085`:
  `+24` total emits, with last-flush emit count staying `1` and payload flags
  staying `0x00`.
- `s91_emit0_attr01` stayed `0x318AC210`; `s91_emit1_attr01` stayed `0`.
- `s91_vertical_pack` kept floor `posVec[1] >> 12 == 16`; signed active-lift
  samples seen in this window were `-2, -1, 0, 1, 2, 3, 8, 9, 10, 13, 14`.
- `s91_actor_pack` stayed type-3 with `B4 = 3`, `B6 = 3`; the packed
  `(B8 >> 12)` sample cycled through the observed `0x003C..0x004F` range.

Landing/stationary tail f125-f179:

- `s91_status` stayed `0x0000008F`.
- `s91_counts_a` advanced from `0x00860086` to `0x00A100A1`:
  `+27` flushes and `+27` exact type-3 hits.
- `s91_counts_b` advanced from `0x00010086` to `0x000100A1`:
  `+27` total emits, with last-flush emit count staying `1` and payload flags
  staying `0x00`.
- `s91_emit0_attr01` stayed `0x318AC210`; `s91_emit1_attr01` stayed `0`.
- `s91_vertical_pack` kept floor `posVec[1] >> 12 == 16`; signed active-lift
  samples seen in this tail were `-2, -1, 10, 11, 14, 15, 16`.

Interpretation:

- S91 proves the selected `0xE1` primary actor survives past the S90
  `0x0201F554` mapping and reaches the downstream command-packet enqueue path
  after flush during the full f075-f179 missing-shadow window.
- The exact saved-actor type-3, flush, and emit counts move one-for-one in the
  active-hop and landing-tail windows. The missing floor shadow is therefore
  not explained by the selected actor failing to flush or by the exact flush
  enqueuing zero command packets.
- Each exact saved-actor flush produced exactly one sampled command-packet
  enqueue in this run; there was no second enqueue for this actor. This does
  not by itself prove there was exactly one final sprite/OAM primitive. It
  matches S90's earlier `s90_secondary == 0` result and suggests the repro is
  not using a separate secondary actor enqueue in this downstream path.
- The actor payload low byte stayed `0x00`, so S91 did not see the tested
  payload skip/hidden bits on `actor + 0x30`.
- The first copied payload word sampled as `0xC210`; its `0x0200` bit is only
  a payload observation under the provisional `word & 0x0300` check until S92
  classifies the GX/OAM path.
  Because the harness still tracks a visible moving body while the accepted
  floor shadow is absent, the next useful probe should distinguish whether
  this exact enqueue payload is the visible body, a suppressed shadow/effect
  payload, or a payload later transformed by `0x020C2528` or a subsequent OAM
  stage.

Cleanup and clean rebuild:

- Removed the temporary S91 hooks, diagnostic initializers, hidden variables,
  and helper code from `armips/asm/fairy.s`.
- Verified `armips/asm/fairy.s` and `armips/asm/overworlds.s` contain no
  remaining `S91`/`s91` labels, hooks, or data.
- Rebuilt clean through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:28`; UI opened `test.nds`.
  - Copied clean ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1600.nds`.
  - Existing non-S91 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Clean built-byte restoration checks:
  - `base/overlay/overlay_0001.bin` at `0x021F7908` is back to stock
    `02 f0 6e fd`.
  - `base/arm9.bin` at `0x02023998` is back to stock `00 f0 28 fb`.
  - `base/arm9.bin` at `0x0201F580` is back to stock `a0 f0 a2 eb`.
  - `base/arm9.bin` at `0x020C0458` is back to stock `32 08 00 eb`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` is back to
    `ff` fill for `0x02209B44..0x02209B57`, then original zero bytes for
    `0x02209B58..0x02209B5F`.
  - Temporary S91 helper/storage pads are restored:
    `0x02071C54..0x02071C9F` and `0x02110258..0x021102A3` back to `ff`;
    `0x02108D74..0x02108E9F` back to zero padding;
    `0x02108FC8..0x02108FE7` and `0x021103A0..0x021103B7` back to `ff`.

### S92 - GX Material Command Classification Probe

Purpose:

- S92 is instrumentation-only, not a proposed visual fix.
- S91 proved the selected `0xE1` primary actor reaches the downstream
  command-packet enqueue path, but the sampled word was likely GX/G3 material
  payload rather than OAM attr0/attr1.
- This probe classifies the exact saved actor's material packet at
  `0x020C0458 -> 0x020C2528`, using the live context where `r7 = work`,
  `r5 = material record`, and `[r7 + 4] == actor + 0x30` for the exact actor.

Implementation plan:

- Patch overlay 1 callsite `0x021F7908`, stock bytes `02 F0 6E FD`
  (`bl 0x021FA3E8`), to save the selected object `0xE1` primary actor.
- Patch ARM9 Thumb callsite `0x0201F580`, stock bytes `A0 F0 A2 EB`
  (`blx 0x020BFCC8`), to count exact saved-actor flushes and reset the
  per-flush material-packet counter.
- Patch ARM9 ARM callsite `0x020C0458`, stock bytes `32 08 00 EB`
  (`bl 0x020C2528`), to sample only material calls where `[r7 + 4]` matches
  the exact saved actor plus `0x30`.
- Avoided hooking `0x020C2528` directly because it is generic and hot.
- Store exactly seven public diagnostic words at `0x02209B44..0x02209B5F`.
  Hidden saved-actor and per-flush state lived in ARM9 padding and was removed
  after the probe.

Diagnostic words:

- `0x02209B44 s92_status`
- `0x02209B48 s92_counts`
  (`low16 = exact flush count`, `high16 = exact material emit count`)
- `0x02209B4C s92_diff_amb = [r5 + 0x04]`
- `0x02209B50 s92_spe_emi = [r5 + 0x08]`
- `0x02209B54 s92_poly_attr = [r5 + 0x0C]`
- `0x02209B58 s92_tex_param = [r5 + 0x10]`
- `0x02209B5C s92_pltt_base_flags =
  low16([r5 + 0x14]) | high16([r5] & 0xFFFF)`

Status bits:

- `0x0001`: selected object `0xE1` primary actor saved.
- `0x0002`: exact saved-actor flush seen.
- `0x0004`: exact saved-actor material emit seen.
- `0x0008`: command pack matched `r0 = 0x00293130` and `r2 = 6`.
- `0x0010`: more than one material packet seen for one exact saved-actor flush.

Command summary:

- At `0x020C0458`, stock has built a six-word GX material payload:
  `0x00293130`, `[r5 + 0x04]`, `[r5 + 0x08]`, `[r5 + 0x0C]`,
  `0x00002B2A`, `[r5 + 0x10]`, `[r5 + 0x14]`.
- The first command word packs GX commands `0x30`, `0x31`, and `0x29`
  (`DIF_AMB`, `SPE_EMI`, and `POLYGON_ATTR`).
- The second command word packs GX commands `0x2A` and `0x2B`
  (`TEXIMAGE_PARAM` and `PLTT_BASE`).

Implementation and build notes:

- Added temporary source hooks only in `armips/asm/fairy.s`.
- Helper code occupied temporary ARM9 pads at `0x02071C54..0x02071C9F`,
  `0x02110258..0x021102A3`, `0x02108D74..0x02108E9B`, and hidden storage at
  `0x021103A0..0x021103A7`.
- Instrumented build was through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:34`; UI opened `test.nds`.
  - ROM header: title `POKEMON HG`, game code `IPKE`, maker `01`.
  - Copied instrumented ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1601.nds`.
  - Existing non-S92 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.

Instrumented built-byte spot checks:

- `base/overlay/overlay_0001.bin` at `0x021F7908` changed from stock
  `02 f0 6e fd` to `7a f6 a4 f9`.
- `base/arm9.bin` at `0x0201F580` changed from stock `a0 f0 a2 eb` to
  `f0 f0 6a fe`.
- `base/arm9.bin` at `0x020C0458` changed from stock `32 08 00 eb` to
  `45 22 01 eb`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s92_gx_material_classification_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s92_status:u32:0x02209B44 \
  --memory-read s92_counts:u32:0x02209B48 \
  --memory-read s92_diff_amb:u32:0x02209B4C \
  --memory-read s92_spe_emi:u32:0x02209B50 \
  --memory-read s92_poly_attr:u32:0x02209B54 \
  --memory-read s92_tex_param:u32:0x02209B58 \
  --memory-read s92_pltt_base_flags:u32:0x02209B5C
```

Harness result:

- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Target selection passed:
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `28`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `47`.
- `movement_progress_pass.passed`: `true`.
  - `distinct_center_x_count`: `38`; `progress_left_delta`: `72`.
  - `progress_window_end_frame`: `125`.
- Landing/stationary tail was detected from f125 through f179.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Contact sheet inspected:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s92_gx_material_classification_probe_contact.png`
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s92_gx_material_classification_probe_summary.json`

Final diagnostics:

- `s92_status`: `0x0000000F`.
  - Set: selected object `0xE1` primary actor saved.
  - Set: exact saved-actor flush seen.
  - Set: exact saved-actor material emit seen.
  - Set: command pack matched `0x00293130` with payload count `6`.
  - Clear: more than one material packet per exact saved-actor flush.
- `s92_counts`: `0x01080108`
  (`flush count = 264`, `material emit count = 264`).
- `s92_diff_amb`: `0x318AC210`.
- `s92_spe_emi`: `0x39CE4A52`.
- `s92_poly_attr`: `0x001F8081`
  (`alpha = 31`, fully opaque in the standard GX polygon alpha field).
- `s92_tex_param`: `0x2D23407E`.
- `s92_pltt_base_flags`: `0x000000ED`
  (`pltt_base low16 = 0x00ED`, material flags low16 = `0x0000`).

Active-hop f075-f124:

- `s92_status` stayed `0x0000000F`; the multi-material bit stayed clear.
- `s92_counts` advanced from `0x006D006D` to `0x00850085`:
  `+24` exact flushes and `+24` exact material emits.
- `s92_diff_amb` stayed `0x318AC210`.
- `s92_spe_emi` stayed `0x39CE4A52`.
- `s92_poly_attr` stayed `0x001F8081`.
- `s92_tex_param` alternated only between `0x2D23403E` and `0x2D23407E`.
- `s92_pltt_base_flags` stayed `0x000000ED`.

Landing/stationary tail f125-f179:

- `s92_status` stayed `0x0000000F`; the multi-material bit stayed clear.
- `s92_counts` advanced from `0x00860086` to `0x00A100A1`:
  `+27` exact flushes and `+27` exact material emits.
- `s92_diff_amb` stayed `0x318AC210`.
- `s92_spe_emi` stayed `0x39CE4A52`.
- `s92_poly_attr` stayed `0x001F8081`.
- `s92_tex_param` alternated only between `0x2D23403E` and `0x2D23407E`.
- `s92_pltt_base_flags` stayed `0x000000ED`.

Interpretation:

- S92 classifies S91's sampled word as GX material payload, not OAM attr0/attr1.
  The exact actor emits the material command pack
  `DIF_AMB/SPE_EMI/POLYGON_ATTR` plus `TEXIMAGE_PARAM/PLTT_BASE`.
- Aggregate exact saved-actor flush and material-packet counts stayed
  one-for-one in both the active-hop and landing-tail windows, with no
  persistent second material packet. The `>1 material packet` status bit never
  set.
- The packet is body-like: material colors are stable, `poly_attr` has normal
  opaque alpha (`31`), palette base is stable at `0x00ED`, flags low16 are
  clear, and texture changes are limited to `0x2D23403E/0x2D23407E`.
- Therefore, S91's enqueue is likely the visible Pokemon body material. The
  missing floor shadow is likely not emitted by the selected primary actor path.
  The next useful probe should inspect a separate shadow path or later
  geometry/vertex/display-list emission, rather than treating this material
  payload as hidden/translucent shadow OAM.

Cleanup and clean rebuild:

- Removed the temporary S92 hooks, diagnostic initializers, hidden variables,
  and helper code from `armips/asm/fairy.s`.
- Verified `armips/asm/fairy.s` and `armips/asm/overworlds.s` contain no
  remaining `S92`/`s92` labels, hooks, or data and have no remaining source
  diff.
- Rebuilt clean through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:25`; UI opened `test.nds`.
  - Clean ROM header: title `POKEMON HG`, game code `IPKE`, maker `01`.
  - Copied clean ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1602.nds`.
  - Existing non-S92 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Clean built-byte restoration checks:
  - `base/overlay/overlay_0001.bin` at `0x021F7908` is back to stock
    `02 f0 6e fd`.
  - `base/arm9.bin` at `0x0201F580` is back to stock `a0 f0 a2 eb`.
  - `base/arm9.bin` at `0x020C0458` is back to stock `32 08 00 eb`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` is back to
    `ff` fill for `0x02209B44..0x02209B57`, then original zero bytes for
    `0x02209B58..0x02209B5F`.
  - Temporary S92 helper/storage pads are restored:
    `0x02071C54..0x02071C9F`, `0x02110258..0x021102A3`, and
    `0x021103A0..0x021103B7` back to `ff`;
    `0x02108D74..0x02108E9B` back to zero padding.

### S93 - Passive Separate Material Census

Purpose:

- S93 is instrumentation-only, not a proposed visual fix.
- S90-S92 showed the selected `0xE1` primary actor maps cleanly from overlay
  draw to ARM9 flush and emits one opaque body-like GX material packet per
  exact flush.
- This probe keeps the exact actor mapper/flush window, but does not filter the
  material enqueue hook to only the exact owner. During the selected actor's
  flush window it passively samples all `0x020C0458 -> 0x020C2528` material
  packets and classifies exact body packets separately from non-body,
  shadow-like candidates.

Implementation plan:

- Patch overlay 1 callsite `0x021F7908`, stock bytes `02 F0 6E FD`
  (`bl 0x021FA3E8`), to save the selected object `0xE1` primary actor and
  `primary + 0x30`.
- Patch ARM9 Thumb callsite `0x0201F580`, stock bytes `A0 F0 A2 EB`
  (`blx 0x020BFCC8`), to mark the exact selected primary flush window when
  `r0` or `r5` matches saved `primary + 0x30`.
- Patch ARM9 ARM callsite `0x020C0458`, stock bytes `32 08 00 EB`
  (`bl 0x020C2528`), to sample every material packet while the exact selected
  flush window is active. Live context is `r7 = render work`,
  `r5 = material record`, `[r7 + 4] = owner/actor+0x30-like pointer`,
  `[r5 + 4] = DIF_AMB`, `[r5 + 8] = SPE_EMI`,
  `[r5 + 0x0C] = POLY_ATTR`, `[r5 + 0x10] = TEX_PARAM`, and
  `[r5 + 0x14] = PLTT_BASE`.
- Skip the optional effect-family hooks for the first S93 run unless the core
  census is clearly small enough; the material census is the decisive question.
- Store exactly seven public diagnostic words at `0x02209B44..0x02209B5F`.

Diagnostic words:

- `0x02209B44 s93_status`
- `0x02209B48 s93_counts`
  (`low16 = selected mapper hits`, `high16 = exact primary actor flushes`)
- `0x02209B4C s93_material_counts`
  (`low16 = exact owner/body material packets`,
  `high16 = non-body shadow-like candidate packets`)
- `0x02209B50 s93_body_material`
  (`alpha | palette_low8 << 8 | tex_low16 << 16`)
- `0x02209B54 s93_shadow_owner`
  (best non-body candidate owner from `[r7 + 4]`, or `0`)
- `0x02209B58 s93_shadow_material`
  (`alpha | palette_low8 << 8 | diffuse_low8 << 16 | tex_low8 << 24`)
- `0x02209B5C s93_effect_counts`
  (`0` when the optional effect-family counters are not implemented)

Status bits:

- `0x0001`: mapper saw selected object `0xE1`.
- `0x0002`: exact selected primary flush seen.
- `0x0004`: exact owner body material seen.
- `0x0008`: non-body shadow-like material candidate seen.
- `0x0010`: optional effect-family hit seen, if implemented.
- `0x0020`: exact selected flushes ran with no non-body candidate observed yet.
- `0x0040`: non-body material seen in-window but rejected by the shadow-like
  heuristic.

Classifier notes:

- Body-like means owner equals saved `primary + 0x30`, alpha is `31`, palette
  low16 is `0x00ED`, and texture matches S92's stable body texture signature
  after masking the observed `0x40` variant bit.
- A non-body shadow-like candidate must have a nonzero owner different from the
  saved body owner, nonzero alpha, and either translucent alpha (`< 31`) or a
  dark diffuse color where all BGR555 channels are at most `8`.
- The rejected-non-body bit is intentionally broad. It distinguishes "no
  separate material in this selected flush window" from "separate material
  existed, but did not look like a floor shadow under this passive heuristic."

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s93_passive_material_census \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s93_status:u32:0x02209B44 \
  --memory-read s93_counts:u32:0x02209B48 \
  --memory-read s93_material_counts:u32:0x02209B4C \
  --memory-read s93_body_material:u32:0x02209B50 \
  --memory-read s93_shadow_owner:u32:0x02209B54 \
  --memory-read s93_shadow_material:u32:0x02209B58 \
  --memory-read s93_effect_counts:u32:0x02209B5C
```

Implementation and build notes:

- Added temporary source hooks only in `armips/asm/overworlds.s` and
  `armips/asm/fairy.s`.
- Diagnostic words were stored at `0x02209B44..0x02209B5F`; no helper code was
  placed in that diagnostic-data range.
- Helper code/storage occupied temporary ARM9 pads:
  - mapper wrapper in `0x02071C54..0x02071C9F`;
  - exact flush wrapper in `0x02108D74..0x02108E9F`;
  - ARM material census wrapper in zero padding `0x020FEA68..0x020FEBD3`;
  - hidden saved actor/window state in `0x021103A0..0x021103AB`.
- Optional effect-family counters were not implemented for this run; the
  `s93_effect_counts` word stays `0`.
- Initial instrumented build attempts failed in ARMIPS before producing a ROM:
  first due to a case-insensitive `S93_STATUS` label/equate collision, then due
  to trying to place the combined flush/material code in one `0x02108D74`
  zero pad, then due to the standalone flush wrapper exceeding
  `0x02110258..0x021102A3` by 8 bytes. The final split layout above built
  cleanly.
- Final instrumented build was through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:32`; UI opened `test.nds`.
  - Copied instrumented ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1603.nds`.
  - Existing non-S93 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.

Instrumented built-byte spot checks:

- `base/overlay/overlay_0001.bin` at `0x021F7908` changed from stock
  `02 f0 6e fd` to `7a f6 a4 f9`.
- `base/arm9.bin` at `0x0201F580` changed from stock `a0 f0 a2 eb` to
  `e9 f0 f8 fb`.
- `base/arm9.bin` at `0x020C0458` changed from stock `32 08 00 eb` to
  `82 f9 00 eb`.
- `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` contained seven
  zero-initialized diagnostic words before the harness run.

Harness result:

- Exit: success because `--no-fail-on-shadow-pass` was enabled.
- DSV:
  `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
- Target selection passed:
  - Target was the upper ledge-spawn Igglybuff, bbox `[105,84,118,95]`,
    center `[111,89]`, with `75` new pink pixels.
- `actual_left_hop_start_frame`: `28`.
- `movement_pass.passed`: `true`.
  - Window: f075-f179.
  - `tracked_frame_count`: `105` / `105`; `tracked_percent`: `100`.
  - `origin_left_delta`: `95`; `window_left_delta`: `47`.
- `movement_progress_pass.passed`: `true`.
  - `distinct_center_x_count`: `38`; `progress_left_delta`: `72`.
  - `progress_window_end_frame`: `125`.
- Landing/stationary tail was detected from f125 through f179.
- `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0` / `105`.
  - `missing_shadow_frame_count`: `105`.
  - `max_missing_run`: `105`.
  - `tracked_percent`: `100`.
- Contact sheet inspected:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s93_passive_material_census_contact.png`
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s93_passive_material_census_summary.json`

Final diagnostics:

- `s93_status`: `0x00000027`.
  - Set: mapper saw selected object `0xE1`.
  - Set: exact selected primary flush seen.
  - Set: exact owner body material seen.
  - Clear: non-body shadow-like material candidate seen.
  - Clear: optional effect-family hit.
  - Set: exact selected flushes ran with no non-body candidate observed.
  - Clear: non-body material seen but rejected by the heuristic.
- `s93_counts`: `0x010801B8`
  (`selected mapper hits = 440`, `exact primary actor flushes = 264`).
- `s93_material_counts`: `0x000000F8`
  (`exact owner/body material packets = 248`,
  `non-body shadow-like candidate packets = 0`).
- `s93_body_material`: `0x407EED1F`
  (`alpha = 31`, `palette_low8 = 0xED`, `tex_low16 = 0x407E`;
  the sampled body texture alternated with `0x403E`).
- `s93_shadow_owner`: `0x00000000`.
- `s93_shadow_material`: `0x00000000`.
- `s93_effect_counts`: `0x00000000`.

Active-hop f075-f124:

- `s93_status` stayed `0x00000027`.
- `s93_counts` advanced from `0x006D0084` to `0x008500B4`:
  `+48` mapper hits and `+24` exact primary flushes.
- `s93_material_counts` advanced from `0x0000005D` to `0x00000075`:
  `+24` exact body materials and `+0` non-body candidates.
- `s93_body_material` alternated only between `0x403EED1F` and
  `0x407EED1F`.
- `s93_shadow_owner` and `s93_shadow_material` stayed `0`.

Landing/stationary tail f125-f179:

- `s93_status` stayed `0x00000027`.
- `s93_counts` advanced from `0x008600B4` to `0x00A100EA`:
  `+54` mapper hits and `+27` exact primary flushes.
- `s93_material_counts` advanced from `0x00000076` to `0x00000091`:
  `+27` exact body materials and `+0` non-body candidates.
- `s93_body_material` again alternated only between `0x403EED1F` and
  `0x407EED1F`.
- `s93_shadow_owner` and `s93_shadow_material` stayed `0`.

Interpretation:

- S93 found no non-body, shadow-like material candidate at
  `0x020C0458 -> 0x020C2528` while the selected actor's exact primary flush
  window was active, under the S93 owner/material heuristic. It also did not
  set the broad rejected-non-body bit in the sampled window.
- During the full f075-f179 missing-shadow window, exact primary flushes and
  exact body material packets advanced together (`+52` each), while the
  non-body candidate count stayed `0`. This is the meaningful window result;
  the total-run flush/body-material gap existed before f075 and is not evidence
  about the active missing-shadow window.
- The missing floor shadow is therefore likely suppressed before GX material
  enqueue, emitted outside this selected primary actor flush window, or emitted
  through an owner-zero/same-owner/effect-family/sprite/display-list path not
  covered by this passive material census.
- Next useful work should run a stock good-hop differential with the same
  material counters plus the skipped effect-family counters, rather than
  tinting or treating the selected actor's body material as a hidden shadow.

Cleanup and clean rebuild:

- Removed the temporary S93 hooks, diagnostic initializers, hidden variables,
  and helper code from `armips/asm/fairy.s` and `armips/asm/overworlds.s`.
- Verified those two source files contain no remaining `S93`/`s93` labels,
  hooks, or data and have no remaining source diff from the temporary probe.
- Rebuilt clean through the UI endpoint with `runAfter:true`.
  - Result: success, exit code `0`, elapsed `0:39`; UI opened `test.nds`.
  - Copied clean ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1604.nds`.
  - Existing non-S93 warning remained:
    `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Clean built-byte restoration checks:
  - `base/overlay/overlay_0001.bin` at `0x021F7908` is back to stock
    `02 f0 6e fd`.
  - `base/arm9.bin` at `0x0201F580` is back to stock `a0 f0 a2 eb`.
  - `base/arm9.bin` at `0x020C0458` is back to stock `32 08 00 eb`.
  - `base/overlay/overlay_0001.bin` at `0x02209B44..0x02209B5F` is back to
    `ff` fill for `0x02209B44..0x02209B57`, then original zero bytes for
    `0x02209B58..0x02209B5F`.
  - Temporary S93 helper/storage pads are restored:
    `0x02071C54..0x02071C9F` and `0x021103A0..0x021103B7` back to `ff`;
    `0x02108D74..0x02108E9F` and `0x020FEA68..0x020FEBD3` back to zero
    padding.

### S94 - Aborted Same-Object Grass-Only Control

Purpose:

- S94 was intended to compare a visually passing early same-object window
  against the failing f075-f179 midair window.
- The proposed control window was f027-f038 for the selected ledge-spawned
  Igglybuff.

Result:

- The premise was rejected before keeping instrumentation results: shadow on
  grass tiles is irrelevant to the bug.
- The actual issue is the midair transition after moving off grass/canopy onto
  a tile where a floor shadow should be visible.
- The early f027-f038 window can pass the shadow oracle, but it is grass-only
  setup evidence and must not be used as a good control for the real bug.

Cleanup:

- The temporary S94 source hooks/data were removed from `armips/asm/fairy.s`
  and `armips/asm/overworlds.s`.
- A clean UI build was run afterward to clear stale instrumented build outputs.
  - Result: success, exit code `0`, elapsed `0:33`; UI opened `test.nds`.
  - Copied clean ROM:
    `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1606.nds`.

Conclusion:

- Do not repeat the f027-f038 same-object control comparison.
- The next probe must key off the first airborne non-grass/non-canopy floor
  sample within the same failing hop.

### S95a - Terrain-Transition Sampler Rejected

Purpose:

- S95a was instrumentation-only, not a proposed visual fix.
- The probe was meant to sample the selected ledge-spawn Igglybuff during the
  real airborne grass-to-non-grass leftward hop, not the earlier grass-only
  setup frames.

Harness result:

- Command prefix:
  `igglybuff_shadow_s95_terrain_transition`
- Target selection passed and selected the intended upper ledge Igglybuff.
- `movement_pass.passed`: `true`.
- `shadow_pass.passed`: `false`, `0 / 105`, matching the known bug.

Why this run is rejected:

- `s95_terrain_pack` was `0xFFFFFFFF` throughout the run.
- The position-derived floor coordinates were huge because the probe converted
  `posVec` with `>> 12`.
- This codebase's map tile size for these vectors is
  `OW_WILD_SPAWNER_TILE_FX32 == 0x10000`, so the sampler must use `>> 16`
  or the existing tile-size division logic.
- Do not use S95a to infer terrain state. S95b must rerun the same harness with
  corrected `posVec` tile conversion and byte-masked coordinate packs.

### S95b - Corrected PosVec Terrain Sampler Still Invalid

Purpose:

- S95b repaired the S95a sampler only; it was not a proposed visual fix.
- The `posVec` floor-tile conversion was changed from `>> 12` to `>> 16`,
  matching `OW_WILD_SPAWNER_TILE_FX32 == 0x10000`.
- `s95_coord_pack_a` and `s95_coord_pack_b` now mask each packed coordinate
  byte to its low 8 bits before shifting.
- The same selected ledge-spawn Igglybuff and the same real failing midair
  grass/canopy-to-floor hop were used. The f027-f038 grass-only setup window
  remains irrelevant.

Hook/data sites:

- Overlay 1 `0x021F7908`, replacing stock `02 F0 6E FD` with a mapper probe
  that preserves the stock call to `0x021FA3E8`.
- Overlay 1 `0x021F8E3A`, replacing stock `00 F0 C1 F8` with a terrain-gate
  probe that preserves the stock call to `0x021F8FC0`.
- Seven diagnostic words at `0x02209B44..0x02209B5F`.
- Optional effect-family hooks were skipped for size/risk; `s95_effect_counts`
  intentionally remained `0`.

Build and harness:

- Instrumented UI build with `runAfter:true`: success, exit code `0`, elapsed
  `0:36`; UI opened `test.nds`.
- Copied instrumented ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1608.nds`.
- Existing warning remained:
  `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Harness command prefix:
  `igglybuff_shadow_s95b_terrain_transition`
- Harness:
  `scripts/headless-overworld-shadow-harness.py --prefix igglybuff_shadow_s95b_terrain_transition --capture-frames 360 --contact-every 4 --target-igglybuff ledge-spawn --no-fail-on-shadow-pass --memory-sample-every 1 --memory-read s95_status:u32:0x02209B44 --memory-read s95_coord_pack_a:u32:0x02209B48 --memory-read s95_coord_pack_b:u32:0x02209B4C --memory-read s95_terrain_pack:u32:0x02209B50 --memory-read s95_gate_counts:u32:0x02209B54 --memory-read s95_effect_counts:u32:0x02209B58 --memory-read s95_render_heartbeat:u32:0x02209B5C`
- Result:
  - Target selection passed.
  - `movement_pass.passed`: `true`.
  - `shadow_pass.passed`: `false`, `0 / 105`.
  - Missing-shadow window: f075-f179.
  - Landing stall: f124-f179.
- Summary:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s95b_terrain_transition_summary.json`
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s95b_terrain_transition_contact.png`

Diagnostics:

- `s95_status` was `0x000000F7` for all 361 per-frame samples.
  - Set: selected object `0xE1` seen.
  - Set: primary/body pointer non-null.
  - Set: airborne inferred.
  - Clear: first non-grass/non-canopy sample.
  - Set: terrain gate hit.
  - Set: terrain gate returned nonzero at least once.
  - Set: terrain gate returned zero at least once.
  - Set: exact primary render-data relation observed.
- `s95_terrain_pack` stayed `0xFFFFFFFF` for all samples.
- No airborne non-grass/non-canopy terrain sample was observed.
- The corrected coordinate packs were byte-bounded, but still not usable as
  stock map-behavior coordinates:
  - f075: `coord_pack_a = (144, 145, 144, 145)`,
    `coord_pack_b = (144, 145, 144, 145)`.
  - f124: `coord_pack_a = (147, 145, 146, 145)`,
    `coord_pack_b = (147, 145, 147, 145)`.
  - f179: `coord_pack_a = (150, 145, 149, 145)`,
    `coord_pack_b = (150, 145, 150, 145)`.
  - f360: `coord_pack_a = (159, 145, 158, 145)`,
    `coord_pack_b = (159, 145, 159, 145)`.
- `s95_gate_counts` stayed entirely in the before-first-non-grass bucket
  because the first-non-grass bit never set:
  - f075: `pre = 116`, `post = 0`, last return zero.
  - f124: `pre = 164`, `post = 0`, last return nonzero.
  - f179: `pre = 220`, `post = 0`, last return zero.
  - f360: `pre = 394`, `post = 0`, last return nonzero.
  - Final read after capture: `0x000001A8` (`pre = 424`, `post = 0`,
    last return zero).
- `s95_effect_counts`: `0x00000000` because optional effect hooks were skipped.
- `s95_render_heartbeat` advanced through the missing-shadow window:
  - f075: `132`.
  - f179: `236`.
  - f360: `412`.
  - Final read after capture: `442`.

Interpretation:

- S95b fixed the S95a fixed-point conversion error and packed bounded bytes,
  but it still did not obtain valid terrain behaviors. `GetMetatileBehaviorAt`
  returned `0xFF` for current, previous, pos-derived floor, and current-as-
  landing proxy throughout the run.
- The live gate hook and render heartbeat prove the selected object/body path
  remained active during the f075-f179 failure, but terrain/gate/effect behavior
  cannot be compared before and after a non-grass transition from this data.
- The remaining blocker is the coordinate source used by the passive sampler:
  direct raw `LocalMapObject` fields and `posVec >> 16` at these render hooks
  still do not provide the stock map-behavior coordinates. The next terrain
  proof should either use the stock `MapObject_GetCurrentX/Y` accessors or log
  the actual coordinate inputs used inside/around `0x021F8FC0`.

Cleanup status:

- Temporary S95b hooks/data were removed from `armips/asm/fairy.s` and
  `armips/asm/overworlds.s` after the harness data was collected.
- Source residue check for `S95`, `s95`, `02209B44`, `021F7908`, `021F8E3A`,
  `020FEA68`, and `02108D74` in those two source files returned no matches.
- Clean UI rebuild with `runAfter:true`: success, exit code `0`, elapsed
  `0:33`; UI opened `test.nds`.
- Copied clean ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1610.nds`.
- Post-clean-build byte checks:
  - Overlay 1 `0x021F7908` restored to stock `02 F0 6E FD`.
  - Overlay 1 `0x021F8E3A` restored to stock `00 F0 C1 F8`.
  - Former diagnostic window `0x02209B44..0x02209B5F` restored to stock
    `FF` fill through `0x02209B57`, then zero bytes through `0x02209B5F`.
  - ARM9 helper pads at `0x020FEA68` and `0x02108D74` are zero-filled.

### S94 - Same-Object Good/Bad Differential Probe

Purpose:

- S94 is instrumentation-only, not a proposed visual fix.
- S93 found no non-body shadow-like GX material candidate during the bad
  f075-f179 selected-primary flush window.
- The existing ledge repro now provides a same-object visual control: the good
  f027-f038 window passes shadow detection, while the bad f075-f179 window
  still has shadow `0/105` with movement passing.
- This probe reuses the selected object `0xE1` mapper and exact primary flush
  window, then compares material and effect-family diagnostic deltas over the
  good and bad windows from the same instrumented ROM.

Implementation plan:

- Reuse the S93 material counters:
  - overlay 1 `0x021F7908`, stock `02 F0 6E FD`, selected object mapper /
    primary actor.
  - ARM9 Thumb `0x0201F580`, stock `A0 F0 A2 EB`, exact selected-primary
    flush window.
  - ARM9 ARM `0x020C0458`, stock `32 08 00 EB`, GX material enqueue census.
- Add passive effect-family counters where safe:
  - overlay 1 `0x02205CB4`, stock call to `0x021F771C`.
  - overlay 1 `0x02205CBA`, stock call to `0x02023E78`.
  - overlay 1 `0x02205E7A`, stock call to `0x021F771C`.
  - overlay 1 `0x02205E82`, stock call to `0x02023E78`.
- Count effect-family hooks only when the live object matches the selected
  saved object or object ID `0xE1`; treat them as passive correlation only.
- Store exactly seven public diagnostic words at `0x02209B44..0x02209B5F`.

Diagnostic words:

- `0x02209B44 s94_status`
- `0x02209B48 s94_counts`
  (`low16 = selected mapper hits`, `high16 = exact primary actor flushes`)
- `0x02209B4C s94_material_counts`
  (`low16 = exact owner/body materials`,
  `high16 = non-body shadow-like candidates`)
- `0x02209B50 s94_body_material`
  (`alpha | palette_low8 << 8 | tex_low16 << 16`)
- `0x02209B54 s94_candidate_pack`
  (`alpha | palette_low8 << 8 | diffuse_low8 << 16 | owner_low8 << 24`)
- `0x02209B58 s94_effect_counts_a`
  (`low16 = 0x02205CB4 selected hits`,
  `high16 = 0x02205CBA selected hits`)
- `0x02209B5C s94_effect_counts_b`
  (`low16 = 0x02205E7A selected hits`,
  `high16 = 0x02205E82 selected hits`)

Status bits:

- `0x0001`: mapper saw selected object `0xE1`.
- `0x0002`: exact selected primary flush seen.
- `0x0004`: exact owner body material seen.
- `0x0008`: non-body shadow-like material candidate seen.
- `0x0010`: selected-object effect-family hook seen.
- `0x0020`: exact selected flushes ran with no candidate observed yet.
- `0x0040`: non-body material seen in-window but rejected by the heuristic.

Expected interpretation:

- If effect-family counters tick in the good window but not the bad window, the
  fix likely belongs before or at effect/shadow creation/gating.
- If effects tick in both but a non-body material appears only in the good
  window, trace effect update/lifetime next.
- If both effects and material candidates tick similarly but only the good
  shadow is visible, trace candidate geometry/display-list/depth next.
- If no difference appears, the next step is a lower-level sprite/effect
  creation trace.

User correction:

- Do not run this S94 plan as written. The f027-f038 control window is
  grass-tile setup evidence, and shadow behavior on grass tiles is irrelevant.
- The only meaningful pass/fail window is the actual airborne hop after the
  selected Igglybuff has moved off grass/canopy toward non-grass floor tiles.

### S96 - Refresh Stock Wild Aux Setup Latch During Active Long-Hop

Purpose:

- S96 is a proposed visual fix.
- Prior probes showed the `0x021F78E6 -> 0x02205808` wild terrain/aux helper
  callsite did not run during the repro because the stock small-Pokemon
  callback's render-data latch was already set.
- Earlier S22/S24 called the aux helper manually, and S47 patched the helper
  callsite, but those attempts did not prove what happens when the stock
  callback naturally re-enters its own aux setup branch during the actual
  airborne grass-to-non-grass hop.

Patch plan:

- In `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`, while the
  custom diagonal long-hop is active, clear `renderData[0x17]` bit `0` through
  the known relation `renderData == object + 0x108` from S90.
- This should make the stock small-Pokemon draw callback re-run its existing
  wild aux update `0x02205808` on the next draw, with the normal stock
  arguments/order.
- Do not touch `posVec[1]`, `faceVec[1]`, `unk88[1]`, movement flags, terrain
  behavior sampling, field effects, raw G3 drawing, or global clearbits.

Expected success signal:

- The repaired ledge-spawn harness keeps `movement_pass=true` and changes the
  f075-f179 airborne non-grass shadow pass from `0 / 105` to passing.

Expected failure signal:

- The build overflows overlay 149, Pokemon movement regresses/stalls, or the
  f075-f179 shadow pass remains `0 / 105`, proving this stock aux latch is not
  the missing midair shadow owner.

Implementation:

- Added a C-only latch clear in
  `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`, clearing
  `object + 0x108 + 0x17` bit `0` while the custom diagonal long-hop is active.
- The patch was intentionally scoped to active custom long-hop frames and did
  not touch ARMIPS hooks, terrain behavior, field effects, or global render
  gates.

Build:

- UI build endpoint succeeded after the S96 patch and copied
  `test1611.nds` to the Delta ROM folder.

Verification:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s96_aux_latch_refresh \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Result:

- Exit status: `2`.
- Correct target selected: bbox `[105, 84, 118, 95]`.
- Correct hop tracked: `movement_pass.passed == true`,
  `movement_progress_pass.passed == true`.
- Meaningful window: f075-f179, the actual airborne/non-grass hop window.
- `shadow_pass.passed == false`.
- `shadow_pass.present_frame_count == 0 / 105`.
- `shadow_pass.max_missing_run == 105`.

Reviewer finding:

- S96 was effectively a retest of the old S60 latch-clear idea unless a new
  precondition could be proven.
- S69 already showed the relevant stock aux callsite did not run during the
  repro, and S96 still produced `0 / 105` accepted shadow frames in the corrected
  f075-f179 oracle window.

Conclusion:

- Rejected.
- The stock render-data setup latch is not the missing shadow owner for the
  grass-to-non-grass midair hop.
- The S96 source patch was removed before the next build.

### S97 - Owned Field-Effect Floor Shadow With Linger Lifetime

Purpose:

- S97 is a proposed visual fix, not a stock-shadow probe.
- The corrected harness window is f075-f179: the actual ledge-spawned
  Igglybuff hop after it has moved off grass/canopy toward non-grass floor
  tiles. Grass-only setup frames such as f027-f038 are intentionally ignored.
- S93 found no separate non-body shadow material from the selected primary
  actor, and S96 proved the stock aux/setup latch does not restore the floor
  shadow. Continuing to poke stock shadow gates is low value.
- S77 proved an owned field-effect floor mark can become visible, but it failed
  the movement/oracle story because the hop stalled. S97 keeps the owned
  visual strictly observational: no object flag, tile, position, movement, arc,
  param, id, gfx, or render-data writes.

Implementation plan:

- Re-enable the existing elapsed-2 hook in
  `OverworldWildSpawns_UpdateCanopyLongJumpDiagonalLanding`.
- Keep overlay 149 tiny: only call the existing base bridge
  `OverworldWildSpawns_CreateCanopyLongJumpShadowEffect`.
- Implement the effect owner in overlay 150, where there is space:
  - one effect handle per wild object ID slot,
  - create once per object/slot,
  - render a small dark floor quad from `object->posVec` only,
  - ignore `faceVec[1]` and `unk88[1]` for positioning so the shadow does not
    attach to the airborne body,
  - when the arc is no longer live after being seen, linger for enough frames to
    cover the f075-f179 landing tail, then self-destroy,
  - clear all live effects through the existing overlay-cleanup clear entry.

Expected success signal:

- UI build succeeds without overlay 149 overflow.
- The harness selects the ledge-spawned Igglybuff, keeps
  `movement_pass.passed == true` and `movement_progress_pass.passed == true`,
  and changes the f075-f179 `shadow_pass` from `0 / 105` to passing.

Expected failure signal:

- Overlay overflow, spawn crash, Pokemon/follower disappearance, movement
  regression, or `shadow_pass.present_frame_count == 0 / 105`.

Result:

- UI build succeeded and opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1613.nds`
- Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s97_owned_effect_linger \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

- Exit code: `2`.
- Target selection passed and picked the intended newly spawned ledge Igglybuff:
  bbox `[105, 84, 118, 95]`.
- `actual_left_hop_start_frame`: `27`.
- Movement failed before the authoritative f075-f179 window:
  - `movement_pass.passed=false`.
  - `movement_progress_pass.passed=false`.
  - Progress was only `9` pixels left, with `5` distinct center-X positions.
  - No left-progress record happened inside f075-f179.
  - `shadow_pass.tracked_percent=0` because the ledge-spawn target was no
    longer tracked as a valid body in the actual pass window.
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s97_owned_effect_linger_contact.png`
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s97_owned_effect_linger_summary.json`

Interpretation:

- S97 reproduced the old S77 owned-field-effect failure family. It can create
  a visual mark, but creating/owning a field effect during the long-hop update
  interferes with the movement/oracle story and prevents the real f075-f179
  off-grass-to-land hop from being evaluated.
- Reject this approach. The source patch was reverted back to a no-op shadow
  entry and the elapsed-2 effect bridge was disabled before the next build.

Rollback/control verification:

- UI build succeeded after reverting S97 to a no-op entry and disabling the
  elapsed-2 effect bridge.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1614.nds`
- Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s98_noop_control_after_s97_reject \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass
```

- Exit code: `0` because `--no-fail-on-shadow-pass` was used.
- `target_selection.passed=true`; selected bbox `[105, 84, 118, 95]`.
- `movement_pass.passed=true`.
- `movement_progress_pass.passed=true`.
- f075-f179 movement details:
  - `tracked_percent=100`.
  - `origin_left_delta=95`.
  - `window_left_delta=45`.
  - `left_progress_frames_in_shadow_window_count=25`.
- f075-f179 shadow result remains failed:
  - `shadow_pass.passed=false`.
  - `present_frame_count=0 / 105`.
  - `max_missing_run=105`.
- Interpretation: S98 re-establishes the clean moving baseline. Future fixes
  must preserve this movement pass and only change the f075-f179 shadow result.

### S99 - Stock Render-Call Floor Mark During Live Long-Hop Arc

Purpose:

- S99 is a proposed visual fix candidate for the corrected oracle window only:
  f075-f179, where the ledge-spawn Igglybuff performs the real off-grass to
  non-grass airborne hop.
- Per user correction, grass-tile shadow behavior in f027-f038 is irrelevant
  and must not be used as evidence.
- S97/S77 proved an owned dark floor mark can become visible, but field-effect
  ownership through `ov01_021F1620` regressed movement/spawn behavior.
- S90 proved the selected wild object reaches overlay 1 `0x021F7908 ->
  0x021FA3E8` with `r5 = object`, `r1 = primarySprite`, and
  `renderData == object + 0x108`.

Patch intent:

- Leave overlay 1 `0x021F7908 -> 0x021FA3E8` untouched.
- Hook the nearby post-primary callsite `0x021F7910`, preserving the stock call
  to `0x021F8C88` before drawing the mark. This keeps the S99 material writes
  out of the middle of the stock body-render sequence.
- After the stock call, if `[object + 0x08]` is a wild object ID
  `0xE0..0xE9` and the existing long-hop arc carrier
  `faceVec[1] | unk88[1]` is nonzero, draw a tiny dark untextured quad at the
  object's floor position (`posVec[0]`, `posVec[1] + 0x20`, `posVec[2]`).
- This intentionally uses the existing render-only arc state as the latch, so
  overlay 149 does not gain new storage or code.
- Do not create field effects, swap draw callbacks, change object flags, alter
  tile/current-position fields, or touch movement state.

Files/symbols:

- `armips/asm/overworlds.s`
- `OverworldWildSpawns_S99CanopyLongHopShadowWrapper`
- `OverworldWildSpawns_S99DrawFloorShadowMark`
- Overlay 1 hook: `0x021F7910`
- ARM9 helper pad: `0x02108D74..0x02108E9B`

Expected success signal:

- UI build succeeds.
- The harness selects the ledge-spawned Igglybuff.
- f075-f179 keeps `movement_pass.passed == true` and
  `movement_progress_pass.passed == true`.
- f075-f179 shadow detection changes from `0 / 105` to passing, with the mark
  floor-anchored rather than attached to the airborne body.

Expected failure signal:

- Build overflows/overlaps a padding area.
- Spawn/movement/follower visibility regresses.
- The mark is absent in f075-f179, appears attached to the airborne body, or
  leaks render state into later actors.

Implementation status:

- Patch candidate added by implementation-helper pass and then adjusted in the
  main thread to fit Thumb immediate-offset limits.
- First UI build failed because direct Thumb loads from object offsets
  `0x80`/`0x8C` were out of range. Replaced them with base-plus-small-offset
  loads from `object + 0x7C + 4` and `object + 0x88 + 4`.
- Follow-up UI build succeeded and copied/opened
  `.../Delta/ROMs/test1615.nds`.

Verification command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s99_render_call_floor_mark \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2` because the shadow oracle failed.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s99_render_call_floor_mark_contact.png`
- Summary:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s99_render_call_floor_mark_summary.json`
- Target selection remained correct:
  - `target_selection.passed=true`
  - selected bbox `[105, 84, 118, 95]`
- Corrected f075-f179 movement window remained clean:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
  - `left_progress_frames_in_shadow_window_count=25`
- Corrected f075-f179 shadow window still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`

Interpretation:

- S99 is movement-safe in the corrected off-grass hop window, but it does not
  produce a detected floor shadow under the ledge-spawn Igglybuff.
- Grass-only frames before the real off-grass hop remain irrelevant evidence.
- The raw mark either is not visible in the intended render context, is covered
  or culled, or lands outside the harness's floor-shadow core. Do not build the
  next attempt around f027-f038.

### S100 - Pre-Latched Stock Render-Call Floor Mark

Purpose:

- Test the cheapest reviewer-suggested failure mode from S99: the stock helper
  at `0x021F8C88` may mutate or clear the live long-hop carrier before the
  S99 wrapper checks it.
- Keep the same hook and render-only floor mark as S99, but decide whether to
  draw before calling stock, then draw after stock only if the pre-latched flag
  says yes.
- Continue to evaluate only the corrected f075-f179 off-grass to non-grass
  ledge-spawn Igglybuff window. Grass-only frames before this window remain
  irrelevant.

Patch intent:

- Hook overlay 1 `0x021F7910` as before.
- In `OverworldWildSpawns_S100CanopyLongHopShadowWrapper`, save the original
  call arguments, determine the wild slot and live/linger state before
  `bl 0x021F8C88`, restore the original `r0-r3`, call stock, then draw the
  floor mark afterward if the pre-latched flag was set.
- Preserve the no-movement-state rule: no object flags, tile/current-position
  fields, draw-callback swaps, or field effects.

Files/symbols:

- `armips/asm/overworlds.s`
- `OverworldWildSpawns_S100CanopyLongHopShadowWrapper`
- `OverworldWildSpawns_S100DrawFloorShadowMark`
- `OverworldWildSpawns_S100CanopyLongHopShadowLinger`
- Overlay 1 hook: `0x021F7910`

Planned verification command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s100_prelatched_floor_mark \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Expected success signal:

- UI build succeeds.
- Target selection and movement pass remain true.
- f075-f179 shadow changes from `0 / 105` to passing.

Expected failure signal:

- Build overflows the ARM9 helper pad or fails to assemble.
- Spawn/movement/follower visibility regresses.
- f075-f179 shadow remains `0 / 105`, proving the post-stock latch timing was
  not the reason S99 failed.

Build result:

- UI build succeeded.
- Copied/opened `.../Delta/ROMs/test1616.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s100_prelatched_floor_mark \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2` because the shadow oracle failed.
- Contact sheet:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s100_prelatched_floor_mark_contact.png`
- Summary:
  `documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s100_prelatched_floor_mark_summary.json`
- Target selection remained correct:
  - `target_selection.passed=true`
  - selected bbox `[105, 84, 118, 95]`
- Corrected f075-f179 movement window remained clean:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
  - `left_progress_frames_in_shadow_window_count=25`
- Corrected f075-f179 shadow window still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`

Interpretation:

- The S99 failure was not caused by checking the long-hop carrier after
  `0x021F8C88`.
- The next attempt should not keep changing latch timing. It should prove
  whether the raw draw is visible at all in the target's core shadow region, or
  switch to a stock sprite/floor-shadow path that already projects into that
  region.

### S101 - Floor-Mark Execution Status Instrumentation

Purpose:

- S98, S99, and S100 produced identical key-frame metrics, so the raw floor mark
  is not visibly affecting the f075-f179 oracle window.
- S101 keeps the S100 draw path but adds one byte of status instrumentation at
  `0x021103AC` to answer whether the hook/draw branch is actually firing.
- This is a diagnostic attempt, not a proposed production fix.

Status byte at `0x021103AC`:

- bit `0x01`: wrapper entered.
- bit `0x02`: wrapper saw a valid wild object slot.
- bit `0x04`: wrapper saw live long-hop arc carrier state.
- bit `0x08`: wrapper used lingered draw state.
- bit `0x10`: wrapper reached the raw draw call.

Patch intent:

- Keep overlay 1 hook `0x021F7910`.
- Keep the S100 pre-latched draw/linger behavior.
- Add status OR writes only; no movement state, object flags, tile/current
  positions, field effects, or draw callbacks are changed.

Planned verification command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s101_draw_status \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --memory-read s101_status:u8:0x021103AC \
  --memory-sample-every 5 \
  --no-fail-on-shadow-pass
```

Expected diagnostic outcomes:

- If status includes `0x10` but pixels stay identical to S98/S100, the draw call
  is firing but the raw G3 quad is invisible, culled, outside the render state,
  or not compatible with this callback phase.
- If status never includes `0x04`/`0x10`, the long-hop carrier is not present at
  this hook and the next attempt should move the latch/probe to a proven
  long-hop-owned callsite instead of changing draw material.

Build result:

- UI build succeeded.
- Copied/opened `.../Delta/ROMs/test1617.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s101_draw_status \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --memory-read s101_status:u8:0x021103AC \
  --memory-sample-every 5 \
  --no-fail-on-shadow-pass
```

Harness result:

- Exit code: `0` because `--no-fail-on-shadow-pass` was enabled for the
  diagnostic run.
- Corrected f075-f179 shadow window still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`
- Target selection and movement stayed valid:
  - selected bbox `[105, 84, 118, 95]`
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
- Final status byte was `0x1F`, so the wrapper entered, saw a wild slot, saw
  live arc state, used linger state, and reached the raw draw call.

Interpretation:

- The raw draw branch is definitely executing during the real f075-f179
  off-grass hop window.
- Artifact comparison found the custom dark mark visible but fixed near the top
  right of the screen, outside the target's under-body core. That points at a
  wrong owner or wrong matrix/projection contract rather than a grass-only
  oracle problem.

### S102 - Floor-Mark Owner And Coordinate Probe

Purpose:

- Keep the S101 raw draw/status behavior, but record the object id, wild slot,
  and position vector used when the wrapper decides to draw.
- Answer whether the displaced top-right mark belongs to the ledge-spawn
  Igglybuff or another wild object, and whether the world coordinates are sane
  during the corrected f075-f179 off-grass hop.
- Continue ignoring grass-only setup/scared frames.

Probe memory:

- `0x021103AC`: status byte, same bits as S101.
- `0x021103AD`: last drawing object's object id.
- `0x021103AE`: last drawing wild slot index.
- `0x021103B0`: last drawing object's `posVec.x`.
- `0x021103B4`: last drawing object's `posVec.z`.

Planned verification command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s102_draw_owner_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --memory-read s102_status:u8:0x021103AC \
  --memory-read s102_obj:u8:0x021103AD \
  --memory-read s102_slot:u8:0x021103AE \
  --memory-read s102_x:s32:0x021103B0 \
  --memory-read s102_z:s32:0x021103B4 \
  --memory-sample-every 5 \
  --no-fail-on-shadow-pass
```

Expected diagnostic outcomes:

- If the owner is not the ledge-spawn Igglybuff, fix the gate/linger owner
  before changing render state.
- If the owner is correct but the mark remains displaced, stop tuning latch
  timing and move the shadow canary into a render path that uses the stock
  actor/material projection.

Build result:

- First UI build failed because the S102 helper overflowed the ARM9 helper pad
  by `20` bytes.
- Shrunk status writes so the helper stores the byte once at function exit
  instead of OR-writing every bit to memory.
- Second UI build succeeded.
- Copied/opened `.../Delta/ROMs/test1618.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s102_draw_owner_probe \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --memory-read s102_status:u8:0x021103AC \
  --memory-read s102_obj:u8:0x021103AD \
  --memory-read s102_slot:u8:0x021103AE \
  --memory-read s102_x:s32:0x021103B0 \
  --memory-read s102_z:s32:0x021103B4 \
  --memory-sample-every 5 \
  --no-fail-on-shadow-pass
```

Harness result:

- Exit code: `0` because `--no-fail-on-shadow-pass` was enabled for diagnostics.
- Corrected f075-f179 shadow window still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`
- Target selection and movement stayed valid:
  - selected bbox `[105, 84, 118, 95]`
  - `movement_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
- Owner/coordinate result in the corrected f075-f179 window:
  - last drawing object was `0xE1`
  - last drawing slot was `1`
  - `posVec.x` advanced over the window
  - `posVec.z` stayed stable at `26312704`

Interpretation:

- The raw mark belongs to the intended ledge-spawn Igglybuff and the recorded
  object position changes during the real hop.
- The visible displaced top-right mark is therefore a raw-G3 render phase /
  projection problem, not a wrong owner or irrelevant grass-only harness frame.
- Remove the S102 raw draw probe before testing production-shaped fixes.

### S103 - Keep Body Arc In `unk88[1]`, Floor-Zero `faceVec[1]`

Purpose:

- Test the smallest non-renderer state split that current notes do not rule out:
  leave the visible body carrier in `object->unk88[1] = arc`, but stop mirroring
  the arc into `object->faceVec[1]` during the custom long-hop frame.
- This keeps the single existing jump presentation path and avoids field
  effects, raw G3, draw-callback swaps, terrain/tile-field writes, and new
  overlay-149 systems.
- Continue to evaluate only the corrected f075-f179 off-grass hop.

Patch intent:

- Remove the temporary S102 ARMIPS hook and helper.
- In `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`, set
  `object->faceVec[1] = 0` while keeping `object->unk88[1] = arc`.

Expected success signal:

- UI build succeeds.
- The ledge-spawn Igglybuff still visibly hops and `movement_pass.passed` stays
  true.
- f075-f179 `shadow_pass.present_frame_count` improves from `0 / 105`.

Expected failure signal:

- Pokemon no longer visibly hop, the arc shape changes badly, follower/spawn
  visibility regresses, or the shadow remains `0 / 105`.

Build result:

- UI build succeeded.
- Copied/opened `.../Delta/ROMs/test1619.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s103_facevec_floor_unk88_arc \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass
```

Harness result:

- Exit code: `0` because `--no-fail-on-shadow-pass` was enabled.
- Target selection remained correct:
  - selected bbox `[105, 84, 118, 95]`
- Corrected f075-f179 movement window remained clean:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
- Corrected f075-f179 shadow window still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`

Interpretation:

- The one-line `faceVec[1]` floor-zero split is movement-safe, but it does not
  affect the missing midair floor shadow.
- Restore `object->faceVec[1] = arc`; the missing shadow owner is not the
  mirrored `faceVec[1]` value.

### S104 - Downstream Stock-Projected Floor Canary

Purpose:

- S104 is a proposed diagnostic/fix canary for the corrected oracle window
  only: f075-f179, where the ledge-spawn Igglybuff is in the real off-grass to
  non-grass hop. Grass-only setup/scared frames such as f027-f038 are ignored.
- S101/S102 proved the raw overlay-1 G3 floor mark executes for the correct
  owner and sane position, but appears in the wrong screen region. That means
  the overlay object callback is the wrong projection contract.
- S90-S93 proved the selected `0xE1` primary actor reaches the downstream ARM9
  GX command-list path throughout f075-f179, but only emits the opaque body
  material. S104 tests whether an owned floor mark can be emitted from that
  same downstream projection phase.

Patch intent:

- Hook overlay 1 `0x021F7908 -> 0x021FA3E8` only to save the selected
  `0xE1` object and primary actor pointer.
- Hook ARM9 `0x020C0458 -> 0x020C2528`, preserving the stock material enqueue,
  then, only when `[r7 + 4]` matches the saved selected actor and the saved
  object has active long-hop lift, enqueue a tiny dark quad.
- The quad is emitted through the stock command-list enqueue helper, not raw
  G3 writes in the overlay object callback. It uses a matrix push/translate/pop
  around the canary so the dark mark is lowered back toward the floor instead
  of riding with the lifted body.
- Keep `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset` unchanged:
  `faceVec[1] = arc` and `unk88[1] = arc`.

Expected success signal:

- UI build succeeds.
- Strict harness exits `0` without `--no-fail-on-shadow-pass`.
- `movement_pass.passed=true`, `movement_progress_pass.passed=true`, and
  `shadow_pass.passed=true` in f075-f179.

Expected failure signal:

- Build overflow/assembly failure, spawn/hop regression, crash, or strict
  f075-f179 shadow pass remains `0 / 105`.

Result:

- Initial build failed on an invalid Thumb `adds` form in the mapper helper;
  changed it to `mov` + `add`.
- Second build failed because the first ARM helper placement overflowed; moved
  the helper to the earlier free ARM9 padding window.
- Third build succeeded, but the strict harness failed target selection because
  the first mapper helper location was later overwritten by another ARMIPS
  patch. This regressed the overlay hook into fill bytes and prevented the
  ledge-spawn target from appearing.
- Moving the mapper helper to `0x02108D74` fixed the spawn regression.
- UI build then succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1622.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s104_downstream_floor_canary_v2 \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --shadow-check-start-frame 75 \
  --shadow-check-end-frame 179 \
  --memory-read s104_status:u32:0x021103AC \
  --memory-read s104_emit_count:u32:0x021103B0 \
  --memory-read s104_lift_sample:s32:0x021103B4 \
  --memory-sample-every 5
```

Harness result:

- Strict exit: `2`.
- Target selection passed for the corrected upper ledge Igglybuff:
  bbox `[105, 84, 118, 95]`.
- Corrected f075-f179 movement stayed valid:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
- S104 canary fired for the selected actor:
  - `s104_status=0x0000000F`
  - `s104_emit_count=200`
  - `s104_lift_sample=-11564`
- Corrected f075-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`

Interpretation:

- The downstream selected-actor/material hook is live during the real off-grass
  hop, so the owner gate is useful.
- The injected primitive draws visibly, but as a large black block displaced
  from the Igglybuff instead of as a floor shadow under the body.
- Because the current long-hop writes the same vertical arc into both
  `faceVec[1]` and `unk88[1]`, S104's `-(faceVec[1] + unk88[1])` compensation
  likely double-compensates. The primitive also remains too large and opaque to
  judge as a production shadow.

### S105 - Tiny One-Arc Downstream Floor Canary

Purpose:

- Keep only the proven S104 owner/lift gate and test whether the downstream
  matrix can place a small floor primitive under the selected Igglybuff during
  the authoritative f075-f179 off-grass hop.
- Grass-only setup/scared frames such as f027-f038 remain irrelevant.

Patch intent:

- Reuse the S104 overlay mapper and ARM9 material-wrapper hook.
- Change vertical compensation from `-(faceVec[1] + unk88[1])` to
  `-faceVec[1]`; both fields currently carry the same arc, so this removes the
  obvious double-lift error.
- Shrink the quad from roughly `0x3000 x 0x1800` to `0x1000 x 0x0800`.
- Lower the polygon alpha from full opaque to a moderately dark canary.

Expected success signal:

- UI build succeeds.
- Strict harness exits `0`.
- `movement_pass.passed=true`, `movement_progress_pass.passed=true`, and
  `shadow_pass.passed=true` in f075-f179.

Expected failure signal:

- Spawn/hop regression, crash, or the canary still appears displaced/attached
  while the strict f075-f179 shadow result remains failed.

Build result:

- UI build succeeded.
- Copied/opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1623.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s105_tiny_one_arc_downstream_floor_canary \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --shadow-check-start-frame 75 \
  --shadow-check-end-frame 179 \
  --memory-read s105_status:u32:0x021103AC \
  --memory-read s105_emit_count:u32:0x021103B0 \
  --memory-read s105_lift_sample:s32:0x021103B4 \
  --memory-sample-every 5
```

Harness result:

- Strict exit: `2`.
- Target selection passed for the corrected upper ledge Igglybuff:
  bbox `[105, 84, 118, 95]`.
- Corrected f075-f179 movement stayed valid:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `window_left_delta=47`
- S105 canary fired:
  - `s105_status=0x0000000F`
  - `s105_emit_count=200`
  - `s105_lift_sample=-5782`
- Corrected f075-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`

Interpretation:

- The smaller one-arc canary still does not become an accepted floor shadow.
- The broad diagnostic sees dark pixels in many frames, but the strict core
  stays failed because the canary is not locally centered under the Igglybuff.
- Contact-sheet inspection shows the canary remains in the wrong projected
  area while the body moves left. This means the downstream material-wrapper
  command-list injection is not using the floor/body projection contract we
  need.
- Stop tuning this path as a production fix. If it is used again, it should be
  only as instrumentation. The next fix attempt should target the stock
  primary sprite/floor-shadow owner or create an owned floor visual outside the
  material wrapper.

### S106 - Raw Display-List Actor-Matrix Floor Canary

Purpose:

- Continue evaluating only the corrected f075-f179 window, where the
  ledge-spawn Igglybuff performs the real off-grass to non-grass hop. Grass
  setup/scared frames such as f027-f038 are irrelevant.
- S104/S105 proved the selected actor gate is live, but the material-wrapper
  hook at `0x020C0458` uses the wrong projection/matrix contract: the canary
  draws displaced while the body moves left.
- Test the next downstream boundary recommended by the renderer probes: the
  actor raw display-list callsite at `0x020C23B0 -> 0x020C2474`, after the
  selected actor's stock shape display list has been submitted.

Patch intent:

- Keep the overlay selected-object mapper at `0x021F7908`, saving object
  `0xE1`, primary actor, and `primary + 0x30`.
- Restore the failed material-wrapper hook at `0x020C0458` to stock.
- Hook only the raw display-list callsite `0x020C23B0`.
- The wrapper calls stock `0x020C2474` first, then, only when `[r7 + 4]`
  matches the saved selected actor owner and the saved object has active
  long-hop lift, emits the same tiny dark canary through `0x020C2528`.
- Translate by `-(faceVec[1] + unk88[1])` because stock position building
  includes both fields in the visible body lift for the current long-hop
  presentation.
- Record lightweight status/emit/lift diagnostics at `0x021103AC..0x021103B7`.

Expected success signal:

- UI build succeeds.
- Strict harness exits `0`.
- `movement_pass.passed=true`, `movement_progress_pass.passed=true`, and
  `shadow_pass.passed=true` in f075-f179.

Expected failure signal:

- Spawn/hop regression, crash, or the canary still appears displaced/attached
  while strict f075-f179 shadow remains `0 / 105`.

Build/review result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1624.nds`.
- The probe was invalidated before harness verification by read-only review:
  at `0x020C23B0`, `r7` is not an owner pointer. The `[r7 + 4]` owner gate
  only applies to the earlier material path at `0x020C0458`.
- No harness run was used as evidence for S106, because the callsite register
  assumption was wrong and could contaminate or crash the result.

Conclusion:

- Replace S106 with a selected-primary flush flag around the known
  `0x0201F580 -> 0x020BFCC8` flush call, then let the raw display-list wrapper
  key off that flag during the selected actor's real flush window.

### S107 - Selected-Flush Raw Display-List Canary

Purpose:

- Continue the S106 idea with the corrected raw display-list ownership
  contract. The authoritative window remains f075-f179; grass-only setup
  frames remain irrelevant.
- Avoid using `[r7 + 4]` at `0x020C23B0`.

Patch intent:

- Keep the overlay selected-object mapper at `0x021F7908`.
- Add a Thumb wrapper at `0x0201F580`, replacing stock
  `blx 0x020BFCC8`, to set an internal `selected_flush_active` status bit only
  while the selected primary actor's flush is running.
- Hook ARM raw display-list callsite `0x020C23B0`, call stock `0x020C2474`
  first, then emit a tiny canary only when `selected_flush_active` is set and
  the saved object has active long-hop lift.
- Store diagnostics in the existing hidden S106/S107 window:
  `status`, `emit_count`, and `lift_sample` at `0x021103AC..0x021103B7`.

Expected success signal:

- UI build succeeds.
- Strict harness exits `0`.
- f075-f179 keeps movement valid and gains stable floor-shadow detection.

Expected failure signal:

- Build failure, spawn/hop regression, crash, or strict f075-f179 shadow still
  fails with the canary displaced or absent.

First build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1625.nds`.
- Strict harness did not reach the shadow question. Target selection failed
  because no new upper ledge Igglybuff appeared after LEFT:
  `target_selection.passed=false`, `eligible_candidate_count=0`.
- S107 diagnostics stayed zero:
  `s107_status=0`, `s107_emit_count=0`, `s107_lift_sample=0`.
- Byte check showed the direct cause: `0x0201F580` branched to
  `0x02071C54`, but `0x02071C54..` was still `0xFF` fill in the built
  `base/arm9.bin`. The Thumb helper was not emitted in that pad.

Adjustment:

- Move the Thumb flush wrapper to the proven ARM9 zero pad immediately after
  the overlay mapper, `0x02108DC0`, and rebuild before rerunning the same
  strict harness.

Second build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1626.nds`.
- Byte checks confirmed:
  - `0x0201F580` branches to `0x02108DC0`.
  - `0x02108DC0` contains the emitted Thumb flush wrapper.
  - `0x020C23B0` branches to the S107 raw display-list wrapper.
  - `0x020C0458` is restored to stock.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s107b_selected_flush_raw_display_canary \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --shadow-check-start-frame 75 \
  --shadow-check-end-frame 179 \
  --memory-read s107_status:u32:0x021103AC \
  --memory-read s107_emit_count:u32:0x021103B0 \
  --memory-read s107_lift_sample:s32:0x021103B4 \
  --memory-sample-every 5
```

Harness result:

- Strict exit: `2`.
- Target selection passed for the corrected upper ledge Igglybuff:
  bbox `[105, 84, 118, 95]`.
- Corrected f075-f179 movement stayed valid:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
- Corrected f075-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`
- Diagnostics:
  - `s107_status=0x00000003`
  - `s107_emit_count=0`
  - `s107_lift_sample=0`

Interpretation:

- The selected-object mapper and the selected-primary flush wrapper both fire.
- The raw display-list wrapper does not see the selected-flush active bit while
  it is scoped only around `0x0201F580 -> 0x020BFCC8`. It therefore does not
  emit the canary.
- This does not prove the raw display-list phase is useless; it proves it is
  not nested inside that narrow selected-flush call. The cheapest next
  distinction is to keep a pending selected-flush latch until a later raw-list
  call sees active long-hop lift.

### S108 - Pending Selected-Flush Raw Display-List Canary

Purpose:

- Test whether the relevant raw display-list phase runs shortly after, rather
  than inside, the selected-primary flush wrapper from S107.
- Continue using only the corrected f075-f179 off-grass hop as evidence.

Patch intent:

- Keep the S107 mapper, selected-flush wrapper, and raw display-list hook.
- Change the selected-flush bit from scoped-active to pending: the flush
  wrapper sets bit `0x100`, and the raw display-list wrapper clears it only
  after it sees pending plus active long-hop lift and emits the canary.
- Record the same diagnostics at `0x021103AC..0x021103B7`.

Expected success signal:

- Target selection and movement still pass.
- `s108_emit_count` becomes positive.
- Strict f075-f179 shadow passes, or contact-sheet inspection shows where the
  emitted canary lands if the strict oracle still fails.

Expected failure signal:

- Spawn/hop regression, crash, `emit_count` remains `0`, or the canary is
  emitted but still displaced from the Igglybuff's floor shadow core.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1627.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s108_pending_flush_raw_display_canary \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --shadow-check-start-frame 75 \
  --shadow-check-end-frame 179 \
  --memory-read s108_status:u32:0x021103AC \
  --memory-read s108_emit_count:u32:0x021103B0 \
  --memory-read s108_lift_sample:s32:0x021103B4 \
  --memory-sample-every 5
```

Harness result:

- Strict exit: `2`.
- Target selection passed for the corrected upper ledge Igglybuff:
  bbox `[105, 84, 118, 95]`.
- Corrected f075-f179 movement stayed valid:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=45`
- Corrected f075-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`
- Diagnostics:
  - `s108_status=0x0000010F`
  - `s108_emit_count=200`
  - final `s108_lift_sample=-11564`

Interpretation:

- The pending latch proves a raw display-list call does occur after the
  selected flush while the saved object has active hop lift.
- The emitted primitive still does not become an accepted under-body floor
  shadow. Contact-sheet inspection shows it remains in the displaced/projection
  failure family rather than centered under the Igglybuff.
- This is strong evidence that hand-emitting a primitive through the raw
  display-list/GX command path is not enough; the missing shadow likely needs
  either a stock shadow sprite/effect owner or a floor-space coordinate path
  rather than more command-list canary tuning.

### S109 - Material-Owner Pending Raw Display-List Canary

Purpose:

- Run one final owner-specific raw-list timing probe before abandoning the
  command-list canary family.
- S108 proved a pending selected-flush latch can reach later raw-list calls,
  but it did not prove those calls belonged to the selected actor's exact
  material/shape phase.
- Reuse the known-good material owner gate from S104/S105 only to set pending;
  do not draw from the material hook itself.

Patch intent:

- Keep the selected-object mapper at `0x021F7908`.
- Restore the selected-flush wrapper at `0x0201F580` to stock.
- Hook `0x020C0458 -> 0x020C2528` with a wrapper that:
  - calls stock `0x020C2528`,
  - checks `[r7 + 4] == savedActor30`,
  - sets pending bit `0x100` and status bit `0x0002` when the exact material
    owner is observed.
- Keep the raw display-list hook at `0x020C23B0`, but consume the material-owner
  pending bit there before emitting the tiny canary.
- Store diagnostics at `0x021103AC..0x021103B7`:
  - `0x0001`: mapper saw selected `0xE1`
  - `0x0002`: exact material owner set pending
  - `0x0004`: raw wrapper consumed pending
  - `0x0008`: canary emitted
  - `0x0010`: pending consumed with null object
  - `0x0020`: pending consumed with zero lift
  - `0x0040`: raw wrapper ran without pending
  - `0x0100`: pending currently set

Expected success signal:

- Target selection and movement pass.
- `emit_count` becomes positive.
- Strict f075-f179 shadow passes, or contact-sheet inspection shows an
  owner-specific raw canary under the Igglybuff.

Expected failure signal:

- Build failure, spawn/hop regression, crash, `emit_count=0`, or emitted
  canary still displaced from the strict floor-shadow core.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1628.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s109_material_owner_pending_raw_display_canary \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --shadow-check-start-frame 75 \
  --shadow-check-end-frame 179 \
  --memory-read s109_status:u32:0x021103AC \
  --memory-read s109_emit_count:u32:0x021103B0 \
  --memory-read s109_lift_sample:s32:0x021103B4 \
  --memory-sample-every 5
```

Harness result:

- Strict exit: `2`.
- Contact sheet was fully black, so this run did not produce usable visual
  evidence for the authoritative f075-f179 hop window.
- Target selection failed and movement did not pass:
  - `target_selection.passed=false`
  - `movement_pass.passed=false`
  - `movement_progress_pass.passed=false`
- Corrected f075-f179 shadow result remained failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`
- Diagnostics:
  - `s109_status=0x00000001`
  - `s109_emit_count=0`
  - `s109_lift_sample=0`

Interpretation:

- The mapper saw selected object `0xE1`, but the exact material-owner pending
  wrapper never observed the saved owner, and the raw display-list wrapper never
  emitted.
- Because the screen went black, S109 is a regressive/invalid probe rather than
  a meaningful shadow attempt.
- This reinforces the S108 conclusion: stop spending attempts on raw
  GX/display-list canaries and move to a stock shadow/effect-owner or
  floor-space lifecycle path that preserves normal rendering.

### S110 - Follower-Target Floor Sample Effect Resolver

Purpose:

- Try the stock overlay-1 effect target path instead of raw GX/display-list
  canaries.
- Hook the two callsites that normally resolve the follower's primary actor for
  the effect sequence:
  - overlay 1 `0x02205CB4`
  - overlay 1 `0x02205E7A`
- During active wild long-hop frames, attempt to sample the owning object at
  floor height, then fall back to the stock follower resolver otherwise.

Patch result:

- Added `OverworldWildSpawns_FloorSampleEffectTarget` in the ARM9
  `0x02071C54..0x02071CA0` helper cave.
- The helper incorrectly treated incoming `r0` as a `LocalMapObject *`.
- Follow-up disassembly shows both hook sites load `r0` from `[r5 + 0x3C]`,
  which is the map-object manager/context passed to stock `0x021F771C`, not the
  wild object.
- Stock `0x021F771C` then hardcodes object id `0xFD`, calls
  `GetMapObjectByID`, calls `0x0205F40C`, and returns the follower primary
  actor.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1630.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s110_floor_sample_effect_target \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --shadow-check-start-frame 75 \
  --shadow-check-end-frame 179
```

Harness result:

- Strict exit: `2`.
- Target and movement passed.
- Corrected f075-f179 shadow failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=0 / 105`
  - `max_missing_run=105`

Diagnostic pre-roll result:

- Additional capture with `--contact-start-frame 55` confirmed the user's
  visual report that the old shadow mark blinks once around `f065`.
- The `f065` mark is diagnostic only. It is not evidence of a fix, because the
  later corrected authoritative off-grass to non-grass hop window is
  `f064..f179`.
- In the same run, the strict oracle still reported `0 / 105` accepted shadow
  frames for the then-current `f075..f179` window. This run is retained as
  historical evidence only; future runs use `f064..f179`.

Interpretation:

- S110 did not actually retarget the stock effect helper to the wild object.
- The single-frame `f065` ledge blink is the existing transient behavior, not a
  stable midair floor shadow.
- The next patch should keep the same stock effect-target callsites, but replace
  the helper with a manager-aware wild-object resolver.

### S111 - Manager-Aware Wild Effect Target Resolver

Purpose:

- Correct the S110 mistake while staying in the stock overlay-1 effect-target
  family.
- Avoid overlay 149 growth and avoid returning to raw GX/display-list probes.

Patch intent:

- Replace `OverworldWildSpawns_FloorSampleEffectTarget` with a compact Thumb
  helper that treats incoming `r0` as the map-object manager/context.
- Scan wild object ids `0xE0..0xE9` with `GetMapObjectByID` (`0x0205EE60`).
- Select the first wild object whose long-hop lift is active:
  - `object + 0x80` (`faceVec[1]`)
  - `object + 0x8C` (`unk88[1]`)
- Return the selected object's primary actor using `0x0205F40C` and `ldr [r0]`.
- Fall back to stock `0x021F771C(manager)` if no active wild long-hop object is
  found.

Expected success signal:

- Target selection and movement still pass.
- f064-f179 shadow pass reports a stable accepted shadow, not just the f065
  blink.

Expected failure signal:

- Build overflow in the small ARM9 cave, crash/spawn regression, or the strict
  f064-f179 oracle still reports no stable shadow.
- If this fails with good movement, the likely reason is that returning the wild
  primary actor still samples the airborne actor transform rather than a
  floor-space owner.

Window correction:

- After the first S111 run, the user clarified that the harness should evaluate
  `f064..f179`, not `f075..f179`, because the visible one-frame ledge blink is
  around `f065`.
- The pass rule still requires stable coverage and keeps
  `shadow_check_max_missing_run=3`, so a one-frame blink cannot satisfy the
  oracle by itself.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1631.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s111_manager_aware_effect_target_f064 \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- Target and movement passed:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=55`
- Corrected f064-f179 shadow failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=7 / 116`
  - `present_frames=64..70`
  - `present_percent=6`
  - `max_missing_run=109`
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s111_manager_aware_effect_target_f064_contact.png`.

Review notes:

- The compact scan fits the ARM9 helper cave and preserves `r4-r6, lr`.
- It scans `0xE0..0xE9` and falls back to stock if no active lifted wild object
  is found.
- A follow-up safety improvement could add a null-primary fallback before
  returning the selected object's actor, but this would not explain the shadow
  failure because the harness did not crash and movement remained valid.

Interpretation:

- S111 correctly fixes the S110 manager/object mistake, but the effect-target
  path still only captures the early ledge blink.
- The real midair window remains missing after frame `70`.
- Continue investigating either why the overlay-1 effect target does not
  provide a per-frame floor-space shadow, or return to the S78 clue where stock
  shadow existed but movement stalled.

### S112 - Render-Interval Native Start Bits With Movement-Entry Clear

Purpose:

- Follow the strongest useful clue from S78 without repeating its movement
  freeze.
- S78 proved the stock floor-shadow path can appear when
  `BIT_MOVE_START | BIT_JUMP_START` remain visible, but preserving those bits
  globally stalled the custom long-hop.
- S84 proved restoring those bits at the end of the small draw callback is too
  narrow.

Patch intent:

- Remove the failed S111 effect-target hooks so this attempt is isolated.
- Hook the stock small-Pokemon draw callback entry at overlay 1 `0x021F7894`.
- For wild object ids `0xE0..0xE9` with `MAPOBJECTFLAG_UNK13` set, OR
  `0x00010004` (`BIT_MOVE_START | BIT_JUMP_START`) into `object->flags`, then
  return to the stock callback body without restoring the bits immediately.
- Hook ARM9 `0x0205FE48`, the stock movement cleanup/update entry identified by
  S76, and clear the injected `0x00010004` for wild objects with
  `MAPOBJECTFLAG_UNK13` before the stock movement logic's first bit test.
- Do not touch `posVec`, `faceVec`, `unk88`, field effects, raw display lists,
  overlay 149, or manual long-hop interpolation.

Expected success signal:

- f064-f179 movement remains valid.
- f064-f179 shadow pass reports stable accepted shadow coverage after the
  f064-f070 ledge blink.

Expected failure signal:

- Shadow still disappears after f070, proving the missing native shadow is not
  only a post-callback flag-lifetime issue.
- Movement stalls or changes, proving the movement-entry clear is still too
  late or too broad.

#### S112a - Invalid Entry-BL Trampoline

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1632.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s112_render_interval_start_bits \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- Invalid visual repro:
  - ready screenshot fully black
  - `target_selection.passed=false`
  - `actual_left_hop_start_frame=null`
  - `movement_pass.passed=false`
  - `shadow_pass.passed=false`

Interpretation:

- This was a trampoline regression, not a valid S112 shadow result.
- Both initial hooks used `bl` at function entry:
  - overlay 1 `0x021F7894`
  - ARM9 `0x0205FE48`
- Because `bl` overwrites `lr` before the stock prologue has saved the caller
  return address, the helpers saved the hook return address instead of the
  original caller return address. The stock `pop {..., pc}` then returned into
  the middle of the hooked function instead of back to its real caller.
- S112b must preserve entry LR:
  - use an `ldr/bx` branch at the overlay-1 draw entry and let the helper execute
    the overwritten prologue plus the overwritten `0x0205F40C` call before
    jumping back to `0x021F789C`,
  - move the ARM9 movement-entry hook after the original `push {r4, lr}` so the
    caller return is already saved before using `bl`.

#### S112b - Correct Trampolines, Draw-Entry Bit Exposure

Patch result:

- Replaced the overlay-1 draw-entry `bl` with an `ldr/bx` trampoline so the
  original callback `lr` survives.
- Moved the movement-entry clear hook from `0x0205FE48` to `0x0205FE4A`, after
  the stock `push {r4, lr}`.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1633.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s112b_render_interval_start_bits_trampoline \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- Target and movement passed:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=55`
- Corrected f064-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=7 / 116`
  - `present_frames=64..70`
  - `present_percent=6`
  - `max_missing_run=109`

Interpretation:

- Correctly preserving LR fixes the black-screen regression from S112a.
- Exposing `BIT_MOVE_START | BIT_JUMP_START` at draw-entry and leaving them
  live after the callback is still too late or not the right lifetime. It
  produces the same early ledge blink only.
- The next attempt should move the exposure earlier: immediately after the
  known S76 clearer at `0x0205FE60`, while still clearing the injected bits
  before the next movement bit-test at `0x0205FE4E`.

### S113 - Re-Expose Native Start Bits After Known Stock Clearer

Purpose:

- Test whether the stock shadow path needs the native start bits live before the
  draw callback begins, not merely during or after it.
- Keep the S112 movement-entry clear so the bits are removed before the next
  movement bit-test.

Patch intent:

- Remove the S112 overlay-1 draw-entry hook.
- Keep an ARM9 hook after the stock movement function prologue at `0x0205FE4A`
  to clear injected `0x00010004` before the stock `BIT_MOVE_START` test.
- Wrap the exact S76-known stock clear call at `0x0205FE60`:
  - call stock `MapObject_ClearBits(object, 0x00010004)`,
  - if the object id is `0xE0..0xE9` and `MAPOBJECTFLAG_UNK13` is set, OR
    `0x00010004` back into `object->flags`.
- This should leave the native start bits live from movement cleanup through the
  render frame, but clear them before the next movement update can react.

Expected success signal:

- f064-f179 movement remains valid.
- Shadow coverage continues after f070 instead of only showing the ledge blink.

Expected failure signal:

- Same `7 / 116` shadow frames, meaning pre-draw flag lifetime is not enough.
- Movement stalls, meaning the bits still leak into movement logic too early.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1634.nds`.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s113_reexpose_after_known_clear \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- Target and movement passed:
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=57`
- Corrected f064-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=8 / 116`
  - `present_frames=64..71`
  - `present_percent=7`
  - `max_missing_run=108`
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s113_reexpose_after_known_clear_contact.png`.

Interpretation:

- S113 is movement-safe, but it only extends the early ledge blink by one frame.
- The cheap native start-bit lifetime family is not enough:
  - S78: shadow passes but movement freezes.
  - S84/S112/S113: movement passes but shadow remains only f064-f070/f071.
- Pivot back to terrain/shadow suppression. The acceptable product behavior is a
  stable floor shadow regardless of grass/canopy terrain, so a guarded terrain
  gate bypass may be more direct than further flag lifetime attempts.

### S114 - Keep Terrain Latch Positive On Zero-Return Long-Hop Frames

Purpose:

- Test the narrow reviewer-recommended latch path instead of forcing the whole
  terrain gate return.
- S86 proved the selected `0xE1` object reaches the terrain gate and receives
  both zero and nonzero returns while the shadow is missing.
- S87/S88 proved the same object reaches the primary depth helper and final
  vector writeback through the missing-shadow window.
- S113 proved the native start-bit lifetime family still only keeps the early
  f064-f071 blink.

Patch intent:

- Remove the failed S113 movement/start-bit hooks from the live source.
- Hook overlay 1 `0x021F8E52`, replacing the zero-return path's
  `mov r0, #0; strb r0, [r4, #21]`.
- At that point, `r4 = renderData` and `r5 = LocalMapObject *object`.
- For wild object IDs `0xE0..0xE9` with `MAPOBJECTFLAG_UNK13` set, write `1`
  to `renderData[0x15]`; otherwise preserve stock behavior and write `0`.
- Do not force the terrain gate return, do not change the `-0x2000` Y
  adjustment, do not touch movement state, field effects, raw display lists,
  object IDs, or overlay 149 code.

Expected success signal:

- UI build succeeds.
- f064-f179 target selection, movement, and movement-progress checks pass.
- f064-f179 shadow coverage continues after the early blink and satisfies the
  strict shadow oracle.

Expected failure signal:

- The result stays around `7-8 / 116` present frames, proving
  `renderData[0x15]` alone is not the missing floor-shadow owner.
- Movement regresses, build fails, or the Pokemon/follower visibility regresses.

Implementation result:

- Removed the failed S113 movement/start-bit hooks from `armips/asm/fairy.s`.
- Added an overlay 1 hook at `0x021F8E52`:
  `mov r0, #0; strb r0, [r4, #21]` ->
  `bl OverworldWildSpawns_KeepTerrainLatchForWildLongHop`.
- Added the helper in the ARM9 `0x02110258..0x021102A3` padding window.
- Built-byte spot check after the UI build:
  - `base/overlay/overlay_0001.bin` at `0x021F8E52` is patched to
    `17 f7 01 fa`.
  - The terrain-gate call at `0x021F8E3A` remains stock `00 f0 c1 f8`.
  - The primary depth helper call at `0x021F8E2E` remains stock
    `2b f6 69 f8`.

Build result:

- UI build succeeded and opened:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1635.nds`.
- Build elapsed `0:43`.
- Only the existing unrelated unused-parameter warning in
  `src/battle/battle_script_commands.c` was reported.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s114_keep_terrain_latch \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- The run used the authoritative `f064..f179` window:
  - `authoritative_run.passed=true`
  - `actual_shadow_window=[64,179]`
- Target and movement passed:
  - `target_selection.passed=true`
  - `actual_left_hop_start_frame=27`
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=55`
- Corrected f064-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=7 / 116`
  - `present_frames=64..70`
  - `present_percent=6`
  - `max_missing_run=109`
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s114_keep_terrain_latch_contact.png`.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s114_keep_terrain_latch_summary.json`.

Interpretation:

- S114 is movement-safe, but it is visually equivalent to the pre-S113
  failure: the shadow only passes in the early f064-f070 blink.
- Keeping `renderData[0x15]` positive on the zero-return terrain branch does
  not create or preserve the missing floor-shadow owner.
- Do not repeat the `renderData[0x15]` latch-only path without a new variable.

### S115 - Emulate Full Terrain-Positive Branch On Zero-Return Frames

Purpose:

- S114 only kept `renderData[0x15]` positive on the zero-return terrain path.
- S88 showed the stock terrain-positive branch normally couples that latch with
  a `finalVec.y -= 0x2000` adjustment before `0x0205F97C` writes the sprite
  vector.
- Test the materially new variable by making the zero-return branch emulate the
  full terrain-positive behavior for wild long-hop objects.

Patch:

- Kept the overlay 1 hook at `0x021F8E52`.
- Replaced the S114 helper with
  `OverworldWildSpawns_EmulateTerrainBranchForWildLongHop`.
- For wild IDs `0xE0..0xE9` with `MAPOBJECTFLAG_UNK13`, the helper wrote
  `renderData[0x15] = 1` and subtracted `0x2000` from `[sp + 0x0C]`.
- Everything else preserved the stock zero-return behavior.

Build result:

- UI build succeeded and opened `test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1636.nds`.
- Build elapsed `0:58`.
- Warnings were limited to the existing generated-profile missing `hopTime`
  initializers and the unrelated battle unused parameter.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s115_full_terrain_branch \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- The run used the authoritative `f064..f179` window.
- Target selection failed before the real shadow question:
  - `target_selection.passed=false`
  - no newly spawned ledge Igglybuff was found in the upper ROI
  - `actual_left_hop_start_frame=null`
  - `tracked_percent=0`
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s115_full_terrain_branch_contact.png`.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s115_full_terrain_branch_summary.json`.

Interpretation:

- The full branch emulation was register/stack safe enough to build and run,
  but the guard was too broad: it altered the spawn/setup/scared-hop phase
  before the harness could select the ledge-spawned Igglybuff.
- This is not a valid shadow improvement and should not remain live.

### S115b - Full Terrain Branch Only After Native Start Bits Clear

Purpose:

- Preserve the S115 idea while avoiding the spawn/scared setup regression.
- S85 showed the real failing window usually has native start bits already
  cleared, while the setup/scared phase can still expose them.
- Narrow the S115 helper so it refuses to emulate the terrain-positive branch
  when `BIT_JUMP_START` or `BIT_MOVE_START` is present.

Patch:

- Kept the `0x021F8E52` hook and `finalVec.y -= 0x2000` behavior.
- Added guards that fall back to stock zero-return behavior when
  `object->flags & BIT_JUMP_START` or `object->flags & BIT_MOVE_START` is set.

Build result:

- UI build succeeded and opened `test.nds`.
- Delta copy:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1637.nds`.
- Build elapsed `0:31`.
- Warnings were limited to the existing generated-profile missing `hopTime`
  initializers and the unrelated battle unused parameter.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s115b_terrain_branch_after_startbits \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Strict exit: `2`.
- The run used the authoritative `f064..f179` window:
  - `authoritative_run.passed=true`
  - `actual_shadow_window=[64,179]`
- Target and movement passed:
  - `target_selection.passed=true`
  - `actual_left_hop_start_frame=27`
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_percent=100`
  - `origin_left_delta=95`
  - `window_left_delta=55`
- Corrected f064-f179 shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=7 / 116`
  - `present_frames=64..70`
  - `present_percent=6`
  - `max_missing_run=109`
- The broad diagnostic candidate list included the whole authoritative window,
  but the body-relative strict shadow core still only passed for the early
  blink.
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s115b_terrain_branch_after_startbits_contact.png`.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s115b_terrain_branch_after_startbits_summary.json`.

Interpretation:

- S115b fixed the setup regression from S115 but produced the same accepted
  shadow result as S114: only the f064-f070 blink.
- The primary terrain-positive branch variables (`renderData[0x15]` and the
  paired `finalVec.y -= 0x2000`) are not sufficient to create or preserve the
  missing floor-shadow owner.
- Do not continue the terrain-branch emulation family without a genuinely new
  variable or hook point.

### S116 - Broad Material Enqueue Census Across f064-f179

Purpose:

- Instrumentation-only, not a visual fix.
- Goodall's review found that S92/S93 sampled the selected primary actor's
  already-enqueued body material and did not prove whether other material
  enqueues exist during the user-confirmed `f064..f179` window.
- S116 asks whether a non-body material candidate is still reaching the global
  material enqueue path after the existing early blink.
- The meaningful split is the existing early blink (`f064..f070`) versus the
  failing tail (`f071..f179`).
- Reviewer note: the first two-hook draft did not fit in the small ARM9 cave at
  `0x020FEA68..0x020FEBD3` and incorrectly declared space through nonzero stock
  data at `0x020FEBD4`. Do not revive that draft as-is.

Patch plan:

- Hook ARM9 `0x020C0458 -> 0x020C2528` with an ARM wrapper that records the
  actual enqueue path, then tail-branches to stock `0x020C2528` so the original
  caller return stays intact.
- Keep the helper inside the zero-padded ARM9 range
  `0x020FEA68..0x020FEBD3`.
- Store six public diagnostic words at `0x021103A0..0x021103B7`:
  - `s116_status`
  - `s116_enqueue_count`
  - `s116_non_body_candidate_count`
  - `s116_alpha_zero_count`
  - unused/reserved
  - `s116_last_nonzero_pack`
- Status bits:
  - `0x02`: enqueue wrapper ran
  - `0x08`: broad non-body candidate seen
  - `0x10`: alpha-zero enqueue seen
  - `0x80`: body-like material seen
- Material packs use:
  `alpha | palette_low8 << 8 | diffuse_low8 << 16 | tex_low8 << 24`.
- Treat the known body material as non-candidate:
  `alpha=31`, `palette_low8=0xED`, `tex_low8=0x3E` or `0x7E`.
  Other nonzero-alpha materials are broad candidates for this census.
- `s116_last_nonzero_pack` only updates for nonzero-alpha enqueues; alpha-zero
  enqueues increment `s116_alpha_zero_count` but leave the pack unchanged.

Expected useful signal:

- Per-frame memory samples show candidate/enqueue deltas during `f064..f070`
  that stop or become alpha-zero in `f071..f179`.

Expected failure signal:

- Candidate/enqueue counters do not distinguish the blink frames from the
  failing tail, meaning the visible blink is not explained by this broad
  material enqueue path.

Build:

- UI `/build` was tried first, but the viewer returned `running=false` with
  `ok=null`, `code=null`, and an empty output buffer after an incomplete run.
  To recover a real build log for this shadow attempt, `./docker-makerom.cmd`
  was run directly.
- Direct build succeeded and copied:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1638.nds`.
- Built ARM9 verification:
  - `0x020C0458 = 82 f9 00 eb`, branch to the S116 wrapper.
  - `0x020FEA68..0x020FEBD3` contains the helper.
  - `0x020FEBD4` still contains the stock nonzero word, so the helper did not
    overwrite the forbidden byte range.
  - `0x021103A0..0x021103B7` starts zeroed in the built ARM9.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s116_enqueue_census_f064 \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s116_status:u32:0x021103A0 \
  --memory-read s116_enqueue_count:u32:0x021103A4 \
  --memory-read s116_non_body_candidate_count:u32:0x021103A8 \
  --memory-read s116_alpha_zero_count:u32:0x021103AC \
  --memory-read s116_reserved:u32:0x021103B0 \
  --memory-read s116_last_nonzero_pack:u32:0x021103B4
```

Harness result:

- Process exit: `0` because `--no-fail-on-shadow-pass` was used.
- The run used the authoritative `f064..f179` window:
  - `authoritative_run.passed=true`
  - `actual_shadow_window=[64,179]`
  - `target_igglybuff=ledge-spawn`
- Target and movement passed:
  - `target_selection.passed=true`
  - `actual_left_hop_start_frame=28`
  - `movement_pass.passed=true`
  - `movement_progress_pass.passed=true`
  - `tracked_frame_count=116 / 116`
  - `origin_left_delta=95`
  - `window_left_delta=57`
  - `progress_left_delta=72`
  - `left_progress_frames_in_shadow_window_count=30`
- Corrected `f064..f179` shadow still failed:
  - `shadow_pass.passed=false`
  - `present_frame_count=8 / 116`
  - `present_frames=64..71`
  - `present_percent=7`
  - `missing_shadow_frame_count=108`
  - `max_missing_run=108`
- Broad `candidate_shadow_frames_in_authoritative_window` covered all
  `64..179`, but the strict body-relative shadow core only passed for
  `64..71`. The broad candidate list is therefore not proof of a floor shadow.
- Landing/stall tail remains detected after the hop reaches the far-left tile:
  `landing_stall.detected=true`, starting at frame `125`.

S116 memory result:

- Final reads:
  - `s116_status=0x0000008A`
  - `s116_enqueue_count=0x00005C51`
  - `s116_non_body_candidate_count=0x0000597A`
  - `s116_alpha_zero_count=0x00000000`
  - `s116_reserved=0x00000000`
  - `s116_last_nonzero_pack=0x7ECEED1F`
- Early visible-blink section, `f064..f071`:
  - enqueue delta: `217`
  - non-body candidate delta: `211`
  - alpha-zero delta: `0`
  - last pack remains `0xBECEED1F`
- Failing tail, `f072..f179`:
  - enqueue delta: `3677`
  - non-body candidate delta: `3516`
  - alpha-zero delta: `0`
  - last pack changes `0xBECEEA1F -> 0x7ECEED1F`
- Whole authoritative window, `f064..f179`:
  - enqueue delta: `3961`
  - non-body candidate delta: `3794`
  - alpha-zero delta: `0`

Artifacts:

- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s116_enqueue_census_f064_contact.png`
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s116_enqueue_census_f064_summary.json`

Interpretation:

- The missing-shadow tail is not explained by the global
  `0x020C0458 -> 0x020C2528` material enqueue disappearing.
- It is also not explained by this path producing alpha-zero materials, because
  `s116_alpha_zero_count` stayed `0`.
- S116 is not a conclusive proof about every possible render path, but it
  strongly argues that the next useful attempt should focus on positional,
  matrix, or tile/floor-gating state for the shadow rather than broad material
  enqueue/alpha state.

### S117 - Selected Final Vector and Tile-State Census

Purpose:

- Instrumentation-only, not a visual fix.
- The user-confirmed harness window is `f064..f179`; grass-only setup frames
  are irrelevant, and the early `f064..f071` blink is not success.
- S116 proved broad material enqueue continues through the missing-shadow tail
  and alpha does not drop to zero. S117 therefore asks what native draw state
  the selected ledge-spawned Igglybuff is feeding into the floor/shadow logic
  exactly when the blink stops.

Patch plan:

- Remove the live S116 material enqueue hook from `armips/asm/fairy.s` so this
  run does not carry an unrelated broad material wrapper.
- Patch overlay 1 `0x021F8E68`, the stock call to
  `0x0205F97C(object, &faceVec)`, with one compact wrapper.
- Only log when the draw object has object id `0xE1`, matching the selected
  ledge-spawned Igglybuff used by prior selected-object probes.
- Tail-call the stock `0x0205F97C` after restoring registers so native face
  vector writeback remains unchanged.
- Store compact diagnostics at `0x02209B44..0x02209B5F`:
  - `s117_status`
  - `s117_object`
  - `s117_pos_x`
  - `s117_face_y`
  - `s117_tile_render_pack`
  - two reserved words

Diagnostic packing:

- `s117_status`:
  - `0x01`: selected `0xE1` object was observed.
  - `0x02`: the `0x0205F97C` writeback hook ran for that object.
- `s117_tile_render_pack`:
  - bits `0..7`: `renderData[0x15]`
  - bits `8..15`: `renderData[0x17]`
  - bits `16..23`: `object->xCurr`
  - bits `24..31`: `object->yCurr`

Expected useful signal:

- The per-frame samples show a specific face-vector, logical-tile, or
  render-data transition at or just after the `f064..f071` blink.

Expected failure signal:

- The selected final vector/tile/render state continues smoothly through the
  failing tail with no clear transition, meaning the next probe must move
  deeper into native matrix/projection or effect-owner state rather than object
  fields.

Build and byte checks:

- UI build through the viewer endpoint with `runAfter:true`: success, exit
  code `0`, elapsed `0:36`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1639.nds`.
- Built bytes confirmed the intended live state:
  - Overlay 1 `0x021F8E68` changed from stock to a branch into
    `s117_final_vec_probe`.
  - Overlay 1 `0x02209B44..0x02209B5F` contained seven zeroed diagnostic words.
  - ARM9 `0x02108D74` contained the S117 helper.
  - ARM9 `0x020C0458` was restored to stock `32 08 00 eb`, so the S116
    material enqueue wrapper was not active.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s117_final_vec_tile_state_f064 \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s117_status:u32:0x02209B44 \
  --memory-read s117_object:u32:0x02209B48 \
  --memory-read s117_pos_x:s32:0x02209B4C \
  --memory-read s117_face_y:s32:0x02209B50 \
  --memory-read s117_tile_render_pack:u32:0x02209B54 \
  --memory-read s117_reserved_a:u32:0x02209B58 \
  --memory-read s117_reserved_b:u32:0x02209B5C
```

Harness result:

- Exit code `0` only because `--no-fail-on-shadow-pass` was enabled.
- Authoritative run shape was correct:
  - `scenario=ledge-repro`.
  - `target_igglybuff=ledge-spawn`.
  - `actual_shadow_window=[64,179]`.
  - Target selection picked the upper ledge-spawn Igglybuff, bbox
    `[105,84,118,95]`.
- Movement stayed valid:
  - `movement_pass.passed=true`.
  - `movement_progress_pass.passed=true`.
  - `tracked_percent=100`.
  - `origin_left_delta=95`.
  - `window_left_delta=39`.
  - `left_progress_frames_in_shadow_window_count=9`.
- Strict `f064..f179` shadow still failed:
  - `shadow_pass.passed=false`.
  - `present_frame_count=0 / 116`.
  - `missing_shadow_frame_count=116`.
  - `max_missing_run=116`.
- Artifacts:
  - Contact sheet:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s117_final_vec_tile_state_f064_contact.png`
  - Summary:
    `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s117_final_vec_tile_state_f064_summary.json`

Diagnostic result:

- `s117_status=3`, so the selected-object final-vector hook did run.
- The sampled object pointer switched during setup from `0x022AEBC4` to
  `0x022AEF48`, which means filtering only by object id `0xE1` is not a
  perfect identity lock for the visually tracked Igglybuff.
- During the authoritative window, the final-vector writeback continued
  through the missing-shadow frames. `renderData[0x17]` stayed `1` and
  `renderData[0x15]`/`face_y` toggled, but no transition correlated with a
  stable accepted floor shadow.

Interpretation:

- S117 is not a fix.
- The missing shadow is not explained by the selected final-vector writeback
  stopping, and the S117 object-id-only filter is too coarse to resolve the
  exact visual target by itself.
- This reinforces S90/S116: the next useful attempt should target the stock
  primary actor / downstream projection or a stock-compatible shadow owner,
  not object field logging, broad material enqueue, or the early `f064..f071`
  blink.

### S118 - Primary Actor Floor Projection Vector

Purpose:

- S118 was a proposed visual fix, but this exact variant was rejected before
  build/runtime testing.
- The authoritative harness window is `f064..f179`; grass-only setup frames are
  irrelevant, and the early blink does not count as success.
- S90/S117 proved the selected ledge-spawned Igglybuff keeps reaching the
  normal small-Pokemon primary draw path and the final vector writeback.
- S93/S116 ruled out broad material enqueue loss/alpha loss as the explanation.
- S86/S114/S115 ruled out the primary terrain-gate/latch family.

Patch plan:

- Remove the live S117 final-vector probe:
  - restore overlay 1 `0x021F8E68` to the stock call to `0x0205F97C`;
  - replace the ARM9 helper at `0x02108D74`;
  - reuse the diagnostic words at `0x02209B44..0x02209B5F` for S118.
- Hook overlay 1 `0x021F7908`, the small-Pokemon primary position call:
  `bl 0x021FA3E8(object, primarySprite)`.
- The wrapper first calls stock `0x021FA3E8`, preserving the visible body
  position.
- For wild object ids `0xE0..0xE9` only, and only while the custom long-hop
  carrier is live (`MAPOBJECTFLAG_UNK13` plus `faceVec[1] | unk88[1]`), write a
  floor-space vector to the same primary actor's secondary vector slot with
  `0x02023E78(primarySprite, &floorVec)`.
- The floor vector uses `object->posVec[0]`, `object->posVec[1]`, and
  `object->posVec[2] + 0x6000`, matching the stock z bias in `0x021FA3E8`
  while leaving the visible primary vector untouched.
- Do not touch movement flags, logical tile sync, terrain latches, material
  state, field effects, secondary sprite creation, or the C long-hop
  interpolation path.

Pre-build review result:

- A review pass found that `0x02023E78` writes the actor fields at
  `actor + 0x0C`, and stock callers write neutral `0x1000, 0x1000, 0x1000`
  vectors there.
- That strongly suggests this field is scale/projection state rather than a
  floor-position/shadow-position vector.
- Writing world/floor coordinates to it would be likely to distort, cull, or
  corrupt the primary actor instead of moving the floor shadow.
- The S118 source hook was removed before any UI build or emulator run.

Conclusion:

- Do not retry this variant.
- `0x02023E78(actor, &worldOrFloorVec)` is treated as a no-go for shadow
  placement unless a future disassembly pass proves a different semantics.

### S119 - Per-Frame Effect Resolver Targets Active Wild Long-Hop

Purpose:

- S119 is a proposed stock-path diagnostic/fix.
- S110/S111 retargeted the earlier follower/effect resolver callsites at
  `0x02205CB4` and `0x02205E7A`, but those only preserved the early
  `f064..f070` ledge blink.
- A follow-up disassembly pass found two later resolver calls inside the
  `0x02206180` per-frame effect state machine:
  - `0x022061B8`: load manager/context from `[r6 + 0x3C]`.
  - `0x022061BA`: stock `bl 0x021F771C`.
  - `0x0220621E`: load manager/context from `[r6 + 0x3C]`.
  - `0x02206220`: stock `bl 0x021F771C`.
- This path is a better candidate for maintaining the async floor/effect state
  through the real `f064..f179` midair window than the small-Pokemon body draw
  callback or the earlier setup resolver calls.

Patch plan:

- Leave the manager/context loads at `0x022061B8` and `0x0220621E` stock.
- Replace only the two `bl 0x021F771C` instructions at `0x022061BA` and
  `0x02206220`.
- The replacement helper:
  - receives the same `r0 = manager/context`;
  - scans dynamic wild object IDs `0xE0..0xE9` with `GetMapObjectByID`;
  - selects an object only when `MAPOBJECTFLAG_UNK13` is set and
    `faceVec[1] | unk88[1]` is nonzero;
  - returns the selected object's primary actor via
    `0x0205F40C(object)` then `[renderData + 0]`;
  - falls back to stock `0x021F771C(manager)` if no active wild long-hop object
    with a primary actor is found.
- Do not write actor vectors, movement flags, tile fields, render-data latches,
  raw GX packets, or custom field-effect objects.
- Put helper code in ARM9 padding instead of the tight overlay 1 tail or
  overlay 149.

Expected success signal:

- UI build succeeds.
- The ledge-spawn target is selected from the upper ROI.
- `movement_pass` and `movement_progress_pass` remain true.
- Strict authoritative `f064..f179` shadow coverage passes or materially
  improves beyond the one-frame/early blink pattern.

Expected failure signal:

- The result remains the same early blink only, proving these later resolver
  calls still return an actor whose state is not a persistent floor shadow
  owner.
- Spawn/visibility/movement regression, proving this per-frame effect resolver
  is too invasive even when movement state is untouched.

Static review:

- A helper review found no blocking static issue:
  - the patch replaces only the two `bl 0x021F771C` instructions, leaving the
    manager/context loads intact;
  - the Thumb branches to the ARM9 helper are in range;
  - the helper fits in `0x02108D74..0x02108E9F`;
  - `r4-r6, lr` are preserved and `r0-r3` are caller-clobbered as expected;
  - the fallback to stock `0x021F771C(manager)` is preserved;
  - unlike S118, no actor vector or render-state field is written.

Build:

- First UI build attempt failed before compilation because Docker was not
  running:
  `Cannot connect to the Docker daemon at unix:///Users/christofferandersen/.docker/run/docker.sock`.
- Docker Desktop was started and `docker info` returned successfully.
- Rebuilt through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:36`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1640.nds`.
- Existing warning remained:
  `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Built-byte sanity:
  - `0x022061B8` still loads the manager/context from `[r6 + 0x3C]`.
  - `0x022061BA` now branches to `0x02108D74`.
  - `0x0220621E` still loads the manager/context from `[r6 + 0x3C]`.
  - `0x02206220` now branches to `0x02108D74`.
  - `0x02108D74` contains the S119 resolver and stock fallback.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s119_per_frame_effect_resolver \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- Target selection passed and selected the intended upper ledge-spawned
  Igglybuff, bbox `[105, 84, 118, 95]`.
- `actual_left_hop_start_frame`: `27`.
- `movement_pass.passed`: `true`.
- `movement_progress_pass.passed`: `true`.
- Strict `f064..f179` shadow result failed:
  - `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0 / 116`.
  - `present_percent`: `0`.
  - `max_missing_run`: `116`.
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s119_per_frame_effect_resolver_contact.png`.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s119_per_frame_effect_resolver_summary.json`.

Metric notes:

- The summary's `authoritative_run.passed=true` means only that this was the
  correct scenario/window/target, not that the shadow passed.
- The actual pass field is `shadow_pass.passed=false`.
- `candidate_shadow_frames_in_authoritative_window` covered `64..179`, but the
  accepted yellow floor-shadow core did not pass:
  - f064: `shadow_core_relative_dark_pixels=7`,
    `shadow_core_delta_mean=2.785`,
    `shadow_core_local_contrast=-61.393`.
  - f083 and later: `shadow_core_relative_dark_pixels=0`,
    strongly negative `shadow_core_delta_mean`, and negative local contrast.

Interpretation:

- S119 is movement-safe but not a fix.
- Retargeting these later per-frame resolver calls to the active wild primary
  actor does not create an accepted floor-anchored shadow.
- The broad candidate-dark signal likely came from body/nearby terrain
  darkening, not from the real floor-shadow core.
- The next useful question is whether this effect state machine needs a
  floor-space actor/coordinate source rather than the wild primary actor, and
  whether that can be done without S118-style actor-vector writes or custom
  field-effect ownership.

### S120 - Per-Frame Effect Enqueue Floor-Y Compensation

Purpose:

- S119 proved that retargeting the per-frame resolver to the active wild
  primary actor is movement-safe, but still not enough: the authoritative
  `f064..f179` window had `0 / 116` accepted shadow-core frames.
- Follow-up disassembly showed the `0x02206180` state machine immediately reads
  the selected actor's packed coordinate through `0x02023FB0(actor)`, converts
  it into enqueue arguments, and calls `0x020205D8`.
- That means S119 still feeds body/airborne screen coordinates into the stock
  effect payload. It does not create or supply a floor-space coordinate.

Patch plan:

- Keep the S119 active-wild resolver family, but make the resolver store a
  transient compensation word when it selects an active wild long-hop object.
- Use the object's vertical long-hop carrier state as the first compensation
  probe:
  - `faceVec[1]` at `object + 0x80`;
  - `unk88[1]` at `object + 0x8C`;
  - `compensation = (faceVec[1] | unk88[1]) >> 9`.
- The `>> 9` converts fx32 vertical arc to the same approximate units used by
  the `0x020205D8` screen-space enqueue arguments: fx32-to-pixels `>> 12`, then
  payload coordinate `<< 3`.
- Hook only the two per-frame enqueue calls:
  - `0x022061E0`: `bl 0x020205D8`;
  - `0x02206246`: `bl 0x020205D8`.
- The wrapper preserves the incoming enqueue arguments, adds the stored
  compensation to `r3`, then calls stock `0x020205D8`.
- Clear the compensation when no active wild long-hop object is selected.
- Do not write actor vectors (`0x02023E50` / `0x02023E78`), map-object vectors,
  movement flags, material state, terrain latches, or custom field effects.

Expected success signal:

- UI build succeeds.
- The authoritative harness selects the upper ledge-spawned Igglybuff.
- `movement_pass` and `movement_progress_pass` remain true.
- `shadow_pass.passed` improves from S119's `0 / 116` accepted frames, ideally
  passing the strict `f064..f179` floor-shadow oracle.

Expected failure signal:

- No accepted core frames, proving the stock per-frame effect payload is not
  simply using an airborne Y coordinate.
- A one-frame blink only, proving this is still tied to the same terrain
  transition behavior rather than a persistent floor-shadow owner.
- Spawn, visibility, or movement regression, proving this enqueue adjustment is
  too broad even without mutating actor state.

Build:

- Built through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:49`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1641.nds`.
- Existing warning remained:
  `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Built-byte sanity:
  - `0x022061BA` and `0x02206220` branch to `0x02108D74`.
  - `0x022061E0` and `0x02206246` branch to `0x02108DD0`.
  - `0x02108D74..0x02108DE4` contains the resolver/wrapper.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s120_enqueue_floor_y_comp \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

Harness result:

- Exit code: `2`.
- Target selection passed and selected the intended upper ledge-spawned
  Igglybuff, bbox `[105, 84, 118, 95]`.
- `movement_pass.passed`: `true`.
- `movement_progress_pass.passed`: `true`.
- Strict `f064..f179` shadow result failed:
  - `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0 / 116`.
  - `present_percent`: `0`.
  - `max_missing_run`: `116`.
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s120_enqueue_floor_y_comp_contact.png`.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s120_enqueue_floor_y_comp_summary.json`.

Diagnostic probe command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s120_comp_probe \
  --capture-frames 360 \
  --contact-every 8 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass \
  --memory-sample-every 1 \
  --memory-read s120_comp:u32:0x02209B44
```

Diagnostic result:

- `0x02209B44` stayed `0xFFFFFFFF` for every sampled frame.
- This revealed an S120 patch flaw: the scratch word at `0x02209B44` was not
  explicitly initialized in the overlay patch, so the wrapper's no-write state
  was unsafe.
- It also means S120 did not prove the active-wild resolver wrote a
  compensation during the authoritative harness.

Interpretation:

- S120 is not a valid fix.
- Treat the compensation result as inconclusive because the scratch word was
  uninitialized and never observed to change.
- The next useful attempt should initialize the scratch words, record whether
  the resolver and enqueue wrapper are actually executing, and use
  `faceVec[1] + unk88[1]` rather than `faceVec[1] | unk88[1]` for the vertical
  compensation.

### S121 - Initialized Enqueue Compensation With Runtime Diagnostics

Purpose:

- Correct S120's uninitialized scratch word.
- Verify whether the two per-frame resolver and enqueue hooks actually run in
  the authoritative harness.
- Try the more faithful vertical compensation:
  `compensation = (faceVec[1] + unk88[1]) >> 9`.

Patch plan:

- Reserve initialized diagnostic words at `0x02209B44..0x02209B5F`.
- Word layout:
  - `0x02209B44`: current compensation;
  - `0x02209B48`: resolver select count;
  - `0x02209B4C`: enqueue wrapper count;
  - `0x02209B50`: last pre-adjust enqueue `r3`;
  - `0x02209B54`: last post-adjust enqueue `r3`.
- Keep S119's active-wild object/primary actor resolver shape.
- When a wild long-hop object is selected, store the summed vertical
  compensation and increment the resolver-select count.
- In the enqueue wrapper, increment the wrapper count, record pre/post `r3`,
  and add the compensation only when it is nonzero.
- Do not write actor vectors, map-object movement state, terrain latches,
  material state, or custom field effects.

Expected success signal:

- The diagnostic words show resolver and enqueue activity.
- Shadow coverage improves in the strict `f064..f179` window while movement
  stays valid.

Expected failure signal:

- Resolver/enqueue counts stay zero, proving this stock effect state path is
  not active in the repro.
- Counts are active but shadow remains `0 / 116`, proving this enqueue-Y
  compensation family is not sufficient.

Build:

- Built through the UI endpoint with `runAfter:true`.
- Result: success, exit code `0`, elapsed `0:38`; UI opened `test.nds`.
- Copied ROM:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1642.nds`.
- Existing warning remained:
  `src/battle/battle_script_commands.c:5516:54` unused parameter `bsys`.
- Built-byte sanity:
  - `0x022061BA` and `0x02206220` branch to `0x02108D74`.
  - `0x022061E0` and `0x02206246` branch to `0x02108DD6`.
  - `0x02209B44..0x02209B5F` is initialized to zero in overlay 1.
  - `0x02108D74..0x02108DF4` contains the resolver/wrapper and diagnostic
    writes.

Harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s121_init_sum_comp_diag \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --memory-sample-every 1 \
  --memory-read s121_comp:u32:0x02209B44 \
  --memory-read s121_resolver_selects:u32:0x02209B48 \
  --memory-read s121_enqueue_count:u32:0x02209B4C \
  --memory-read s121_pre_r3:u32:0x02209B50 \
  --memory-read s121_post_r3:u32:0x02209B54
```

Harness result:

- Exit code: `2`.
- Target selection passed and selected the intended upper ledge-spawned
  Igglybuff, bbox `[105, 84, 118, 95]`.
- `movement_pass.passed`: `true`.
- `movement_progress_pass.passed`: `true`.
- Strict `f064..f179` shadow result failed:
  - `shadow_pass.passed`: `false`.
  - `present_frame_count`: `0 / 116`.
  - `present_percent`: `0`.
  - `max_missing_run`: `116`.
- Final diagnostic reads:
  - `s121_comp = 0`.
  - `s121_resolver_selects = 0`.
  - `s121_enqueue_count = 0`.
  - `s121_pre_r3 = 0`.
  - `s121_post_r3 = 0`.
- Per-frame diagnostic samples stayed at `0` for all five words.
- Contact sheet:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s121_init_sum_comp_diag_contact.png`.
- Summary JSON:
  `/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync/documentation/verification_screenshots/overworld_shadow_harness/igglybuff_shadow_s121_init_sum_comp_diag_summary.json`.

Interpretation:

- S121 is not a fix.
- The `0x02206180` per-frame effect state-machine route is inactive during the
  authoritative Igglybuff repro. This closes the S119/S120/S121 family for this
  bug.
- Future attempts should remove these inactive hooks before testing a different
  path and should pivot to the native Pokémon draw/shadow chain
  (`0x021F7894` / `0x021F8D80` / `0x021FA3E8` / `0x021F8C88` /
  `0x021F8FC0`) or the C-side map-object state that those draw functions read.

### S122 - Real Sprite Payload For Owned Shadow Object

Hypothesis:

- The current owned floor-shadow object uses overworld tag `6999` / gfx `1553`,
  but `data/graphics/overworlds/1553.png` is a single-color green placeholder
  with no transparent pixels and no dark shadow pixels.
- If the owned object exists but its payload is blank/placeholder art, the
  harness can only ever see the stock one-frame terrain blink, not the intended
  owned floor shadow.
- Replace the placeholder sheet with eight identical transparent 32x32 frames
  containing a compact dark oval near the floor anchor, and mark the shadow
  object's table entry as `OVERWORLD_SIZE_SMALL_NO_SHADOW` so stock rendering
  does not try to draw a second shadow under the shadow.

Files/symbols:

- `data/graphics/overworlds/1553.png`
- `src/field/overworld_table.c`
- `OW_WILD_LONG_HOP_SHADOW_TAG`
- `OW_WILD_LONG_HOP_SHADOW_GFX`

Expected success signal:

- The owned shadow object has a visible dark floor payload during the
  authoritative `f064..f179` Igglybuff hop window.
- The target selection and movement gates remain valid.
- The strict shadow oracle improves beyond the stock one-frame/early blink
  pattern, ideally passing without relying on sparkle/shiny-style pixels.

Expected failure signal:

- The shadow oracle remains at the old blink/zero pattern, proving the owned
  shadow object is either not being drawn in the needed phase or is positioned
  outside the pass core.
- The shadow appears in contact sheets but fails the core check, meaning the
  sprite anchor/oval placement needs adjustment rather than another render
  hook.

First patch:

- Replaced the single-color green placeholder `1553.png` with eight identical
  transparent frames containing a small dark floor oval.
- Changed the shadow object's overworld table entry to
  `OVERWORLD_SIZE_SMALL_NO_SHADOW`.

First harness result:

- UI build succeeded and opened `test.nds`.
- Authoritative harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s122_real_owned_shadow_sprite \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

- Exit code: `2`.
- Target selection passed.
- `movement_pass.passed=true`.
- `movement_progress_pass.passed=true`.
- `shadow_pass.passed=false`, but improved from the prior zero/blink pattern:
  `present_frame_count=10 / 116`, frames `64..73`.
- Contact-sheet inspection showed the owned black oval is real and visible
  early, but the active-hop-only lifecycle clears or stops positioning the
  owned shadow before the authoritative window ends.

Follow-up patch:

- Keep the owned shadow object alive for a bounded 128-frame post-hop linger
  when the source spawn object still exists.
- During the linger, keep syncing the owned shadow object to the landed source
  object and decrement the linger counter.
- Hard-clear the owned shadow during global movement reset/slot cleanup so map
  transitions and despawns do not leave stale floor marks.

Follow-up harness result:

- UI build succeeded and opened `test.nds`.
- Authoritative harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s122_linger_owned_shadow_sprite \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

- Exit code: `2`.
- Target selection passed.
- `movement_progress_pass.passed=true`.
- `shadow_pass.passed=false`.
- `present_frame_count` remained `10 / 116`, frames `64..73`.
- Contact-sheet inspection showed the owned sprite can appear during the
  linger, but at the far-left landed tail it sits too high/at the edge of the
  yellow floor-shadow core and does not pass the strict core oracle.

Second follow-up patch:

- Move the shadow oval lower within each `1553.png` frame and make it slightly
  wider/taller so the floor mark reaches the harness core at the clipped
  far-left landing position.

Second follow-up harness result:

- UI build succeeded and opened `test.nds`.
- Authoritative harness command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_s122_lower_owned_shadow_sprite \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

- Exit code: `2`.
- Target selection passed.
- `movement_progress_pass.passed=true`.
- `shadow_pass.passed=false`.
- `present_frame_count` improved to `16 / 116`, frames `64..79`.
- User observed the yellow pass/fail box is not tracking the Igglybuff arc, so
  this harness result undercounts visible shadows and should not be treated as
  the sole authority for visual tuning.

### S123 - Smaller Lighter Dithered Owned Shadow Sprite

Hypothesis:

- The owned floor-shadow object is now visible enough, but the current payload
  reads too much like a solid black slab.
- The overworld BTX path uses 4bpp indexed art and palette transparency rather
  than PNG alpha blending, so real semi-transparent pixels are not available
  through this asset path.
- A smaller oval with sparse/dithered opaque pixels and lighter palette entries
  should read as a transparent shadow while staying within the safe owned
  map-object approach.

Files/symbols:

- `data/graphics/overworlds/1553.png`
- `data/graphics/overworlds/1553-tsure_poke0.pal`
- `data/graphics/overworlds/1553-tsure_poke1.pal`

Initial patch:

- Shrank the shadow payload to a compact dithered oval near the floor anchor.
- Reduced visible pixels across the sheet from `1184` to `368`.
- Lightened the shadow palette colors from near-black greys to muted
  blue-greys:
  - center: `64 72 80`
  - edge: `88 96 104`
- Build failed because `nitrogfx` rejects LF-only JASC palette files:
  `LF line endings aren't supported.`

Follow-up patch:

- Replaced the dithered oval with the user-provided reference silhouette:
  eight 32x32 frames, each with a small 17x7 two-tone blue-grey oval.
- Palette colors:
  - center: `32 40 48`
  - edge: `48 56 64`
- Wrote both `1553-tsure_poke*.pal` files with CRLF line endings so
  `tools/overworld-btx.py` / `nitrogfx` can convert the asset.
- First follow-up build still failed because the generated JASC palette declared
  `16` colors but only contained `15` color rows. Added the missing filler row
  and re-verified both palette files contain `19` CRLF-terminated lines
  (`3` header lines plus `16` colors).
- UI build after the palette correction succeeded, converted
  `data/graphics/overworlds/1553.png`, and opened `test.nds`.

Expected success signal:

- In-game long-hop shadows should look lighter and smaller, closer to a
  transparent floor shadow.
- Because the pass harness currently tracks a rigid yellow box, visual
  inspection may be more useful than the old strict pass count for this tuning
  attempt until the harness core is made dynamic.

### S124 - Invisible Native Shadow Carrier

User correction:

- Normal overworld Pokemon already cast their own stock shadows correctly.
- The special handling is only for the midair long-hop window where moving off
  grass/canopy terrain can make the normal shadow blink or disappear.
- The fix should not replace normal ground shadows and should not draw a fake
  shadow graphic.

Hypothesis:

- The existing owned long-hop companion object can become a temporary native
  engine shadow carrier instead of a visible shadow sprite.
- `OVERWORLD_SIZE_SMALL` should enable the stock engine shadow, while
  `OVERWORLD_SIZE_SMALL_NO_SHADOW` disables it.
- If the engine shadow path does not require visible body pixels, a fully
  transparent carrier sprite can sit on the floor under the airborne Pokemon
  and cast a normal shadow only during the long-hop arc.

Files/symbols:

- `src/field/overworld_table.c`
  - `OW_WILD_LONG_HOP_SHADOW_TAG`
  - `OW_WILD_LONG_HOP_SHADOW_GFX`
  - carrier callback params changed from `OVERWORLD_SIZE_SMALL_NO_SHADOW` to
    `OVERWORLD_SIZE_SMALL`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_SyncCanopyLongJumpShadowObject`
  - `OverworldWildSpawns_ClearCanopyLongJumpDiagonal`
- `data/graphics/overworlds/1553.png`
- `data/graphics/overworlds/1553-tsure_poke0.pal`
- `data/graphics/overworlds/1553-tsure_poke1.pal`

Patch:

- Keep using the owned companion object lifecycle that already avoids the
  crashy raw-G3/draw-wrapper/field-effect paths.
- Make the carrier's overworld table entry use the stock small-shadow callback
  params.
- Replace the visible `1553.png` payload with a fully transparent indexed
  sheet. This object should not draw a shadow-shaped body; it exists only to
  request the engine's own shadow.
- Remove the post-hop linger. The carrier now clears as soon as the long-hop
  diagonal state clears, leaving normal landed Pokemon shadow behavior alone.

Risk to verify:

- If the engine skips stock shadow drawing for a fully transparent sprite, this
  will fail visually even though the carrier object exists. In that case the
  next attempt should keep the native-shadow carrier idea but find the cheapest
  engine-visible/invisible-body condition rather than returning to fake shadow
  art.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- `test.nds` was opened by the UI server.

### S142 - Restore Settled Landing Carrier Ownership

User direction:

- Regression: the landing animation / shadow fix was lost.

Hypothesis:

- The S139/S140 rule was accidentally collapsed back into one broad cleanup
  path: `OverworldWildSpawns_ClearCustomJump` deleted the custom jump shadow
  object every time.
- That deletes the owned native-shadow carrier immediately after a successful
  landing, so the landing tile no longer keeps the recovered shadow assist.
- The correct cheap rule is still:
  - generic custom-jump state cleanup preserves a settled landing carrier;
  - actual next custom-hop start deletes the old carrier;
  - pickup, despawn, context loss, and movement reset delete the carrier
    explicitly.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_ClearCustomJump`
  - `OverworldWildSpawns_StartCustomJump`
  - `OverworldWildSpawns_ResetSlotMovementCommand`
  - `OverworldWildSpawns_StartCarriedThrowTarget`

Patch:

- Removed the shadow-object delete from `OverworldWildSpawns_ClearCustomJump`.
- Added an explicit delete at `OverworldWildSpawns_StartCustomJump`, preserving
  S139's "clear only when the next real hop starts" boundary.
- Kept/added explicit delete in reset and pickup cleanup paths so stale landing
  carriers do not survive pickup, despawn, context loss, or command reset.

Expected result:

- A successful custom-hop landing can keep its native shadow carrier on the
  landing tile.
- The carrier disappears when that same Pokemon actually begins a later custom
  hop.
- Pick up + throw does not leave the picked-up Pokemon's old landing shadow
  behind.
- The landing-animation bit normalization from the sprite-speed fix remains
  separate; this patch does not restore a permanent `0x00020028` flag state.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0` in `0:32`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1717.nds`.
- `test.nds` was opened by the UI server.

### S143 - Pulse Landing Animation Bits After Custom Hop

User direction:

- The landing animation is still missing after S142.

Hypothesis:

- S142 restored the landing shadow carrier lifecycle, but the landing animation
  itself was still suppressed.
- `OverworldWildSpawns_SetObjectLandingTile` clears `0x00020028`, and
  `OverworldWildSpawns_PlayCustomJumpLandingFeedback` also cleared the same
  bits, so the stock landing animation state never survived into a rendered
  frame.
- The old sprite-speed regression came from leaving those bits up permanently,
  not from showing them briefly.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OW_WILD_SPAWNER_CUSTOM_JUMP_LANDING_ANIM_BITS`
  - `OW_WILD_SPAWNER_CUSTOM_JUMP_LANDING_ANIM_FRAMES`
  - `OverworldWildSpawns_PlayCustomJumpLandingFeedback`
  - `OverworldWildSpawns_TickCustomJumpLandingFeedback`
  - `OverworldWildSpawns_FrameMovementTask`

Patch:

- Added a two-frame landing animation pulse timer.
- `PlayCustomJumpLandingFeedback` now sets the landing animation bits and arms
  the short timer.
- The frame task decrements the timer and clears those bits when the pulse
  expires.
- The thrown-Pokemon landing path now clears stale custom-jump state before
  playing landing feedback, so cleanup does not erase the pulse immediately.

Expected result:

- Custom-hop landing gets a visible landing animation again.
- The landing animation bits are still cleared shortly after landing, avoiding
  the old permanent fast sprite-animation state.
- S142's settled shadow carrier ownership remains unchanged.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0` in `0:32`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1718.nds`.
- `test.nds` was opened by the UI server.

### S141 - Seed Land-Origin Carrier At Custom Jump Start

User direction:

- When a Pokemon jumps from a land tile, the shadow sometimes flickers off for
  what looks like a single frame.

Hypothesis:

- S139 correctly clears the old landing carrier only when the next custom jump
  actually starts, but the active carrier is currently first synced on the next
  movement tick.
- If the native Pokemon shadow state is still suppressed from an earlier
  grass/canopy-to-land hop, that leaves a one-frame gap after the old lingering
  carrier is cleared and before the new active carrier is born.
- Seeding the existing native shadow carrier immediately after
  `StartCustomJump` should remove that gap for land-origin hops.
- Grass/canopy-origin hops should remain safe because the existing terrain gate
  inside `SyncCustomJumpShadowObject` still refuses to create the carrier while
  the source is over grass, long grass, headbutt/canopy, or surf.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_StartPreparedCustomJumpCommand`
  - `OverworldWildSpawns_SyncCustomJumpShadowObject`

Patch:

- After `OverworldWildSpawns_StartCustomJump`, call
  `OverworldWildSpawns_SyncCustomJumpShadowObject` once before spin/movement
  bookkeeping continues.

Expected result:

- Land-origin custom jumps have a carrier object ready on the same frame the
  jump starts, avoiding a single-frame missing-shadow gap.
- Grass/canopy-origin jumps still do not birth the carrier on suppressing
  terrain at hop start.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1709.nds`.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.

### S138 - Clear Landing Shadow When Movement Starts Again

User direction:

- Shadow lingers after landing. It should no longer be there if the Pokemon hops
  again.

Hypothesis:

- The landing assist should remain only while the Pokemon is settled after a
  custom jump.
- The old landing carrier should be cleared at the accepted-new-hop boundary,
  not by weakening the normal landing-shadow preserve path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_ClearCustomJump`
  - `OverworldWildSpawns_FinishPendingStagedHop`
  - `OverworldWildSpawns_StageHopTarget`

Patch:

- Kept `OverworldWildSpawns_ClearCustomJump` preserving the existing
  post-landing shadow behavior.
- Call the existing shadow-object cleanup directly when `StageHopTarget` accepts
  a new staged hop, so the previous landing shadow disappears during the next
  hop windup instead of lingering on the old tile.
- Rejected the first broader helper/funnel cleanup version because overlay 149
  exceeded its `.text` budget.

Expected result:

- Landing shadows can remain briefly while the Pokemon is settled.
- Once the same Pokemon accepts another staged hop, the old landing carrier is
  deleted instead of lingering on the previous floor tile.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1665.nds`.
- `test.nds` was opened by the UI server.

### S140 - Clear Landing Shadow When Picked Up

User direction:

- Edge case: a Pokemon being picked up by pick up + throw leaves the shadow
  behind.

Hypothesis:

- S139 correctly lets a landed shadow linger until the Pokemon's next hop.
- Pickup is not a hop. It hides the target and attaches it to the carrier, so
  the target's lingering landing shadow must be force-cleared at pickup time.
- Calling `ClearStagedHopTarget` is not enough in the completed-hop case,
  because `ClearCustomJump` intentionally preserves the post-landing carrier.

Patch:

- In `OverworldWildSpawns_StartCarriedThrowTarget`, force-clear the target
  slot's custom jump shadow object immediately after clearing staged hop state
  and before setting the target to the picked-up behavior class.

Expected result:

- A Pokemon's landing shadow can still linger while it is grounded.
- If that Pokemon is picked up for pick up + throw, its old floor shadow is
  removed immediately and does not remain behind.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1704.nds`.
- `test.nds` was opened by the UI server.

### S139 - Keep Landing Shadow Until Actual Next Hop

User direction:

- Shadow should linger until the Pokemon hops again.

Hypothesis:

- The previous S138 patch cleared the landing carrier too early, when a next hop
  was accepted/staged.
- The desired rule is stricter: the carrier should persist while the Pokemon is
  settled or winding up, then disappear only when the next custom hop actually
  starts.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_TickMovementParams`
  - `OverworldWildSpawns_StageHopTarget`
  - `OverworldWildSpawns_StartPreparedCustomJumpCommand`
  - `OverworldWildSpawns_StartCustomJump`

Patch:

- Removed the inactive landing-shadow countdown from the movement tick loop so
  a settled landing carrier is not auto-cleared after a fixed number of frames.
- Removed the S138 clear from `StageHopTarget`, so choosing/staging the next hop
  does not erase the landing shadow.
- Removed the early clear from `StartPreparedCustomJumpCommand`, so failed prep
  attempts do not erase the landing shadow.
- Kept the existing `StartCustomJump` clear as the actual next-hop boundary.

Expected result:

- Landing shadows remain visible indefinitely while the Pokemon is settled.
- The old landing shadow disappears when the Pokemon actually starts its next
  custom hop.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1701.nds`.
- `test.nds` was opened by the UI server.

### S137 - Rename Generic Staged Hop Bookkeeping

User direction:

- Continue the custom-jump cleanup and do step 4.

Hypothesis:

- The remaining generic pending-hop execution layer was still named
  `CanopyHop`, even though it now stages custom jumps for more than canopy
  behavior.
- Renaming that queue/bookkeeping layer to `StagedHop` makes the code clearer
  without changing behavior or broadening the canopy-specific policy surface.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Patch:

- Renamed generic staged-hop fields from `movementCanopyHop*` to
  `movementStagedHop*`.
- Renamed generic staged-hop task/list storage from
  `sOverworldWildCanopyHopMovement*` to
  `sOverworldWildStagedHopMovement*`.
- Renamed generic staged-hop helpers such as `ClearCanopyHopTarget`,
  `StageCanopyHopTarget`, `ExecutePendingCanopyHop`,
  `FinishPendingCanopyHop`, and movement-list tick/finish helpers to their
  `StagedHop` equivalents.
- Left true canopy behavior/policy names alone, including `CanopyHopper`,
  tree-top/path logic, canopy sound names, and existing canopy movement
  command IDs.

Expected result:

- No behavior change.
- The staged-hop code path should read as generic infrastructure, while actual
  canopy-specific behavior remains visibly named as canopy-specific.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1663.nds`.
- `test.nds` was opened by the UI server.

### S135 - Canopy-Hop Landing Uses Existing Custom Jump Shadow Carrier

User direction:

- Do step 2 after the `CustomJump` rename: cover canopy-origin hops that can
  land on normal shadow-capable tiles without creating a larger separate shadow
  system.

Hypothesis:

- The active custom-jump shadow carrier is now the safest native-shadow assist.
- A separate origin-specific helper or new per-slot state is too expensive for
  overlay 149.
- The cheapest dynamic rule is to let normal canopy-hop completion sync the
  existing custom-jump carrier once at the landed object's current floor tile.
  The existing carrier sync already rejects grass, long grass, headbutt/canopy,
  and surf, so it only persists on shadow-capable landing tiles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_FinishPendingCanopyHop`
  - `OverworldWildSpawns_SyncCustomJumpShadowObject`
  - `movementCustomJumpElapsedFrames`
  - `movementCustomJumpShadowObjects`

Patch:

- First tried an explicit canopy-origin predicate using the stored hop origin
  and `GetMetatileBehaviorAt(..., OW_WILD_TILE_HEADBUTT)`.
- That overflowed overlay 149, even after compressing the predicate to reuse
  cached origin coordinates.
- Final patch removes the origin predicate and reuses the existing
  shadow-capable floor filter in `OverworldWildSpawns_SyncCustomJumpShadowObject`.
- After `OverworldWildSpawns_ClearCanopyHopTarget`, normal canopy-hop finish now
  calls `OverworldWildSpawns_SyncCustomJumpShadowObject(state, slot, object)` and
  primes the existing post-landing carrier countdown with
  `OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_FRAMES`.
- If the landing floor is grass, long grass, headbutt/canopy, or surf, the sync
  helper clears/avoids the carrier and the countdown has no visible object.

Build result:

- First UI build failed: `overworld_wild_spawns_overlay_linked.o section .text
  will not fit in region rom`.
- Second compressed predicate build failed with the same overlay 149 overflow.
- Final UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Linked overlay 149 `.text` is `45020` bytes.
- Build copied the ROM to Delta as `test1661.nds`.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.

### S136 - Rename Public Shadow Entry To Custom Jump Shadow

User direction:

- Continue making hop/custom jump more universal after the active overlay rename
  and canopy-hop landing-shadow assist.

Hypothesis:

- The remaining live `CanopyLongJump` names are no longer in the active jump
  engine; they are in the exported shadow-entry ABI/wrapper used between the
  overworld wild overlays.
- Renaming that ABI surface to `CustomJumpShadow` removes the last misleading
  source-level coupling without changing the entry layout or spending bytes in
  overlay 149.

Files/symbols:

- `include/overworld_wild_behavior_data.h`
  - `OverworldWildCreateCustomJumpShadowEffectFunc`
  - `OverworldWildClearCustomJumpShadowEffectFunc`
  - `OverworldWildCustomJumpShadowEntry`
  - `OVERWORLD_WILD_CUSTOM_JUMP_SHADOW_ENTRY`
- `include/overworld_wild_spawns.h`
  - `OverworldWildSpawns_CreateCustomJumpShadowEffect`
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
  - `customJumpShadow`
  - `OverworldWildBehavior_CreateCustomJumpShadowEffectNoop`
  - `OverworldWildBehavior_ClearCustomJumpShadowEffectNoop`
- `src/overworld_wild_spawns.c`
  - `OverworldWildSpawns_CreateCustomJumpShadowEffect`
- `src/overlay.c`
  - `OVERWORLD_WILD_CUSTOM_JUMP_SHADOW_ENTRY`

Patch:

- Renamed the exported shadow entry and wrapper from `CanopyLongJumpShadow` to
  `CustomJumpShadow`.
- Kept the overlay entry layout byte-identical: legacy encounter lookup first,
  then the two function pointers for create/clear.
- Left low-level `CANOPY_HOPPER_*` animation command names alone because those
  still refer to existing movement command IDs, not the custom jump concept.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Build copied the ROM to Delta as `test1662.nds`.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.

### S134 - Rename Custom Jump Core And Retain Canopy-Origin Landing Carrier

User direction:

- Make hop more universal.
- The active `CanopyLongJumpDiagonal` naming is misleading; this is really a
  custom jump system, not a canopy-only or diagonal-only path.
- Do the rename/refactor first, then handle canopy-origin hops that sometimes
  lose shadow when landing on land.

Hypothesis:

- The long-hop shadow carrier is now stable enough to keep as the native shadow
  assist.
- Normal canopy-origin hop landings can bypass the active custom-jump carrier
  because they finish through `OverworldWildSpawns_FinishPendingCanopyHop`
  after the custom-jump active state has already been cleared.
- Keeping a short custom-jump landing carrier when the hop origin was a canopy
  tile and the landing tile is shadow-capable land should cover canopy-to-land
  landings without broadening the carrier to every land-to-land hop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - Renamed live `CanopyLongJump` / `CanopyLongJumpDiagonal` symbols to
    `CustomJump`.

Patch:

- Renamed the active custom-hop runtime fields, helpers, macros, and diagnostic
  symbols away from `CanopyLongJumpDiagonal`.
- Kept terrain-specific names such as `CanopyHop`/`CanopyHopper` where they are
  still about headbutt tree-top policy rather than the custom jump engine.
- Tried a tiny canopy-origin landing-shadow hook after the rename, but overlay
  149 overflowed even after trimming the extra helper. Removed that hook and
  kept this pass as the behavior-preserving `CustomJump` rename only.
- To fit the rename inside overlay 149, trimmed duplicate guards and one-off
  helper layers from the custom-jump path:
  - removed redundant start/runtime checks from internal-only custom-jump helpers;
  - inlined one-off timing/shadow gate helpers;
  - removed debug-only last-action writes from the immediate custom movement
    command path;
  - removed the secondary-axis clamp that was already bounded by the max custom
    jump distance.

Build result:

- First UI build failed: `overworld_wild_spawns_overlay_linked.o section
  .text will not fit in region rom`.
- Second UI build after trimming also failed with the same overlay 149 overflow.
- Removed the canopy-origin landing-shadow hook and rebuilt the rename-only pass.
- Final UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Build copied the ROM to Delta as `test1660.nds`.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.
- Canopy-origin landing-shadow coverage still needs its own follow-up patch; this
  pass deliberately stopped at the safe rename/refactor.

### S132 - Long-Hop Carrier On Any Shadow-Capable Floor Tile

User direction:

- The grass-to-land case works, but if the Pokemon jumps again after landing on
  land, the next hop has no shadow.
- The user clarified that shadows cannot duplicate because a tile can carry at
  most one shadow.

Hypothesis:

- The S131 gate was too narrow because it only enabled the carrier when the
  long-hop started on grass/long grass/headbutt and then moved over land.
- The native shadow state can remain suppressed after that landing, so a second
  land-origin hop needs the same carrier even though the start tile is no
  longer grass.
- If shadows cannot duplicate, the cheapest stable rule is to let the carrier
  serve as the long-hop floor-shadow provider whenever the current floor tile is
  shadow-capable.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_ShouldUseCanopyLongJumpShadowObject`

Patch:

- Removed the start-tile behavior check from the carrier gate.
- Removed the early return that disabled the carrier while the interpolated
  floor tile still matched the jump start tile.
- The carrier now requires only an active long-hop and a current floor behavior
  that is not grass, long grass, headbutt, or surf.

Expected result:

- Grass-to-land first hops keep the working S131 shadow.
- Immediate follow-up land-to-land hops also get a carrier shadow instead of
  relying on the possibly still-suppressed native Pokemon shadow state.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Build copied the ROM to Delta as `test1656.nds`.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.

### S133 - Retain Carrier Briefly On Landing Tile

User direction:

- S132 works, but one remaining issue is that the carrier needs to remain on
  the landing tile.

Hypothesis:

- The frame task already has an inactive-shadow countdown path for
  `movementCanopyLongJumpShadowObjects`, but normal long-hop completion deletes
  the carrier inside `OverworldWildSpawns_ClearCanopyLongJumpDiagonal` before
  that countdown can keep it on the landing tile.
- Letting completed landings keep the existing carrier briefly should provide a
  landing-tile shadow and give the native object shadow state time to recover.
- Cancellations/resets/despawns must still delete the carrier immediately.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_ClearCanopyLongJumpDiagonal`
  - `OverworldWildSpawns_ShouldUseCanopyLongJumpShadowObject`
  - inactive `movementCanopyLongJumpShadowObjects` frame loop

Patch:

- Reused `movementCanopyLongJumpDiagonalElapsedFrames` as the landing-shadow
  countdown when a carrier exists and the long-hop has reached its final frame.
- `OverworldWildSpawns_ClearCanopyLongJumpDiagonal` now keeps that carrier
  alive on completed landings and deletes it immediately for non-completed
  clears.
- The inactive frame-loop now only decrements the landing countdown and clears
  the retained carrier at zero; it does not resync the carrier after the hop is
  inactive.

Expected result:

- A completed long-hop keeps the carrier on the landing tile for the existing
  short landing-settle frame count.
- Mid-hop cancels and cleanup paths still remove the carrier immediately.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Build copied the ROM to Delta as `test1658.nds`.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.

### S126 - Spawn Native Carrier Only After Leaving Shadow-Suppressing Tile

User correction:

- Creating the carrier at long-hop start duplicates the original problem when
  the hop starts on grass/canopy. The helper is born on the same
  shadow-suppressing terrain and can inherit the same bad shadow state.
- The carrier should spawn in the actual issue window: when the airborne
  Pokemon leaves a grass/canopy/headbutt tile and its floor position is now on a
  non-suppressing tile.

Hypothesis:

- Do not create the carrier at hop start.
- During long-hop render sync, only create/sync the carrier if:
  - the long-hop start tile is grass, long grass, or headbutt;
  - the current interpolated floor tile is different from the start tile;
  - the current interpolated floor tile is not grass, long grass, headbutt,
    surf, or blocked.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_SyncCanopyLongJumpShadowObject`
  - `OverworldWildSpawns_ShouldUseCanopyLongJumpShadowObject`

Patch:

- Added a creation gate before the carrier object is ensured.
- The gate uses the long-hop runtime start tile and the source object's current
  interpolated floor tile.
- Shadow-suppressing start/current tiles are grass, long grass, and headbutt;
  the current tile must also be non-surf and unblocked.
- If the gate is false while a carrier exists, the carrier is cleared.
- Removed the hop-start carrier sync call so only the per-frame render sync can
  birth the helper.

Expected result:

- No carrier is spawned while the Pokemon is still above the grass/canopy start
  tile.
- The carrier is created only after the floor position crosses onto an allowed
  non-suppressing tile, so it should avoid inheriting the bad grass/canopy
  shadow state.

Build result:

- First S126 build failed because the more dynamic profile/allowed-tile gate
  pushed overlay 149 over its size limit.
- Shrunk the gate to the specific issue state: grass/long-grass/headbutt start
  tile, different current floor tile, and current tile not grass/long-grass/
  headbutt/surf/blocked.
- UI build endpoint then ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- `test.nds` was opened by the UI server.

Runtime result:

- User reported this did not work.
- Likely explanation: a fully transparent/empty carrier sprite does not reach
  enough of the native sprite/shadow path to emit the stock shadow.

### S127 - Non-Wrapping Stock Carrier Body Hide Offset

User direction:

- The native carrier shadow is nearly working, but the Jigglypuff carrier body
  flickers.

Hypothesis:

- The S125 body hide offset used `0x00100000`, which is 16 tiles / 256 pixels.
- Some sprite/render paths store or derive screen-space offsets through
  byte-sized values; an exact 256-pixel offset can wrap to 0 and briefly draw
  the carrier body at the floor position.
- A 15-tile / 240-pixel hide offset should still push the carrier body
  offscreen, while avoiding the exact wrap boundary.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OW_WILD_CANOPY_LONG_JUMP_SHADOW_BODY_HIDE_Y_FX32`

Patch:

- Changed the stock carrier body hide offset from `0x00100000` to
  `0x000F0000`.

Expected result:

- The stock Jigglypuff carrier should continue to cast the native floor shadow.
- The carrier body should no longer flicker into view during the grass-to-land
  long-hop transition.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- `test.nds` was opened by the UI server.

Runtime result:

- User reported Jigglypuff still flickers.
- This means avoiding the exact 256-pixel hide offset was not sufficient.

### S128 - Birth-Hidden Native Carrier

User direction:

- Shadows are basically in; the remaining visible issue is the Jigglypuff carrier
  body flickering.

Hypothesis:

- The carrier body may be leaking on the creation frame before its hidden
  `faceVec[1]` / `unk88[1]` state is stable in the native render path.
- Keeping the newly-created carrier vanished for its first sync frame should
  suppress that birth-frame body leak.
- On the following sync, the carrier unvanishes with the body-hide vectors
  already installed, preserving the stock shadow path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_SyncCanopyLongJumpShadowObject`

Patch:

- Added a `justCreated` flag inside the carrier sync helper.
- Newly-created carriers now set `BIT_VANISH` immediately.
- The final sync clears jump/move flags every frame, but only clears
  `BIT_VANISH` for carriers that already existed before this sync.

Expected result:

- The helper should skip drawing on the creation frame.
- The native shadow should resume on the following frame without showing the
  Jigglypuff body.

Build result:

- UI build failed before ROM generation.
- Linker error: overlay 149 `.text` no longer fit in region `rom`.
- Rejected as too expensive for the current overlay budget.

Runtime result:

- Not tested because the build failed.

### S129 - Single Body-Hide Carrier Field

User direction:

- Jigglypuff carrier body still flickers, but the native carrier shadow is close.

Hypothesis:

- Feeding the large hide offset into both `faceVec[1]` and `unk88[1]` may make
  one of the native draw/shadow stages occasionally see a wrapped or conflicting
  body position.
- Prior shadow work found `faceVec[1]` participates in the visible body carrier,
  while `unk88[1]` also feeds later stock positioning/shadow-sensitive phases.
- Keep the body lift in `faceVec[1]`, but leave `unk88[1]` at floor zero for the
  shadow carrier.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildSpawns_SyncCanopyLongJumpShadowObject`

Patch:

- Reverted the oversized birth-hidden S128 code path.
- Changed the shadow carrier sync so `faceVec[1]` remains
  `OW_WILD_CANOPY_LONG_JUMP_SHADOW_BODY_HIDE_Y_FX32`, while `unk88[1]` is `0`.

Expected result:

- The carrier should still be native-shadow enabled and floor-synced.
- If the flicker was caused by the double hide offset feeding a later phase, the
  Jigglypuff body should stop leaking into view.

Build result:

- First UI build failed before ROM generation because overlay 149 `.text` was
  32 bytes over the `rom` region.
- Shrunk the patch by relying on the stock idle carrier object's existing zeroed
  X/Z and extra render vectors, and only touching the Y fields needed for the
  body-hide/shadow split.
- Second UI build was still 4 bytes over the overlay limit.
- Final shrink leaves `unk88[1]` at the carrier object's stock initialized value
  instead of writing it every frame.

Runtime result:

- Not tested because the builds failed.

### S130 - Compact Stock Carrier Sprite

User direction:

- The remaining visible issue is the Jigglypuff carrier body flickering.

Hypothesis:

- Overlay 149 has no practical room for first-frame/stateful body suppression.
- The native stock-shadow carrier can use a smaller stock shadow-enabled
  overworld tag instead of Jigglypuff.
- A compact Unown carrier keeps the same stock shadow path, but any body leak
  should be a tiny dark speck rather than a visible pink Jigglypuff spirit.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OW_WILD_CANOPY_LONG_JUMP_SHADOW_SPRITE_ID`

Patch:

- Restored the S127 stock carrier sync shape that fits overlay 149.
- Changed the carrier tag from Jigglypuff `490` to compact stock Unown tag
  `696`.
- Reclaimed overlay space by reading the source map object's `xCurr` / `yCurr`
  fields directly in the shadow-carrier helper instead of calling
  `MapObject_GetCurrentX` / `MapObject_GetCurrentY` there.
- Further shrunk the helper by setting the carrier object id directly, skipping
  redundant zero vector writes on the stock idle helper, and only clearing
  `BIT_VANISH`.
- Further shrunk the helper/gate by dropping stale-pointer clearing on
  out-of-context sync and by removing the blocked-tile check from the
  shadow-only gate. The helper remains pass-through; the gate still excludes
  grass, long grass, headbutt, and surf tiles.
- Further shrunk the gate by deriving the current interpolated floor tile from
  nonnegative fixed-point `posVec` with `>> 16`, avoiding the more expensive
  signed floor helper in this shadow-only path.

Expected result:

- Native midair floor shadows should remain present.
- If the carrier body still leaks, the leak should be much smaller and darker.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- `test.nds` was opened by the UI server.

Runtime result:

- User reported the same visible carrier leak with Unown.
- This confirms the issue is the native carrier body path, not Jigglypuff's
  particular art.

### S131 - Nearly-Empty Native Shadow Carrier Payload

User direction:

- Unown still flickers, so swapping to another real Pokemon is not enough.

Hypothesis:

- S124's fully transparent custom carrier likely failed because the native
  shadow path did not see a meaningful sprite payload.
- A nearly-empty payload can keep the stock `OVERWORLD_SIZE_SMALL` shadow path
  active while making any leaked carrier body effectively invisible.
- The carrier should not be a real Pokemon species and should not draw a fake
  floor shadow.

Files/symbols:

- `src/field/overworld_table.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OW_WILD_CANOPY_LONG_JUMP_SHADOW_SPRITE_ID`
- `data/graphics/overworlds/1553.json`
- `data/graphics/overworlds/1553.png`
- `data/graphics/overworlds/1553-tsure_poke0.pal`
- `data/graphics/overworlds/1553-tsure_poke1.pal`

Patch:

- Added unused low overworld tag `230` as a shadow-enabled carrier row:
  `gfx = 1553`, `callback_params = OVERWORLD_SIZE_SMALL`.
- Changed the long-hop shadow carrier from stock Unown tag `696` to custom tag
  `230`.
- Created `1553.png` as a 32x256 paletted overworld sheet with exactly one
  non-transparent dark pixel per 32x32 frame.
- Created matching CRLF JASC palette files for `tsure_poke0` and `tsure_poke1`.

Expected result:

- The native shadow path should still receive a normal shadow-enabled map object.
- The visible Unown/Jigglypuff carrier leak should disappear; if the body path
  still leaks, it should be reduced to a single dark pixel away from the floor
  anchor instead of a visible Pokemon spirit.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- Build converted `data/graphics/overworlds/1553.png` into the Pokemon
  overworld archive.
- `test.nds` was opened by the UI server.

Runtime result:

- Pending user verification.

### S125 - Stock Pokemon Carrier With Body Lifted Offscreen

User direction:

- Instead of an empty sheet, use a Pokemon and make it invisible.

Hypothesis:

- The stock shadow path may require a normal Pokemon-backed overworld sprite,
  not a fully empty graphics payload.
- Reusing an existing stock Pokemon overworld tag should make the helper object
  a normal shadow-casting field object.
- The helper's body can be hidden without `BIT_VANISH` by pushing only its
  render vertical offset far above the screen, while keeping its floor X/Z
  synced under the airborne Pokemon.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OW_WILD_CANOPY_LONG_JUMP_SHADOW_SPRITE_ID`
  - `OW_WILD_CANOPY_LONG_JUMP_SHADOW_BODY_HIDE_Y_FX32`
  - `OverworldWildSpawns_SyncCanopyLongJumpShadowObject`
- `src/field/overworld_table.c`

Patch:

- Removed the custom long-hop shadow table entry and stopped using custom gfx
  `1553`.
- The helper now creates a normal Jigglypuff overworld object via existing tag
  `490`.
- The helper keeps `BIT_VANISH` clear so the stock draw/shadow callback still
  runs.
- The helper syncs floor `posVec[0]` / `posVec[2]` to the jumping Pokemon and
  pins `posVec[1]` to the floor height.
- The helper sets `faceVec[1]` and `unk88[1]` to `0x00100000` so the Pokemon
  body should be offscreen while the floor shadow remains at the synced tile.
- Removed the now-unused generated `1553.png` / `1553-tsure_poke*.pal` files
  from the working tree.

Risk to verify:

- If the engine culls the whole map object based on the lifted body position,
  the shadow may disappear with it.
- If the sign/direction of the vertical render offset is wrong, the helper
  Pokemon body may become visible rather than hidden.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0`.
- `test.nds` was opened by the UI server.

### S144 - Preserve Landing Pulse Across All Custom Jump Finish Paths

User direction:

- The landing animation was still missing after S143.

Hypothesis:

- S143 correctly changed landing feedback from a permanent clear into a short
  pulse, but two older finish paths still called
  `OverworldWildSpawns_PlayCustomJumpLandingFeedback` before
  `OverworldWildSpawns_ClearCustomJump`.
- `ClearCustomJump` clears the reused pulse timer, so those paths could erase
  the landing animation immediately after arming it.

Patch:

- Changed the post-landing render-settle finish path to clear custom-jump state
  before playing landing feedback.
- Changed the non-post-restore finalize path to clear custom-jump state before
  playing landing feedback.
- Verified the remaining searched paths now use:
  `ClearCustomJump` -> `PlayCustomJumpLandingFeedback`.

Expected result:

- The landing animation pulse survives into rendered frames on every custom-hop
  finish path currently guarded by the searched call sequence.
- The pulse is still cleared by `OverworldWildSpawns_TickCustomJumpLandingFeedback`,
  so the old permanent fast-sprite state should not return.

Build result:

- UI build endpoint ran `./docker-makerom.cmd`.
- Build succeeded with exit code `0` in `0:25`.
- Copied `test.nds` to
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test1719.nds`.
- `test.nds` was opened by the UI server.

### S145 - Defer Native Shadow Reconciliation After Retained Transition

Hypothesis:

- A retained map-header transition preserves each Pokemon map object, but its
  native shadow effect still holds a snapshot of the old map ID. After that
  effect observes the identity change and self-deletes, the separate
  `MAPOBJECTFLAG_UNK15` shadow-present/ownership latch remains stale.
- Recreating/reconciling the shadow during canonicalization is too early: the
  old effect needs one field frame to observe the identity change and delete
  itself.
- Arm a one-frame runtime restore after successful canonicalization, then on
  the next player-frame service pass clear the stale `MAPOBJECTFLAG_UNK15`
  shadow-present/ownership latch on authenticated active primaries before
  calling the existing `OverworldWildSpawns_ReconcileNativeShadow` helper. The
  reconciler preserves or recomputes the legitimate `MAPOBJECTFLAG_UNK20`
  terrain/render state.

Files/symbols:

- `src/field/map_teleport.c`
  - `OverworldFieldService_OnMapHeaderChangedImpl`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - `OverworldWildOverlayRuntimeState`
  - `OverworldWildSpawns_DetachAllMovementStateOnContextLoss`
  - `OverworldWildSpawns_PrepareMapHeaderChange`
  - `OverworldWildSpawns_OverlayOnPlayerFrame`

Expected result:

- Retained Pokemon recover their stock native shadows on the frame after the
  previous shadow effect has had time to self-delete.
- Ordinary movement and the established long-hop presentation remain
  unchanged; there is no broad per-movement flag clear and no carrier object.

Build result:

- V2 UI build succeeded in `0:37`.
- Overlay 149 packaged size was `0xA7BA`; the ABI gate reported 28 bytes.
- Copied the ROM to Delta as `test2224.nds`.
- `test.nds` was opened by the V2 UI.

Runtime result:

- Pending user verification; the successful build was not runtime-tested.
