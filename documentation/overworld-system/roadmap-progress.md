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
| D1 — reported faults | root | verified | The retained spawn-work gates pass, and the user confirms the current ROM no longer stutters | Preserve through final acceptance |
| D2 — schema/resolver/facade | root | verified | Binding, resolver, Inspect, owner-control, transfer, ABI, and packaged checks passed | Preserve through final acceptance |
| D3 — Walk/chains/roles/Ram | root | source-ready | `NONE` and `PAUSE` are separate chain actions. Rattata look-around now converts chain ticks to its authored field-frame time; exact-C and ROM3145 memory checks pass | User checks normal bird and Rattata chain timing; preserve the regressions |
| D4 — Hop/Teleport/mount | root | source-ready | Shared Motion owns Walk, Hop, and Teleport. Due actors can start together. A directed Hop now requires a strictly closer landing | User checks bird rooftop behavior; preserve the exact-C planner regression |
| D5 — world/transition/population | root | verified | Warp, mounted-Walk transition, Wild battle handoff, and the 5,000-frame mounted-Hop transition pass | Preserve through final acceptance |
| D6 — remove old paths | root | verified | All 40 migration rows are ported or obsolete. ROM3150 passes every linked ownership and packaged overlay deletion check | Preserve through final acceptance |
| D7 — final acceptance | root | active | ROM3150 is the frozen code candidate. D1, D5, and D6 are verified | Run only stale or missing required proofs, then the roadmap gate |

States: queued, active, paused, source-ready, open, verified, blocked.
Verified means the whole slice has current evidence; source-ready does not.

## Active issue and next action

- D3 and D4 still need the user's normal bird-chain and rooftop checks.
- Next action: inspect the final gate and run only stale or missing proofs.

## Current candidate and checks

- Workspace ROM: `test.nds`, SHA256
  `047bb6bb8bab4b824570eca6b6b5c87cad8a25b7121a6a108dcc4fac615346ea`.
- Delta: `test3150.nds`, same SHA256. Workshop open-after-build is off.
- The [Wild battle handoff proof](../../build/overworld-devtools/test-944bd15d61684a34bbc0f90c4b069292/manifest.json)
  passes on ROM3150: the same live Rattata completes a natural Walk, receives
  the natural A edge, and enters one successful battle request.
- The [mounted-Hop transition proof](../../build/overworld-devtools/test-9ebab17b07054c34a6807d02946c13c0/manifest.json)
  passes on ROM3150 with 5,000 post-transition input frames and 10,832 observed
  frames. The current linked/package legacy-owner deletion check also passes.
- The build passed Actor, Wild, Field terrain, mount, spawn identity, occupancy,
  move-history, and packaged-ROM gates.
- The retained [spawn-work proof](../../build/overworld-devtools/test-1847baa9d74f4855970a4da14aa43c26/manifest.json)
  passed: 340 frames, 240 candidate queries, one profile
  and metadata preparation, at most 16 queries per update, and no late frame
  or render stall.
- The retained [zero-stutter proof](../../build/overworld-devtools/test-2ad7edfb32a947cbb3792f842ae80381/manifest.json)
  passed on its unchanged Continue save: 2600 strict frames,
  1935 moving frames, 272 joined spawn-work witnesses, at most 16 scan frames,
  and zero late loops or render stalls.
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

- Root owns integration on `feature/overworld-actor-system-roadmap`; preserve
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
