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

- **Begin during movement.** Run `scripts/owctl scenario run mount.begin-current-follower --json`. Select during a normal player step must wait for that step, mount the same current follower, and complete a later Hop with player movement restored.
- **Responsive Select mid-run.** Run `scripts/owctl scenario run mount.select-mid-run --json` on the unchanged saved Mankey follower. Right stays held through Select and the role change. The same moving follower must mount within eight completed game frames of the native Select edge and finish one mounted Hop with control returned.
- **Smooth acceleration.** Run `scripts/owctl scenario run mount.movement.frame-pacing --json`. Require seven rendered motions, exactly seven normal player-step callbacks, no rider/Pokemon delta mismatch, callback and boundary gaps no greater than two, at most one leading zero frame, and final control release.
- **Mounted Stantler speed changes and gait.** Run `scripts/owctl scenario run mount.stantler-speed-slew --json` on the copied save. Hold Right for thirteen natural Walks with Sprint starting at six frames, variance two, acceleration one, and Mounted maximum speed two frames. Keep full keyed variance through the first nominal two-frame tile; each later committed normal Walk reduces its width by one until zero. Thus widths are 2,2,2,2,2,1,0,0,0,0,0,0,0. Preserve the exact eased ground path, shared rider/mount base and thirteen normal step callbacks. Check each native gait pose against the distance/frame reference with the authored bounce2, stride2, settle1 and lean1 controls; check actual graphics XYZ, a ground-anchored camera and shadow, and continuous gait phase through speed changes. Release input and require two four-frame stop-skid tiles with one normal step callback per tile, then zero final gait offsets. Copied controls must reject persistent variance at top speed, extra motion, missing bounce, missing lean, phase reset, a common position snap, a stale visible sprite and a trailing shadow. The current pose-reader control also changes one native gait offset and restores it without advancing the guest. This checks one clear lane; the compiled gait model covers all32 speeds and all256 packed control values. Prior accepted gait run `test-d8d95e267b0a4e83a492c6231ca9362f` is the old-behavior baseline: its ninth Walk still took four frames after reaching nominal two-frame speed. That run cannot accept the new variance rule.
- **Mounted Stantler Sprint parity.** Run `scripts/owctl scenario run mount.stantler-sprint-parity --json`. The prepared Stantler must accelerate from nominal Walk speed 8 to 4 under held Right. On clear ground, it must complete at least eight one-tile Walks with no Hop and keep speed 4. Authored variance can add up to two display frames to a Walk tile. With Up and Right held together, no diagonal Walk or diagonal player step may occur. The copied-data controls reject a missing Walk start, slow Walk, unexpected Hop, speed reset, diagonal target and changed actor.
- **Mounted Stantler key edge.** Run `scripts/owctl scenario run mount.stantler-key-edge --json`. The prepared Stantler first reaches a second Right Walk at nominal speed 7. Release Right while that tile finishes, then press Right on the completed frame after `COMMIT_PENDING`. The first true native `newKeys` Right sample must already have the next Walk moving at speed 6. At most one preceding stale key sample is allowed. The copied-data control rejects the preserved idle frame and speed reset; this short test does not replace the full clear-lane or obstacle proof.
- **Mounted Stantler wall approach.** Run `scripts/owctl scenario run mount.stantler-sprint-wall-approach --json` with the copied `test.sav` start at Route 29 (585,406). Hold Right for 120 completed frames. The same mounted Stantler must complete four cardinal Walks to the last clear tile (589,406), not stop at (588,406) or enter the blocked wall (590,406), then turn Up and settle at (589,405). The copied-data controls reject an early stop, wall entry, wrong Walk target, missing start or commit, missed Up turn and changed actor. This one wall does not replace the general Sprint or obstacle-Hop cases.
- **Non-Sprint Waddle.** Run `scripts/owctl scenario run mount.bellsprout-waddle-sway --json`. One prepared Bellsprout takes a normal Meander Right Walk at nominal time 14 plus at most two variance frames. Live player and Pokémon poses must share signed lateral Waddle sway, stay on one logical lane, center at the end, and return control after one commit. Copied-data controls reject lost sway, a split pose, Follower speed cap, extra start, wrong lane and changed actor. This case does not test nonzero Walk pause.
- **Four-frame Stantler turn skid.** `mount.stantler-turn-skid-facing` requires a displayed four-frame Walk before Down, then two consecutive eight-frame east-travel skid tiles. Both sprites must face Down on all sixteen frames, each tile must commit and return control once, and Down recovery must follow. Missing second-tile and missing-commit controls must fail. The fixed Right49 run-up and fixed-offset pair reader predate the gait change; confirm that run-up and finish its gait-aware reader before claiming current runtime proof. Do not relax the four-frame boundary or pair checks.
- **Repeated reliability.** Repeat the accepted frame-pacing scenario for the original failure window. Any failed repetition keeps the bug open. Use the S5 detach and streaming scenarios for long-lived control and world races.
- **One mounted Hop.** Run `scripts/owctl scenario run hop.mounted-single-motion --json`. The S5 frame receipt and rendered pair stay synchronized.
- **Detach.** Run `scripts/owctl scenario run mount.detach-restores-control --json`. One continuous session must complete the authored commit and turn floors, prove the live mounted Cyndaquil identity, then return normal player control after detach and mounted control after remount. The absent-Cyndaquil negative control must fail.
- **Follower resume after detach.** Run `scripts/owctl scenario run mount.detach-follower-resumes-motion --json`. The same Cyndaquil must rebound from Mounted to Follower and finish its first normal follower Walk no later than two completed frames after the player moves away. The delayed-motion copied-data control must fail.
- **Transition.** Run `scripts/owctl scenario run mount.transition-mid-motion --json`. The movement completes across the map change and remains synchronized.
- **Proof.** Read each manifest's native render-pair and frame-timing measurements. Screenshots never prove acceleration or any other test claim.

## Gotchas

- The player is the engine anchor. The Pokemon is dependent presentation.
- Two independently started motions can end at the same tile and still look wrong.
- A single green run cannot clear a stutter that appeared in repeated movement.
- Do not use a short hard-coded turn lane. Validate the complete live lane and
  keep turn points far enough from both ends for the full authored skid.
- Population or streaming work can create a visible frame gap even when motion math is correct.
