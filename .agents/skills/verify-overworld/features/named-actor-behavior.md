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
- **Pokémon collision HP and knockback.** Run
  `scripts/owctl scenario run pokemon-hp.collision-knockback --json` on the
  current ROM. The private fixture mounts level50 Cyndaquil and places Wild
  Snorlax and Weepinbell on Route29. Ordinary Ambush motion must damage the
  Wild target, then the mounted party Pokémon and rider. Completed queue
  samples read the actual resident/party HP, target identity, hit guard, and
  one-tile jump arc and landing. The mount and rider share one anchor and
  restore their seat height. Missing real HP loss or a missing jump fails.
  Prepared placement does not prove natural spawning, healing, or selection.
- **Follower sight pickup and Throw Away.** Run
  `scripts/owctl scenario run follower.throw-moving-cargo --json` on the current
  ROM. One naturally noticed moving Bellsprout is both Object of interest and
  Cargo. Keep its full handle, subject and engine identity through legal pickup
  and native flight. Its accepted Walk must commit and return control before
  carry. Mankey must complete a half-speed pursuit Hop (Long Hop7→3), resolve
  held Find Position and Follower Away target14 at half speed, then launch the
  same Bell to an admitted cardinal endpoint exactly8 tiles away with greater
  Chebyshev separation from Player. Require complete dense native flight,
  timed commit, landing and control return; normal follow then uses base7 again.
  A legal Away line at pickup needs no Position Hop. If a Position Hop is
  admitted, its complete timing/commit/return still applies. Keep all original
  identity, binding, movement, field, speed and recovery controls, plus exact
  Interest, range, endpoint direction and flight-return controls.
  The native plan proves the admitted endpoint. Actual-C Away tests own safe
  selection and the same saved aim/support recheck before launch; this reader
  does not observe the saved windup aim. Accepted player-damage source capture
  without Vision remains the separate `follower.throw-player-damage` case. Its
  normal left sidestep releases at the first logical tile admission; neutral
  Player and Follower settle gates must pass before the source spawns. These
  setup moves earn no hit or Throw credit.
  The first complete Cargo Hop must keep its current unlimited-range query key
  and retained graph on every moving sample and on the exact native return.
  Run `scripts/owctl scenario run follower.throw-away-non45 --json` for the
  separate uneven-angle contract. Only Bell placement changes to590403. Keep
  the same full identity, own moving Cargo completion, search timing, query,
  held phase and normal return guards. The real flight must match the outward
  projection at Chebyshev radius8 with two nonzero, unequal offsets. A straight
  or 45-degree fallback fails. Require the authored release clock and exact
  native landing support height. Its native plan distance remains8; the shared
  logical path can contain more advances. Host Away and trajectory checks own
  saved support recheck and all crossed-cell probes. ROM3530 passed the
  registered full-flight case in `test-a055bcfe17df4db0aa423c9317bcd991`:
  Bellsprout flew from585402 to583394, landed at the native support height,
  and Mankey returned to normal Follow. The separate current
  `player-hp.throw-contact` pass retains cardinal launch, damage and Slide.
  `wild.throw-moving-candidate` remains the separate Wild Cargo/aim counterpart.
  It uses ordinary Sprint Stantler234 at585403 and Geodude74 at583403.
  Stantler has no Wild attack condition. Its current own profile must stay fixed
  through pursuit; only actual pickup may take its native AUTO control.
  Require that same full Cargo still has an ordinary accepted moving plan in
  the frame immediately before pickup. Its exact native CANCEL and CONTROL
  return must precede the same HELD claim. Idle pickup earns no credit, and
  the carrier must not be canceled. Keep current raw plan/token and control
  copies, full source/engine identity, claim masks, and native event order.
  Its first Notice may be a current zero-pointer Pending before Player capture
  contributes Search. Keep the authored20-frame alert; resume query work at its
  end. Retain the first prepared exact-Cargo graph through one complete8-frame
  Walk and its native commit, finish and control return. Reachable admits Walk
  within one frame. Only exact-Cargo ownership fixation0→1 is allowed. A graph
  already prepared before Notice must still survive the alert. This replaces
  the obsolete requirement that every first Notice already has a graph; it
  does not credit missing movement, identity, query budgets or launch.
  Each observed stock bubble sound must have its exact synchronous quiet Stop.
  Stock bubble reuse can return before the sound initializer; the quiet wrapper
  still stops the sequence. An authenticated extra Stop after a real pair earns
  no pair credit. Keep its current clock, sequence, caller and sound-ID checks.
  Run `scripts/owctl scenario run follower.throw-query-priority --json` for the
  saved-Mankey stop regression. Use unchanged Continue with no Y, party or
  follower writes. The first native Geodude must land at595407 and own a busy
  unclaimed Wild Cargo query. Replay the saved initial RIGHT160 and neutral40
  approach, Route29 teleport and settle20, first Geodude587408 and wait180,
  occluded Geodude589408 and wait220, then RIGHT16 and neutral100. This is the
  measured failure setup. The occluded Geodude is behind a blocked tile and
  does not earn Sight credit. Spawn the distinct clear source587404, which
  must give Mankey fresh Sight Interest. Require the same workspace to hand off
  to that full Follower identity, current Reachable route proof, the exact new
  Geodude claim and pickup, complete Away flight, and full normal Follow return.
  Keep Notice20, half-speed search and Hop pause5. A Pending read earns no route
  or movement credit. Copied old-owner, wrong-target, lost-claim and missing
  flight-control faults must fail their named guards. A fixture that does not
  recreate the old busy owner fails; it does not prove generic fairness or
  timeouts. ROM3530 passed this complete chain twice in
  `test-c2cdcdefa9094a048ce7f414f68f3443` and
  `test-7febd2071ec4474cbbf085e69dc42e05`, with882 observed frames each.
  The same workspace hands off after Notice20; Cargo binds two frames later.
  Keep the failed setup attempts as evidence of their failed layer. They
  cannot supply gameplay credit. Final proof and the current zero-stutter
  gates are listed in `build/tickets/tkt41/rom3530-final-ticket-evidence.json`.
  The old `follower.throw-approach-cargo` case is retired because its required
  separate Interest/Cargo and aim at Interest contradict the new Follower
  pickup-and-throw-away contract. Its old native artifacts stay unchanged;
  they do not earn current proof. Prepared placement does not prove natural
  spawning, every walk-up approach, Walk timing or Chase boost.
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

