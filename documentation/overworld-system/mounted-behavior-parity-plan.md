# Mounted Pokémon behavior parity plan

Status: proposed repair plan. No runtime change or acceptance claim is made by
this document.

## Outcome and comparison rule

A mounted Pokémon must keep its authored movement behavior. Mounting changes
who supplies intent (rider input instead of Wild or Follower AI) and how the
single motion is displayed (player engine anchor, rider, dependent Pokémon).
It must not silently change the selected Pokémon's travel times, acceleration,
direction permission, pause, sway, skid, chain action, Hop, or Teleport values.
Only fields explicitly set by the Mounted System profile may override those
values. Mounted currently has no field operators.

Use the Pokémon's **normal selected Owner behavior plus Mounted**, not the
Follower System profile, as the movement comparison. Follower's chase, spawn,
land-only, speed-cap, and zero-Walk-pause fields are for following. The role
controller may turn an authored Wander/Walk request into rider-directed Walk;
it may not rewrite the movement fields used for that Walk. AI target choice,
the rider's interaction/collision duties, and the rider's fixed vertical offset
are intentional role differences. Do not promise AI chase or target-triggered
attitudes while rider input owns the actor.

This is a proposed clarification of the current contract, which says Mounted
inherits Follower. Update `CONTEXT.md`, `README.md`, `architecture.md`, the
resolver scenario, and the feature map when implementing it. Do not change the
catalog just to compensate for runtime adapter errors.

## Baseline facts and open measurement

- `Mounted` is empty, but mount begin forces **Follower + Mounted**. Follower
  changes eight fields, including `chillSpeed` (at most 8), `walkPause` (0),
  and land traversal. Worse, mount begin then copies the live Follower slot
  profile over the resolved Mounted profile while retaining the first result's
  fingerprint and layer mask. The binding can therefore describe different
  values from those actually used. See
  `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` at
  `OverworldWildSpawns_BeginMountSelectedFollower` and
  `OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot`.
- A pre-fix same-ROM mounted Stantler memory trace has a Walk at frame 1104,
  one idle frame at 1105 after a fresh Right press, then a new Walk at 1106
  with base travel time 8. `OverworldMount_ProcessPlayerControl` reads
  `directionInputHeld`, which is updated later in `OverworldMount_Tick`.
  Diagnostic artifact: `build/overworld-devtools/session-5s9k92xo/recording-22165b125456.json.gz`.
- A mounted Walk moves the player object and mirrors its coordinates to the
  Pokémon. In the saved mounted Stantler trace, the Pokémon's movement command
  stays 255 and step 0. A Wild Stantler Walk uses command 62 and moving flags.
  This proves a native state difference, **not** its visible effect. The active
  Walk timing contract does not add a separate leg-animation system. Do not
  copy Wild flags or start a second Pokémon movement command merely because
  these bytes differ. Diagnostic artifacts:
  `build/overworld-devtools/session-5s9k92xo/recording-11bdb9d7810c.json.gz`
  and `recording-155fd54923ff.json.gz` in that directory.
- Mounted Stantler did complete an eight-frame stop skid in the saved trace
  `recording-c8b12908df7f.json.gz`. The earlier claim that mounted stop skid
  is always skipped was wrong. Preserve this behavior during the repair.
- A previous mounted trace shows an idle frame after a chain Hop before the
  next Walk. This is a parity candidate, not yet a matched Wild/Mounted proof.
- Sprint Stantler has `walkPause=0` and default Walk sway 0, so those hardcoded
  mounted values do not explain this particular Stantler report. They are still
  generic inheritance defects for profiles with nonzero values.

Before editing product code, retain one matched clear-lane Wild/Mounted
Stantler recording on the same current ROM/profile. Match accepted direction,
nominal time, motion kind, chain action, and field-frame boundary; do not force
policy counters or RNG to manufacture parity. Read native render X/Y/Z,
facing, vertical offset, visibility, shadow base, and any authenticated sprite
pose/animation state. If the existing reader lacks the last value, add only
that bounded read and its wrong-identity/changed-value control. Do not use
screenshots. The existing key-edge trace already supplies its pre-edit
reproduction; repeat its exact input schedule after the fix.

