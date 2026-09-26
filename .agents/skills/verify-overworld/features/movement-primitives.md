# Walk, Hop, Teleport, and chain actions

Movement tests prove exact travel timing, collision decisions, one terminal
commit, rendered motion, and control return for each movement primitive.

## Sub-features

- `walk-timing` covers cardinal frame values and acceleration.
- `walk-diagonal` covers legal diagonal movement and corner blocking.
- `walk-blocked-facing` covers Wild Exeggcute trapped on a tree canopy.
- `walk-skid` covers one-step turn deceleration, turn skid, and control release.
- `hop` covers cardinal, nearest diagonal, mounted, and ledge movement.
- `teleport` covers fixed and per-tile timing.
- `chain-pause` covers semantic commit counting and pause presentation.

## How to get to it (user POV)

- Walk or hold a direction as a wild Pokemon or mount.
- Turn at speed to skid.
- Move with a Pokemon whose profile uses Hop or Teleport.
- Let a wild Pokemon reach its configured chain-pause count.

## Driving it with owctl

Preconditions:

- `scripts/owctl scenario validate` passes.
- The matching scenario is active. An active scenario is still a proof gap
  until its accepted run belongs to the final ROM.

- **Walk timing.** Run `scripts/owctl scenario run walk.cardinal.frames-1-32 --json` and `scripts/owctl scenario run walk.acceleration.mounted-parity --json`. Exact frame and terminal-boundary measurements pass.
- **Diagonal Walk.** Run `scripts/owctl scenario run walk.diagonal.corner-block --json`. Natural input, the blocked decision, the legal commit, and control return pass.
- **Blocked Wild facing.** Run `scripts/owctl scenario run walk.wild.blocked-facing --json`. The current Wild Exeggcute must keep one facing and one tile for 128 continuous completed frames on the blocked canopy at map 33 (580,409).
- **Mounted stomp.** Run `observation.stomp-policy-control`, then
  `walk.stomp.feedback` through `owctl scenario run`. Reuse a current accepted
  reader control when the controller permits it. The two prepared Cyndaquil
  moves check dust/sound-start at threshold2 and no feedback at travel time3,
  exact player-step count, paired poses and control return. This is not Wild
  role parity, authored-profile timing, or sound-from-speakers proof. See
  [checked tests](../../../../documentation/overworld-system/devtools-tests.md#author-an-executable-test).
- **Hop.** Run `scripts/owctl scenario run hop.cardinal-and-diagonal --json` and `scripts/owctl scenario run hop.ledge-up-and-down --json`. For mounted lifecycle races, also run `scripts/owctl scenario run hop.mounted-single-motion --json`.
- **Teleport.** Run `scripts/owctl scenario run teleport.fixed-and-per-tile --json` when its shared port is active. Require native visibility, pose, timing and terminal-event measurements; screenshots supply no proof.
- **Chain pause.** The current `chain.pause.counts-semantic-moves` case is a
  controlled retry, not normal Ledyba timing proof. Use the
  [named-actor recipe](named-actor-behavior.md) for identity, case limits, and
  the separate required normal-play witness.
- **Proof.** Read the measurements in each manifest. End coordinates alone do not prove timing, an arc, or control release.

## Gotchas

- Skid, reposition, interpolation, and stream-anchor changes are not extra
  chain-eligible movement decisions. A motion can still have a terminal result.
- Use shared devtools for diagnosis and checked tests. The old standalone
  runners are removed. A pending migration remains an explicit proof gap.
- Screenshots supply no proof. Read the native presentation samples across the complete motion, not only its endpoint.
