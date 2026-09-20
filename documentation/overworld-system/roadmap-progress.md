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
| D1 — reported faults | root | source-ready | Current-ROM spawn-work and zero-stutter gates pass | User checks the same ROM for the reported stutter |
| D2 — schema/resolver/facade | root | source-ready | Conditional-profile resolver, evaluator, live controller, ABI, and packaged checks pass | Run the affected roadmap gate after the user check |
| D3 — Walk/chains/roles/Ram | root | source-ready | `NONE` and `PAUSE` are separate chain actions. Rattata look-around now converts chain ticks to its authored field-frame time; exact-C and ROM3145 memory checks pass | User checks normal bird and Rattata chain timing; preserve the regressions |
| D4 — Hop/Teleport/mount | root | source-ready | Shared Motion owns Walk, Hop, and Teleport. Due actors can start together. A directed Hop now requires a strictly closer landing | User checks bird rooftop behavior; preserve the exact-C planner regression |
| D5 — world/transition/population | root | source-ready | Current-ROM spawn pacing passes; older transition and battle proofs predate the conditional-profile cutover | Run only affected stale proofs at the final gate |
| D6 — remove old paths | root | source-ready | Active, attentive, and the condition shadow bridge are removed; the linked deletion/build checks pass | Preserve through the affected roadmap gate |
| D7 — final acceptance | root | active | ROM3287 is the current candidate; automated conditional-profile and pacing acceptance passes | Finish user checks, then run the affected roadmap gate |

States: queued, active, paused, source-ready, open, verified, blocked.
Verified means the whole slice has current evidence; source-ready does not.

## Active issue and next action

- D1 needs the user's stutter check on ROM3287.
- D3 and D4 still need the user's normal bird-chain and rooftop checks.
- Next action: finish those user checks, then run only stale or missing proofs.

## Current candidate and checks

- Workspace ROM: `test.nds`, SHA256
  `e3783bbbac6a4c042dcd59e3b81a91f63c08f520380770644cc3214c0a8b9633`.
- Delta: `test3287.nds`, same SHA256. Workshop open-after-build is off.
- The build passed Actor, Wild, Field terrain, mount, spawn identity, occupancy,
  move-history, conditional-profile, and packaged-ROM gates.
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
  passed and were accepted on this ROM. The live controller proof includes
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