## Repair sequence

### 1. Bind one truthful mounted behavior result

1. In mount begin, resolve the current subject once with its normal selected
   layers and forced Mounted System layer. Pass the current valid conditional
   application set into that same request where appropriate. Do not call the
   Follower slot helper to overwrite `resolution.profile`; that helper can
   also rebind Follower policy as a side effect.
2. Snapshot the **same** result's Owner lane, primitives, fingerprint, and
   layer mask. Swap the actor policy only after that result is ready. On
   failure, leave Follower policy and presentation untouched. On detach,
   restore the Follower binding from the saved pre-mount result.
3. Assert field-by-field inheritance for Sprint and at least one profile with
   nonzero Walk pause/sway or a base time slower than 8. Check the eight
   Follower-only fields explicitly so an accidental Follower layer cannot
   pass merely because Sprint happens to share its current numeric values.
   Check provenance and that the fingerprint describes the exact bound bytes.

Exit: Mounted differs from normal selected movement only where an explicit
Mounted operator exists; the actor's snapshot, policy binding, and resolver
receipt agree.

### 2. Repair the tile-boundary input transaction

1. At `CONTINUATION_READY`, use the current `newKeys | heldKeys` passed to
   `OverworldMount_ProcessPlayerControl`, not the direction sampled by the
   previous actor tick. A current direction gets a same-field-control-pass
   start when the player-step and world-gate checks admit it. A real current
   `NONE` follows the shared stop/skid rule. A rejected direction remains a
   rejected candidate; it must not become a stop or reset momentum.
2. Keep the existing `INPUT -> START_RESULT -> COMMIT` order and the stock
   `PLAYER_MOVE_STATE_END` receipt. Do not preload elapsed time or start a
   second actor tick. Preserve momentum if no actual stop committed; after a
   real stop, restart from the base travel time.
3. Give mounted Walk the same chain-enabled, step-validation, turn-skid
   corridor, and direction-permission policy inputs as Wild. Use the player
   anchor for field collision/streaming, but keep the actor's same typed
   accept/reject result. Cardinal-only Stantler must choose one cardinal
   axis when two keys are held; a diagonal-capable profile must pass the same
   destination and two-side-tile check as Wild.
4. Keep Select-edge capture in its existing field-ready owner. Do not add a
   second detector while changing direction input. A short Select press
   during a run stays buffered to the safe handoff; holding Select across
   mount begin cannot toggle again without a release and new press.

Exit: replay frames 1104-1106 with the same key schedule. A fresh press is
handled on the first eligible frame, with no unexplained idle frame. Held
straight Walk remains continuous; genuine release still produces its correct
stop skid and speed reset; wall rejection does not alter momentum.

### 3. Make the presentation seam share meaning, not engine ownership

The existing shared `OverworldMotionSample` is the seam. Keep two real engine
adapters: Wild owns one Pokémon object; Mounted owns one player engine anchor
and one dependent Pokémon presentation. Define a small internal sample-to-pose
projection for render position, unswayed logical tile, ground base, height
offset, facing, visibility, and shadow/effect state. Both adapters use those
semantic values. The mounted adapter must not call Wild's MapObject command
path or create a second motion owner; that would fight the player stream and
can reintroduce a full-tile split at Walk boundaries.

First use the native pose measurement to decide which mounted outputs differ.
Then change only the affected application points in
`OverworldMount_UpdateCustomMotion` and
`OverworldFieldService_SyncMountedPresentation`. Ensure the field sync does
not overwrite a motion-owned Pokémon pose each tick. Keep the rider's offset
relative to the Pokémon ground/arc pose. For Hop, derive logical tile and
path advances from the shared unswayed path, not `renderX/Z >> 16` when sway
is nonzero. For Walk, feed authored sway and pause through the same motion and
post-commit units as Wild, without extending the terminal boundary twice.
If a versioned field-presentation call must change, update its ABI checks and
linked overlay-size proof together.

Exit: same actor motion samples give the expected player/Pokémon pair pose on
every completed game frame, including Walk terminal frame, Hop arc/landing,
shadow, turn, cancel, detach, and transition rebind. A movement-command byte
may differ if the semantic pose and lifecycle are correct.

