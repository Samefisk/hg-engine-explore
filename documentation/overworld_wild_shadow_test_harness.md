# Overworld Wild Shadow Test Harness

This harness captures the saved Igglybuff grass-to-non-grass leftward hop repro
for the midair shadow issue.

## Repro Flow

The current `test.dsv` is saved so that:

1. Booting to the loaded save reaches the overworld repro spot.
2. After a short post-load wait, one LEFT command spawns Igglybuff on the grass
   tile directly beside the left ledge.
3. One RIGHT command triggers that Igglybuff's scared hop-in-place and then its
   actual leftward hop across the grass-to-non-grass boundary.

Run:

```bash
scripts/headless-overworld-shadow-harness.py
```

Useful options:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_after_patch \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn
```

The script uses `test.nds` and the normal `test.dsv` search order from
`scripts/headless-overworld-test.py`. It tracks the ledge-spawned Igglybuff by
default. In `ledge-spawn` mode, the initial target must be a newly appeared
pink component inside the upper ledge repro ROI, `x=70..145` and `y=70..115`,
scored from the ready screenshot versus the after-LEFT screenshot. If that
upper ROI seed is missing, the harness records `target_selection.passed=false`
with an error and exits with status `2`; it does not fall back to the global
largest pink component. After the seed is chosen, continuity tracking is also
limited to the upper hop band, `center_y <= 125`, so lower pink or terrain
components cannot steal the ledge-spawn track.

`--target-igglybuff left`, `--target-igglybuff right`, and
`--target-igglybuff largest` remain global diagnostic modes. The default
`--load-frames 60` is intentionally short; waiting too long lets the Igglybuff
appear before the LEFT command and invalidates the repro sequence.

## Diagnostic Custom Captures

The default no-argument run is still the ledge repro: boot, LEFT spawn,
after-LEFT screenshot, RIGHT-held capture, and `ledge-spawn` ROI target
selection. Custom scenarios are diagnostic captures only. They cannot prove the
midair shadow fix, because only the ledge repro with the `64..179` window covers
the user-confirmed off-grass to non-grass hop.

For nearby diagnostics, use the opt-in custom scenario:

```bash
scripts/headless-overworld-shadow-harness.py \
  --scenario custom \
  --prefix diagnostic_custom_capture \
  --action wait:12 \
  --action hold:RIGHT:20:30 \
  --action capture:control_seed \
  --action capture-hold:LEFT:20:220:30 \
  --target-igglybuff roi \
  --target-stage control_seed \
  --target-roi 90,70,150,125 \
  --target-max-center-y 130 \
  --shadow-check-start-frame 64 \
  --shadow-check-end-frame 179 \
  --disable-movement-pass-check