Basic attack is currently disabled through its0% condition chance. Run
`scripts/owctl scenario run profile.basic-attack --json` only after an explicit
request enables it again. Its prior native runs remain scoped to the enabled
catalog. The host check uses an explicitly enabled disposable catalog and also
proves that the shipping0% condition cannot activate or retain an old activation.
The prepared adjacent Wild Snorlax/Cyndaquil pair uses the authored condition
without profile or timer writes. It proves current target capture, inherited
Hop time four on both legs, Face movement, exact target landing, an immediate
return to the saved origin, a20–40-frame pause after the pair, real20 HP loss
and control return. The native host
check `python3 -B tools/overworld/test_basic_attack_profile.py` covers all
species IDs, eight adjacent directions, same-tile targets, full-handle self
exclusion, while-true ending beyond range one, and inherited
knockback. The live case grants no separate all-direction or lifetime claim.

- Changing the expected profile species is not actor evidence.
- A non-null stale pointer is not a live object.
- A motion-start counter without finish and control return is incomplete.
- A different Pokemon performing the expected movement is a failed named test.
- Four reposition motions do not establish the number of preceding normal moves.

- **Ram ledge continuity.** Run `scripts/owctl scenario run profile.ram.ledge-continuity --json` on the current ROM. The exact Wild Onix makes a natural South charge and crosses the Route29 ledge590396 after a normal Right player dodge. The same current owner must finish Hop590395→590397, preserve raw heading/Linear acceleration and active Until Crash state, and complete the next South Walk590397→590398 without Crash or cancellation. This complements the separate long-charge/Crash proof; it does not replace it.

- `wild.throw-cargo-competition` checks a nearer Wild Geodude taking the same free Cargo that a farther Wild Geodude is pursuing. Keep the normal Player sight trigger and authored alert. Require full current bindings, one protected HELD owner, immediate losing claim cleanup, same Cargo launch, and normal losing carrier progress. The shared actual-C handoff checks cover the Follower path; this native fixture has two Wild carriers.
