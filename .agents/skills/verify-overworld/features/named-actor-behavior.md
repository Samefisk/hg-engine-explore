# Named live actor behavior

Named-actor tests prove that the requested Pokemon exists in the current map
and performs the measured behavior. This prevents a configured species or
empty spawn slot from passing as live proof.

## Sub-features

- `named-identity` proves the live species, object, actor handle, and generations.
- `named-motion` proves the same actor starts and finishes the target motion.
- `ledyba-chain-pause` requires Ledyba's normal chain interval and pause action.
- `ledyba-chain-retry` covers the controlled retry/reposition case only.
- `floaty-bounce-hop-pause` checks two normal Jigglypuff Hops. A host
  catalog check guards Igglybuff's shared Floaty Bounce assignment, but this
  live test gives no Igglybuff cadence credit.

## How to get to it (user POV)

- Enter the test map where the named wild Pokemon can spawn.
- Wait for the Pokemon to appear from off screen.
- Observe its complete movement chain and pause action.

## Driving it with owctl

Preconditions:

- The species-specific scenario has a `live-actor-identity` claim.
- Its registry contract requires species, live object pointer, actor handle,
  object/map/script flags, encounter-generation match, and presentation flags.

- **Controlled Ledyba retry.** Run `chain.pause.counts-semantic-moves` after
  current live reader calibration. Its shared recipe `chain.ledyba-retry`
  acquires natural Ledyba, then rejects one selected action-5 start. Require
  preserved action/ticks and commit count, a full cooldown frame, and all
  profile-defined reposition legs through terminal control. It does not write
  RNG, counters, cooldowns or position. The old nine-forced-Walk fixture is
  archived; do not restore it. Controlled setup cannot close normal timing.
- **Normal Ledyba behavior.** Use `scripts/owctl scenario list` for current
  readiness and `scripts/owctl scenario run chain.pause.ledyba-normal-profile
  --json` only once its exact shared-tool witness is registered. A pending
  migration is a proof gap, and a started job is not a passing result;
  inspect its current manifest and fixture failures before fixing behavior.
  Use the shared devtools for bounded diagnosis, without substituting prepared
  spawn for this normal trigger. Observe real off-screen spawn,
  the normal resolved chain count, complete eligible moves, pause duration and
  action, and visible movement. Record the profile fingerprint and requirement
  used for the expected count. Do not write chain/cooldown values during the
  measurement window. Keep the controlled retry case as separate coverage.
  The registered shared recipe is `chain.ledyba-witness`. Run it through the
  scenario command above for S4 acceptance. Its preflight requires a current
  accepted `observation.live-actor-and-motion-control` calibration; run that
  scenario first after tool changes. A direct `dev test start` is diagnostic,
  not accepted S4 proof. Keep the normal native spawn location and full actor
  identity; do not replace its landing point with another species' destination.
- **Own spawn site.** `spawn.ledyba-pool-site` checks the actual native POOL
  input, finalized destination and completed first Hop of the same natural
  Ledyba. It requires the native field-object creation call, elapsed-zero actor
  render and elapsed-zero engine render to all use the off-screen origin, so a
  one-frame landing-tile flash fails before later state can hide it. Run current
  live recorder calibration first. This is separate S3
  evidence: it does not clear the tree/roof/flower-bed surface-legality report
  or prove later mobility. See the POOL measurement in
  [checked tests](../../../../documentation/overworld-system/devtools-tests.md).
- **Floaty Bounce Hop pause.** Run
  `scripts/owctl scenario run profile.floaty-bounce-hop-pause --json` on the
  current ROM. It prepares Wild Jigglypuff at Route 29 (592,402), then checks
  two complete ordinary Hops from that actor. Each needs the resolved Hop
  time 12, the authored 10-frame settle, a rendered landing, logical commit,
  and control return. The prepared Mankey at (594,402) is setup only. The
  copied zero-pause control must fail. This does not prove natural spawning.
- **Inspect proof.** Open the returned manifest and locate live identity,
  controlled-action, commit, engine-boundary, rendered-motion, and
  control-release measurements for the controlled case. Do not relabel its
  controlled-action claim as natural input.
- **Intermittent behavior.** Repeat the accepted scenario, or promote it to an S5 frame floor, when the report says it fails only after time. Keep every failed run in the result.
- **Proof.** The declared case passes only if the named actor is present and its
  measured lifecycle passes in the same current run. Report any normal-play
  gap separately; a passing controlled test does not remove it.

## Native actor interface lookup

For the roadmap's native `Inspect` interface only, run
`scripts/owctl scenario run actor.inspect-current-and-stale --json`.
This is a separate controlled lookup test, not a named-motion test. It binds
the saved Mankey and checks current/stale native queries without movement or
menu setup. Use its exact `controlled-action` acceptance; do not add a motion
window or claim that it proves movement, selection, or every actor role.
Read the lookup contract in
[checked tests](../../../../documentation/overworld-system/devtools-tests.md)
when changing its recipe or reader.

## Gotchas

- Changing the expected profile species is not actor evidence.
- A non-null stale pointer is not a live object.
- A motion-start counter without finish and control return is incomplete.
- A different Pokemon performing the expected movement is a failed named test.
- Four reposition motions do not establish the number of preceding normal moves.
