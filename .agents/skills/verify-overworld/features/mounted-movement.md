# Mounted movement and control

Mounted tests prove that the player engine anchor and Pokemon dependent
presentation execute one smooth motion and return control at each terminal
boundary.

## Sub-features

- `mount-begin` binds the current follower and resolved Owner lane.
- `mount-frame-pacing` proves smooth acceleration and render cadence.
- `mount-single-motion` proves the rider does not run a second Hop.
- `mount-detach` proves normal control returns after repeated movement.
- `mount-transition` proves a complete motion survives an area transition.

## How to get to it (user POV)

- Highlight the current follower and press Select.
- Hold a direction to accelerate while mounted.
- Hop, cross a stream boundary, enter a new area, or dismount.

## Driving it with owctl

Preconditions:

- `scripts/owctl doctor` passes with the current ROM and save.
- The mounted scenario uses natural input and current-run proof measurements.

- **Begin.** Run `scripts/owctl scenario run mount.begin-current-follower --json`. The current live follower and resolved profile match.
- **Smooth acceleration.** Run `scripts/owctl scenario run mount.movement.frame-pacing --json`. Require seven rendered motions, exactly seven normal player-step callbacks, no rider/Pokemon delta mismatch, callback and boundary gaps no greater than two, at most one leading zero frame, and final control release.
- **Repeated reliability.** Repeat the accepted frame-pacing scenario for the original failure window. Any failed repetition keeps the bug open. Use the S5 detach and streaming scenarios for long-lived control and world races.
- **One mounted Hop.** Run `scripts/owctl scenario run hop.mounted-single-motion --json`. The S5 frame receipt and rendered pair stay synchronized.
- **Detach.** Run `scripts/owctl scenario run mount.detach-restores-control --json`. One continuous session must complete the authored commit and turn floors, prove the live mounted Cyndaquil identity, then return normal player control after detach and mounted control after remount. The absent-Cyndaquil negative control must fail.
- **Transition.** Run `scripts/owctl scenario run mount.transition-mid-motion --json`. The movement completes across the map change and remains synchronized.
- **Proof.** Read each manifest's native render-pair and frame-timing measurements. Screenshots never prove acceleration or any other test claim.

## Gotchas

- The player is the engine anchor. The Pokemon is dependent presentation.
- Two independently started motions can end at the same tile and still look wrong.
- A single green run cannot clear a stutter that appeared in repeated movement.
- Do not use a short hard-coded turn lane. Validate the complete live lane and
  keep turn points far enough from both ends for the full authored skid.
- Population or streaming work can create a visible frame gap even when motion math is correct.
