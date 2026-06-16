# Headbutt Leaf Effect Without Field-Move Reveal Log

Date: 2026-06-14

Scope: this log records the work done after the request to make the VFX tester produce the headbutt leaf effect without running the field-move animation, specifically the orange bar / Hoothoot reveal sequence.

## Goal

Make visual tester slot `102` spawn the headbutt leaf particles on or near the player, while avoiding the full field-move presentation.

The unwanted path is the stock Headbutt presentation path that brings up the orange transition/reveal. The desired path is only the leaf effect.

## Current Code State When This Log Was Written

Slot `102` is currently routed through:

- `OverworldWildSpawns_PlayVisualTesterHeadbuttLeaves`
- `OverworldWildSpawns_CreateVisualTesterHeadbuttLeafBurst`
- manual ov02 work allocation/resource setup
- manual particle-manager allocation
- `0x0224A9D8` for the leaf burst

The current route intentionally avoids the high-level orange presenter entry, but it still uses part of the ov02 field-move resource path and currently corrupts or replaces the normal top-screen render after a few frames.

## Field-Move Path We Want To Avoid

Runtime tracing of the real Headbutt sequence showed that vanilla Headbutt reaches the field-move visual sequence through ov02 code. Important addresses from the trace:

- `0x02249458`: mode-based high-level Headbutt field task candidate.
- `0x02249584`: task dispatcher neighborhood.
- `0x02249EC0`: orange field-move presenter/setup path.
- `0x0224A080`: resource/setup path used by the Headbutt presentation.
- `0x0224A9D8`: actual 26-leaf burst function.

The current understanding is:

- `0x02249EC0` is strongly associated with the orange field-move presentation.
- `0x0224A9D8` is the leaf burst we want.
- `0x0224A080` appears dangerous in the standalone tester because it sets up resources for the field-move presentation scene, not the normal overworld render.

## Attempts Since The No-Reveal Request

### 1. Direct ov02 Headbutt Task / Field-Move Candidates

Tried high-level or near-high-level Headbutt calls in the visual tester, including variants around:

- `ov01_021FC748(fieldSystem, 0, 0)`
- `ov01_021FC748(fieldSystem, 0, 1)`
- mode variants around the same call family
- ov02 task-style candidates leading toward the normal Headbutt field task

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_headbutt_task_cleanup_*.png`
- `documentation/verification_screenshots/vfx_102_mode1_*.png`
- `documentation/verification_screenshots/vfx_102_mode2_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_ov02_task_*.png`

Result:

- These are too close to the stock field-move path.
- They either did not give the isolated leaf effect or risked invoking the unwanted presentation behavior.
- Not the right final route for "leaf effect only".

### 2. Existing ov01 Leaf Handle Restart

Tried the map-object effect-list route:

```c
effectContext = ov01_021F146C(playerObject);
effect = ov01_021F1450(effectContext, 0x15);
ov01_022006D4(effect);
```

Relevant visual tester case:

- `OW_WILD_VISUAL_TESTER_HEADBUTT_SAFE_LEAF_RESTART`

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_leaf_restart_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_ov01_restart_*.png`

Result:

- This route is orange-free.
- It does not allocate a new raw effect.
- It does not own the returned handle, so it should not destroy it.
- It is still the safest conceptual route, because vanilla map objects already preload effect ID `0x15`.
- It did not clearly produce the full visible headbutt leaf shower in the slot-102 tester captures, so it needs another targeted pass before being declared solved.

Important note:

- This route should remain the preferred next experiment before returning to raw constructors or ov02 presentation resources.

### 3. Raw ov01 Leaf Constructor

Tried direct construction through:

```c
effectContext = ov01_021F146C(playerObject);
effect = ov01_022006A8(effectContext);
```

with cleanup via:

```c
ov01_022006C4(effect);
```

Representative screenshots and traces:

- `documentation/verification_screenshots/player_step_leaf_022006a8_*.png`
- `documentation/verification_screenshots/player_step_leaf_022006a8_cleanup_*.png`
- `documentation/verification_screenshots/player_step_leaf_022006a8_trace.json`
- `documentation/verification_screenshots/player_step_leaf_022006a8_cleanup_trace.json`
- `documentation/verification_screenshots/vfx_102_leaf_raw_create_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_raw_downface_*.png`

Result:

- This can show the desired green/yellow leaf particles.
- It is risky. A clean retest in the older attempts log froze when using the raw direct constructor path.
- The direct constructor is only valid when passed the effect context from `ov01_021F146C(playerObject)`, not the `LocalMapObject *` itself.
- Even with the correct argument, repeated direct allocation may freeze if lifecycle or preloaded-list assumptions are wrong.

Conclusion:

- Do not use this as the default slot-102 path unless the existing-handle restart path fails and we add a very strict lifecycle guard.

### 4. Wrapper / Nearby ov01 Candidates

Tried nearby wrappers and object-effect helpers already known from the VFX tester:

- `ov01_02200730(playerObject)`
- `ov01_02200540(playerObject, variant, TRUE)`
- `ov01_021FCFEC(fieldSystem->playerAvatar)`
- `ov01_022008B4(fieldSystem->playerAvatar)`
- related cleanup wrappers

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_wrapper_leaf_*.png`
- `documentation/verification_screenshots/vfx_102_wrapper_cleanup_*.png`
- `documentation/verification_screenshots/vfx_102_direction_leaf_*.png`

Result:

- These were stable enough to test, but they did not isolate the desired Headbutt leaf shower.
- Some produced other object effects, fishing/headbutt-adjacent behavior, or no useful visible leaf burst.
- They are not the current best candidate for slot `102`.

### 5. Manual ov02 Work Allocation Without Orange Presenter

Implemented a direct ov02 work path to avoid `0x02249EC0`:

- allocate work with `0x0224955C`
- allocate temp/setup data with `0x0224A074`
- call resource setup `0x0224A080`
- destroy temp with `0x0200770C`
- allocate particle manager with `0x020689C8`
- write expected work fields manually
- call leaf burst `0x0224A9D8(work, 1)`
- track the work for timed cleanup

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_leaf_ov02_resources_no_reveal_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_manual_work_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_manager_no_reveal_*.png`

Result:

- This avoided the orange presenter.
- It did not crash immediately.
- It blackened or replaced the normal top screen after a few frames, often showing the bottom VFX tester box while the top screen became black / `Mystery Zone`.
- No reliable visible leaf shower was confirmed in the tester.

Conclusion:

- Avoiding `0x02249EC0` is not enough.
- `0x0224A080` is likely still too invasive because it prepares field-move presentation resources.

### 6. Script Lock / Wait Variants

Tried different script timing and lock behavior around slot `102`:

- normal locked tester flow
- `releaseall` before waiting
- `lockall` after waiting
- no-wait variants
- longer wait windows before cleanup

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_leaf_nowait_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_releaselock_*.png`
- `documentation/verification_screenshots/vfx_102_leafonly_wait_*.png`

Result:

- Changing script lock/wait behavior did not fix the display corruption.
- This suggests the problem is not simply the script engine holding the player/menu lock.

### 7. Display/VBlank Guard Variants

Tried preserving or repairing the display state around the manual ov02 path:

- display-register snapshots
- display guard variants
- vblank guard variants
- restore-style cleanup variants

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_leaf_display_guard_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_display_guard2_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_vblank_guard_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_ov02_resources_display_regs_after_24f.png`
- `documentation/verification_screenshots/vfx_102_leaf_display_regs_before_play.png`

Result:

- The top-screen corruption still happened.
- The display registers captured after the final pumped attempt looked superficially normal, which points away from a simple register bit being left off.
- The likely damage is resource/background/scene setup from the ov02 field-move resource path, not just display register state.

### 8. Manual Particle Manager Pump

Added a per-frame pump for the manually created particle manager:

- set work `+0x10` to active state `1`
- read particle manager from work `+0x1E0`
- call `0x02068BAC(manager)` each temporary-effect tick
- clear work `+0x10` before destroy

Representative screenshots:

- `documentation/verification_screenshots/vfx_102_leaf_pump_*.png`
- `documentation/verification_screenshots/vfx_102_leaf_pumped_no_reveal_*.png`

Verification from the latest run:

- Build succeeded and copied `test.nds` to Delta as `test841.nds`.
- Headless slot-102 run did not halt.
- Selection memory read confirmed slot `102`.
- Temporary cleanup type was `17`, the manual headbutt-leaf work cleanup.
- Display registers read as normal-looking values:
  - `DISPCNT = 0x00011F18`
  - `BG0CNT = 0x9E01`
  - `BG1CNT = 0x0013`
  - `BG2CNT = 0x0117`
  - `BG3CNT = 0x0208`
  - `BLDCNT = 0x0000`

Result:

- No orange field-move reveal.
- No immediate emulator halt.
- Still no confirmed visible leaf shower.
- Top screen still became black / `Mystery Zone` after a few frames.

Conclusion:

- The missing particle-manager tick was not the only problem.
- The manual ov02 resource path is still not safe for the normal overworld tester.

## Important Trace Findings

Long real-Headbutt trace used hooks on:

- `0x0224A080`
- `0x02249EC0`

Trace output:

- `documentation/verification_screenshots/headbutt_effect_trace_long_work_for_tester.json`
- `documentation/verification_screenshots/headbutt_effect_trace_long_work_for_tester_*.png`

Finding:

- Stock Headbutt does call `0x02249EC0` and `0x0224A080`.
- The direct no-reveal route intentionally skipped `0x02249EC0`, but still called `0x0224A080`.
- Since the no-reveal route still corrupts the top screen, `0x0224A080` is now the main suspect.

## Current Best Next Direction

Stop using the ov02 resource setup path for slot `102`.

The next implementation attempt should route slot `102` through the existing map-object effect handle:

```c
effectContext = ov01_021F146C(playerObject);
effect = ov01_021F1450(effectContext, 0x15);
if (effect != NULL) {
    ov01_022006D4(effect);
}
```

Expected properties:

- no orange field-move reveal
- no `0x02249EC0`
- no `0x0224A080`
- no ownership of the effect handle
- no destructor call for that handle
- low risk of corrupting top-screen resources

If that still does not visibly show leaves in slot `102`, the next fallback should be a tightly guarded raw `ov01_022006A8(effectContext)` probe with strict one-shot cleanup, but only after confirming the existing handle path cannot be made visible.

## Do Not Repeat Without A New Reason

Avoid repeating these as final-slot candidates:

- Full/high-level Headbutt field task routes if they can invoke the orange reveal.
- Raw `ov01_022006A8` with the wrong argument type.
- Repeated raw `ov01_022006A8(effectContext)` allocation without strict cleanup.
- Direct `0x0224A080` resource setup inside the normal overworld tester.
- Timing-only fixes around script lock/wait if the underlying path still uses `0x0224A080`.