```

Custom actions are deliberately small:

- `wait:frames`
- `hold:KEY:frames[:release_frames]`
- `capture:stage`
- `capture-hold:KEY:hold_frames:capture_frames[:release_frames]`

A custom run must have exactly one `capture-hold` step, and it must be the
final action, because the shadow and movement oracles evaluate one capture
window. `--target-stage` can be `ready` or any earlier `capture:stage`; if
omitted, the latest captured stage before `capture-hold` is used. With
`--target-igglybuff roi`, the initial body is chosen from pink components whose
center is inside `--target-roi x_min,y_min,x_max,y_max`. After that seed,
tracking follows the nearest full-body component; `--target-max-center-y`
optionally constrains continuity tracking so lower pink components cannot steal
the track.

The movement pass is still tuned for the original leftward ledge repro. For
right-moving or control captures, either disable it with
`--disable-movement-pass-check` or keep it non-fatal with
`--no-fail-on-movement-pass`. Do not use custom runs or grass-only frames such
as f027-f038 as a passing control for this bug.

## Outputs

By default, outputs are written under:

```text
documentation/verification_screenshots/overworld_shadow_harness/
```

Each run writes:

- `<prefix>_00_ready.png`
- `<prefix>_01_after_left_spawn.png`
- `<prefix>_frames/<prefix>_fNNN.png`
- `<prefix>_contact.png`
- `<prefix>_summary.json`

Custom scenarios write `capture:stage` screenshots as
`<prefix>_NN_<stage>.png` instead of `<prefix>_01_after_left_spawn.png`. The
summary records these under `stage_screenshots` and records per-stage pink
component candidates under `stage_pink_components`.

The contact sheet shows only the top DS screen. The magenta rectangle marks the
selected Igglybuff body. The blue rectangle marks the broad floor context below
the body. The yellow rectangle marks the smaller pass/fail shadow core. `core=`
is the number of pixels in that yellow core that darkened compared with frame 0
at the same screen coordinates, and `ok` means that frame met the per-frame
shadow signal.

The summary also includes `dsv_path`, `target_selection`,
`ready_pink_components`, `after_left_pink_components`,
`movement_progress_pass`, and `landing_stall`. For the intended repro, the
ready screenshot should not already contain the ledge-adjacent Igglybuff, and
the after-LEFT screenshot should contain an eligible upper ROI target near
`[105, 84, 118, 95]`. `target_selection.target_roi` and
`target_selection.tracking_band` record the exact ROI and continuity band used
for the run.
Only authoritative ledge repro runs can count as a real pass:
`scenario=ledge-repro`, `target_igglybuff=ledge-spawn`, and shadow window
`64..179`. The summary records this as `authoritative_run.passed=true`. If a
custom run or a different window would otherwise pass both checks, the script
still exits with status `2` unless one of the no-fail/disable flags is used.
`candidate_shadow_frames` and `longest_candidate_shadow_run` are diagnostic
hints for frame/contact-sheet inspection.

For authoritative ledge repro runs, the contact sheet starts at frame `64` by
default. In the current save, frame `27` is only the first tracked leftward
progress marker during setup. It is useful context, but it is not part of the
shadow bug because shadow behavior on grass tiles is irrelevant. Use
`--contact-start-frame N` only when you deliberately want an exact diagnostic
capture window; the actual pass/fail oracle still evaluates frames `64..179`,
where the ledge-spawned Igglybuff should enter and continue the real off-grass
to non-grass hop.

## Interpretation

The harness now has an enabled-by-default pass/fail oracle for the
user-confirmed jump window, frames `64..179`.

The oracle first validates that the tracked object still looks like the real
Igglybuff body:

- `pink_pixels >= 75`
- body height at least `13` pixels

For each valid body frame, the harness marks `shadow_present` only when the
yellow shadow core:

- has at least `10` pixels darker than the same coordinates in frame 0,
- has an average same-run darkening of at least `10`, and
- is at least `8` brightness points darker than nearby side samples in the same
  frame.

That last two-part relative check is intentional. The game changes palette
brightness by time of day, so the oracle avoids absolute "this RGB is dark"
judgment for pass/fail. It compares against the same run's reference frame and
against nearby same-frame pixels instead.

The run passes only if:

- at least `90%` of frames in `64..179` still track a valid Igglybuff body,
- at least `80%` of frames in that window have `shadow_present`, and
- there is no missing-shadow run longer than `3` frames, and
- the tracked body keeps making the real leftward hop:
  - at least `90%` of frames in `64..179` still track a valid Igglybuff body
    for movement evaluation,
  - its minimum center X in `64..179` must move at least `60` pixels left of
    the after-LEFT origin, and
  - it must move at least `24` pixels farther left within the same `64..179`
    window, and
  - `movement_progress_pass` must pass.

The movement check exists because S78 produced a false positive: the shadow
oracle passed, but the Igglybuff froze near the ledge instead of completing the
leftward hop. It now keeps the corrected `64..179` movement checks and also
requires a detected left-progress sequence after `actual_left_hop_start_frame`:

- total progress from the first tracked hop center to the last new leftward
  center must be at least `24` pixels,
- the hop track must include at least `8` distinct center-X positions, and
- at least one new leftward-progress record must happen inside the `64..179`
  shadow window.

This progress gate is tied to body tracking, not shadow color, so the
time-of-day unaffected shadow oracle remains unchanged. It prevents a fix from
passing on a stalled ledge-spawn target that never performs the real leftward
hop. `landing_stall` is reported separately for review; a stationary tail after
the detected progress window is diagnostic and does not fail the run by itself.
Use `--disable-movement-pass-check` only for diagnostic captures.

If either oracle fails, the script exits with status `2`. Use
`--no-fail-on-shadow-pass` or `--no-fail-on-movement-pass` to keep exit status
`0` for one check while collecting evidence, or use
`--disable-shadow-pass-check` / `--disable-movement-pass-check` for
capture-only runs.

For the current bug, inspect the frames where Igglybuff is visibly midair over
the grass-to-non-grass transition. A fixed result should show a stable floor
shadow through the midair section, not a one-frame blink.

## Review Run

Command:

```bash
scripts/headless-overworld-shadow-harness.py \
  --prefix igglybuff_shadow_harness_movement_gate_review \
  --capture-frames 360 \
  --contact-every 4 \
  --target-igglybuff ledge-spawn \
  --no-fail-on-shadow-pass
```

Result on the current clean ROM with the authoritative `64..179` window:

- `shadow_pass.passed=false`: only the early blink frames pass the shadow core
  oracle, currently `7/116` frames (`64..70`), with a long missing-shadow run
  afterward.
- `movement_pass.passed=true`: the ledge-spawn target tracked for `116/116`
  frames in `64..179`, with `origin_left_delta=95` and
  `window_left_delta=45`.
- `movement_progress_pass.passed=true`: actual hop start was frame `27`, the
  detected left-progress window ran through frame `124`, moved `72` pixels
  left, recorded `38` distinct center-X positions, and had `25` left-progress
  records inside the `64..179` shadow window.
- `landing_stall.detected=true`: the late clipped/landing tail was stationary
  from frame `124` through frame `179` at center X `16`.

The process exited `0` because `--no-fail-on-shadow-pass` was used; without
that flag, this clean-ROM run would still fail on the missing shadow.