### 4. Complete chain action and retry behavior

Use one action decision and typed outcome (`started`, `retryable`, or final
no-action) for both roles. The mounted action executor must honor every
action that an inherited profile can select: `NONE`, `PAUSE`,
`HOP_FORWARD`, `HOP_IN_PLACE`, `LOOK_AROUND`, and the three reposition modes.
It must not silently consume an unsupported action or a temporary failed
Hop start. Keep action timing, chain counter, nominal speed, and next-chain
start tied to the same terminal commit. A chain Hop must preserve momentum
only through successful start/finalize; cancel, context loss, and failed
stream preparation must reset it before Follower policy is restored.

The current mount-chain overlay is a fixed 0x300-byte block with little room.
Do not squeeze a large second action engine into it. Put shared selection and
outcome logic behind the existing actor/policy service and use an audited code
home for any extra mounted engine action adapter. Retain the fixed entry ABI
and prove the linked byte limits before a ROM run.

Exit: Stantler's natural `HOP_FORWARD` is two tiles at the committed heading,
uses twice the current nominal Walk time, has no extra idle frame or pause,
and the next chain resumes at the prior speed. A retryable busy result retains
the pending action; a permanent blocked result follows the same Wild policy.
Representative actions from the other categories obey their authored times.

### 5. Integrate one current-ROM proof set

- Extend `profile.resolve.follower-mounted-parity` or replace its claims with
  a normal-vs-Mounted field/provenance case. Keep a separate Follower-to-Mount
  identity/restore test; do not erase that lifecycle coverage.
- Keep `mount.stantler-sprint-parity` for natural acceleration, two chain Hops,
  and cardinal input. Add a focused registered key-edge scenario with the
  preserved pre-fix trigger and a copied-data control that rejects the old
  idle/reset result. Add a matched Wild/Mounted pose case at S4 for fields
  shown by the baseline to matter. Test a non-Sprint profile with nonzero
  pause/sway and each inherited chain-action family.
- Run the smallest host policy/resolver tests first. Then package/ABI and
  overlay-size checks. Build a fresh ROM through the saved Delta-build
  workflow, repeat the pre-fix measurements unchanged, and run the affected
  registered scenarios: mounted frame pacing, Stantler Sprint, turn/stop
  skid, diagonal corner block, Hop single-motion, mount/detach, and mounted
  Walk/Hop field transitions. Keep existing Wild counterparts passing.
  Include short-press, held-press, and release/repress Select cases, a
  retryable chain start, and cancel/detach during a pending chain Hop.
- If profile data, generated data, destination masks, Follower Hop planning,
  or Hop landing validation change, also run the two extracted-C spawn-budget
  checks, the current-ROM short spawn-work scenario, and
  `world.unmounted.spawn-zero-stutter` on that **same** ROM and unchanged
  Continue save. Do not carry an older ROM's D1 pass forward.
- Use accepted memory-backed S3/S4 proof, not static checks or screenshots,
  for the game-feel and presentation claim. Update the canonical contract,
  feature map, scenario claims, and current work table after the integrated
  result. Give the user that same ROM for a Stantler ride check. Do not mark
  the work complete while the user still reports the mismatch or required
  proof remains open.

## Boundaries and risks

- Keep one actor, one reservation, one terminal commit, and one player
  engine anchor throughout the mount session. No independent Pokémon motion
  command and no raw copy of Wild MapObject flags without native meaning.
- Wild AI may choose a different heading or rest state. Compare the same
  accepted movement and resolved Owner fields, not random AI choice against
  a player's chosen key. A distinct Mounted fingerprint is fine; mismatched
  fields behind that fingerprint are not.
- Follow the current field-control order, transition epoch, and stream
  acknowledgement. An apparent one-frame improvement is not valid if it
  double-commits a tile, skips a warp, or loses control after Hop/transition.
- Keep the active Walk specification's no-extra-leg-animation rule. Only add
  an animation mechanism if authenticated native pose data show a missing
  requirement and the contract is changed deliberately.
