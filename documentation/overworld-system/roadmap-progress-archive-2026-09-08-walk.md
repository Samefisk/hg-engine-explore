# Historical resume snapshot — superseded by roadmap-progress.md

Archived before recording build3091. This is an evidence index, not current acceptance.

# Overworld Roadmap — Current State

## Read this first

- [Roadmap](roadmap.md): required scope and completion rules.
- This page: current work and next action. Replace stale state; do not append run reports.
- Run manifests: detailed results and proof identity. Relevant input changes can make acceptance stale.
- [Archive](roadmap-progress-archive-2026-09-07.md): past investigations. Read only for a named failure, not normal resume.
- [Handoff rules](verification.md#progress-and-handoffs): how to maintain this page.

## Current work table

Scope and exit criteria live in the [finite slices](roadmap.md#finite-delivery-slices).
An evidence link does not close a whole slice.

| Slice | Owner | State | Evidence / remaining work | Next action |
| --- | --- | --- | --- | --- |
| D0 — proof workflow | root | source-ready | melonDS shared runtime passes26 live tool checks; old backend paths removed | Resume D2 through melonDS; retain existing full-slice proof rules |
| D1 — reported faults | root | open | Normal Ledyba spawn/chain accepted5017 frames; route still fails at spawn851 | Separate remaining emulated work from host reader cost; do not repeat the completed omission experiment |
| D2 — schema/resolver/facade | root | source-ready | Previously accepted runtime artifacts are now missing; host checks remain | Restore relocated evidence or recreate exact native proof; no new scope |
| D3 — Walk/chains/roles/Ram | root | active | Controlled Ledyba retry now accepted on melonDS; broader Walk/role parity remains | Port seven-commit Wild/Mounted acceleration parity through existing native Walk reader and bridge |
| D4 — Hop/Teleport/mount | root | queued | Normal current-follower Select and one Hop accepted; not presentation or soak proof | Check original detach, motion and presentation contracts |
| D5 — world/transition/population | root | queued | Boundary bridge reads current adapter token instead of receiving captured motion identity | Prove stale receipt A cannot complete motion B; cut over explicit receipt |
| D6 — remove old paths | root | queued | Removal needs replacement ownership proof and memory limits | Remove only paths whose replacement is proved |
| D7 — final acceptance | root | queued | No complete final proof set | Freeze candidate; run required current proof and final roadmap gate |

States: queued, active, source-ready, open, verified, blocked. Verified means
the whole slice has current required evidence; source-ready does not.

## Active issue and next action

- User confirmed deleting the old `build/overworld-devtools` data to free space.
  No cleanup command from this task removed those files. Missing links below are
  historical claims, not current acceptance. Do not infer proof from this page.
  Source ROM/save hashes are unchanged. Root will create fresh current reader
  calibration and controlled retry; missing old proof must be recreated as needed.
- Build3090 passed; game bytes unchanged and Delta copy matches. Native v2
  phase bridge rebuilt; synthetic CPU/timing checks pass without ROM.
- No more DeSmuME test runs. Do not claim old evidence as melonDS proof.
- Current route: one hitch/640 cycles, median12.728ms, max25.509ms at851.
  Snapshot2.200ms; measured callbacks10.474ms. This is still an open failure.
- Paired spawn diagnostic:120 identical game snapshots/244 equal dispatch records;
  cycle851 is24.840ms with readers and21.061ms without six optional reader groups.
  Omission is not a fix. Snapshot-local ID cache preserves exact output;
  reads718→462, median2.399→1.779ms. Keep the normal timing gate unchanged.
- D1 reader-cost details are in the archive and linked memory data below.
- D2 was closed for its finite Phase0–3 scope: host schema/resolver/view/lane/ABI
  and command checks, plus native binding/Walk, resolver, profile transfer,
  mount-begin and Inspect evidence below. Independent review found no gap.
  This does not close later movement, detach, world or soak requirements.
- Current normal Ledyba test accepted5017 continuous frames:34 complete chain
  intervals,18 complete actions, zero chain/render errors. Actual natural Wild
  Ledyba165 was bound; no chain/cooldown edits or images. Execution225.109s,
  final acceptance51.935s. Separate live wrong-render/identity control accepted
 915 frames in108.052s. Both sessions closed with no errors.
- D3 controlled retry accepted777 bound frames on fresh melonDS. Exact natural
  Wild Ledyba165: one rejection, unchanged completed idle1797, retry1798,
  all four profile-defined legs and terminal control1830. All six checks pass;
  no claim for the elapsed-zero successor Walk. Execution113.374s and controller
  acceptance71.484s. This is controlled retry, not normal chain cadence or D3 closure.
  Earlier c592 timeout was a test-tool clock/cooldown error; evidence stays linked.
  Both clocks now survive and match authenticated native call fields. Seven
  focused regressions pass after review; the broader76 checks passed before
  the final clock-equality addition. Calibration3625 was canceled at startup;
  replacement36037 accepted915 frames. No product/ROM edit or build was needed.
- Next: `walk.acceleration.mounted-parity` / `legacy.acceleration-parity`.
  Native COMMIT reader now captures exact lane and before/after policy32 bytes.
  Checked `walk-policy.reset` runs public RESET through FieldReturnBridge,
  preserving actor/profile/pose and guarding staged work with an authenticated
  on-demand reader. Public command, prepared typed setup, and host gate are wired.
  Pure seven-per-role meter uses native terminal events and MotionRecorder;
  Mounted uses the player anchor and input1, Wild its object and input0.
  172 focused host checks passed after the final diagonal/review additions;
  46 scenarios validate and the devtools-only guard passes459 files. No live run
  or ROM build for these changes. Prior reader calibration is now stale.
  Review gaps are fixed with failing-then-passing host controls: exact role/lane,
  raw fingerprint/mask binding, and native actor clocks. The exact intended
  diagonal/cardinal case is covered; host fixtures are not live acceptance.
  Correction: Flying insect/Ledyba is NOT a valid acceleration fixture: its
  walkOptions96 includes DISABLE_ACCELERATION32. Earlier audit missed that flag;
  no live run used it. Synthetic diagonal8/3/2 tests prove arithmetic/direction
  only, not authored Ledyba acceleration. Full host audit found no eligible
  natural Wild8/3/2 match: Mewtwo's Owner lane has no movement. Authored Onix
  Wild/Mounted both16/3/2 are the replacement parity fixture; no Cyndaquil-specific
  claim and no authored profile edits. See the checked-test fixture rules.
  Bounded Wild direction input and shared begin/end windows are now wired.
  Package/ELF RESET authentication and two-role controller checks are added;
  final150 focused host checks pass in7.274s;46 scenarios validate. Review caught a
  real nullable flat-Walk argument; its failing callback test now passes.
  Same-reader control and both Onix recipes are now registered;47 scenarios
  validate. Calibration failed before movement twice: missing teleport boundary,
  then a declared empty trace stream was rejected. Both test-tool defects have
  regression checks. The second immutable failure now replays through frame727
  with no error and no movement credit. Game/ROM bytes are unchanged.
  Fresh calibration4cf20 passed the old failure and completed native mounted
  Onix setup in155 frames, exceeding its120-frame setup budget. Retained data
  replay cleanly through frame886. Both recipes now allow180 setup frames;
  movement limits and claims are unchanged. Next calibration bdd6 reached the
  first Walk: its checker rejected lossless ring reuse, then elapsed1 at the
  first completed mounted update. Both cases now replay through888 unchanged.
  Root control tests cover missing start, wrong pose/commit, skipped frames and
  unread trace loss. The acceleration reader gets the same bounded corrections.
  Reader fixes passed32 host checks. Fresh02139 reaches all16 travel frames,
  then stays COMMIT_PENDING903–948 with commit9 unchanged, player command60
  step2, while actor clock469–514 advances. No native policy COMMIT; the fault
  control remains armed and has not written its test byte. This is a live
  terminal-motion stall, not a missing start or permission to raise the timeout.
  Root and independent review confirm a circular wait: WORLD_GATE blocks
  COMMIT_PENDING; FieldInputProcess clears MOVEMENT; stock field_control.c211
  therefore cannot call ProcessStep/Repel/PlayerStepBridge; that bridge supplies
  the END needed by CompletePendingStep. Gate/source locations: mount.c782–797,
  actor.c1895, motion_model.h180. Product fix is now in source: one pre-gate
  END latch, deferred stock-step replay, no successor before replay, stale-field
  guard and detach cleanup. pendingFieldStep reuses one reserved layout byte.
  Compiled real-function host checks fail old code and pass fixed code, including
  removed-handoff and removed-successor-guard controls. Public onPlayerStep
  entry remains as retry only; it cannot create another END.
  Build is not yet complete: latest link has motion2100/reserve1976 (+124bytes),
  text4024/~4012 (+12), step44+20 fits64, fieldinput8+84 fits96. Public addresses
  and limits unchanged; last packaged ROM remains3090. Build retries stopped
  pending measured reduction. Source-only planner+14 controls pass.
  Next: reduce/place private helper code within current reserves, build through
  Workshop (saved runAfter=false), rerun02139's unchanged live recipe. Do not
  claim fixed gameplay or use partially rebuilt artifacts as a candidate.
  Keep RESET package checks, all14 lifecycles and original four measurement rows.
  These scenarios are active but do not yet have accepted runtime proof.
- Storage defaults are implemented and live-proved: gzip1 lossless logs,
  low-space stops, verified private-ROM removal after core close. Latest retry
  evidence is5.8 MB, no plain duplicate; source saves unchanged. `AGENTS.md` and
  linked storage rules enforce these defaults. Do not keep extra test ROMs.
  D1 remains open: existing CPU timing mixes guest/emulator/readers.
  A new causal check needs per-frame emulated execution/halt/DMA/FIFO totals,
  not another identical six-reader omission run or weaker CPU threshold.

## Evidence — open only when needed

These are retained results, not instructions to rerun them.

- [Walk setup boundary failure](../../build/overworld-devtools/test-70ab1c860ad04614ace0850f62324aa2/manifest.json): missing teleport marker; zero movement frames; closed session.
- [Walk empty-stream failure](../../build/overworld-devtools/test-befaf62b353349c9a41960357b1fbcb4/manifest.json): stream1 at sequence0; zero movement frames; closed session. Unchanged saved data replays through setup after the checker fix, not accepted game proof.
- [Walk mount setup budget](../../build/overworld-devtools/test-4cf20c9faec54125ada5c728d159982f/manifest.json): native Onix mount completed in155 setup frames; recipe allowed120. Zero measured movement; closed session. Setup budget corrected, not a motion threshold change.
- [Walk first-update reader failure](../../build/overworld-devtools/test-bdd6e9bd4e244fdb9921f425ab0303f6/manifest.json): two observed frames; lossless ring reuse and real elapsed1 start. Replay is diagnosis only; private core closed and ROM removed.
- [Mounted Walk terminal stall](../../build/overworld-devtools/test-02139ba5a0204e83837db4797558d8f0/manifest.json):62 observed frames,16-frame travel then45 more pending updates; no COMMIT/control return. Reader control never fired. No accepted proof.

- Host D2 checks: [command suite](../../scripts/verify_overworld_actor_command_sequence.py) and [resolver suite](../../scripts/verify_overworld_behavior_resolver.py) with `--rule-removal-control`; source regression tests, not game acceptance.
- [Recovered retry status](../../build/overworld-devtools/recovered-test-095aebe5e6674275b73113d6fc1092c9.json): saved from the same live service after directory removal; original observations missing, not accepted proof.
- [Retry arm failure](../../build/overworld-devtools/test-f5a1d25870a1431897046ad3c934f6c3/manifest.json):663 frames, saved compressed data, clean session/ROM cleanup. Row1005 replay accepts only when endpoint is its exact native receipt; no retry completion evidence yet.
- [Retry clock failure](../../build/overworld-devtools/test-c59224b7937f4de28051fc07742af662/manifest.json):2463 frames, all four native legs retained; checker clock/cooldown error. Session closed and private ROM removed. Replay is diagnosis only.
- [Controlled retry accepted](../../build/overworld-devtools/test-de0a72da8730444dbbae5711573822d3/manifest.json):777 bound frames, exact six checks and controller acceptance; full four-leg action, closed control/session, automatic ROM removal.
- [Current reader calibration](../../build/overworld-devtools/test-36037b19bace46d9921e3977e4fa78c2/manifest.json):915 frames accepted on final retry-checker inputs; session closed and private ROM removed.
- [Current reader calibration/storage proof](../../build/overworld-devtools/test-8bcaaeeffb884d8c92dd3a2a692d0ba0/manifest.json):915 frames accepted with compressed evidence and verified automatic ROM cleanup.
- [Normal Ledyba accepted](../../build/overworld-devtools/test-3fc350715cb14533bb2b06e6438367cf/manifest.json):5017 frames,34 chain intervals,18 actions; exact natural spawn/count/pause/motion scope.
- [Ledyba live controls accepted](../../build/overworld-devtools/test-69aafc10f3a7415b8a70c87f7ed02383/manifest.json): same reader rejects native render and inactive-object faults; separate from normal-play proof.
- [Native Inspect accepted](../../build/overworld-devtools/test-23274b3de2ed48918fd64665669212a2/manifest.json): controlled lookup only; current/stale query, exact subject/generations/object/role, native boundaries and cleanup. Prior [manual data](../../build/overworld-devtools/session-v2ul19p8/event-details-489b27ee23cf.json) remains diagnostic.
- [Binding accepted](../../build/overworld-devtools/test-686161abac874cfb8188431c0b372997/manifest.json):
  exact three measurements1/0/0 and full same-subject Walk on melonDS.
- [Packaged resolver](../../build/overworld-devtools/test-662f6dedb8d94e9495ee7fbefbf132c2/manifest.json):
  seven native calls match Workshop; deployment proof, not movement timing.
- [Reader control](../../build/overworld-devtools/test-46cece1932d747278c9854b378adc9ca/manifest.json):
  native wrong-byte rejection and exact restoration on melonDS.
- [Profile transfer](../../build/overworld-devtools/test-4a607afc9c0a483e8a6511ee60900452/manifest.json):
  same current follower and exact getter/Begin/Owner bytes on melonDS.
- [Select/Hop accepted](../../build/overworld-devtools/test-32039c1674054c84bc7dbdcf88a8ffc1/manifest.json):
  Y789/Y791/Select857; Hop859–896; seven original rows; current reader control.
- [Current route control](../../build/overworld-devtools/test-be2c842325ff427598e42036f6565a1c/manifest.json): accepted31 frames; CPU-delay and control-stall faults detected.
- [Current route failure](../../build/overworld-devtools/test-95c97c5fb64a4f679d5082c8b1d19e79/manifest.json):317 frames; one CPU hitch; no accepted proof.
- [Optimized paused reader](../../build/overworld-devtools/session-6e7k4pp_/snapshot-probe-0547e3fd873a.json):128 snapshots; exact pre-change output hash, fewer reads, no game advances.
- [Paused reader at713](../../build/overworld-devtools/session-gtvhbgfb/snapshot-probe-c82a3fb56bb2.json) and [at793](../../build/overworld-devtools/session-gtvhbgfb/snapshot-probe-cdd7d12e3f34.json):384 snapshots; unchanged state within each probe; not game proof.
- [Spawn baseline](../../build/overworld-devtools/test-387de47346d74dde8368a8abb06a6f65/manifest.json) and [reader omission](../../build/overworld-devtools/test-480c3190260344d38afffcdf61b6fc20/manifest.json): same short prefix; expected incomplete-route verdict. Comparison command/result: `/tmp/ow-spawn-cost-7Z1WOH/compare.py` / `result.json`.
- Host-copy diagnostic: `/tmp/ow-host-cadence-nDEzf8/probe.py` and `result.json`; temporary host-only evidence, not game proof.
- [melonDS tool smoke](../../build/melonds-devtools-smoke-20260907.json):
  26 checks pass; diagnostic tool coverage, not roadmap gameplay acceptance.
- Older timing and DeSmuME investigations remain in the archive linked above;
  they are not current melonDS proof and do not clear D1.

Missing artifacts are a proof gap. Use `scripts/owctl progress --json` for
recorded status; manifests own details. Do not infer fresh proof from this page.

## Session and candidate ownership

- Branch: `feature/overworld-actor-system-roadmap`; root integrates the dirty tree.
- ROM3090, `test.nds`; exact Inspect acceptance included in tool/build identity.
  Build/manifest identities, not this label, determine evidence freshness.
- Shared backend is melonDS; old DeSmuME transport must not be run.
- Latest retry `test-de0a72da8730444dbbae5711573822d3` accepted;
  `session-su91sagc` closed with no errors and private ROM removed. Current
  calibration `36037b19bace46d9921e3977e4fa78c2` also accepted and closed.
- Re-read `dev status` and `dev test status` before live control. This note
  does not prove a session remains idle. Do not take over another owner.
- Preserve the user's melonDS process, ROM, saves and unrelated edits.

## Completion

The roadmap is not complete. The [roadmap](roadmap.md) owns the full scope.
The final candidate must pass `scripts/owctl verify roadmap --rom test.nds --json`
and its required current evidence. This page must not redefine that outcome.
