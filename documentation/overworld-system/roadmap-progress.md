# Overworld Roadmap — Current State

## Read this first

- [Roadmap](roadmap.md): scope and completion rules.
- This page: short resume state. Replace stale state; do not append run reports.
- Manifests own proof. Changed inputs can make older results stale.
- Detail indexes: [September 7](roadmap-progress-archive-2026-09-07.md),
  [Walk/September 8](roadmap-progress-archive-2026-09-08-walk.md),
  [timing matrix/September 9](roadmap-progress-archive-2026-09-09-matrix.md),
  [stomp/September 9](roadmap-progress-archive-2026-09-09-stomp.md), and
  [crash/September 9](roadmap-progress-archive-2026-09-09-crash.md).
- Missing evidence reopens its requirement. Some old artifacts were deleted.

## Current work table

Scope and exit criteria live in the [finite slices](roadmap.md#finite-delivery-slices).
One accepted contract does not close a whole slice.

| Slice | Owner | State | Evidence / remaining work | Next action |
| --- | --- | --- | --- | --- |
| D0 — proof workflow | root | verified | Shared checked jobs, retained evidence, failure records, and proof-input identity are in place | Reopen only for a concrete tool fault |
| D1 — reported faults | root | source-ready | Both extracted-C spawn-budget checks pass. On ROM3389, `population.spawn-work-budget` stopped at setup: the unchanged independent `test.sav` has Stantler, not the required Mankey follower. The original Delta save has Mankey but starts on Route 29. `world.unmounted.spawn-zero-stutter` has the same missing Route 30/Mankey fixture | Restore the reviewed Route 30 Continue fixture without changing either save, then rerun both short gates on ROM3389 |
| D2 — schema/resolver/facade | root | source-ready | Conditional-profile resolver, evaluator, live controller, ABI, and packaged checks pass | Run the affected roadmap gate after the user check |
| D3 — Walk/chains/roles/Ram | root | source-ready | `NONE` and `PAUSE` are separate chain actions. A lone `PAUSE` now uses chain action chance for mounted and unmounted actors; extracted-C pass/reject checks pass. Rattata look-around converts chain ticks to its authored field-frame time; exact-C and ROM3145 memory checks pass | User checks normal bird and Rattata chain timing; a live lone-`PAUSE` chance below 100% remains unproved |
| D4 — Hop/Teleport/mount | root | active | ROM3371 mounted Sprint reaches the last open tile at a wall and turns away; the registered wall case passed twice. Mounted static-blocker and NPC Hop and Wild static-blocker Hop passed on ROM3371. The Wild NPC case completed its primary Hop but its exact-one-start proof rejected a second chain Hop on the landing frame, so that result is not accepted. Older Pokémon-midpoint and long detach stress remain unaccepted | Keep the user ride and bird rooftop checks open; fix the Wild NPC proof only if its chain-start assumption blocks a required gate |
| D5 — world/transition/population | root | source-ready | Spawn pacing passed on ROM3287, not the current ROM3389; older transition and battle proofs predate the conditional-profile cutover | Run only affected stale proofs at the final gate |
| D6 — remove old paths | root | source-ready | Active, attentive, and the condition shadow bridge are removed; the linked deletion/build checks pass | Preserve through the affected roadmap gate |
| D7 — final acceptance | root | active | ROM3389 is the current candidate for the Floaty Bounce correction. Jigglypuff Hop cadence has accepted proof; spawn pacing, Wild NPC proof, and other roadmap gates remain open | Restore the Route 30 fixture, finish affected proofs and user checks, then run the roadmap gate |

States: queued, active, paused, source-ready, open, verified, blocked.
Verified means the whole slice has current evidence; source-ready does not.

## Active issue and next action

- D1 needs an unchanged Route 30 Continue fixture with Mankey already following for the short current-ROM gates, then the user's stutter check on that same ROM.
- D3 and D4 still need the user's normal bird-chain and rooftop checks.
- The ROM3371 Wild NPC Hop proof needs a reviewed chain-start allowance; the observed primary Hop completed before a second chain Hop began.
- Next action: recover the reviewed D1 fixture without changing either save, then run only stale or missing proofs.

## Current candidate and checks

- Workspace ROM: `test.nds`, SHA256
  `5c9adefa04df45e14a926501a7ec12bbe327b857af8cb7b8403a9ec4c038006b`.
- Delta: `test3389.nds`, same SHA256. Workshop open-after-build is off.
- The independent `test.sav` has SHA256
  `4a9782f24d663fcc6ed168542221cb8fc3ef0ea855b5ef00820a6e04bcaf5203`;
  the untouched Delta original has SHA256
  `c98778b55bf6a018adece1457cb07de6b9fe074b69b93199d88df5a856360e91`.
- [Floaty Bounce Jigglypuff Hop pause](../../build/overworld-devtools/test-456c59a3ccab4e5a8f0d79dd039f1748/manifest.json)
  passed and was accepted on ROM3389: two complete normal Hops each retained
  10 landing-pause frames. The shared Igglybuff profile resolves the same pause;
  Igglybuff has no separate live cadence credit.
- [Mounted Stantler wall approach](../../build/overworld-devtools/test-4900d70c65264ff18e2c640568e6cc95/manifest.json)
  and its [repeat](../../build/overworld-devtools/test-a4bcc037bbee42cd89e0fa23bb7d2434/manifest.json)
  passed and were accepted on ROM3371: four cardinal Walks reach the last
  open tile (589,406), none targets the blocked wall (590,406), and an Up
  Walk commits at (589,405) with control returned.
- Current-ROM [Mounted static Hop](../../build/overworld-devtools/test-eddfb5435e3e48dea31c012eb767fc4f/manifest.json),
  [Wild static Hop](../../build/overworld-devtools/test-664e8347ea194cd98578d3474549ca18/manifest.json),
  and [Mounted NPC Hop](../../build/overworld-devtools/test-d086df5f08e643d29867ce663b67e496/manifest.json)
  passed and were accepted. The [Wild NPC Hop](../../build/overworld-devtools/test-46907c993dd14da791517f33cc9fcf31/manifest.json)
  completed the first two-tile Hop but is not accepted: a second chain Hop
  started on the landing frame, while its proof requires exactly one start.
- The build passed Actor, Wild, Field terrain, mount, spawn identity, occupancy,
  move-history, conditional-profile, and packaged-ROM gates.
- ROM3365 diagnostic memory data: mounted Stantler jumped from (580,397) to
  (582,397) across blocked (581,397) in 16 frames, then resumed Walk and
  accelerated. Wild Stantler did the same from (573,395) to (573,397) across
  blocked (573,396). These recordings are not accepted proof.
- The following ROM3359 mounted results are history. Their changed Sprint
  profile and movement source inputs make them stale for ROM3365.
- The [mounted Stantler route](../../build/overworld-devtools/test-d4bbececeaed4ae8baa90b5ba70000b0/manifest.json)
  passed and was accepted on ROM3359: 840 route frames kept 9/9 nearby
  terrain cells loaded, followed by 25/25 recovery frames and more than
  eight tiles of movement. The earlier ROM lost terrain and faulted on Select.
- The [Stantler skid turn](../../build/overworld-devtools/test-8d421fb2b67b4565ae4c0b6b5ae7d738/manifest.json)
  passed and was accepted on ROM3359: eight east-travel skid frames kept
  the Down-facing turn before recovery. Old-facing and short-skid controls
  were rejected.
- The [Stantler Sprint proof](../../build/overworld-devtools/test-a4b42606976f4b3d8ed88252a0efaddc/manifest.json)
  passed and was accepted on ROM3359: acceleration to speed four, two
  forward chain Hops, and cardinal-only input.
- The [mounted map-crossing proof](../../build/overworld-devtools/test-b7a3c9ad1b5543f5bf234692395674a0/manifest.json)
  and [mid-run Select proof](../../build/overworld-devtools/test-2ede705e9e2b4eae9bd7a20955cc5c17/manifest.json)
  both passed and were accepted on ROM3359. The latter held Right through
  handoff and resumed the same Mankey mount after five frames.
- The [current owner-reader control](../../build/overworld-devtools/test-b1a09649cf9a4f18a3a1d09798622af9/manifest.json)
  passed and was accepted on ROM3359.
- The [long mounted control run](../../build/overworld-devtools/test-b69ca5d4af7540bcaeb7cbb015f7134a/manifest.json)
  on ROM3357 completed 24,032 observed frames without a freeze. It failed at
  Select: its fixed-profile check rejects the Follower policy restored in
  that frame, and its fixed route reached only 1,498 of the required 2,000
  motions. This is not accepted proof.
- The following spawn-work, zero-stutter, and conditional-profile results were
  accepted on ROM3287. They are not proof for the changed ROM3365.
- The [spawn-work proof](../../build/overworld-devtools/test-720a1d96329e4641a7d09f706364d1aa/manifest.json)
  passed and was accepted on ROM3287: 21 destination updates, 169 candidate
  queries, at most 12 per update, one profile/metadata/class preparation, one
  normal Hoothoot spawn Hop, 137 moving frames, and zero late loops or render
  stalls.
- The [zero-stutter proof](../../build/overworld-devtools/test-ec8c77e3840c4f89ae44ef8bfff56952/manifest.json)
  passed and was accepted on the same ROM and unchanged Continue save: 2,620
  observed frames, 1,935 moving frames, and zero late loops or render stalls.
- [Packaged resolver parity](../../build/overworld-devtools/test-706d2f9f2d9b4224bcc3b63afec00671/manifest.json),
  [packaged condition evaluation](../../build/overworld-devtools/test-b2c466b24fbd4df9806ef832282d27a0/manifest.json),
  and the [live Wild condition controller](../../build/overworld-devtools/test-d16169e8d70741088748bfcf026a99d9/manifest.json)
  passed and were accepted on ROM3287. The live controller proof includes
  trigger, held activation, and stale-target fail-close behavior.
- The ROM3143 [Hoothoot chain data](../../build/overworld-devtools/session-ml43dg3r/recording-ec49a9f3e111.json.gz)
  is memory evidence, not acceptance proof. The resolved Bird profile used
  action `PAUSE` (`6`); after its linked movement, the actor entered a 24-tick
  passive wait with no visual chain action.
- ROM3145 [Rattata look-around memory data](../../build/overworld-devtools/session-zf4z6i62/recording-36912f82eaaa.json.gz)
  measured 22, 26, and 28 chain ticks as 44, 52, and 56 field frames. The
  [pre-fix data](../../build/overworld-devtools/session-_lys0g_l/recording-1a9bc7c6901d.json.gz)
  measured a 20-tick action as only 20 field frames. These recordings are
  diagnostic memory evidence, not accepted proof.
- The extracted production reducer and Wild adapter pass separate `NONE`,
  `PAUSE`, and full-frame look-around cases. The current exact-Wild-Walk test
  is not accepted because its independent Wild-clear control is stale and its
  replacement control failed `wild Walk idle no-op clear differs`.

## Session and candidate ownership

- Root owns integration on `feature/conditional-profiles`; preserve
  dirty work.
- Use melonDS shared tools only. No images or video. Do not add a private driver.
- Inspect `dev status` and `dev test status` before live work. Do not take over
  another owner. Tests own a fresh private session.
- Preserve source ROMs, saves, the user's emulator, and the saved build-open
  preference.

## Completion

The roadmap is not complete. Recorded status is not final acceptance. The frozen
candidate must pass all required current proof and
`scripts/owctl verify roadmap --rom test.nds --json` must report `passed: true`.
