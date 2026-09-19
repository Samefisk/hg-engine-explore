# Archived Overworld Progress Log — 2026-09-07

Historical record only. This file preserves the former log, including stale
tables and superseded next actions. Do not load it during normal resume or use
its headings as current instructions. Read only for a named past failure.
See [current state](roadmap-progress.md); run manifests own detailed evidence.

This file owns current work state and the next action. The roadmap owns scope;
run manifests own proof. Do not infer a current pass from the history below.
The authoritative final exit result is:

```sh
./scripts/owctl verify roadmap --rom test.nds --json
```

The roadmap is complete only when that command reports `"passed": true` for
the final packaged ROM.

## Current checkpoint

- D2 current-follower transfer now has accepted native proof on ROM3081:
  test-475317cebe6e4f8ca5da458fc5534a29 passed/accepted77.841s, one final
  observed frame. Saved Mankey56/PID2920357538 getter186 profile216/primitives11
  match Begin189; stored Owner72 matches; same handle65543 remains mounted
  with Owner/input ownership. It independently revalidated accepted reader
  control7a3f4d014ff04a25bb6e3bfb03bf1a27 (45.428s). Both private sessions
  closed/errors[]. This is prepared caller-transfer proof, not Select/Hop or
  melonDS movement proof. The handoff fix consumed native ring events without
  setup credit; the normal run then exposed retained pre-window boot diagnostics
  (failed45c989b1...,38.933s), which are now kept distinct from ring events.
  Saved failures replay correctly and43 focused handoff/job/controller tests
  pass2.550s. No game source edit or ROM build. Next resume remaining D2 role
  coverage and the existing finite roadmap slices; do not rerun this short
  transfer after unrelated note changes or treat it as movement coverage.

- D2 reader dependency is now wired through the shared controller: normal
  transfer requires a separate current accepted `profile.owner-reader-control`
  manifest, revalidated against source/ROM/save and exact native fault/restore
  bytes. Real dependency host tests caught an unaccepted-manifest reuse bug;
  the shared gate now rejects it. Related Ledyba mock fixture needed its
  claimed passed flag; nine focused follow-up tests pass0.863s. Seventy-three
  broader checks ran29.365s with only those two fixture-related failures;
  their unchanged revalidation assertions passed after fixture correction.
  Registered native control3de99b0ee8014f349939e299b6712ef8 failed38.165s at
  frame735 before acceptance: generic observer-control recording began before
  prepared spawn, but generic evaluator omitted spawn receipt native events1–5
  and rejected next normal events6–10 as a gap. All events are retained in
  observations.jsonl. Session-7yvvzd2t closed/errors[]. This is a tool handoff
  fault, not a game regression or accepted calibration. Next fix/check the
  prepared command event handoff from retained data before another boot;
  normal transfer remains unrun and all movement requirements remain open.

- D2 native reader calibration is implemented and exercised, not yet a
  registered acceptance dependency. Opt-in mounted `owner-transfer-control`
  changes one owned byte and checks/restores it before guest execution.
  Session-_o6ui9yn/event-details-5c3402f7d778.json retains mount189 for saved
  Mankey56/PID2920357538: Owner byte03→02 was rejected by the same reader;
  byte03 and the full104-byte state were restored, both clocks stayed
  frame733/nativeCycle1860. Command succeeded in0.198s after boot; private
  session stopped. This is DeSmuME native reader calibration, not melonDS or
  normal movement proof. Twenty-six focused host checks pass0.200s;45 scenario
  contracts validate. Next wire this calibration into the transfer proof's
  controller dependency, then run the unchanged normal transfer scenario.

- D2 transfer checker: keep the new short follower-to-mounted Owner test;
  it covers caller byte transfer, not Select input or Hop. The real job writes
  five rows including a recording boundary. A matching host fixture failed
  the old four-row checker before the fix. The checker now validates the
  boundary identity, context and clocks and uses it for endpoint continuity.
  Fourteen focused controller/resolver/transfer checks pass (0.152s), including
  missing, stale and wrong-identity boundaries and an advanced valid boundary.
  These are synthetic host checks, not fresh game acceptance. No ROM build or
  emulator run was needed. Next: finish native reader calibration before
  accepting this new transfer scenario; original Select/Hop coverage stays open.

- D2 native Owner-transfer diagnostic now works and persists its data:
  session-2i7uuq11/event-details-734e742219ec.json retains getter194/195 and
  mount198. Getter195 output pointers and all216 profile/11 primitive bytes
  match mount input; stored Owner72 bytes match exactly, same Mankey
  PID2920357538. Session closed. Earlier jji6lha0 mounted successfully but
  its generic manual receipt omitted events; a RED command-retention test
  caught that and the explicit bounded profileObservation field now survives
  after stop. The halfword catalog and pending/completed hook cleanup fixes
  have compiled-layout and first-fault regressions;156 focused checks pass.
  This remains diagnostic: registered transfer comparison/acceptance is next.
  Short unmounted timing probe260e09344b1e4a56bb3f85e0b5f7da6e ended47.430s:
  120 observed/112 active frames,312 cycles all retain threadCpuNs. Process
  median13.920ms vs thread13.801ms; maximum process25.314ms, no hitch. Largest
  process-minus-thread difference3.126ms. Only expected short-prefix/full-route
  incompleteness failed; no full-route proof. Session-gyr07if5 closed/errors[].
  These normal samples do not attribute the earlier rare spike. Next integrate
  a registered same-follower getter-to-mount transfer proof using retained data;
  use new thread costs at the next required full-route run, not blind reruns.

- D2 opt-in owner-transfer reader is wired through spawn, off by default;
  current saved Mankey avoids party edits or selection detours. First live
  command in session-1dmdi7gi failed safely before proof: reader demanded
  four-byte alignment for valid two-byte-aligned SurfaceCatalog0x022b976a.
  Header members require only halfword alignment. Exact first error retained
  in event-details-6661a509d691.json; session stopped automatically. Helper
  owns reader/layout regression fix and pending-return cleanup found in review.
  No game fix or acceptance claim.150 runtime/release/reader and43 wiring/
  observer checks passed before live discovery;76 cadence checks pass41.048s.

- D1 next discriminator implemented: optional threadCpuNs measures the native
  worker thread inside the unchanged whole-process CPU interval. It cannot
  subtract reader cost or weaken the hitch rule. Raw replay rejects invalid
  bounds and clock errors; historical rows need no invented thread value.
  Actual step test first failed for missing timing. Independent review exposed
  end-clock exceptions masking the first native fault; its regression failed
  before the guard, then passed.136 focused runtime/timing/raw checks pass
  in0.208s. No fresh native timing run yet. D2 helper owns only the new bounded
  role-profile reader and tests; integrate and freeze before the next core run.

- D1 full route dd0260f710044fa1af77b07f77f4a884 failed in296.049s:
  4,499 observed/4,180 active frames,1,045 player and764 follower completions,
  85 tiles/3 cells/2 maps, no object waits. First CPU hitch at native interval
  10,686 (completed game frame5748,route-099):30,182,000ns vs median13,812,000ns;
  wall146,471,500ns. Selected callbacks explain7,450,334ns, including sampler
  5,412,042ns (nearby samplers2.8–3.1ms). Remaining CPU cost is not attributed;
  this does not establish a game freeze. Immutable raw memory data retained,
  session-y0o4g9pz closed/errors[]. No retry or threshold change. Next bounded
  investigation: distinguish whole-cycle native-thread work from other process
  work and sampling/collection cost before another full route. D2 actual
  getter-to-mount Owner-lane receipt is an independent remaining proof seam.

- D1 current route calibration6bc019c22186409bb3c169db55c1aa2e passed and
  was accepted in60.798s/54 frames. Nine evaluator controls passed; private
  session-vihb161u closed/errors[]. Compact manifest2,241,311 bytes fits the
  shared reader bound. Full unchanged route dd0260f710044fa1af77b07f77f4a884
  ended with the CPU fault above. Sources and native readers stayed unchanged
  during the run. Prior CPU faults stay open.

- D2 packaged resolver acceptance passed on ROM3081:
  test-3ed02e988c944f6d88b3e50f4d332db2,47.842s,passed/acceptedProof true.
  All eight original measurements and seven copied-data rejection controls
  passed. Seven native cases used one native resolver cycle, zero completed
  movement frames; no live role-caller credit. Session-yjx1rfgf closed/errors[].
  Scoped independent review found no blocker.73 focused host checks passed
  in2.440s;44 scenarios validate; retirement guard passes396 files.
  Test decision: keep packaged parity for actual ROM/Workshop equality;
  skip unrelated movement setup. Next keep route calibration because current
  observer inputs changed, then run unchanged full unmounted cadence proof.
  Actual follower/mount caller ownership and D1 CPU faults remain open.

- D2 registered deployment acceptance is wired to the existing shared job.
  It keeps the original eight measurements, seven fixed native calls, full
  byte/provenance comparison with a fresh Workshop result, exact call and
  cleanup checks, and seven wrong-data controls. The service-only scenario has
  no actor subject and counts only native resolver cycles, not boot or motion
  frames. Controller integration tests caught an unlisted-action replay gap;
  job dispatch tests caught the omitted full resolver receipt. Both now reject
  the wrong path. Focused host checks precede one fresh registered native run.
  Ported registration is not yet accepted proof. D1 full-route calibration and
  actual follower/mounted callers remain open; no ROM source changed.

- D2 native resolver diagnostic now completes: shared resolver.probe in
  session-5k6z3obo made seven successful calls and freed its8,000-byte heap11
  block in0.216s after boot. Immutable event-details-55e1848812a0.json keeps
  all native receipts. Comparison first failed because the host packer assumed
  12 primitive bytes. The real public structure has11, with its alignment byte
  after behaviorLimitKey. A compiled-C full256-byte layout witness reproduced
  that error, then passed after the fix. Retained native data now matches fresh
  Workshop results for all seven cases and ordered trace counts8,12,11,11,15,8,11.
  Ten probe/comparator tests pass0.176s. This is diagnostic parity, not accepted
  roadmap proof; registered recipe/controller wiring and real role caller
  ownership remain next. No new game boot was needed for the comparator fix.
  Session confirmed stopped. Manifest/controller checks pass86 in30.841s;
 44 scenarios validate, retirement guard passes391 files. No ROM source change.

- Empty setup IRQ retirement ran on093bae2c903b440ba31dbeb20df99329:
  all nine removed, zero added frames,120 observed/112 active frames,
  302 CPU cycles median15,562,000ns/max28,538,000ns with no hitch. Only the
  expected diagnostic-prefix incompleteness failed; no full-route credit.
  Calibration5fcada9c0798444c9a92301438349626 was accepted in103.979s/57
  frames; session-e7k_9rhl closed/errors[]. Full routec71634cb57cb41b2846d128e9fa33949
  failed preflight before gameplay: calibration manifest15,346,861 bytes
  exceeded its reader's8 MiB bound despite matching source identities.
  Compact serialization preserves every field in6,817,806 bytes. The writer
  now shares the reader limit and rejects oversized accepted controls. Original
  artifacts remain unchanged.36 focused writer/jobs checks pass; no ROM edit.
  D2 fixed native probe is now wired through shared devtools, with natural
  discovery, current service/blob authentication, seven calls and owned cleanup.
  62 resolver/observer/engine and185 command/record/runtime host checks pass.
  Actual native probe and registered comparator acceptance remain pending.
  Test decisions: update manifest writer (retained failure), keep one native
  resolver diagnostic for the missing D2 calls, skip rebuild/unrelated game
  tests. After tools freeze, refresh calibration before full-route acceptance.

- Callback-cost checks are implemented without subtracting time from the CPU
  limit. Diagnostic prefix3b97c347d61f486e9656b4cd1601d6fa found no hitch in
  286 cycles, but 264,605 empty setup IRQ callbacks crossed the native binding.
  Fresh calibration3d78d92fdd294b44be2c7a202b94c1a1 was accepted in53.023s.
  Full route99a5ab6b3cec43e8b4cc2494978970ac then failed in77.223s with
  one CPU hitch:31,866,000ns versus15,579,000ns median,515 cycles,220 observed
  frames/204 active,51 player moves/24 follower motions. Timed active Python
  callbacks used237,420ns in that cycle; its remaining cost is not attributed.
  Keep this failure open. Both owned sessions closed with no cleanup errors.
  A one-time empty setup IRQ unregister pass is now source-ready, with six
  focused host checks; it retains active hooks and all timing/freeze limits.
  Next: validate a short native prefix and inspect its observationSetup receipt
  before another full run. Calibration is stale after these tool edits.
  D2's seven-case byte/provenance comparator has four host checks, but actual
  packaged native parity and follower/mount caller proof remain missing.
  Test selection: keep narrow callback/job/receipt checks and the diagnostic
  prefix for current CPU attribution; skip rebuild and unrelated feature runs
  because no product source changed. D1 and D2–D7 remain open. Shared backend
  is still DeSmuME; these results do not prove melonDS behavior.

- Fresh calibration abdf69f51f7f4b69b0df6044de8e3987 is accepted on3081:
  26 observed frames/54.196s, five actual native clear collision receipts,
  expected CPU/player faults detected, session-_susqx9q closed/errors[].
  It proves the new reader runs and the recorder still detects those faults;
  no object-only block occurred. Full route466ab8d6eeb9406dbb5f7301ef0d25b4
  then FAILED after56 observed frames/51.825s,13 complete player moves,
  52 active frames and11 follower motions. Original CPU check found8 slow
  native cycles in129 samples (median15,202,000ns/max37,163,000ns). No
  collision waits; no input-lock failure. Session-gol50pa2 closed/errors[]
  and service confirms stopped. Keep this failure; do not retry or relax
  the CPU limit. Saved slow-cycle data include completed queue sampling and
  walk-policy reads, often without a player collision read. Current process
  timer wraps both emulator work and Python native/sampler callbacks, so it
  does not yet identify the cost owner. Next bounded step: measure those
  callback costs separately in the same shared cycle receipt, retain the
  original total CPU check, and inspect a short native route before another
  full run. Do not label these host costs a proved in-game freeze or claim
  melonDS proof (shared backend remains DeSmuME). D2 next-step inspection is
  complete: seven packaged resolver cases and real follower/mount caller
  ownership remain missing; reuse current native resolver receipts/Workshop
  resolver, not another driver. No product edits or new build this turn.

- Collision-aware route observation is source-ready, not live-proved. The
  native reader binds the full stock collision body and walking caller to the
  package and live memory. Exact object-only mask0x2 allows a bounded stationary
  unadmitted wait (120 frames total,18 between receipts); exact clear returns
  to unchanged admission/render checks. Waits earn no travel credit, and CPU
  and follower checks remain active. Pending waits block acceptance.
  The new raw-stream witness failed before wiring at frame4 and passes after:
  17 blocked frames then clear/admission and complete player/follower motion.
  Eight integration checks pass0.853s, including immutable2a32 still failing
  player-input-not-admitted at1157 with no collision receipts.70 focused
  cadence checks pass36.126s (including retained839 full-route replay),37
  reader/wait/control checks pass1.026s; native ABI/auth checks pass8 in0.033s.
  Independent review found and corrected incomplete native body authentication;
  final cadence review has no scoped blocker.44 scenarios validate and the
  devtools-only guard passes378 files. Test decisions: update collision reader
  and route checks; keep fresh live calibration/full route; skip rebuild and
  unrelated feature runs (no product change). Previous policy-only turn was
  no progress; this turn changes the shared measurement and adds regression
  evidence. Next: freeze tools, refresh idle Workshop, run fresh calibration
  then the full route on3081. D1 and D2–D7 remain open.

- Frozen calibration1210b8eef64c4204baf572a5a88d5d2f is accepted on3081
  (45 observed frames,86.652s; session-cz_bstgn stopped). Full route
  2a32e0781e064d748d42e0a670706012 FAILED after42 measured frames/81.601s
  at first LEFT leg: player-input-not-admitted1157,585,398→584,398. This is
  retained failure, not accepted proof. Its exact private session2dhyhuna
  cleanup is closed/errors[] and service confirms stopped. Native memory shows
  identity-verified WILD Rattata slot3 entering584,398 at1153, native current
  tile there1154, settled at its center1155–1157. Player commands42 then30;
  player remains585,398 while follower and actor clocks advance. Thus the route's
  assumed clear target is occupied; this is not evidence of a whole-engine
  freeze. Exact native rejection cause is not yet observed. Do not dismiss the
  failure or retry blind. Next: add the smallest native collision-reason check
  and bounded dynamic-obstacle handling to the shared route, with retained-data
  and wrong-reason controls. Preserve active-movement floors and fail real
  control locks; no blocker/wait frame may count as travel. No product edit.

- Full-route acceptance wiring is source-ready: original six claims/ten rules,
  unchanged moving/distance/map floors, exact current route calibration and
  owned-session cleanup. The prepared fixture is separate from intervention-free
  normal input; no nurse/menu detour. Retained839dec passes independent replay
  in13.665s and all eight own-reason negatives in0.704–0.815s each. The helper
  rechecks all61 crash proofs and missing-recovery/restore controls.10 focused
  proof/cleanup/registration tests pass16.678s including full retained replay;
  42 focused job/controller checks pass3.047s. Validation passes44 scenarios;
  retirement guard passes373 files. An outdated host fixture used scalar
  placeholders for coordinates; it now uses coordinate pairs and its unchanged
  pending-recovery assertion passes. Independent review found no scoped blocker.
  Test decisions: update route acceptance and cleanup checks, keep unchanged
  live calibration and full movement witness, skip unrelated feature runs/build.
  Freeze source now, then fresh calibration and full route on3081. Earlier856bf
  calibration has old proof-source identity after these edits and is not reused.
  Full-route accepted proof remains pending; D1 and D2–D7 are still open.

- Fresh registered route calibration856bf040a8f845e4a1f92999e68d76f2 is
  completed, passed true and acceptedProof true on3081 in43.654s. Its25 frames
  include four clean player moves, three follower motions and46 baseline CPU
  samples with zero hitches. Real CPU-work cycle2031 costs114,770,000ns; the
  live player pin causes startStall1/reachedTarget false at813. All nine
  copied-data controls fail for their exact cause. Cleanup is closed/released
  with zero extra frames; private session-d1070w_8 is confirmed stopped.
  This accepts only legacy.live-route-observer-controls through shared DeSmuME,
  not melonDS or normal/S5 gameplay. Manifest:
  `build/overworld-devtools/test-856bf040a8f845e4a1f92999e68d76f2/manifest.json`.
  No rebuild or product edit this turn. Next: wire full unmounted route
  acceptance to its original requirements and this separate calibration,
  replay retained839dec first, then run the frozen accepted route. Keep
  existing active-movement/distance/map floors and the remaining slices open.

- Route calibration acceptance is now wired to the original two requirements.
  Selected tests: keep the route control (detects real CPU and player stalls);
  update its host acceptance/negative checks (new controller path); skip ROM
  rebuild and normal healing/selection (tool-only change and movement fixture).
  Retained e640 data passes the independent baseline/CPU/pin/cleanup check;
  all nine copied-data faults fail for their own exact reason, with no boot.
  The scenario and recipe validate among all44 contracts.34 focused checks
  pass1.505s; retirement guard passes368 files. A64-test integration run had
  one obsolete fixed pending-count assertion (38 versus37); it now checks the
  actual pending IDs while retaining all40 original requirements. The focused
  retirement/registration run passes10 checks0.654s. Independent review found
  no scoped blocker. Source is ready for a fresh registered calibration on3081;
  no new live acceptance is claimed. Full route, Ledyba and D2–D7 remain open.

- Live route-control diagnostic e640cfaf24d047ff83344047ebc518ba passes on
  3081 in28.339s,25 observed frames. Clean baseline has four player motions,
  three follower motions and a held segment. The actual CPU-work cycle2028
  costs115,219,000ns and is the only classified hitch. Four live pinned
  samples produce startStall1/reachedTarget false at813 without crediting a
  fifth player move. Cleanup releases input with zero extra frames and
  requires disposal; private session-lwyud6vx is stopped. This is diagnostic
  passed true/acceptedProof false; registration remains pending.
  Before this run,85 focused checks passed7.762s. New per-frame controls were
  RED for future-pin lookahead and later-fault masking, then GREEN with exact
  pin frame/cycle coverage and a stop at first detection.
  The saved baseline CPU summary was stale (empty), although its local check
  ran. The exported baseline now saves that exact classifier and its samples.
  A regression fails before the export fix;10 focused checks pass afterward.
  Replay of the unchanged live stream passes and retains44 clean baseline CPU
  samples (median14,041,000ns, maximum20,280,000ns, zero hitches) and both
  expected detections. Do not overwrite the original manifest or treat replay
  as new live acceptance. Next: exact registration/acceptance adapter for
  legacy.live-route-observer-controls, including copied-subject/event controls,
  then fresh accepted calibration and full route. No further ROM edit needed
  for this tool-only step. Shared tools now need a restart after export fix.

- Live-route calibration implementation is in progress after the full route
  pass below. New native control and thin cadence wrapper reuse the shared
  runtime and unchanged classifiers; no second engine, arbitrary address
  command or changed S5 floor. Typed recipe uses direct prepared Cyndaquil
  setup and four UP moves. Root owns shared job/runtime/replay wiring;
  record_size owns the wrapper's per-frame receipt correction; melonds_memory
  reviewed native ownership and first-fault order.80 related host checks
  pass7.398s; six direct wiring checks pass0.024s. Retirement guard passes364
  files. Review found future-frame receipt lookahead and incomplete pin-frame
  binding; those are being fixed before the first live calibration. No live
  calibration pass or new accepted gameplay proof is claimed. Shared session
  remains stopped, product3081 unchanged; restart stale tools only after the
  reviewed control implementation is frozen.

- Fresh full diagnostic839dec8cf9b348a98d8f2acf1b55afb7 passes on3081 in
  457.387s (execution457.376s). Manifest: completed/passed true,
  acceptedProof false because native route controls and exact registration
  remain open. The unchanged route covers5875 observed frames,5428 active
  movement frames,85 tiles,3 cells,2 maps,1357 player motions and1078 follower
  motions. All61 crash presentations restore and the one map handoff recovers.
  CPU14316 samples: median18,035,000ns, maximum34,220,000ns, zero hitches
  under the unchanged classifier. No evaluator failure or evidence gap.
  Setup retention succeeds; the private session-x_y3_lvw is stopped.
  The earlier full failed route took1690.402s; this current full pass takes
  457.387s. This is measured run cost, not a universal emulator speed claim.
  Next: implement the small live-route control wrapper around the existing
  cadence meter, using separate baseline/CPU/player-fault stages and unchanged
  classifiers; then wire exact controller acceptance. No second route engine.
  Keep the full route and fault controls: they prove different current risks.

- ROM3081 builds successfully through Workshop in74.212s. Its SHA-256 is
  65c3ba20d486210557fdb9912fc62cb107780c8dfe12955c392fb439cfe1e30c;
  the numbered Delta copy matches and both source saves are unchanged.
  The first link attempt exceeded the fixed core reservation by8 bytes.
  Equivalent bounded arithmetic reduced the mapping; the linked core now
  ends023bd348 with8 bytes free before the unchanged023bd350 entry.
  Actual-C lane and actor-view checks pass; independent review confirms all
  u8 states. No memory reservation or fixed entry moved. Workshop is current,
  open-after-build remains false. Doctor passes, but its native transport
  is still DeSmuME, as documented in the earlier migration gap. Do not label
  the next shared route melonDS proof. Next: fresh diagnostic route, followed
  by native route controls and controller acceptance; neither D1 nor D2 closes
  on this build alone.

- Setup retention and D2 lane projection are source-ready, not runtime proof.
  Run7003230c58c048ca8b42352750642e97 failed in prepared follower setup:
  4464 native events over509 frames overflowed the4096-event queue by368.
  No route frames were accepted. A bounded command-scoped collector now
  drains completed events each native cycle without changing normal buffers
  or hiding loss. Its exact overflow regression retains all4464 events.
  Independent review found no scoped blocker. The actual-C lane regression
  now maps raw Emoting to Owner and preserves raw controller state; unknown
  states map to NONE.38 focused checks pass in1.037s; the original actor-view
  check also passes672 fills and224 syncs. Test selection: keep retention,
  lane projection, actor-view preservation and compact-report checks because
  they cover these changed contracts; skip unrelated healing and selection.
  Next: build this source, check its fixed overlay budget, then run the
  unchanged full route with retained setup events. Current ROM3080 is stale
  for the lane change. Native route controls and D2 live parity remain open.

- Report-copy cost cut integrated: raw frame callbacks, ready polls, shared
  jobs and controller replay use detached compact status; public/default and
  terminal reports remain full. All raw samples, callbacks, sequence checks,
  fault frames and retained proof histories stay in place. Independent review
  found no scoped blocker.55 related integration/job tests pass8.254s; five
  compact-report controls pass0.096s, including a guard that forbids full
  exports inside ordinary movement frames and readiness polls.
  The exact5830-frame failed run replays in17.419s with unchanged5428 active
  frames,1357/1058 player/follower moves,68 crash histories and zero CPU hitches.
  It still fails at6618; the diagnostic now explicitly reports
  crashPresentationPending=true and handoffRecoveryPending=false.
  Full serialized measurement comparison against the original manifest has
  no differences after excluding only those two new diagnostic fields.
  The saved-state export microbenchmark (not game throughput) takes0.985288s
  for20 full reports versus0.000619s for20 compact reports. Product3080 is
  unchanged. Next: fresh full route with the corrected final completion wait,
  then native recorder controls and controller acceptance. Do not call this
  one diagnostic route or the roadmap accepted yet.
- Full diagnostic route2aaf2d7d3e584fc78ef52187505a6e30 ran1690.402s on3080:
  5830 observed frames,5428 active movement frames,85 tiles,3 cells,2 maps,
  1357 player moves and1058 complete follower moves. No movement failure was
  reported before the final assertion. Final state6618 is IDLE but starts a
  crash shake (timer10); actor-IDLE alone let the final wait stop before exact
  restoration. The run is FAILED/acceptedProof false, not a completed route
  proof. Its native memory remains intact; private session-voezxahb is stopped.
  The final wait now uses the existing full measurement-complete predicate
  with unchanged256-frame/30-second bounds. A permanent same-checker test is
  RED for the old wait and GREEN for timer10..0 restoration with the new one.
  Test selection: update the final wait, retain all route/effect floors; do
  not rerun28 minutes before fixing the observed report-copy cost. Helper
  melonds_memory owns that bounded internal cost fix; root owns integration.
  Next: benchmark/review the compact internal report path, replay unchanged
  evidence, then fresh full route and native recorder controls/acceptance.
- Fresh unchanged routeb965add470fc4947acdd079a18f5c6a0 stopped40.184s
  at completed frame866: cancellation occurred at elapsed1/8, not0/8.
  This exposed an overly narrow origin-cancellation rule, not a CPU freeze.
  NORMALIZE_SLOT centers the current engine tile regardless of partial
  rendered travel. The meter now requires unchanged origin ownership and
  exact signed Walk interpolation for every retained partial sample, then
  exact normalized coordinates, unchanged commit and full cancel/rebind
  events. Review added the native halfway path boundary: elapsed0–3 can
  retain origin, but elapsed4–7 cannot silently miss logical advancement.
  Native PATH_ADVANCED also forbids retaining origin. Both terminal branches
  require current/previous engine coordinates to match logical position.
  Tests cover all eight points and reject interior render drift.71 related
  host checks passed19.248s before these added guards; all9 cancellation
  checks pass afterward. Exact retained data
  replays through866 with only the expected short-route incomplete result.
  Product3080 and route limits unchanged. Next: reviewed frozen-tool rerun.
  Keep this test: ordinary map crossings can interrupt any movement frame.
- D1 retained-data replay now reaches the end of live run
  test-4a2b1f1615f3491f92e5e489b04aeca2 at frame865 without a reader or
  movement failure. It correctly remains incomplete:77 observed frames,
  68 active player frames, one canceled follower handoff, not the full route.
  Two source-checked meter fixes were needed: context events can be drained
  under the old trace header before the epoch notice; a Walk canceled at
  elapsed0 can remain exactly at its origin without a commit. New tests fail
  before each fix and pass afterward. Wrong event order/epoch, missing events,
  origin movement and later canceled-pose drift still fail.25 focused checks
  pass; independent source review confirms both boundaries. The related
  107-test host integration set passes17.301s. Product ROM3080 is unchanged.
  Next: fresh unchanged route on the restarted shared service;
  native fault controls and final acceptance wiring remain open.
  Test selection: update cadence trace/cancel tests for these current native
  boundaries; keep trace loss, crash restoration and shared replay checks;
  skip healing/selection and unrelated actor tests for this tool-only change.
- The preceding live run4a2b failed41.063s at the map33→67 measurement,
  not a proved game freeze. It contains a complete crash-shake restoration
  and a rebind with follower pass-through bit18 retained on3080. The earlier
  run0476b5f391354a0d9c8b21540776b545 failed32.423s because the reader lacked
  that crash effect. The shared reader now measures its actual timer, saved
  base and object identity; the checker retains all11 raw offsets through
  exact restoration. Actual-C effect checks reject wrong offsets/sign/timer.
  These narrow observations do not close unmounted stutter or the roadmap.
- Confirmed rebind policy fix built as3080 (Workshop1788785673.1954298,
  55.888s, exit0, open-after-build off). The only product change restores
  ApplySpawnPassThroughFlag after successful NORMALIZE_SLOT. The unchanged
  actual-C test goes from follower-specific RED to all40 cases GREEN.
  Saved live1215 data already fails the permanent flag invariant; the fresh
  full route is still blocked by the separate stock-turn measurement error,
  so no fixed-game control/cadence claim is made. ROM and Delta copy share
  SHA25650e770f1305d3c5ed1584e78dd82355c6ff64c534084c0f11173299607c86fb4;
  test.sav/test.dsv hashes remain unchanged. Next: replay/fix turn measurement,
  then run the unchanged route on3080. Keep the wider D1/D2–D7 work open.
- Prepared-sequence handoff corrected in TestEvaluator from the raw meter's
  already-validated setup watermark. Exact cb947 retained data now advances
  through789, sequence80;12 focused tests pass, including skipped/duplicate
  next events and invalid prepared receipts. New live2be613687d2e4975b9f10e4a4131b80a
  reaches normal input but fails35.367s at the initial UP admission limit.
  Memory matches the older manual run:1116 input not yet consumed,1117–1119
  stock command40 turning,1120 admission. The meter incorrectly counts the
  unconsumed/turn frames as translation delay. Next: source-bound stock turn
  handling and consumed-input fence, retaining the two-frame translation
  limit and all CPU/frame data. No product edits yet; core stopped.
- Shared route cb947d3eeb324c79934afef1f7ed5e83 failed25.056s before
  movement at789: TestEvaluator rejects the first native event sequence after
  prepared setup. Initial733/party737/spawn788/bind788 are retained in its
  observations.jsonl. This is a prepared-boundary tool defect, not a successful
  runtime flag-loss witness. Product unchanged. Next: replay this exact file
  to fix the shared evaluator's setup handoff without relaxing sequence checks,
  then rerun the same typed route. Core is stopped.
- The live flag invariant independently rejects saved frame1215 with
  follower-pass-through-lost/flags0xC421.40 cadence tests pass, including the
  review-found requirement for a later complete motion after cancellation.
  Independent route review confirms1357 steps,85 distinct tiles,three cells
  and two maps; it does not supply the required5000 live movement frames.
- D1 retained-follower collision defect is now localized. In memory export
  recording-cdd29c9f50f8.json, frame1214→1215 keeps the same follower object
  but changes flags0x4E405→0xC421: pass-through bit18 is lost at map33→67
  and stays absent. NORMALIZE_SLOT clears it; Wild REBIND does not restore
  ApplySpawnPassThroughFlag. Stock normal-player walking calls the bit-aware
  sub_02060BFC from sub_0205DAA8 (BL0205DB54). Do not route around this fault.
  The actual-C normalize/rebind/policy regression is RED before product edits.
  Next: fail the permanent shared route on this invariant, restore the existing
  role policy after normalization, then rerun unchanged on the fixed ROM.
  The new typed route uses checked saved-party setup, semantic step counts and
  settled endpoints:1357 tiles, three cells, two maps; full proof remains open.
- D1 canceled-handoff meter now retains partial Walk samples and requires exact
  cancel/control/context/rebind events; canceled work earns no completed-motion
  credit.55 relevant host checks pass. Replay of the real1208–1234 follower
  window retains seven partial samples and verifies the next complete Walk.
  This is follower-only replay, not CPU or full-route acceptance. Keep these
  tests because real transitions can cancel motion; retain idle-handoff tests
  for the other supported boundary. Skip unrelated healing/selection runs.
- D1 route discovery session-vecw8n2j used checked saved Cyndaquil setup and
  normal input only, no images. Memory export recording-cdd29c9f50f8.json
  has384 dense snapshots/no drops. Path reaches three32-tile cells and maps
  33→67: (585,406)→(585,396)→(585,398)→(565,398)→(565,393)→
  (543,393)→(543,402)→(555,402)→(555,400). Final UP input stops beside
  the idle follower at555399 despite clear static terrain; that occupied
  route point is not yet a freeze claim. Manual session stopped. At1215 the
  area boundary cancels an in-flight Walk with exact CONTEXT_LOST/control
  events and rebinds; new motion1226 completes1234. The idle-only cadence
  handoff rule is too narrow for this supported cancellation. Next: add exact
  canceled-handoff measurement without completed-motion credit. The later
  pass-through finding above supersedes the proposed route workaround.
- Final current-reader setup944d474f passed39.121s on3079, no failures;
  its acceptedProof=false correctly remains diagnostic-only. This and91ba
  establish repeatable successful prepared setup after the raw-flag fix, not
  long-route freeze/stutter acceptance. Owned core stopped. Next: construct
  the complete unmounted route from checked loaded terrain, use this same
  seven-action prepared setup, then calibrate/activate its exact cadence proof.
- Reader-fixed live91ba6c36 passed35.418s on3079 with the same exact saved
  Cyndaquil and native sourceActive=3. Default IRQ execution checks=0; direct
  write guards remain active. Independent review found four downstream copies
  of the same obsolete ==1 rule. Shared spawn_identity.live_spawn_flags now
  serves live setup, normal play, cadence, chain-abort identity and controller
  replay.126 focused host tests pass19.245s, with all byte values and invalid
  types checked against the source-defined flags. Actual91ba memory data
  passes normal-play, cadence identity and controller replay. New shared
  reader dependencies are included in service freshness/run hashes. Final
  unchanged setup repetition next, then full unmounted route work.
- Write-only run79f28a0c failed49.272s at the native selection bound, not the
  wall deadline. Game reached1543 frames; exact FOLLOWER155 was present and
  IDLE, with sourceActive as its only failed identity check. Raw active=3 is
  valid native TRUE|AGGRO (release overlay2); ball hits also set PENDING=4.
  Fixed shared reader to accept only defined live combinations1/3/5/7, not
  inactive or undefined flags. Permanent test failed on3/5/7 before correction;
  it also now rejects Python bool.45 narrow tests pass; retained actual
  Cyndaquil data passes all17 identity checks. Runtime recipe/budget unchanged;
  live rerun pending. This reader bug explains a false setup failure, not
  completion of the unmounted stutter route or the full roadmap.
- Progress reader33-test host module passes. Fixed3079 setup c68f9968 passed
  in30.195s with exact FOLLOWER155/PID2046726716 and one post-bind frame;
  unchanged repeat1638fb66 failed77.043s at the command deadline. Its57
  rate-limited memory receipts show game frame736→1087, cycle1866→2815,
  1,103,282 IRQ checkpoints and zero watched writes. This is observed live
  progress, not an engine freeze; the absent final actor still prevents setup
  acceptance. Retire mandatory deep IRQ execution tracing from routine setup:
  default write-only keeps the direct corruption detector and normal health
  checks, while explicit releaseDiagnostics=irq retains the investigation tool.
  Keep the scenario and deadline unchanged; next run tests this cheaper path.
- Fixed-build diagnostic `test-7277482b824147efab67ca0981a09dec` failed in
  78.328 seconds on3079: `command-wall-budget` during prepared follower
  selection. No old IRQ-write fault was returned; that absence is not a pass.
  The worker's last snapshot predates the command and stderr is empty, so the
  failure cannot yet distinguish slow observation from a guest stall. Add a
  rate-limited native progress receipt to this same shared observer before
  another run. Keep the recipe and deadline unchanged. Root owns integration;
  melonds_memory owns that reader and its tests; record_size checks the known
  D2 lane projection regression without product edits or emulator control.
- Workshop build 1788781664.693693 passed in 54.107 seconds and copied
  `test3079.nds` to Delta. Open-after-build stayed off. The exact package
  metadata check now passes without removing it. Scoped diff whitespace
  check passed. A pre-build attempt to reuse the old package manifest was
  correctly rejected because its verifier source hash was stale; the new
  build regenerated the manifest. No new runtime proof yet: next run is the
  unchanged prepared Cyndaquil fault witness, then normal movement proof.
- Test selection policy: keep current regressions, update stale setup, skip
  unrelated checks, and retire removed behavior with a recorded reason and
  replacement where needed. Reuse each decision until its inputs change.
  The build at 1788781276.795724 failed package metadata validation after
  Summary bounds passed. This check remains needed: it detects wrong y9/FAT
  packaging. Update only overlay129's exact size/end pins for the 28-byte
  guard (0x7FEC / 0x3E29EC); the next 512-byte boundary is unchanged.
  Independent review confirms all other metadata and real bounds stay fixed.
  This is a test expectation update, not permission to accept arbitrary sizes.
- Guard implemented as an appended28-byte overlay129 section, preserving old
  exports/prefixes. Permanent host check uses actual GNU assembler, actual
  linker script and packaging redirect; NULL unwind, non-NULL parity and a
  removed-branch control pass. It now catches linker syntax too, after the
  first new ASSERT's trailing semicolon failed a build. Regular .text placement
  was rejected by the unchanged overlay153 prefix gate and replaced, not waived.
  Build then exposed a legacy Summary whole-image headroom target0x7FD0.
  Review found no owner for those spare48 bytes; replaced that historical
  target with real overlay129 reservation0x8000. Current image0x7FEC leaves20
  bytes; exact-boundary and overflow controls pass. Summary entry/ownership,
  old prefix checks and the guard's32-byte cap remain. Two focused checks
  pass0.627s; fixed runtime proof still pending.
- Build prerequisite audit preserved existing Makefile header-dependency
  narrowing and overlays.mk atomic link changes. Reversing only those changes
  reproduced the two old trusted hashes; all10 learnset consumers and sole
  battle-header consumer are covered. Updated only the two stale pins, not
  the other owner's build files. The pre-Make gate passes; all other included
  source pins already matched. Build/core are stopped before the next retry.
- Pool probe `test-2aeaad5ca3864f0faf1610d9f1644373` failed24.210s at
  764/native1938. Authenticated stock caller/allocation code and exact pool
  chain: capacity32, used32, last slot31 non-NULL. The grass-effect initializer
  still uses NULL after creation fails. Stock sub_02068A08 already supports
  initializer FALSE: it destroys the task and resets its slot without calling
  the effect destructor. Proposed fix rejects only this failed initialization;
  successful grass effects and movement stay unchanged. Do not increase the
  pool or silence NULL setters globally. melonds_memory owns the bounded
  assembly guard/checker; record_size reviews cleanup and proof needs; root
  owns integration and any build/live tests.40 focused observer/setup/wiring
  host checks pass. No product fix built yet; core stopped.
- Stack probe `test-889bb08a49d143c7b1464d5bd366de35` failed22.448s on
  the same first low write (751/native1905). Saved caller021FF21D identifies
  BL021FF218 inside stock field-effect initializer ov01_021FF174; its
  environment is023391D0. The initializer stores a failed effect creation
  handle at+3C and passes NULL to sub_02023F1C. This is the exact unsafe use,
  not a nearest-symbol guess. Creation may fail from a full pool, missing
  pool or NULL free slot; none is measured yet. Next first-fault diagnostic
  reads that exact source-authenticated pool chain before deciding the fix.
  Do not increase capacity or suppress the effect from assumption alone.
  Core stopped. Roadmap D1 remains open; no movement-fix claim.
- Writer probe `test-68dcd0fefca94bb8801f5a9f8cd73180` failed22.960s with
  first changed write at frame751/native1905: address000000B8,size4,valueC000,
  canonical IRQ01FF80B8 (one changed word). Native bridge inactive. ARM9
  PC02023F30/r0=0/r5=B8 matches stock sub_02023F1C's NULL-assert-then-store
  at02023F2C. This catches corruption before the later invalid IRQ return;
  it is not a walking proof. The write callback itself does not label CPU.
  Original caller is not yet proved: LR02025523 belongs to the assertion
  path, so the probe now saves bounded64-byte public stack data on first
  fault.35 relevant host checks pass. Core stopped; next one bounded setup
  probe obtains that caller; no product edit or ROM build yet.
- Removed the stale nurse-only paragraph from verification.md and the two
  planned unmounted route contracts. Both now declare checked prepared
  HP/status/follower setup; movement/timing/distance limits are unchanged.
  Their setup audits are pending until the complete adapters are implemented,
  not inherited from the old setup. Scenario validation passes. This is a
  current-contract correction, not gameplay acceptance or a reason to rerun
  healing tests.
- First-fault tool improvement: IRQ evidence now retains up to16 changed words
  plus total counts, and compares against both stock and a full live baseline.
  The old hash-only receipt could not identify the changed bytes or date them
  against a complete live baseline.13 focused observer tests pass, including
  short-read rejection and pre-existing stock differences. No new game run
  yet: inspect whether a bounded write hook can identify the writer directly.
- Scoped follower-release IRQ reader: first run
  `test-0a706f760f1c451aa3dade4c10fa707c` passed37.181s (diagnostic only).
  Its four retained setup records pass the actual prepared cadence evaluator;
  two prepared commands contribute zero movement frames. The bounded repeat
  `test-06aa36b658994d1081cf42e000ca199c` failed25.173s at frame764/native1942.
  First invalid checkpoint is stock IRQ no-switch return01FF80F4, SP027E3F64,
  stack target1; earlier valid returns used SP027E3F60 and BIOS targetFFFF0290.
  IRQ body hash also differs from the authenticated stock image. This narrows
  the setup fault but does not prove its writer or a game fix. Core stopped.
  Next: validate this checkpoint against stock assembly and inspect the first
  changed code/stack boundary; no blind repetition or full-route claim.
  Root owns integration; melonds_memory independently checks the saved fault.
- First-fault inspection of bf558: the native selection request returned1,
  then normal queues advanced to766 before the120-cycle stall. This is not
  native-call time wrongly charged to the queue watchdog. PC0233BF7C is outside
  the recorded bridge allocation022CCC3C; CPU is ARM IRQ, LR020D0F54.
  Selector133 is BOUNCING|AGGRO_FLAG, so the failing interval is the normal
  follower release/bounce path. Cause/write is still unproved; do not infer
  bridge innocence or fix the game from this alone. Keep the automatic fault
  threshold. Same-frame already-selected prepared readback is separately fixed
  with45 host checks: only a validated unbound setup receipt can refresh, with
  no frame credit; ordinary duplicate frames still fail. No new live run.
- Fast fixture implemented: `world.cyndaquil-prepared-setup` uses7 setup actions,
  not156. Run `test-ae9a6a5cea9a40849b0270b8f8e1c079` passed28.314s with the
  correct FOLLOWER155 PID2046726716 and1 post-bind frame, diagnostic only.
  Retained replay then exposed service receipt truncation: checked jobs had
  saved the manual summary, not full party/spawn readback. Fixed the internal
  dispatch to retain the full worker receipt;73 service/job checks pass.
  The required fresh rerun `test-bf55828b9dc7440e86f3589d5eec41de` failed20.099s
  during prepare-follower: automatic main-queue-stalled at completedFrame766,
  nativeCycle2065,120 cycles without progress. Saved CPU is in IRQ mode,
  no current follower actor, releaseState133. This is an open prepared-setup
  fault, not a measured walking/stutter failure. Core stopped; no blind rerun.
  Root owns integration/ledger; melonds_memory inspects the saved first fault.
  record_size fixes the separate same-frame already-selected receipt edge in
  the raw evaluator with host tests. Current prepared cadence setup permits
  only HP/status and saved-follower commands before bind; route/CPU limits are
  unchanged.97 integration checks and116 runtime/boundary checks passed before
  the final receipt transport fix. No product/ROM/save edits or builds.
  Next: resolve this actual setup failure using retained CPU/native evidence,
  then the full route. Before each step, check need versus legacy and choose
  the fastest sufficient method; this is now in AGENTS, not a new planning task.
- Durable setup-cost correction: AGENTS and all three overworld skills now
  select the cheapest setup that preserves the actual trigger under test.
  Shared validation/catalog/start report setup costs; start rejects typed
  nurse/dialogue detours for unmounted cadence before creating a worker.
  The real nurse recipe converted to cadence is the regression fixture; actual
  healing/Center diagnostics remain allowed.80 focused host checks pass
  (29 job tests,51 efficiency/contract/cadence integration tests); three skill
  validators pass. Independent read-only decision checks select fast movement
  setup, real Y-menu input, natural spawn input, and retained-data replay for
  the four matching tasks. Workshop restarted while idle and returns the new
  report, with no emulator/build started. The check prevents this known waste,
  not every possible inefficiency. Next remains prepared cadence setup and
  full route/control proof; no movement claim is closed by these tool checks.
- User correction: movement/stutter setup must use the existing party-edit
  tools, not repeat nurse healing. Normal healing/Y-selection is not a cadence
  requirement. Stopped root-owned manual session6av52a63 and paused the
  nurse-based route-builder work (no helper edits). Next: change the cadence
  meter/recipe and exact scenario setup contracts to accept checked prepared
  HP/follower setup, then measure normal movement with all original motion,
  identity, distance and timing limits. Use the fresh post-setup native step
  count, not the nurse route's count50. The75-second setup pass below is
  historical setup evidence, not a required step for future movement tests.
- Normal Cyndaquil setup passes on3078: `test-100cc09132e24a2cabbdef7241b81be9`,
  74.526s,1321 sampled frames and1 real post-bind frame, no failures. This is
  diagnostic setup only (`acceptedProof:false`), not unmounted cadence proof.
  Both exact automatic door receipts, normal nurse healing, normal Y/R
  selection and current FOLLOWER binding pass. The owned core is stopped.
  Previous `test-f77117c4aba2496baece7c431c521152` reached the correct follower
  but failed because its already-true final player-position wait collected
  zero post-bind frames. The final wait now uses `measurement-complete`;
  exact settled-player/PID/HP assertions remain.32 focused host checks pass,
  including the zero-frame pre-check regression; independent review found no
  must-fix.44 scenario contracts validate. No product, ROM or save changes.
  Next: author the normal outdoor route and native route controls. The reverse
  Center path offers only about34 unique tiles and2 cells; read loaded terrain
  to extend it before claiming80 tiles/3 cells/2 maps/5000 active frames.
  Root owns the next run and integration. The melonDS migration remains a
  recommendation from the user's question, not an implemented change.
- Setup run `test-a9e73b918645442dace3086374bc8ec1` now proves both automatic
  doorway receipts and normal nurse healing: same PID2046726716 reachesHP21
  at1589; fresh native getter confirms21 at1854; exit observed1907; Y opens1968.
  It fails70.964s at1984 on `selector-next-r`: the actual menu starts at slot2
  (current Mankey), so one R selects3, not required Cyndaquil slot1. This is a
  wrong recipe start assumption, not a game lock. record_size owns bounded
  observed-highlight R cycling with explicit native edges/releases; root owns
  next run. Core stopped; no ROM/product/save change. Automatic doorway fix
  passed86 focused checks plus5 final setup checks, with retained real entry
  and exit receipt replay. No generic transition admission exemption was added.
- Setup retry `test-44e24c125a0040388b3b2a76b7fec919` reaches the normal Center
  door, then fails39.859s at941: the raw cadence transition tracker forbids
  every native admission, including stock automatic UP step36 from67(564,392)
  to(564,391) under the live doorway task. The standalone Center meter had
  supplied an empty admissions list, so its pass did not test this constraint.
  The retained native receipt contains before/after object, pose, direction and
  step identity. Next: check only the exact stock entry/exit automatic steps,
  preserving all unrelated-admission rejection. record_size owns tracker/tests;
  melonds_memory reviews; root owns integration and next run. Core stopped.
  Prior ring-reuse fix passed63 focused tests plus5 final trace negatives;
  full failed2fc stream replays through750, Center event stream through1064.
  Actual lost data, unknown trace notices, resets and missing context still fail.
- Normal setup is now implemented as diagnostic `world.cyndaquil-normal-setup`
  with strict native healing confirmation, native A-edge input, exact nurse
  step counts, normal Y/R and IDLE follower binding. Review removed premature
  exit input and lost one-frame A taps. Full host1151 passed136.125s; final
  A-edge recipe correction passed14 focused checks. First live run
  `test-2fc19971f7c54906be352adc839af73b` failed27.898s before nurse setup:
  at750 the shared trace reported ring-overwrite/count1/unreadEventsLost0,
  while cadence assumed every status carried coverageComplete:true. This is
  a meter/trace-contract mismatch, not lost game data or a gameplay pass.
  Root owns integration; melonds_memory fixes exact no-loss status handling
  with retained replay/negative controls; record_size reviews it. Sources may
  change; the owned core is stopped. No product/ROM/save change after3078.
- Current3078 Ledyba proof passed: calibration461fa67b7d1b4d97a33905dfa34db1b5
  accepted in151.887s; normal chain cda55af45ece4dd0aef3e7b8e6f3795f accepted
  5024 observed frames,587 completed motions,482 eligible moves,35 complete
  intervals of8–14 and26 pause actions. Same WILD165 PID2930533025, handle131072,
  map34; no failures. Execution350.475s plus acceptance56.216s,406.691s total.
  This covers its normal named-actor contract, not unmounted travel stutter or
  all maps. Both owned cores stopped. The next gap is concrete: no shared
  nurse/Cyndaquil setup or full cadence recipe exists, although its raw meter
  is implemented. Root owns dispatch/ledger; record_size assembles the normal
  setup recipe/meter; melonds_memory separates in-Center healing observation
  from the later natural Y-selector HP getter confirmation. No party/save edits
  or new product changes are needed for this setup work.
- Center test `test-ed7fb7009fb340a6b2f22c6ad2c71afd` passes on3078 in46.774s:
  entry941->980, exit985->1059, then settled control at67(564,393), frame1064.
  Each transition retained10 lifecycle-absence rows; none supplied movement
  credit. No failures. This is a diagnostic typed test (`acceptedProof:false`),
  not broad transition or freeze acceptance. The shared guard/strict absence
  validator passed173 integrated host checks. Previous turn made concrete
  progress: product reload regression RED->GREEN, build3078, automatic live
  failure diagnosis, and now a passing unchanged door recipe. Next is the
  normal nurse/Cyndaquil route setup and unmounted cadence/control proof.
- ROM3078 built successfully through Workshop (open-after-build remained off).
  test.nds and numbered Delta copy both hash
  `4855949dfcc069a3773e59c5ee2bbe11446161062b5e9748286ddd2d1e978d04`;
  test.sav/test.dsv hashes are unchanged. Field131 ends023CCEC2, below023CCFD8;
  fixed entries remain at8010/8148/8154. Full host gate1123 checks passed in
  139.671s, and devtools-only retirement passed334 files. Unchanged Center
  run08e4af2a42f541d491ab2848efae4646 now gets past exit cleanup: at996 the
  field manager is absent and fieldReady0. It still fails acceptance after
  45.806s because the sampler treated a retained global field pointer as live
  and read freed player bytes. This is a new observation gap, not a game pass.
  Actor-position bounds remain strict. Next: guard sampling with the stock
  field lifecycle predicate, retain actual absence rows, rerun unchanged3078.
- Center lock follow-up: unchanged ROM3077 runs486237 and11d480 both fail
  automatically at the exit no-progress deadline (frames1224/1225). Entry is
  measured without requiring an absent field sample; the two transient null
  player rows remain in the evidence. Run486237 reads local active sequence1
  while Actor retains COMPLETE. The actual-C driver/model regression then
  proves a local overlay reload repeats sequence1 and rejects the next map
  pair with reason17. Replacing that local counter with the captured packed
  resident context makes the unchanged reload/retry/wrap regression pass.
  Independent review found no issue. It is now in the permanent host gate.
  The earlier full host run passed1114 tests; later focused checks cover the
  zero-absence and diagnostic changes. Build and unchanged live rerun are next;
  this is not yet a game fix claim. Run11d480's expanded Actor diagnostic was
  unknown because boot-resident overlay158 is not SDK-tracked; the corrected
  reader checks its resident region and exact code/state instead, with8 tests.
- Shared frame-clock fix: test-5597fae753314651aa7b7284df335fc6 failed at
  Center entry after38.369s and now retains the rejected chunk. It has dense
  frames960/961 with one native-cycle stamp2364; no sample was missing. The
  raw validator now maps every queue sample to its actual physical interval,
  charges timing once and invokes meter/evaluator checks per frame. Full
  immutable-stream replay reaches961 without errors, with no readiness/pass.
  Live and replay permit extra completions only in neutral raw setup waits;
  input/observation counts and action/run budgets remain strict. Earlier bad
  frames cannot be rescued by a later state. Independent review found the
  initial replay-count gap; that guard and negative controls are now added.
  The Center entry departure is corrected to564391 from stock STEP_UP plus
  retained live memory; approach564392 and all route inputs are unchanged.
- Cleanup branch observation is now available as fieldControl.fieldCleanup.
  It authenticates owner overlays, defining ELF symbols and live/package code
  before reading32 bytes of transition/selector/helper state.122 focused
  checks pass. Root owns the next unchanged3077 Center run with both tools.
  No product edit/build/save change. The first wider host run had1113 tests
  with one stale watchdog fixture error; it now uses the checked continuous
  input path, and45 focused checks pass. A fresh full host run is in progress.
- Freeze-detector follow-up: player flags, movement commands and unrelated
  context changes could reset the shared job no-progress deadline while the
  player was stationary. The new real-job host witness reproduced all three
  gaps (held input, tile admission, settled target). Movement deadlines now
  use native X/Z and tile admissions only; a true stop predicate at the exact
  deadline remains success. Negative churn and positive movement/settlement
  controls pass with the existing CPU/main-queue and Ledyba-subject guards:
  50 focused host checks including rejected-chunk retention. No product edit or ROM build. These are tool checks,
  not a new gameplay-freeze acceptance claim.
- The durable normal Center entry/exit recipe and exact transition meter are
  implemented. First shared live run test-d990420f68ab4ce49c49a184a7513901
  stopped after39.970s with incomplete-frame-evidence at entry (last evaluated
  frame967, diagnostic endpoint969), before the known exit lock. Its failure
  bundle and observations are retained; passed/acceptedProof false. This is a
  shared stepping/observation gap, not the required red exit witness. The owned
  core stopped. Source analysis found a native-cycle overshoot: the one-frame
  wait returned at969, two completed updates after967. The old job discarded
  that rejected chunk, so its sample count is not recoverable. Jobs now retain
  the raw chunk before validating counts; a real-job host control proves that
  all rejected samples survive and acceptance still fails. No frame/count rule
  was relaxed. Root owns integration. Sources were frozen during the live run.
  Next: rerun with full rejected-chunk evidence, resolve the exact frame boundary,
  rerun the same recipe, then fix the proved cleanup
  refusal path without bypassing cleanup. No screenshots or save writes.
- Minimized normal exit reproduction on3077, session-09tr3lty (stopped): enter
  Center then leave without nurse/healing. First DOWN only turns the player;
  require the actual doorway task before starting the exit deadline. Next DOWN
  creates it at1227;120 later frames leave map69 unchanged. The new bounded
  lifecycle read at1347 proves fieldReady1, owned manager execState2/procState0,
  and the stock leave-wait child under parent door state4. This distinguishes
  the missed leave request from terrain shutdown; the manager never entered
  exit. Exact diagnostic: session-09tr3lty/diagnostics-7c3298876389.json.
  Route/entry memory: recording-428c5ba5e2de.json; actual exit-trigger/failure:
  recording-d9dd1b3993bd.json in the same session directory. No dropped samples.
  No images, product edits or build. The reader plus actual shared diagnostic
  wiring has8 host tests;126 focused checks pass. Source saves still match.
  Next: make this shorter normal door route the durable failing shared test,
  then fix retry ownership without bypassing cleanup, build and rerun unchanged.
  The larger nurse route is now usable once this exit defect is fixed.
- Current live result on3077, session-3_xx63pt (now stopped): the unchanged
  one-frame route now passes the former LEFT failure and reaches Center69.
  Nested nurse contexts are observed; one A edge per checked input wait reaches
  normal healing at frame1604 (same Cyndaquil PID2046726716, HP0 ->21), and
  idle/released control at1869. No party/save writes.218 focused host checks,
  scenario validation and the devtools-only boundary pass. Both input-phase and
  nested-context changes have independent read-only review with no must-fix
  issue. No screenshots or ROM/build change.
- New blocking setup failure: after reaching exit tile69(8,19), waiting alone
  did not warp (the stock exit needs another DOWN). That input created the
  native door task, but240 further frames still did not leave. At2382 the
  child is sub_02055244, waiting for the field manager to disappear; parent
  sub_02055DBC is at state4, destination67. CPU/main queue still run. Memory
  recording: session-3_xx63pt/recording-a6286a6d0921.json (1652 snapshots
  received, none dropped, diagnostic only); endpoint:
  session-3_xx63pt/diagnostics-63048d9fda95.json. This does not prove a general
  freeze fix, normal Center exit, Y selection, or long-route cadence.
- Source investigation found a concrete missed-retry path: the custom field
  leave hook clears field+0x6C only if cleanup succeeds, while the stock caller
  invokes it once then waits. FALSE can leave that wait permanent. Do not yet
  assume this was the live cause: distinguish fieldReady1 (missed leave) from
  manager exit-state3/phase1 (terrain wait). record_size owns a bounded read-only
  field-lifecycle diagnostic and host controls; root integrates it, captures
  the distinguishing values in the normal exit reproduction, and creates the
  durable symptom test before a product fix. Y/cadence remains open.
- Live normal nurse discovery on3077, owned session-la657zq1 (now stopped):
  unchanged test.sav reached Center69(8,19), then nurse69(8,13) through normal
  walking and the door67(564,392). The same slot1 Cyndaquil PID2046726716
  still has HP0. After A, frames1148/1150 reject `script-context-count-or-state`;
  no additional A was sent. The map's stock script calls `std_nurse_joy` through
  CallStd, so the single-context reader needs checked nested-context support.
  Diagnostic memory: session-la657zq1/recording-5c0fec2c2c3a.json,420 received
  snapshots, no drops, acceptedProof false. This is a tool/setup gap, not a
  gameplay pass or a new game freeze. record_size owns dialogue.py and its
  tests; root owns integration and the next normal nurse run.
- The same route exposed a shared manual input timing gap:64 separate one-frame
  LEFT commands at(585,402) did not turn or move; a16-frame LEFT command moved
  three tiles immediately. Two-frame commands then completed the remaining
  checked route. The stock keypad poll precedes the completed queue, so the
  current end-boundary release can discard a command before a poll consumes it.
  melonds_memory owns the bounded runtime input-phase fix and its host witness.
  Do not change game movement or treat the one-frame failure as terrain proof.
- Shared reader follow-up: the bounded native dialogue reader and typed
  `dialogue-state` predicate are implemented. They check the current script,
  printer/menu ownership and code; healing, movement, fade, timer and nurse
  follower recall remain busy, and unknown state permits no input. The focused
  reader/runtime/record/health suite passed183 host tests; the separate health,
  wiring and invalid-free suite passed21. Scenario validation and the retired
  driver boundary check pass. This is host evidence only: normal nurse input,
  same-PID healing and the unmounted cadence route remain unproved. No ROM or
  save changed. Independent read-only review found no must-fix issue; optional
  lead-change teardown remains unproved and unknown callbacks stay closed.
  Restart the idle Workshop before live reader use.
- D1 spawn surface checkpoint on3077: current native height control
  test-b84b430ede0b4c5ba543490708d839f7 passed137 frames/75.995s. Unchanged
  normal spawn.ledyba-pool-site test-03a210b1a2984ec6b56798aca5e924f4 passed
  136 frames/123.520s; repeat test-c811a274adf14e67927671061e476a0a passed
  138 frames/126.572s. All terminal manifests have passed/acceptedProof true.
  This closes the registered own-POOL, loaded-metatile, authored-surface
  exclusion and native terminal-height witness for the measured Wild Ledyba;
  it does not prove every unmodeled tree/roof geometry or later movement.
  All owned cores are stopped. No product/build/save changed in this checkpoint.
- Active next contract: D1 unmounted player/Follower Cyndaquil cadence.
  Root owns integration. Add a bounded shared native dialogue reader and typed
  wait predicate for the normal Center healing route; no direct HP/party/save
  writes. Known script/printer/menu ownership must be checked before an input
  state is reported. Unknown state cannot request A. Reader controls precede
  live setup; fresh same-PID healing and real Y selection still require their
  existing independent observations. Do not count setup toward5000-frame proof.

- Immediate priority: automatic freeze detection and the new Ledyba-area
  melonDS abort. Read-only samples from the user's melonDS 1.1 process 20282
  both show actor frame381, CPSR0x97, rawPC0xFFFF010C, LR_abt0x023BF59A and
  saved SYS LR0x023D070D. Field pause0/task0/ready1 exclude a normal menu wait.
  The failed3076 code loads misaligned Thumb literal data in DirectionKey:
  0x023BF58E reads0xFC2C4770 instead of the intended table address0x023BFC2C;
  the following load at0x023BF592 aborts. The caller is the prepared custom
  jump start. StrictDiagonalAllowed has the same alignment defect.
- Both public entries remain fixed; short Thumb branches reach word-aligned
  bodies. No speed, turn, collision or profile rule changed. Independent
  comparison proves history/save bytes and Field/tail bytes unchanged;
  only the reviewed Walk spans and private helper calls differ. The exact
  20-section input-to-linked alignment check is now required by packaging and
  runtime preflight. Missing/empty/non-code/extra sections fail. The unchanged
  112-call history/save seal remains separate from the revised Walk seal.
- Workshop build1788735686 passed and published3077, SHA-256
  `68b90ee705d6d986df4dff45f2ca02c3f16c79e4df02745df0375136c4fbb76d`.
  Delta test3077.nds matches. Both saves are unchanged; open-after-build false.
  Earlier build1788735489 stopped at the old Makefile seal;1788735555 compiled
  but stopped at the old Walk prefix seal. Exact source/byte checks preceded
  updating these seals; neither failed build is gameplay evidence.
- Shared post-boot cycle control now latches CPU abort/undefined faults and
  a120-native-cycle main-queue stall across separate commands. It keeps the
  first CPU/field memory data and does not advance a failed core. Actor idling
  alone is not a freeze. Host pause is excluded, not ordinary game time.
  162 focused host checks pass, plus12 actual-package/section checks. Permanent
  skill guidance requires inspecting the first fault before retrying.
  Review found bridge-entry waiting was incorrectly excluded; a regression
  reproduced that gap. Exclusion now starts only at native takeover, waiting
  entry stalls fail at120 cycles, and bridge teardown keeps the first health
  fault. No claim that all control locks or individual actor stalls are detected.
- On3077, live reader control test-bf3fd4e4e51a4bdaa6c415a614ac02d1 passed with
  acceptedProof true,1021 observed frames,106.837s. Normal5000-frame run
  test-79f15665f48846c1b043734d30713888 was canceled at440 observed frames to
  fix the tool review finding; it is not a pass. Both owned cores are stopped.
  These earlier tool-input results are historical after the bridge correction.
- Final3077 control test-85b806e520a843be88bdaaafef32687e passed with
  acceptedProof true,1032 frames,110.862s. Unchanged normal Ledyba test
  test-ec7d50484b1a493da8cf1723fbb1ccd2 passed5000 continuous bound frames
  in316.519s; repeat test-58016acf6bd64a90981e269a633ae80c passed5003 frames
  in336.894s. Both terminal manifests have passed/acceptedProof true and no
  failures. These are shared DeSmuME runs, not fresh melonDS runtime proof.
  The user's actual melonDS abort and exact bad literal read were the failing
  diagnosis; package alignment is now checked even when a core tolerates it.
  All owned sessions are stopped. The user's frozen melonDS remains untouched
  and needs3077 reopened. Next roadmap work: current height control and normal
  own-target surface witness, then the open unmounted stutter route/control.

- Prior3076 height control test-1f3aaa09bf1349f983e0bbf24db6b257 passed with
  acceptedProof true,144 observed frames,63.42s. Native Ledyba165 used its own
  target(556,376), cleanY65536, injectedY69632 and restoredY65536 in the same
  callback. Wrong-Y and missing/restoration controls failed as required.
  Prior motion control test-7565dd16fb59434b9f8256b6ea9d600e also passed with
  acceptedProof true,805 observed frames. These are historical after3077 and
  current tool edits; do not reuse them for new surface acceptance.

### Earlier checkpoint history

- D1 resumed after the Continue-load fix: separate native height-reader control
  is now registered as `observation.spawn-height-control`. It uses Ledyba's
  unchanged normal route and own POOL landing. Clean, wrong-Y and restored
  reads share one native callback; no guest instruction runs between them.
  Review caught and fixed a stderr failure that could skip fatal worker exit,
  stale control-clock acceptance (18 invalid cases had passed), and controller
  fault replay modifying retained setup events. The exact regression controls
  now fail for those faults;81 focused host tests and44-scenario validation
  pass. Product ROM remains3076. Next: run the registered live height control,
  then the normal own-target surface witness after both required calibrations.
  Do not claim physical surface acceptance from host data or images.

- Immediate priority (2026-09-07): melonDS Continue-load crash. Read-only memory
  from the user's running melonDS 1.1 process proves ARM9 data-abort mode,
  actor frame stuck at 4, and stock Heap_Free(NULL), called from spawn-metadata
  cleanup (saved SYS LR 0x023C3371; faulting load 0x0201AB12). Diagnostic data:
  `build/melonds-continue-null-free-3075.json`. No recovery input or RAM writes.
  Shared test `test-6bc87d8672af4562b5f7d8d774429b07` now fails on the same
  NULL free and caller after adding a read-only stock-free observer. This
  closes the emulator blind spot; DeSmuME had tolerated the invalid access.
  Earlier `test-814e517444e747a79967f0d1e01a2773` failed source-scan preflight,
  not gameplay. Both failures remain retained.
- Four scoped NULL guards now protect metadata cleanup, optional movement
  cache cleanup, and behavior-blob cleanup/load failure. Actual production-C
  tests pass for never-allocated, failed-allocation, owned and repeated cleanup;
  removing the guard fails the same test. This test and the native-free
  observer checks are in the permanent host gate. Independent review found
  no issue. Current linked overlays fit their unchanged address limits.
- New Workshop build 1788733486 passed in 57.145s. Current ROM is 3076,
  SHA-256 `e0754eb1b97944f20478b675d7a88cc993249ae26b9a2cc4f0f924ee2205edaf`.
  Delta `test3076.nds` matches; both source save hashes are unchanged.
  Open-after-build remains false. Doctor and 43-scenario validation pass.
  Unchanged direct-load test `test-932b819eff814d5cba63bb43b86f433b` passed
  with acceptedProof true, 16 observed frames, 39.995s and no failures.
  A separate normal-load diagnostic session `session-hmwlfdu5` moved in all
  four directions over 480 input updates (UP/LEFT/RIGHT/DOWN, 120 each).
  Actor clock advanced from298 to778; player endpoints were585406,585396,
  576396,587396,587412. No field/clock reset or healing inputs were used.
  Memory artifact `recording-ac53619bfbb6.json` has482 snapshots,2228 events,
  zero dropped rows and zero reported failures; SHA-256
  `ffe7a1697b357850e00504f7a42a112d4ec5a34f9bfe9cf9d3f70b2bc9b9ae28`.
  Session is stopped. This is movement diagnosis, not broad roadmap proof.
  Final unchanged repeat `test-8c72c47d8b0a4702a66876d826ba8672` also passed
  with acceptedProof true,16 observed frames,40.941s and no failures. Its
  private session is stopped. This is the current direct-load witness after
  host fixture maintenance; the ROM and production fix did not change.
  The full host gate initially found outdated fake-ROM callback fixtures and
  an old control-job fixture missing its now-required measurement kind.
  These are corrected without changing runtime guard behavior. The subsequent
  995-test run had zero errors and only the two old job-fixture assertions
  loaded before their correction. All20 job tests pass after that correction;
  114 runtime/guard tests pass. The final combined140-test check passes.
  Do not describe that earlier full run as green.
  The user's old melonDS instance remains untouched and needs a ROM reload.

- Earlier investigation (superseded by the fault above): user reported immediate movement freeze with
  audio continuing after opening test.nds. ROM remains3075/SHA79e6453; save
  hashes unchanged. This is not reproduced or fixed. Shared DeSmuME diagnostic
  session-m0a1ue0c moved19 tiles in120 game updates, then completed600 neutral
  updates; it is stopped. This does not clear the user's melonDS report.
  The app uses adjacent test.sav (no alternate save folder), JIT disabled.
  Surface registry/controller additions are frozen WIP: new controller tests,
  validation and live height-recorder fault control are still required.
  session-_xyywt37 is now stopped. It moved19 tiles over240 updates; exported
  memory data recording-e23eaebf47c2.json has242 snapshots, no dropped rows,
  and SHA26ebb50ad27c2672d752da7882fcfaeba1ad1e1cb9e6903d6f9c4b4d3dd353cf.
  This is diagnostic only. A concrete masking risk was found in shared boot:
  it sent B/X recovery input if the actor clock stalled. That recovery is now
  removed; the unchanged stalled-clock window fails with field/task/pause and
  actor-clock memory data. A regression first failed against the old healing
  path, then passed. Independent review found no blocking issue;197 focused
  host checks and the303-file devtools-only guard pass.
  Fresh session-fhqyw99r loaded without recovery on unchanged3075/test.sav.
  UP120, LEFT120, UP240, RIGHT120 completed600 updates and30 player tiles.
  The third action stayed at576396: own adjacent576395 was loaded with native
  collision bit set (attribute32774); the fourth action moved11 tiles east.
  Thus this particular stop was not an all-direction lock. Memory data:
  recording-f17f926109df.json, SHA80f207a0640e07b1a537430451134f20eadce6637fd4e94a8a3b2be3357c3f23,
  602 snapshots and2151 events with no drops. Session stopped. No game code or
  ROM build changed. This is not accepted proof that the user's freeze is fixed.
  An isolated melonDS1.1 copy was launched with copied ROM/save/config. The
  first GDB read worked; reconnects timed out, so no field-lock witness was
  obtained. The owned app was stopped; original save hashes are unchanged.
  Do not treat that debugger failure as the user's game freeze or a pass.
  Next: obtain the user's locked melonDS state or exact first triggering input;
  inspect native field pause/task and actor clock without recovery input.

- Branch: `feature/overworld-actor-system-roadmap`
- Resume point: D1 gameplay work resumed through shared devtools. Complete
  D1 before broad D2–D6 cutovers, then freeze and prove D7. Do not run the
  former standalone collectors again.
- Packaged ROM: 3075; SHA-256 `79e64530ce843d8d14f2a606d0a39cc124f67b4734d17b6a8a98e776f9b3bc59`.
  Managed build1788728599 passed in72.411s with typed-chain and occupancy
  code-host changes. Delta test3075.nds matches; both source saves are unchanged.
  Doctor and exact occupancy package check pass. Fresh live control
  `test-4cde86f4d9e5431d902e1d304aac0371` passed with acceptedProof true.
  Normal witness `test-6e7e00fff182470d911af6c03f421f8e` passed5000 bound frames,
  with acceptedProof true. Unchanged repeat `test-dc671f0221b046b5a7787ac15bcb4b81`
  passed5002 bound frames with acceptedProof true. Both sessions stopped.
  This closes the narrow repeated normal-chain witness on3075, not physical
  spawn terrain or unmounted stutter. Reader work may now resume.
  The earlier current-context binding receipt is retained below, not promoted
  to final-candidate acceptance. It does not clear the open D1 behavior claims;
  do not reuse historical counts or pass claims as current evidence.
- The branch contains substantial source cutovers. Build 3071 is a buildable
  checkpoint; current3074 also contains the scoped off-screen origin guard. Prove the remaining
  D1 behavior before further broad cutovers.
- The reported engine stutter is not a mounted-only report. Ledyba normal spawn,
  chain timing, pause action, and unmounted play remain required observations.

## Current work table

Active work: D1 actual normal Ledyba behavior and unmounted stutter. Root owns
integration, this ledger and the one live session. Helpers do not start cores
or builds. No product edit is accepted without its current symptom witness.

| Work | Owner | State | Evidence / next action |
| --- | --- | --- | --- |
| Continue-load ARM9 abort | root | scoped NULL-free fix built3076; unchanged direct-load proof passed twice | Actual user melonDS abort and shared RED6bc87 agree on caller023c3371. GREEN932b and repeat8c72 accepted; normal movement diagnosis480 updates. Runtime/guard and job fixture checks pass. User must reload the new ROM, not resume the old aborted instance; live fixed-build checks used the shared emulator, not the user's old melonDS process |
| D1 normal Ledyba spawn/chain/pause measurement | root | two unchanged long witnesses accepted on3077 after literal alignment fix | Current control85b806e5 accepted; normalec7d5048 passed5000 bound frames; repeat58016acf passed5003. Both passed/acceptedProof true, no failures or images. Exact user melonDS abort retained separately; fresh native melonDS runtime, physical spawn surface and unmounted stutter remain distinct proof gaps |
| D1 Ledyba spawn destination legality | root | stronger own-POOL surface witness accepted twice on3077 | Height controlb84b430e accepted; normal03a210b1 passed136 frames and repeatc811a274 passed138. Both prove own site, loaded metatile permission, authored-surface exclusion and native terminal Y; no images. Universal unmodeled geometry and later motion remain outside this exact contract |
| D1 direct-load presentation binding | root | accepted S3 | Unchanged scenario passes on3071: test-06beeabda08240fca381ab5d2adc3e8b,16 frames,31.085 seconds; saved Mankey has exactly one current native ID match |
| D1 unmounted stutter witness | root | Collision waits and empty setup IRQ retirement wired; current full route pending | Short093bae has no hitch in302 cycles. Calibration5fcada passed but its15MB manifest was unreadable by the dependency gate, so fullc716 failed before gameplay. Compact writer and shared8MiB publication check now fix that tool defect without losing data. Refresh calibration after current tool changes, then rerun full route with unchanged thresholds; keep466ab/99a5 CPU failures open |
| D1 Ledyba proof adapter and live recorder controls | root | landing-stage readers calibrated on3074 | test-ea5ab8348f904f5e8bda65092f037f8b:895 subject frames/157.465s, passed and acceptedProof true. Native surface/terrain/occupancy calls and deliberate faults checked without images. Does not close the game stall |
| D1 live setup and integration | root | off-screen spawn-origin boundary fixed and verified on3074 | Pre-fix test-6ccb5b1799524f29a066f54f748c2dd9: actual origin inside view. One bound retains16-tile cardinal travel/own target and rejects edge origins. Actual-C geometry, unchanged live control and two normal S4 runs pass. All owned sessions stopped. Keep physical landing surface and later stall separate |
| D2–D7 remaining roadmap | root | queued after D1 | Preserve all40 original requirements;37 remain unported. Final-current Ledyba proof and the remaining matched behavior proof stay open |

Resume gate evidence: `build/roadmap-resume-shared-gate.json`. In addition to
38 planned scenarios/40 pending runtime requirements, five checks failed:
`walk.pause`, `host.flat-reposition-clearance`, `walk.flying-insect`,
`package.legacy-owner-deletion`, and `walk.momentum`. These are open checks,
not skipped or accepted as game behavior. Four stale host checks have since
been repaired; `package.legacy-owner-deletion` remains open. The scoped
direct-load product fix passed its rebuilt-ROM S3 proof above.

The latest old-method Ledyba run on ROM3069 took 703.8739 seconds and failed.
It measured the actual wild species165, slot0, full handle131072, PID2283826683.
Spawn Hop completed, but no later Walk/chain did. Other wild actors still moved;
this does not prove a whole-engine freeze. Evidence:
`build/roadmap-ledyba-facing-3069.json`, raw
`build/overworld-artifacts/run-ww2qolnv/1-stdout.log`. Do not rerun this method.

## Shared-tool replacement evidence — 2026-09-06

### D1 resumed through shared tools

- Memory capture tool fault fixed: a real fresh-save snapshot exceeded the
  old65,536-byte row bound (~170KB with141KB terrain), breaking record.start,
  inspect and checkpoint. Records now retain full rows up to1MiB while keeping
  the old117,964,800-byte total window, with counted whole-row eviction.71 host
  checks pass in0.397s. After safely restarting the stopped shared service,
  fresh session-_xyywt37 passed live record.start/inspect/checkpoint at733;
  artifact checkpoint-f67170703ec2.json. No images or ROM edit/build. This fixes
  diagnostic capture, not the reported game freeze.

- Added a bounded `spawn-landing-height` native reader for the exact own
  off-screen target, with surface/refresh return data, before/after native
  positions, two point-only terrain reads and stable native identity. Its21
  host tests include actual ARM declarations/layout and wrong/missing native
  callbacks. Root's combined observer/reposition/terrain/jobs/CLI check passes
  157 tests in3.914s. The new test is in the permanent proof gate. Reader review
  found no concrete blocker against the linked call sites and stock refresh.
  Separate pure surface oracle is in progress; no fresh live calibration
  or surface-legality acceptance yet. No game code or ROM changed. New tool
  source requires fresh calibration before final gameplay acceptance.
  Helper unmounted_witness owns only new devtools_spawn_surface_measurement.py
  and its new tests. Root must review and wire it without changing the existing
  own-site claim: known metatile/surface exclusion and exact native terminal Y
  are distinct from unmodeled solid geometry. Retain the existing same-frame
  terminal-with-unmeasured-successor boundary; do not invent an idle gap.

- Shared job status now names the post-game `acceptance` phase instead of
  advertising more game observation during controller replay. The private core
  is already stopped and proof remains unaccepted until completion. A host RED
  reproduced the stale phase; the unchanged timing check now passes. Review
  also found an acceptance-window cancel race: acknowledged cancel could be
  overwritten by a pass. A separate RED reproduced it; cancel recheck and final
  write/publication now share the status lock.47 jobs/CLI host tests pass in2.717s.
  These are tool checks only; no ROM build or gameplay run for this status edit.

- Repeatdc671f02 completed with passed/acceptedProof true on3075:5002 bound
  frames,577 complete motions,476 eligible moves,25 complete actions,41 intervals,
  zero accepted aborts and zero chain/identity/render/measurement errors.
  WILD165 PID2214427025, handle131072/slot0, map34, epochs4/4/encounter2.
  Execution421.666s + acceptance62.010s =483.676s. No images; owned
  session-hzkyf1cn confirmed stopped. The unchanged repeat supplies the second
  long normal-chain witness. Next: scoped native spawn-height/surface receipts;
  physical spawn legality and unmounted stutter remain open. Helper
  plan_rejection_probe owns observer/new reader tests only; root owns integration.

- Normal6e7e00ff passed with acceptedProof true on3075:5000 bound frames,
  606 complete motions,485 eligible moves,30 complete actions,43 intervals,
  zero accepted aborts and zero chain/identity/render/measurement errors.
  WILD165 PID2258412824, handle131075/slot3, map34, epochs4/4/encounter2.
  Execution421.464s + acceptance60.695s =482.159s. No images; owned
  session-mpg28dzt stopped. Stop boundary credits commit606 only, not the
  just-started WALK successor. This is current normal-chain evidence, not
  terrain permission or unmounted stutter proof. Same unchanged5000-frame
  scenario repeatdc671f02 is now running; source remains frozen.
- Read-only physical-spawn audit confirmed the missing observation. Off-screen
  preparation visits16 tiles through ResolveObjectLandingHeight and takes the
  final object Y. Native RefreshHeight at0x02061070 returns FALSE on a failed
  query or ignore-height path and keeps the old Y; it does not mean unchanged
  height (vanilla unk_0205FD20.s:2445 and2699). Next bounded reader must bind
  final own target, actual QuerySurface result, successful native height query,
  native terrain/model provenance and settled pose to this exact spawn actor.
  FALSE surface query alone is not land proof. No image-based classification
  and no all-actor terrain scans. No reader/product changes during live repeat.

- Current-ROM control4cde86f4 completed: passed/acceptedProof true,1013 bound
  frames,149.428s execution+15.713s acceptance=165.141s. Native WILD165 PID389344233,
  handle131072/slot0, epochs4/4/encounter2, map34. Positive baseline has95 motions
  and82 eligible moves; controlled REPOSITION render stall is detected at2050,
  missing active identity at2051. No images (`visualArtifact:null`); cleanup
  completed and session-n4y672j2 is stopped. Normal chain proof is separate:
  registered unchanged6e7e00ff is now running. Read its own result/identity,
  not the start receipt's previous stopped session field.

- Managed build1788728599 passes in72.411s; full receipt
  `build/roadmap-d1-chain-fit-1788728599.json`. Wild managed object text44922,
  data40/BSS32; resident occupancy216 bytes. All fixed-region/package checks
  pass. test.nds and Delta test3075.nds share SHA79e64530ce843d8d14f2a606d0a39cc124f67b4734d17b6a8a98e776f9b3bc59.
  Source SAV/DSV hashes are unchanged. Open-after-build stayed false. Root
  additionally passed doctor and current-ROM occupancy3-wrapper S2 check.
  Fresh registered control4cde86f4 is in preflight; normal chain and stutter
  claims stay open. No automatic images, no commit/push or branch change.

- Observer integration RED found SIDE_TILE3 and OCCUPIED5 admission results
  rejected despite the product's documented post-preparation PROFILE8 mapping.
  Corrected that finite map; all13 native decisions, wrong mappings and unknown
  values are checked. Root rerun:72 observer tests pass in0.618s. Native nested
  decisions remain in memory data; none earns a structural-abort exception.
- Unmounted route audit found no valid completed Center exit in retained
  `run-jkc73q88` memory data (old run reached map69(8,18), then stopped at8,19).
  No complete route was invented or activated. After packaging, use fresh
  normal input to reach nurse69(8,13), verify every route endpoint, start memory
  capture before one A press, then neutral8-frame blocks capped at240frames.
  Stop on unknown dialogue ownership. Missing tool: completed-frame script/
  task/window-owned dialogue state, native printer page-wait2/3, menu state4,
  WaitButton callback and fresh healed-party identity/HP after control return.
  Anchors are vanilla scrcmd_c.c, render_text.c and overlay_27.s, not copied
  runtime addresses. This remains setup work, not unmounted-stutter acceptance.

- Bounded size cut is frozen: local Wild text44646 ->44586 (60 bytes saved),
  data40/BSS32 unchanged. Shared readiness checks now have one body; the chain
  result supplies its own started outcome. No guard, memory region or observer
  ABI changed.18 actual-C chain cases and8 rejected mutants pass; root reran
  motion-start16 cases/205 assertions and flat-clearance11 cases/54 assertions,
  including their rejection controls. The managed compiler has not retried;
  about248 bytes still need space. Next: inspect an existing resident helper
  code home and exact caller ABI before moving a bounded helper, then package.
- Active fit slice: native occupancy queries used by Wild/Follower landing and
  spawn adapters. Existing overlay153 Wild-owned tail ends at0x023C0184 and
  has636 reserved bytes left. Helper owns parity-first extraction of the three
  scan bodies and shared visual-ID filter; original Wild wrapper signatures,
  player shortcuts, ignored pointer and performance count stay unchanged.
  Root owns build/feature-gate wiring and integration. No new state, owner or
  memory region. Managed retry waits for measured fit and exact Thumb/package
  guards. Observer integration also checks every post-preparation reason2..5
  maps to PROFILE8, matching the actual rejected-start contract.
- Occupancy fit measurement with identical Wild compiler flags:
  text44586 ->44238 (348 bytes saved), resident helper216 bytes within the
  existing636-byte tail. This predicts about100 bytes spare after the prior
  60-byte cut; only the managed link can confirm it. The earlier44378 figure
  used different flags and is not the comparison baseline. No extra direction
  helper move is needed. Product subset frozen; original/post-move matrix
  passes2175 assertions with followers enabled and again disabled. Package
  integration must also replace the old spawn-only resident extent check with
  the two exact named functions, without changing the preserved code prefix.
- Occupancy integration frozen and reviewed: original three wrapper symbols
  have no clones in the exact-flags object; callers reach them and each uses
  one typed Thumb BL. Root passes5 occupancy tests (including HOST_CC isolation),
  4 resident-tail tests, chain3 tests, observer72 and identity21.43 scenarios
  validate. The tail gate now rejects28 wrong-copy cases for both exact hosted
  functions and retains the old prefix hash/call inventory. Added the package
  guard to Makefile and sealed its source/dependency/object. The reviewed
  Makefile hash change is exactly that one added command (removing only it
  reproduces the prior c7d207b8 pin). Publication checks now name the capture
  command instead of using its old list index, retaining failure controls.
  Full source contract check is running before the managed retry.

- Typed-chain integration: full host gate934 tests passes in115.396s. The first
  run failed four stale-fixture checks: old16-frame expectation and a replay
  stub missing `uses_raw_records`. Fixed the fixtures, kept the5000-frame rule,
  passed21 focused checks, then reran the full gate.43 scenarios validate.
  Chain17 actual-C cases and8 rejected mutants pass, including actual landing
  classification. Observer70 host checks and abort-oracle111 companion tests
  pass. Old e2ed/639667 streams still fail2/4 and3/4 with zero accepted aborts.
  No images or fresh game run supplied this evidence.
- Managed build1788726423 stopped after5.372s, code2: Wild link tried to move
  the counter from`0x023D810C` back to`0x023D7FD8` (308 bytes over). Full result:
  `build/roadmap-d1-chain-fit-1788726423.json`. No new ROM/Delta copy or open.
  Workshop was restarted only after owned test/session were terminal; health
  is current. Utilities checkboxes were read through accessibility text, all
  off; `runAfter:false` preserved. Source helper now measures mechanical
  outlining/deduplication within the unchanged memory reservation. This is a
  code-size task, not an external blocker or permission to weaken tests.

- Checked-loop efficiency cut:66 focused host checks pass in6.509s. A new RED
  demonstrated that endpoint-only progress checks could miss a stall before
  later movement in the same chunk. Progress now runs per sample on both
  standard and raw-cadence paths, with each step capped at the earliest
  watchdog deadline. Observe-phase measurement waits batch up to8 frames only
  below the required bound-frame floor, then stop at exact single frames.
  The17-frame fixture uses8+8+1 and retains all17 samples; the240-frame stall
  uses30 calls rather than240. Raw-path control fails at15 rather than being
  rescued by movement16. No live wall-time gain claimed yet. No new ROM/core
  run; session-u9ytyfcz remains stopped. Typed chain fix and matching observer/
  oracle integration are active on separate owned files; freeze before build.

- Shared cadence integration completed: typed `unmounted-cadence-v1` with
  sealed setupTransitions, one raw-record path in live jobs and replay,
  per-frame generic checks, no future-frame predicate credit and exact paired
  follower rebind. Service loading previously kept stale field-owned data and
  the memory ring rejected explicit no-field rows. Both tool faults now have
  RED/GREEN tests and fixes; absent rows retain clocks/errors, never actors or
  motion credit.154 affected host tests passed in20.939s; root44 focused tests
  passed in4.911s. The new integration test is in the permanent host gate.
  Route/control recipes and registry activation remain missing, not accepted.
- Current landing reader control `test-ea5ab8348f904f5e8bda65092f037f8b` is
  accepted on3074:895 bound frames/157.465s; owned session-6ufa7_sf stopped.
  It independently retains WILD165 Lv4/PID4221396726, handle131072/slot0,
  commit23:211 exhausted initial searches from1528 through1947. Every candidate
  is rejected by the actual native terrain matcher: `(562,373)`, `(566,373)`,
  `(562,377)` have behavior6 (stock HEADBUTT); `(566,377)` has behavior16
  (stock WATER_RIVER), all with allowed mask1. This is structural rejection,
  not inferred occupancy or an image judgment. This other actor is diagnostic
  evidence, not the control's bound proof subject.
- Unchanged normal scenario `test-0658fefe645e4fe0b277ede606329310` completed
  and was accepted at5000 bound frames. WILD165/PID3619368701, handle65541/slot5,
  field epoch4/map generation4/encounter generation1 retained594 completed
  motions and505 eligible moves. Execution533.378s plus acceptance58.180s
  totals591.558s; memory stream172800767 bytes. Owned session-u9ytyfcz stopped.
  No partial exhausted continuation occurred in this run. This single pass
  does not resolve the earlier two partial-action REDs, the structural first-
  attempt stall, or the new fast policy RED. No game code or ROM changed.
  Review confirms the needed split: temporary occupancy/reservation retains
  grid/count and retries; only fully proved structural exhaustion may abort;
  missing data cannot justify abort. Keep four real segments for completion.
- Build preparation only: current Wild ELF text ends at0x023D7FD8, exactly
  its0xB000 text limit; BSS ends0x023D7FF8 with8 bytes to the overlay end.
  A typed landing/result fix must fit the actual package budget. Do not use a
  shared global reason byte or silently grow the memory placement to avoid it.

- Landing-stage probe added: five scoped native hooks retain up to two surface
  hits, one terrain permission and one occupancy return per candidate, with
  no additional manager scan.61 focused observer/ABI host checks passed in
  0.455s. Live calibration remains pending while shared cadence integration
  is being edited; no source changes during an accepted run.
- New policy regression `ChainActionLifecycleTests.test_temporary_blocker_preserves_selected_continuation`
  fails against the current real C continuation body: one blocked tick clears
  `chainStepsRemaining` before the same landing becomes available next tick.
  This is an intentional S1 RED, not native terrain/occupancy proof. The old
  structural-block fixture and temporary-block fixture currently share the
  same BOOL seam, which is the missing distinction to implement after the
  native occupied-candidate witness. Product source remains unchanged.

- Native plan diagnostics are now implemented and live-calibrated. A scoped
  task6 hook retains the actual48-byte PLAN_HOP call, input/output trajectory
  and typed return inside one chain start. Missing/pending/rejected plans
  cannot become accepted requests. Actual-C ABI/field-offset controls and
  combined99 host checks passed in5.965s;43 scenario contracts and doctor pass.
  Current control `test-dbddee899aa84b39b4b7a0d53c1bb01b` is accepted on3074:
  738 subject frames/98.413s, owned session-uxmzbq9z stopped.
- Unchanged normal witness `test-639667131afe4f7695462e6222d88945` is terminal
  failed, not accepted:2887 subject frames/255.611s, session-30oiirf0 stopped.
  WILD165 Lv2/PID3302762302, handle131072/slot0, field epoch4/map generation4/
  encounter generation2 completed3/4 legs selected at3936. Its path was
  `(550,355) -> (548,357) -> (550,355) -> (552,357)`. At3960 all four next
  landing checks reject, including return to `(550,355)`; no prepared start
  or Hop plan runs. Ordinary Walk resumes3960 and checker fails3968. No
  rejected Hop-plan decision occurs anywhere in this run. The3959 snapshot
  has grid byte154/remaining162, consistent with the third segment; ground
  occupancy uses current tiles only. No other tracked actor is at the return
  tile at3960, but that does not exclude stock objects, surface or grid checks.
  Follow-up checks the preceding frame rather than only the endpoint: other
  Ledyba handle131076/slot4 has native tile `(550,355)` at3959 while its logical
  target is already `(549,355)`. At3960 its native tile becomes `(549,355)`.
  This is consistent with a real blocker leaving later in the same update,
  not a bad grid or self-previous-tile check. The occupancy callback result is
  still needed to prove which rejection happened at the selected actor's call.
  Next missing observation is the landing rejection stage, not more blind
  retries of the same boolean probe. Product source unchanged; no image used.
- Parallel unmounted-meter work adds opt-in, bounded setup transition specs
  to `devtools_cadence_measurement.py`: exact action/departure map/tile and
  live native task, exact settled arrival, complete clocks, and1–600-frame
  bound. Missing-field frames retain errors and earn no route/actor/motion
  credit. Default absence still fails.21 host tests passed in8.698s at root.
  This meter is not connected to jobs/replay yet and has no executable route
  recipe. Remaining wiring: typed sealed transition input, one whole-record
  path shared by live/replay before predicates, exact controller checks and
  the normal healing/selection route. No runtime-ready or stutter-fix claim.

- Fresh calibration `test-5e31ff3c7e954abfb8300c641b3e0137` completed with
  `passed:true`, `acceptedProof:true`,749 subject frames/129.384s. The permanent
  normal run `test-e2edfd258b634f88a6771f110daa89ec` then failed at2781 subject
  frames/260.957s: selected WILD165 Lv3, PID2478425749, handle65541/slot5,
  field epoch4/map generation4/encounter generation1 completed2/4 legs of
  the action selected at3813; ordinary movement resumed3829 and the checker
  failed at3837. These are current terminal manifests, not replay results.
- Native data distinguishes this failure from the earlier pre-request failure:
  at3829 all four landing checks reject and no prepared start runs. The second
  leg returned from `(559,373)` to `(561,375)` at3821. In the coherent3829
  sample, another live Ledyba (handle262147/slot3) has both its logical and
  native current tile at `(559,373)`. The ground occupancy helper at11369
  compares current coordinates only; it does not check previous coordinates.
  Thus this return tile is not blocked by the selected actor's own previous
  tile. The other three rejection reasons are not yet recorded. A physically
  blocked action must not be used as proof of the separate prepared-start
  fault or as permission to remove collision checks. Product source unchanged.
  Next tool work: bounded actual PLAN_HOP decision within the existing chain
  start probe; no screenshots, broad memory trace, or second driver.

- Longer run `test-9d5b13df7d1e4454be995c4cb5cd7660` is **canceled, not
  accepted proof**:6126 bound-subject frames/443.887s. Source was frozen for
  its full run; owned session-tqo4379r is confirmed stopped. WILD165 Lv4,
  PID4268875299/fullhandle131072, has a native prepared start rejection at
  frame2125 after the landing check accepted `(557,402)`. No motion request
  occurred. Its selected action at2109 completed only2/4 legs, then ordinary
  Walk resumed at2125. A later action completed only1/4. These permanent errors
  prevented readiness but were not yet fail-fast; root stopped the run after
  reading the exact native stage data, not images.
- The same run independently retains another actual WILD165 Lv3,
  PID952225759/fullhandle131076:2371 authenticated `landing-search-exhausted`
  attempts from frame2415 through7154, with commit81 unchanged. Its four
  candidates `(552,373)`, `(556,373)`, `(552,377)`, `(556,377)` all rejected
  around `(554,375)`, matching the earlier stall's location. This actor was not
  the scenario's bound subject: retain this as specific native diagnosis, not
  borrowed selected-actor proof or a cleared failure.
- Tool follow-up RED: a selected action with2 legs then an eligible ordinary
  Walk left `failures` empty. `reposition-action-truncated` now fails as soon
  as that normal move fully returns. Review excluded spawn and stop/turn skid
  from this irreversible-resume rule; a deferred action may survive those.
  Host groups119 and final71 checks passed (overlapping scopes). Retained
  prefix replay first rejects at2133 instead of waiting through7154, retaining
  actual2/expected4 and decision/resume frames. Replay is diagnostic only;
  obtain a fresh permanent symptom RED before editing product code.

- Current continuation strengthens the existing normal S4 witness to5000
  continuous bound-subject frames without changing its six claims or normal
  setup. It keeps the single measurement wait and240-frame motion watchdog;
  a global frame wait cannot substitute. Total bounds are12000 frames/900s.
  Two host REDs demonstrated early completion below the floor and acceptance
  of15 later eligible moves with no chain decision after three good actions.
  The tool fixes reject both. Later identity/render/trace/frame faults remain
  checked,14-move tails and delayed settling remain distinct, and previously
  ready measurements still stop at240 stationary frames despite other actors.
- Added bounded native `chain-reposition-attempt` diagnostics (at most8 landing
  checks,1 prepared start,1 typed motion request), authenticated current caller
  and actor/world identity, with two full manager reads per returned attempt.
  Missing requests never become accepted decision0. These stage records are
  not physical-terrain or completed-motion proof. Initial missing-hook host
  cases failed; callback/ABI/mismatched-identity cases pass.
- Result replay now avoids the controller's extra copy of untouched frames;
  fault-mutated data are still isolated. The actual evaluator, all six negative
  controls, artifact/source freshness and retained samples are unchanged.
  Root ran focused host groups of133 tests (8.325s) and63 tests (31.795s), both
  passing. Doctor and43 scenario contracts pass. New controls are registered
  in the permanent host suite. No product edit or new ROM build in this slice.
- Workshop was safely restarted from stopped session/session-g1kdlncn and no
  running build. Live calibration
  `test-cfd89a64f63d44beb971a9abc28c3965` is accepted on3074:810 subject frames,
  89.765s execution +8.043s acceptance =97.808s. Baseline WILD165/PID2145230270,
  fullhandle131072, completed73 motions/60 eligible moves and its own spawn;
  native faults were detected and owned session-cei4xsjc stopped. Stage records
  retain real failed landing candidates followed by accepted decision0 starts.
  Current longer normal witness is `test-9d5b13df7d1e4454be995c4cb5cd7660`;
  source remains frozen. Read its terminal manifest. Image/video
  capture remains off; stale PNG proof wording was removed from the active
  Ledyba scenario and recipe.
- Retained replay benchmark `build/controller-replay-copy-retained-benchmark.json`
  compares both normal/control baselines and all8 required negative checks:
  mean10.60s eager versus7.13s copy-on-write (32.7%,3.47s saved). All complete
  result dictionaries match; source freshness and stream hashes are unchanged.
  This is replay timing only, not an end-to-end speed promise or new ROM proof.

- ROM3074 adds only the off-screen origin bound to product code:
  `visibleTravel >= OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE` rejects a start on
  or inside the visible edge. Independent source review found no blocker.
  Permanent actual-C geometry checks cover89,236 cases/649,081 checks and
  three wrong-code controls in0.461s. The old-guard mutant fails the exact
  live case; it is explicitly not called a pre-edit host run. Pre-edit native
  RED remains `test-6ccb5b1799524f29a066f54f748c2dd9`. Artifacts:
  `build/roadmap-d1-spawn-hop-origin-host-green.log` and
  `build/roadmap-d1-spawn-hop-origin-old-guard-mutant-red.log`.
- Managed V2 build3074 succeeded in54.333s, with package/memory gates passing,
  matching Delta SHA-256 and unchanged source save hashes. Open-after-build
  remained false. Receipt: `build/roadmap-d1-spawn-origin-build-result.json`.
  Twelve focused geometry/POOL checks pass; final geometry mutant checks are
  registered in the host suite. Doctor,43-scenario validation and diff checks
  pass. No commit, push, merge or branch change occurred.
- Unchanged live control `test-823043bfa01b4ce3a42f94a587ad4686` is accepted
  on3074:960 subject frames,104.144s execution +12.295s acceptance =116.438s.
  WILD165 Lv2/PID2981076890 spawned from `(556,390)` to its own `(556,374)`
  with player `(550,382)`; its baseline completed82 motions/69 eligible moves
  and three full four-leg actions. Both native faults and exact cleanup pass.
  Owned `session-dolj2bfh` is stopped; no images were produced.
- Normal S4 `test-310549057ca34226a2b203cd3378828b` is accepted on3074:
  593 observed frames,58 motions/45 eligible moves, three complete actions,
  no measured errors. PID3973441390 spawned `(552,390)`→`(552,374)` with
  player `(550,382)`. Runtime92.410s +acceptance20.554s =112.964s.
  Unchanged repeat `test-4a6d049d227443b5a824810b1f9fbdfa` is accepted:
  804 observed frames,80 motions/67 eligible moves, three complete actions,
  no measured errors. PID2150819510 spawned `(560,388)`→`(560,372)` with
  player `(552,376)`, exercising target X at the same inclusive8-tile edge
  class as the RED. Runtime106.989s +acceptance22.797s =129.787s. Owned
  `session-cw94nwc8` and `session-g1kdlncn` are stopped. No image/video proof.
  These passes support the origin fix, not the untouched pending-action stall.
  Next use a bounded longer witness and aggregate native landing/start/request
  results; do not spend more boots repeating the same short pass. Acceptance
  replay now costs20–23s and is a measured tool-efficiency target, not a reason
  to omit its negative controls or native samples.

- Current retry-reader sources replay retained normal memory data
  `test-c35e2fc1197949c192a27c2d01a7d0c6` successfully at894 observed frames;
  diagnostic replay is not fresh acceptance. Fresh control run
  `test-6ccb5b1799524f29a066f54f748c2dd9` then fails at frame1028/44.537s
  during normal setup, before any fault injection. WILD165 Lv2, fullhandle
  131072, PID3603351161: native spawn input/final target `(558,376)`, actual
  origin `(542,376)`, player at entry `(550,381)`, map34. Origin lies inside
  the inclusive8x6 visible range. Exact native startup and Hop receipts agree;
  no images exist or were used. Own `session-ncjq0k38` is stopped. This repeats
  the earlier origin fault with new exact evidence. Source inspection finds
  `PrepareSpawnHopStart` admits visibleTravel16 for a16-tile hop, starting on
  the visible edge. Root owns the scoped guard; helper owns permanent actual-C
  geometry regression. Keep destination, distance, rank/tie order and profile
  unchanged; distinguish this prerequisite spawn fault from the later stall.

- Retry memory reader integrated: the existing authenticated Walk-policy hook
  now retains operations9–13 with raw request/response, actual return0/1 and
  same public subject. Installed-hook RED dropped those calls. GREEN77 focused
  observer/meter/contract checks include real installed callbacks, ARM header
  anchors, wrong subject/profile/packet controls and rejection of a retry that
  would bridge an earlier RESET to a later lane change. Retry receipts add no
  motion/chance/completion credit. No new hook, driver, product edit or live run.
  Independent review found no blocker. Workshop restarted with no live session,
  test or build; all tool files are released. Next: fresh memory-only runtime
  evidence with the corrected watchdog, then exact landing/request returns if
  the pending action keeps retrying. Prior images are not part of this diagnosis.

- Follow-up image-default audit found a remaining Workshop UI path: manual
  commands and the play timer automatically requested screenshots, even though
  checked jobs did not. Removed every implicit UI capture and kept only the
  explicit Capture button. Native memory data controls now explain that they
  save values/events, not images or video. Actual JavaScript/DOM regressions
  first failed on Start and the play timer; all26 UI/HTTP tests then passed in
  1.736s, with no emulator or image output. The job failure
  `test-ab296655bd1542a99f7bb36a12c48bf6` contains only JSON/JSONL files; its
  stall diagnosis came from native position/commit data, not image review.
- All43 shipped scenarios now set capture to `none` (41 old metadata settings
  corrected); the catalog regression failed41 cases before the change and
  passes afterward. Frozen historical contracts remain unchanged. The scenario
  contract/job group passes73 checks in2.051s and43 scenarios validate. These
  metadata changes do not alter behavior expectations, thresholds or recipes.
  AGENTS and canonical guides require explicit user image capture, remove it
  from first-use steps and distinguish memory data from video in reports.
- Pending-action source investigation distinguishes first and later failures:
  `RunChainReposition` merges no legal landing and rejected motion admission
  into FALSE. First-leg handling puts the action back forever; later handling
  clears its remaining/grid state. No product edit yet. After exact live RED,
  keep temporary admission retries distinct from a completed blocked search;
  rejected start must also restore pending direction/distance. Native named
  landing, prepared-start and request-decision call seams exist in3073 and
  must be paired with actor/world/call context, not hardcoded old addresses.
  The physical surface/height reason remains unknown. Continue this diagnosis
  after the current no-image default and retry-observer checks are integrated.

- Screenshots are no longer proof at any level. AGENTS, all three local test
  skills, feature recipes and canonical verification now require checked native
  observations. Jobs no longer capture images automatically; image transport
  cannot alter a result. Positive and wrong-native-data controls cover the gate.
- Added exact-point native terrain reads through `owctl dev terrain --x X --z Z
  --radius 0 --json`, including rolling neighbor blocks, actual loaded-count
  bounds, loader-in-progress rejection and stable provenance. Live3073 reads
  covered current `(585,406)`, neighbor `(575,406)`, Route30 `(558,373)` and
  unloaded `(0,0)` without images. The neighbor reported collision; unloaded
  remained unknown. These are diagnostic tile reads, not same-actor landing,
  physical surface height or later-mobility proof. Receipts:
  `build/roadmap-d1-memory-point-*.json`. The tree report remains open.
- Checked streams omit duplicate endpoint data and unnecessary endpoint scans,
  not frames or native checks. Retained-stream comparison reduced94,137,478
  bytes to30,255,738 (67.86%) with all1199 samples,3597 events and2870 native
  intervals preserved. Baseline and six negative-control replay results match
  exactly. JSON encode/decode were faster; replay time was unchanged. Do not
  call this a measured emulator speed gain. Manifests now include acceptance
  time in elapsed time; prior89.348s normal-run timing excluded that cost.
- Before the watchdog correction, the full host gate passed833 tests in77.999s
  (`build/roadmap-d1-memory-proof-final-host.log`);43 scenarios validate,
  retirement guard passes291 files and three local skills validate. ROM3073
  is unchanged. Live no-image calibration
  `test-8749f143d13c42788d470b7186b0da42` accepted800 subject frames:
  81.883s execution +8.816s acceptance =90.700s end to end. Its owned session
  `session-rsst5u6o` is stopped.
- The subsequent normal S4 `test-ab296655bd1542a99f7bb36a12c48bf6` is
  canceled, not passed or accepted. WILD165, slot0/fullhandle131072,
  PID3970227773, level3 remained at `(554,375)`, commit55 from frame1638
  through5245. Native terminal/control-return events completed the prior
  motion; policy action0x85 remained pending while other actors moved. Root
  canceled after251.893s and stopped owned `session-ejky2efw`. This is an
  observed selected-actor stall, not a whole-engine freeze or accepted RED
  product-fix witness. The watchdog counted changing facing/flags as progress;
  its host regression and exact retained replay now pass review. The public
  policy observer also omits retry operations above4, so retries versus target
  rejection remain a readback gap. No product patch was made from this guess.
- Watchdog correction:21 focused job tests pass, including a240-frame exact
  selected-actor stop despite changing facing/offsets and another moving actor,
  plus400 advancing travel frames that must not time out. Independent review
  found no blocker. Replay with the real bound Ledyba meter retains4512 complete
  frames/4209 observed frames and unchanged stream SHA-256
  `21cb5583b3d45db0c0db4f54ba2887bc29a396ee255acdbf4ef60970c4bd307f`.
  Old key reset724 times after1638 (722 face-offset changes), never stopping;
  corrected key stops at1878, exactly240 frames after progress stopped,
  avoiding3367 later recorded frames. This is a measured tool improvement,
  not new live acceptance or a fix for the pending-action game fault.
- Final targeted integration after the watchdog change passes194 checks in
  30.141s across jobs, watchdog, terrain, proof and runtime. All43 scenarios
  validate and `git diff --check` passes. Workshop was restarted only after its
  owned session stopped and the build was idle; current instance
  `68dcc7a8552f414fabb1d32288ca3e48` reports `restartRequired:false`.
  No ROM rebuild was needed for these host-only changes. Next bounded task:
  retain authenticated chain retry operations9–13, then use the permanent
  normal Ledyba witness to distinguish retry rejection from a skipped update.

- ROM3073 contains the scoped legacy POOL reset: later POOL clears earlier
  destination rules instead of selecting all ordinary surfaces. Modern masks,
  explicit non-POOL choices and headbutt selection keep their existing rules.
  Workshop keeps the explicit legacy reset through edit/copy. Independent
  review found no blocker;11 actual-resolver/editor regressions and seven C
  golden vectors pass. Full host gate:800 tests in65.394s
  (`build/roadmap-d1-pool-fix-full-host.log`). V2 build took50s, memory/package
  checks and doctor passed,43 scenarios validate, and the Delta copy hash
  matches. Open-after-build stayed off; source saves are unchanged.
- Current live calibration `test-9ba55b90f0624810aab297c890991f4c` is accepted
  S3 on3073:832 subject frames/77.44s, both native faults and exact cleanup.
  The unchanged POOL witness passed twice: first
  `test-06fc0d8569be4c22bf2fcf0f6c76f881`,146 frames/59.118s, PID4290665549,
  own incoming/final/landing site `(557,376)`; then
  `test-b272543d47974d8c8e5174573b3e78ec`,136 frames/58.207s, PID2799994686,
  own site `(558,373)`. Both are accepted S3 with complete spawn Hops and no
  measured errors. Final images were viewed. Leaf overlap remains visible;
  neither test proves physical surface height or later mobility. Keep the
  tree report open. The selected actor must not be replaced by another
  pictured Ledyba when checking this remaining claim.
- Fresh normal chain `test-c35e2fc1197949c192a27c2d01a7d0c6` is accepted S4
  on3073:894 subject frames/89.348s,895 identity samples, seven chain intervals,
  93 complete motions and three complete four-leg actions. No measured chain,
  identity or render errors. Its final image was viewed. All four owned
  private sessions above are stopped; no user's emulator was changed.

- Permanent registered POOL scenario RED on3072:
  `test-da0d95dd30404b31babf4c7438222453`,138 subject frames/59.771s.
  Species165, slot0/full handle131072, PID670203746, level2: original
  Land-pool site `(554,375)` became `(552,375)` in the same native finalizer.
  The actual first Hop completed at the replacement site with all terminal
  events,139 identity samples and no motion/observation errors. The sole
  failure is `pool-destination-replaced`, not an absent actor or setup timeout.
  Its unchanged recipe/measurement is now the pre-fix witness. Source saves
  remain untouched; the owned session `session-qbaty4nw` is stopped.
- Fresh calibration `test-e153c0931c834abe8b6f8d9c9e4f0cc1` failed after
  43.65s at frame1028: level4 Ledyba PID2989285803 chose `(558,373)`, which
  finalization changed to `(558,376)`. Its Hop origin `(542,376)` is inside
  the player's inclusive8x6 visible rectangle at `(550,381)`. This is an
  observed spawn-origin fault, not an accepted calibration; landing was not
  observed because the guard stopped early. Diagnostic pure receipt replay
  also detects the changed site. Keep both issues open, not just the earlier
  chain result. One fresh unchanged calibration
  `test-2769f9dc6ce5476cb708aa441169d877` then passed768 subject frames in
  75.689s and was accepted; its final image was viewed. Host gate passed789
  checks in62.678s and43 scenarios validate on these tool sources.

- New own-POOL witness is registered as `spawn.ledyba-pool-site`, S3,
  requirement `shared.ledyba-pool-site-v1`. It adds no credit to the38 unported
  requirements. Native finalizer input/output pairing is single-use, context-
  bound and byte-exact, including legitimate PID changes and stack buffers.
  Actual ARM public headers anchor offsets and signature; installed callback
  fixtures detect changed sites. The shared measurement reuses the first-Hop
  recorder without claiming three chains. Controller replay rejects missing
  finalization, changed input site, wrong/stale subjects and every missing
  start/terminal meaning, including events during setup before binding.
  Independent review found no blocker. No spawn product fix or live POOL run
  yet. Route30 is authored OnlyLedyba across enabled pools, including Surf;
  land-only expectations would contradict that data. Legacy POOL means keep
  the pool's own chosen position; it is not all-four-surface selection. Even
  coordinate preservation does not prove physical surface legality/mobility.
- On3072, fresh calibration `test-440a55e08894406d81ad95aca4b90d4f`
  passed898 subject frames in85.634s. Normal S4
  `test-c76fe960d4c243c7bdbfc2b397ae0657` passed594 frames/76.422s,
  counts9/13/10/12 and three complete four-leg actions. Unchanged repeat
  `test-35038ea32e0841f09f75f66121d7e07d` passed492 frames/72.828s,
  counts9/13/10 and three complete actions. Both final images were viewed;
  selected-actor trace evidence is not proof that another pictured Ledyba has
  a legal spawn. These passes preceded the new finalizer tool edits, so they
  are not final-source acceptance. Full host gate before those edits passed756
  checks in64.410s. The old pre-fix reset trace still fails at1880 on the same
  three resets under the corrected stop-boundary checker.

- ROM3072 built through V2 in49 seconds, fixed memory/package checks passed,
  and its Delta copy hash matches. Open-after-build remained off; source saves
  are unchanged. `build/roadmap-d1-chain-fix-build-result.json` and
  `build/roadmap-d1-chain-fix-doctor.json` retain the build and preflight.
- Fresh calibration `test-5c18936398bf4ba7bb49288c289045eb` failed at its
  wall limit303.265s/5276 subject frames. The baseline kept requiring an idle
  frame even when each completed motion immediately started its successor.
  The saved stream has46 chain intervals and25 complete four-leg actions;
  its last26th action has only three completed legs and must not pass.
  The scoped meter correction permits only the exact predecessor terminal
  plus sole elapsed-zero successor sample, with full identity, pose, commit
  and start receipt checks. The successor stays unmeasured and uncounted.
  The new fixture failed before the tool edit;44 focused checks pass after it.
  Independent review confirmed the boundary preserves predecessor proof.
  This is a tool failure, not an accepted ROM result. The fresh calibration
  and repeated normal S4 above followed; this failed attempt remains retained.
- The user identified a tree-overlapping Ledyba in the normal S4 final image.
  This is not cleared by the accepted chain measurement. At final frame1544,
  slot4/handle131076, PID1370881495, is still in its spawn Hop (79/106 frames),
  from `(542,378)` toward its own target `(558,378)`. The measured chain subject
  is a different Ledyba: slot0/handle196608, PID4169145579. The saved native
  resolver receipts confirm all three lanes use spawn mask15, explicit
  mask1023, and movement mask1. `Flying insect` explicitly replaces legacy
  destination with POOL; the resolver promotes that to all four ordinary
  spawn surfaces, including canopy. Spawn startup does not use the ordinary
  movement landing filter. This establishes a policy mismatch, not proof of
  this actor's final landing or that all spawn/movement differences are bugs.
  Next: capture this species' actual destination category, loaded tile/surface,
  completed landing and ability to leave; define the intended POOL behavior
  and make a permanent shared-tool scenario fail before a spawn product edit.
  No spawn fix or new ROM test has run for this report. Do not narrow the
  profile silently or call own-target equality a terrain-legality check.
- The final host gate for the pending rejected-direction change passed754
  tests in62.883 seconds (`build/roadmap-d1-rejected-direction-full-host.log`).
  At that checkpoint the product change was unbuilt. ROM3072 and its accepted
  runs above supersede that build state, not the original failure evidence.
- The forbidden-direction product fix is one early return before policy
  initialization: it leaves genuine NONE handling unchanged. Actual compiled
  policy/Wild-role tests first reproduced chain10→0, then passed146 C checks
  plus four rejected old/wrong-code variants after the fix. Allowed lane
  changes, stop/defer/skid and Wild fallback rejection are covered. The host
  gate now includes this permanent test. Independent review found no product
  blocker. The observer also keeps ignored/no-reset INPUT out of lane-handoff
  history; its paired reset control failed before correction.46 focused checks
  pass, and replay of the immutable pre-fix game stream still fails on the same
  three resets at1880. Normal scenario, claims and thresholds are unchanged.
  Next: frozen host gate, build through V2 with open-after-build still off,
  then fresh live calibration and repeated normal S4 on that new candidate.
- After the checker fixes, control `test-7d46d3ded7424df0abd2377c60519674`
  was accepted at S3 (1883 frames,129.979 seconds). Normal S4
  `test-1c0326f5a4054fc2a718182b7787b463` was accepted (507 frames,
  78.392 seconds): own native landing `(549,376)`, normal chains9/13/10,
  three complete pause actions, zero measured identity/chain/render errors.
  Both final images were inspected. Full host gate passed749 checks in58.629
  seconds. Source saves remain unchanged.
- The unchanged S4 repeat `test-00230788a2fc4ac1bd6e85b6312992db`
  failed after845 subject frames/94.585 seconds. The early-stop check caught
  three same-lane INPUT resets at frame1880, directions0/3/2, commit88.
  Actual product cause: `ReduceInput` converts forbidden cardinal directions
  for diagonal-only Ledyba into NONE, then the stop branch clears chain state.
  The final Wild NONE fallback is already rejected by the real role controller
  before policy entry, so do not broaden this into stop/skid ownership changes.
  Affected contract: rejected direction candidates must not mutate policy or
  chain progress; the shared reducer serves Wild and Mounted callers. Root owns
  the product fix; audit_delivery_flow owns a compiled production-boundary host
  test. Keep the current live checker/recipe unchanged. Runtime overlay156 core
  has28 bytes free before its0xB50 fixed limit; use early rejection without
  ABI/storage changes, then prove packaging in the next build. Evidence:
  `build/roadmap-d1-reset-ledyba-repeat-result.json`. This failure keeps Ledyba
  open despite the earlier accepted run.
- Shared field-absence observation is implemented: a null field or uninitialized
  actor system retains its exact completed frame, native cycle and observer
  errors without stale player/actor/party/terrain data. Installed-callback RED
  lost frame5 (`[4,6]`); GREEN retains `[4,5,6]` with two field-present frames.
  Default test evaluation still rejects absence. The explicit cadence setup
  transition allowance and record-level meter integration remain pending.
- Normal Center healing route research found three distinct input states:
  text-printer page waits, overlay27 menu state4 (cursor0=Yes), and final native
  WaitButton callback. The nurse uses `GetMenuChoice`, not `ScrCmd_YesNo`;
  its greeting has two page waits before the choice. Current packaged entries
  were checked against the local vanilla reference. Next shared observation
  seam: exact current script/task/window ownership at completed-frame boundary,
  not guessed A-button delays. Then prove the saved Cyndaquil's same PID and
  restored HP before Y selection. No normal healing route has run yet. Sources:
  `scrcmd_c.c:4981`, `overlay_27.s:5255`, `render_text.c:293`, and
  `scr_seq_0003.s:82` in the read-only reference.
- Normal S4 `test-b55ca1e79c594875bb2c9e8d7166c9dd` failed its300-second
  wall budget after5437 subject frames. It recorded29 complete four-leg pause
  actions, no render or identity errors, and one unexplained reset at frame1225.
  Native receipts show RESET at1225 then INPUT lane0→2 at1226 for the same
  actor/commit. The checker paired only the second reset and incorrectly read
  RESET's zero-filled lane byte as lane0. Pending explicit resets now require
  the next real INPUT transition, with the same subject, commit, eligible count
  and chain boundary and no intervening motion/decision. Unresolved resets
  cannot pass. New controls fail before the correction;41 focused checks pass
  after. Confirmed chain errors now stop immediately. Diagnostic replay of the
  unchanged failed stream reaches ready at3430 sampled frames with14 actions,
  27 intervals and no errors; this is not fresh acceptance. Both private cores
  are stopped. Next: independent review, freeze sources, refresh live control,
  then normal S4. Evidence: `build/roadmap-d1-ledyba-s4-result.json` and
  `build/roadmap-d1-reset-correlation-{red,green}.log`.
- Live control `test-32f566d59e0f4651935e94836566311d` passed and was
  controller-accepted at S3:783 observed Ledyba frames in75.46 seconds, normal
  three-action baseline, two real render-stall samples, actual native ACTIVE
  rejection and exact same-object restoration. The normal S4 above followed
  without source edits and pinned this calibration. This does not clear the
  normal Ledyba or unmounted stutter claims. Evidence:
  `build/roadmap-d1-live-control-accepted.json`.
- Registered live-control run `test-1549b869f96b4352be7b99f4014b10b8`
  reached892 observed Ledyba frames in80.463 seconds. Its normal baseline,
  two native render-stall samples, actual inactive-object rejection and native
  restoration all passed. Controller acceptance correctly failed: the cleanup
  row used the service's UI-merged snapshot rather than its exact fresh worker
  receipt (extra stale terrain/party/screenshot/selector fields). The job now
  writes the exact native snapshot. A real service-merge host control failed
  before the fix;21 job/measurement checks pass after. Diagnostic replay with
  only that row projection corrected passes892 frames and both detections;
  the retained original run remains failed. Its final image was inspected.
  Next: rerun this unchanged registered scenario; no acceptance claimed yet.
- Frozen host integration passed731 checks in58.511 seconds before that narrow
  cleanup-record fix. Scenario validation passed42 contracts; doctor passed;
  the devtools-only retirement guard passed284 files. Both source save hashes
  remain unchanged. No new ROM build was needed for these host-tool changes.
- The user requires each Pokémon to use its own spawn location, not another
  species' destination. The authoring skill and verification contract now say
  this. The normal Hop meter binds raw prepared position to its own startup
  landing target as well as species/PID/current source. A borrowed-position
  control fails before the fix;37 chain/control-measurement checks pass after.
  This is a scenario/checker change, not a gameplay spawn change.
- The two D1 scenarios are now wired to their exact shared adapters and marked
  executable/ported, not accepted. The live-control job freezes its real normal
  baseline, then records actual same-object X/Z stalls and active-bit rejection,
  with a separately labeled zero-frame cleanup readback. Native control checks
  use real byte-memory readers, and its host stream also replays through the
  full shared evaluator. Normal S4 requires that separately rechecked current
  calibration before boot, all original seven measurements, semantic-event
  rejection controls and an owned final PNG. Next: frozen host gate, live
  control, then normal S4; do not mark D1 complete from host fixtures.
- Normal run `test-0b7bea8860ea4629a0dcfeaaa0fe76c2` reached the actual
  newly spawned WILD Ledyba, completed its16-tile spawn Hop and multiple
  four-leg flat skid actions. Root canceled after finding permanent checker
  errors; extra waiting could not fix them. The checker and its synthetic
  fixture both used REPOSITION enum4, but the public game ABI is5. The new
  independent public-header check fails on that old mapping;28 focused checks
  now pass. Replay of the unchanged retained stream reaches ready at1279 total
  sampled frames, with7 valid intervals/3 complete actions and no measured
  errors. This diagnostic replay is NOT a fresh S4 accepted run. Completed
  motion event failures now stop immediately rather than wasting the budget.
- Earlier run `test-dc81855d9fa94eaf8490421fbbf2e076` reached a natural
  Ledyba at312 game frames/31.605 seconds. It stopped because a policy reset
  for an empty slot, before registration in the same frame, was incorrectly
  attributed to the new actor. The meter now starts that actor's policy history
  at its unique native spawn-Hop receipt; a stale call after that boundary
  still fails. Its saved stream confirms the fix up to the retained stop.
- Earlier run `test-6d54a90b1ba4409db6dadd543c166bc9` observed actual natural
  Ledyba preparation and Hop start on Route30, but the checker rejected the
  valid stock DTCM stack pointer0x027E35BC. The full30-byte aligned RAM/stack
  bounds are now tested, including crossing-end failures. Offline replay then
  exposed two legitimate terrain-context requests with one output fingerprint.
  Spawn observations now retain exact nested native resolver calls, bound to
  actual slot/source identity. The meter selects the final observed call, not
  an arbitrary global cached request.43 focused checks and independent review
  pass. No product/ROM bytes changed for these tool fixes.
- Unchanged normal `actor.follower-direct-load` passes on3071 with controller
  `acceptedProof:true`: `test-06beeabda08240fca381ab5d2adc3e8b`,16 frames,
  31.085 seconds. Actual FOLLOWER Mankey56 is attached; native E7 lookup finds
  exactly one eligible object and selects the same pointer. Its screenshot was
  inspected. This closes the narrow direct-load witness, not Ledyba or stutter.
- Normal Ledyba attempt `test-fe6c543e20d0437d86ad49a7074b8187` failed after
  31 game frames/20.172 seconds at route05 settle: the16-entry semantic ring
  lost12 unread records within one completed frame (sequences36–47). Zero
  Ledyba frames were accepted. This is a tool recording fault, not a Ledyba
  behavior failure. The recorder now drains authenticated native writer-return
  bursts into pending host storage and publishes only at queue completion.
  125 focused checks pass, including skipped-callback and multi-ring controls.
  Product/ROM bytes remain3071; unchanged normal route is next.
- The next unchanged Ledyba run, `test-91dc08540069467d89366fcc89e2a1d6`,
  passed the trace-loss point and reached route14/71 frames in21.747 seconds.
  It stopped on a checker error: normal Rattata levels3 and2 resolved to the
  same fingerprint/result, but `_profile` treated their different request bytes
  as changed output. All four live Wild actors were Rattata; Ledyba was not
  present or accepted. Fix the bounded request-to-output observation model,
  preserve exact selected-subject matching, then rerun the unchanged route.
- Build3071 passed in 49 seconds, Workshop job `1788699518.306266`.
  Exact Delta copy hash matches the candidate; opening stayed off and both
  source save hashes remain unchanged. All old153 code bytes stay exact;
  its named new spawn-identity tail is separately verified. Evidence:
  `build/roadmap-d1-build-final-result.json`. Current shared sources are frozen
  for direct-load and then normal Ledyba runs. This is not gameplay proof.
- The normal Ledyba measurement now also binds the native prepared encounter
  to the actual spawn Hop and checks the existing 16-tile approach outside the
  player-centred8×6 rectangle. This is the engine's tile rule, not a pixel
  occlusion claim. Installed callback tests and 49 chain/measurement checks
  pass. S4 and the separate live recorder fault tests still remain open.
- The shared host suite now passes 634 tests in 33.040 seconds
  (`build/roadmap-d1-shared-host-final.log`). New natural party-getter tests
  additionally cover healed HP, max HP, replaced identity and stale receipt
  rejection. Host success is not gameplay acceptance.
- The first rebuild stopped at the pinned Makefile trust check because the
  new package check changed that exact file. Removing only that added line
  reproduced the old trusted hash; the new hash was then recorded. The next
  build compiled but stopped at the old overlay153 extent check. Its newly
  used reserved tail must be explicitly verified, not bypassed. The published
  ROM checkpoint remains 3070 until a full build succeeds.
- Current normal session `session-od5s4138` was stopped after initial inspection.
  A second bounded normal inspection (`build/roadmap-d1-idlookup.json`) proves
  two eligible script2074 objects each for reserved IDs E0, E1 and E7. Stock
  first-ID lookup selects the old object, not the current logical slot pointer.
  Public presentation attachment fails for the saved Mankey and those Wild
  Rattata. The second private core was also stopped.
- Permanent normal scenario `actor.follower-direct-load` failed on ROM3070:
  `test-1c7d603e18344c0d837ce3d182a54c14`, 31.525 seconds. At initial field
  readiness the actual saved FOLLOWER Mankey56 is present but detached, with
  two eligible E7 objects. Its full failure snapshot and screenshot were
  inspected. This is the direct-load attachment witness, not Ledyba chain or
  engine-stutter evidence. No party/spawn/teleport operation was used.
- Two resumed host failures were stale fixtures: flat clearance omitted the
  real BEGIN grid marker; the chain receipt check expected a plan-local
  assignment instead of the actor lifetime increment. Updated fixture and
  check now pass: 11 clearance cases/54 assertions and two bad-planner controls;
  actor receipt rejects nine known-bad source variants. Product code unchanged.
- Walk-pause and Flying-insect S0 failures were stale source extraction/gate
  assumptions. Their checks now use the real definition and complete facing
  gate. Five dedicated checker tests pass; registered in the host suite.
  This repairs source checks only, not reported game behavior.

- Final host suite: 587 tests pass in 27.118 seconds, including the permanent
  retirement guard (`build/devtools-full-host-final.log`). Scenario validation,
  doctor, current 3070 fixture checks and all three skill validators pass.
  Final review found no remaining tool integration blocker. These are host
  and tooling checks, not gameplay behavior proof.
- Final shared scenario `devtools.actor-identity` completed in 32.130 seconds:
  `test-e771aa8409e346e8bf2bb6d35c8d0f12`, `passed:true`,
  `acceptedProof:true`, S3 requirement `shared.actor-identity.prepared-v1`.
  Actual FOLLOWER Mankey species56, PID1923031320, full handle131079 was
  attached and current for 16 consecutive observed frames. The final native
  screenshot was inspected. Evidence:
  `build/devtools-identity-prepared-result-3070.json` and the exact manifest
  under `build/overworld-devtools/test-e771aa8409e346e8bf2bb6d35c8d0f12/`.
  `build/devtools-progress-final.json` and
  `build/devtools-identity-history-final.json` show the current recorded pass
  and the older failed attempt separately. They do not grant new acceptance.
  The private core is stopped, Workshop is current, and both user save hashes
  remain unchanged.
- Every test now saves its attempt source/recipe/fixture identity before
  preflight. Current early failures stay failed; old interrupted attempts are
  stale, unknown older attempts stay visible as unverified, and current
  unfinished attempts still block acceptance without claiming live ownership.
  Progress/history do not launch a game or grant new proof. Final acceptance
  independently checks the saved stream and current inputs.
- Build 3070 passed through Workshop, job `1788686983.1867788`.
  `build/devtools-build-result.json` records it. The Delta ROM hash matches;
  open-after-build stayed off and both source save hashes stayed unchanged.
- Live shared setup/control: all 27 checks pass in
  `build/devtools-shared-session-3070.json`. This verifies actual native party
  reads/edits, real teleport, exact follower/mount/wild Ledyba, bounded stepping,
  retry protection, terrain, capture, recording, reset, recipes and Play/Pause.
  It does not prove Ledyba chain or normal spawn behavior.
- Checked idle smoke `test-b598ea3e393e48f7b786198c75fb2eea` completed 32
  observed frames in 15.738 seconds including boot. It is explicitly diagnostic.
- Missing-actor control `test-523db3371f404dedb9dbd4bf52ab8d65` failed after
  eight game frames with zero subject frames. Its first failure and capture
  are retained. An absent actor cannot pass.
- Cancel control `test-587eae3673264f0499814aaba06e4b81` stopped its owned
  native boot and saved a canceled result in 12.843 seconds overall. Neither
  control grants gameplay acceptance. All three manifests are in
  `build/overworld-devtools/<run-id>/manifest.json`.
- Removed standalone executable files can be recovered from the ignored
  `build/retired-overworld-workflow.VVBOJj/` archive for historical inspection,
  not execution. The permanent retirement check rejects restored drivers,
  imports, dispatch registrations and active instructions. Host/model/package
  and unrelated battle/Summary checks remain supported.
- All 40 prior gameplay requirements remain explicitly pending migration.
  The new prepared identity scenario cannot clear any of them. D1 remains
  open and must resume with a short, symptom-specific shared-tool witness.
- The first registered identity attempt,
  `test-12385ca378f045aaad17b5d15961ef36`, failed direct-load follower setup
  after 49.074 seconds, with zero accepted subject frames. Actual species 56,
  PID1923031320, handle131079, native object36389912 was present in the current
  manager, but its public presentation attachment was false. The decoder and
  C layout agree. Native ID lookup returns the first matching object; an
  earlier same-ID object is a cause candidate, not a proved fact. This game
  setup failure remains open. Its manifest, final capture and full command
  failure are retained under `build/overworld-devtools/<run-id>/`.
  The original actions and assertions are also preserved permanently in
  `tests/overworld/test-recipes/devtools.follower-direct-load.json`. It is an
  unregistered diagnostic reproduction, not accepted gameplay proof.
- The prepared identity tool fixture now explicitly reconstructs the field
  through native teleport to map33 tile(585,405), the setup independently
  verified by the live tool smoke. Its 16-frame exact identity assertions are
  unchanged. This is a declared prepared fixture, not a fix or pass for direct
  save loading. Do not use it to close the failure above.

## Historical resume and tool notes — superseded

The notes below record earlier work, not the current execution workflow.

Active work at that time: D1 normal Ledyba chain/pause and unmounted travel, resumed on
2026-09-06 after the shared [live development tools](devtools.md) were completed.
Root owns integration, product edits, this ledger, and serial build/emulator
access. `audit_delivery_flow` owns the narrow chain-facing guard and regression;
`proof_identity` owns bounded queue-timeout evidence. The independent reviewer
checks both changes. No new broad cutover is active.

- Current doctor and scenario validation pass on 3066:
  `build/roadmap-resume-doctor.json`, `build/roadmap-resume-validation.json`.
  The old Actor/Field/Selector size errors are no longer the next task.
- The unchanged `chain.pause.ledyba-normal-profile` run failed on 3066:
  `build/roadmap-ledyba-resume-3066.json`, receipt
  `build/overworld-runs/chain.pause.ledyba-normal-profile/20260906T072801Z-8d7f86bcab61ec92ce59.json`.
  Actual wild Ledyba (slot 5, PID 3484542379, map 34) spawned normally and made
  20 Walk commits before its first measured chain boundary (expected 8–14).
  The selected action produced one HOP, then no further motion during the
  30000-frame observation. No complete required reposition action was recorded.
  This is not the old no-wander result. Check chain accounting and the action
  handoff separately; neither the counter cause nor motion classification is
  yet proved. Runtime took 698.7 seconds. Product/proof inputs were frozen.
- Root's disposable devtools session `session-jihqzihm` is stopped. Its start receipt is
  `build/roadmap-ledyba-dev-start.json`; it uses copies of the current ROM/save.
  Native teleport reached map 34. The subsequent wild spawn timed out before
  bridge entry (`build/roadmap-ledyba-dev-spawn.json`); no prepared spawn pass is
  claimed. Cleanup: `build/roadmap-ledyba-dev-stop.json`. Preserve this setup
  failure separately from the measured normal-play chain fault.
- Source diagnosis matches the failed action: the first skid requests motion
  before its reposition pending bit exists, so it becomes an ordinary HOP.
  On completion its grid byte `0x9A` is decoded as unsupported pause action 26;
  the continuation is lost. Carver owns the local handoff correction and a
  real-body regression; no speed/profile or counter change is authorized by
  this diagnosis. Mill checks observed reset boundaries: the 20 moves may
  include an interrupted seven-move chain plus a complete thirteen-move chain.
  Do not accept that explanation without the actual reset receipt.
- Normal identity now checks owner map-generation equality. Budget failures
  retain terminal public actor/native context before core cleanup. The attempted
  private policy dump failed the source audit and was removed; no audit exemption
  was added. Both new
  host regressions failed before the observer edit, then all 65 normal-observer
  checks passed (`build/roadmap-observer-host-check.log`). This is observer
  evidence, not a fixed-game pass. An independent reviewer checks these edits
  and both authors' completed changes before the next serial build/live run.
- Chain handoff is source-ready and independently reviewed. Its real-body
  host tests reproduce the old Hop/continuation fault, then pass all nine
  lifecycle cases and four known-bad mutations. Existing motion-start and role
  checks pass. The new lifecycle test is in the normal host proof suite.
- Build `1788681266.052879` produced `test3067.nds` in 52 seconds; SHA-256
  `d00f3f82e47a5b727b09791bc06b336cb14e3d26e1f7ccdbd9027ef65c59e936`.
  Delta copy matches, open-after-build remained off, and both user save hashes
  are unchanged. Build receipt: `build/roadmap-chain-build-status.json`.
  Normal-chain assertions remain 8–14 moves. New public reset/lane receipts
  distinguish interrupted intervals without accepting unexplained resets;
  the old 3066 run remains failed. Next: final host/doctor preflight, normal
  Ledyba proof on 3067, then repeat and the independent unmounted route witness.
- Final preflight passes: all 572 host checks
  (`build/roadmap-chain-proof-host-final.log`), doctor
  (`build/roadmap-chain-doctor-3067.json`), and scenario validation
  (`build/roadmap-chain-validation.json`). Two legacy host mock contexts lacked
  the newly required map-generation field; their schemas were updated without
  changing assertions, and all 17 focused checks pass. Root started
  `chain.pause.ledyba-normal-profile` on 3067 with all product/proof files frozen:
  `build/roadmap-ledyba-fixed-3067.json`. No pass is claimed until its manifest
  and actual motion evidence are reviewed.
- That first 3067 live run failed before actor measurement: the generated debug
  descriptor lacked `state.offsets.mapGeneration`, although the new host mocks
  supplied it. Receipt: `build/roadmap-ledyba-fixed-3067.json` (zero subject
  frames). This is an observer contract failure, not a gameplay pass or new
  game regression. The actual descriptor-writer test now reproduces the gap.
  Supplemental metadata reads the native header's map-generation offset,
  checked by a compile-time `offsetof` assertion; no state/entry layout or
  runtime operation changes. Root is rebuilding the debug contract and rerunning
  host proof before another live attempt. Preserve the failed 3067 receipt.
- Build `1788681892.392591` produced 3068 in 47 seconds; ROM/Delta SHA-256 is
  unchanged from 3067. Debug metadata now publishes the native-checked context
  offset. All 573 host checks pass (`build/roadmap-debug-proof-host-final.log`),
  as do doctor/validation. A prior host HTTP restart test timed out while the
  simultaneous build held the real workspace lock; it passes alone and in the
  full serialized suite. Keep this HTTP suite separate from builds; no timeout
  or assertion was widened. Root started normal Ledyba proof with all code
  frozen: `build/roadmap-ledyba-fixed-3068.json`.
- The 3068 live run remains failed, but proves the handoff diagnosis: naturally
  spawned wild Ledyba completed eight four-leg reposition actions (32 segments,
  eight frames each). All 13 complete measured chains were 8–14 moves. Actual
  public reset/lane receipts separate interrupted chains. Receipt:
  `build/roadmap-ledyba-fixed-3068.json`; raw evidence:
  `build/overworld-artifacts/run-keyrtt2p/1-stdout.log`. Eight facing failures
  remain: the legacy FACE_PLAYER writer overrides active skid facing. Carver
  owns a narrow guard plus real-body regression; normal walking is unchanged.
  After 1834 subject frames the main-queue completion hook stopped for 121
  native cycles. Source review found no normal hook-removal path. This is not
  yet a diagnosed engine deadlock. Root added read-only CPU capture (72 host
  checks and scenario validation pass); Mill adds timeout hook/clock context.
  Next: review the facing fix, build once, repeat the unchanged live witness,
  then run the independent unmounted route. D1 remains open.
- The narrow chain-facing guard is reviewed and source-ready. Its real caller
  and helper reproduce the exact 3068 facing error before the guard, then pass
  111 checks and reject three broken guards. No profile or timing changed.
  The timeout recorder retains the public actor clock, host listener presence,
  boundary bytes, and CPU registers. Stock global clocks remain unavailable:
  their raw reads failed the proof source audit and were removed, not exempted.
  All 580 host checks pass (`build/roadmap-facing-proof-host.log`). Build
  `1788683078.922394` is the next serial candidate; code is frozen for live proof.

Agent workflow integration, 2026-09-06:

- `AGENTS.md` now includes relevant local builds and tests in task scope without
  special keywords. Explicit no-test requests, source/save safety, and accepted
  proof requirements remain in force.
- The permanent entry path is `overworld-devtools` →
  `author-overworld-scenario` → `verify-overworld`. Use only the needed stage.
  Root README, system guides, feature recipes, and roadmap link this path.
- The personal headless skill is a retired, explicit-only redirect. Its old
  playbook is gone; build, battle and merge skills use the current task policy.
  Backend emulator modules remain because devtools and registered proof
  collectors depend on them. No backend migration or gameplay fix is claimed.
- The recording-to-scenario skill names the schema, feature map, measurement
  registry, adapter and proof handoff. A recipe/draft is not auto-promoted.
  Session ownership comes from a start receipt or explicit session-ID handoff;
  status has no owner field. Unknown active sessions remain untouched.
- `build/devtools-workflow-host-check.log`: 563 host checks pass.
  `build/devtools-workflow-scenario-validation.json`: scenario validation passes.
  All seven changed/new skills pass structure validation; 93 local links pass.
  An independent cold-agent check covered Ledyba repair, Mankey setup, recorded
  stutter, occupied sessions and teleport timeout. It found stale readiness and
  direct-runner guidance, now corrected; the repeated check found no remaining
  conflict in those paths. No ROM build or live game run was needed for this
  instruction/help-only change. D1 behavior proof remains open.

Tool checkpoint, 2026-09-06 (not gameplay acceptance):

- UI: `http://127.0.0.1:8766/devtools`; agent entry: `scripts/owctl dev help
  --json`. Shared session control, live inspection, terrain, native setup,
  recording, recipes and unverified drafts are implemented. The full API
  sequence passes twice: `build/devtools-live-check-35-3066.json` and run 36,
  each with 27 checks. They verify the actual Mankey follower and mount,
  wild Ledyba, post-warp party fields, native events, reset, recipe replay,
  and advancing/paused game frames. Source files remain unchanged.
- Final browser testing also created a draft with the exact selected Rattata
  (`session-uuftr6gc/draft-841c9c2ea6f0.json`, under the devtools build directory).
  It remains planned/unverified. Browser Pause was dropped during automatic
  capture (`build/devtools-ui-final-paused.json` still shows `playing:true`);
  the actual-handler regression failed before the bounded control-queue fix.
  Final live UI retest showed Pause queued behind Capture, then held frame
  4138 across delayed reads (`build/devtools-ui-pause-fixed-first.json` and
  `build/devtools-ui-pause-fixed-held.json`). Stop also queued behind Capture
  and stopped only that session at frame 4501
  (`build/devtools-ui-stop-fixed.json`). The visible caption correctly reports
  both newer and older captures relative to the last observed state.
- `build/devtools-host-proof-28.log`: all 563 host checks pass, including error
  cleanup, compact agent output, actor-evidence file round trips, and the actual
  Pause/Stop DOM handlers. Final doctor and all 40 scenario definitions pass
  (`build/devtools-doctor-final2.json`, `build/devtools-scenarios-final2.json`).
- Fresh native party setup passes with PID `3914821014`, both without recording
  (`build/devtools-fresh-pid1-party-07.json`) and with recording
  (`build/devtools-record-party-change-09.json`). Exact species, level, moves,
  HP and status read back from the real party. Source ROM/save copies remain
  unchanged. These are setup diagnostics, not normal-input or movement proof.
- `build/devtools-live-check-25-3066.json` and run 28 prove the post-warp party
  fault: the stock growth helper requests 404 bytes from heap 0, receives NULL,
  and passes that NULL destination to the archive reader. Name loading returns;
  growth loading does not. Earlier IRQ traces did not establish the cause.
  The native call arguments and CreateBox code were correct. No failed setup
  check was removed. Runs 26–27 separately prove that heap 3 cannot allocate
  the 1536-byte private buffer in this fixture.
- The bridge now uses native ARM push/pop and BLX, with separate saved LR and
  caller continuation; it does not restore a guessed stack range. Its private
  heap-11 buffer follows FieldSystem lifetime, not map lifetime. The stock
  ScriptWarp keeps its own heap-11 environment through the same transition;
  Heap_Destroy(11) invalidates the tool buffer before field teardown. Run 30
  then measured a NULL 164-byte move buffer. The finite prepared-only adapter
  now covers the five source-reviewed temporary buffers (growth, moves,
  personal data, stats, mail), with capacity checks and native free receipts.
  Normal gameplay allocation is unchanged. Independent source review found
  no blocker; 98 focused runtime/trace checks pass after the lifecycle fixes.
- `build/devtools-live-check-31-3066.json` passes the unchanged teleport and
  exact post-warp party edit checks. The next follower-selection check fails:
  the menu visits slots 2, 3, 4, 5, 0 but produces no requested subject. This is
  not a spawn pass. Run 33 confirms that Y reaches confirmation and queues
  slot 0, but the release gate stays set while processed keys are zero. Raw
  keys and TaskPoll calls are still needed to classify that pending request;
  neither a lost input nor a game scheduling fault is proved. Run 32 was a
  separate early overlay-observer setup failure, now guarded after load.
  Prepared follower/mount setup now uses the existing fixed native lifecycle
  entries. Run 34 caught early follower return before release settled; runs
  35–36 pass after exact party-slot and settled-release checks. Normal Y
  remains a separate input test; do not mark it fixed by prepared setup.
- A full disk blocked run 21 before boot; host run 20 was incomplete, not a
  runtime failure or pass. Separate byte-checked copy-on-write files now avoid
  duplicate physical ROM storage. Existing complete copies and evidence were
  preserved; only the failed start's incomplete ROM copy was removed.
- Permanent `actor.binding.current-context` measured owner map generation `2`
  versus active actor generation `3` on 3065 before the product edit:
  `build/devtools-binding-red.json`. Wild map re-arm no longer increments the
  generation already issued by the transition owner. Build `1788637861.019608`
  produced `test3066.nds`, SHA-256
  `9bd6db5a64e13816b1066544f657b1dfa50f198fc497f53df1bf3f8b762776ba`;
  its Delta copy matches and was not opened. No movement/profile rule changed.
- The first 3066 run saw matching context and a complete move but was rejected
  for a missing evidence-schema field and changed proof inputs during the run
  (`build/devtools-binding-green-3066.json`). The writer schema now includes
  the existing decoded `presentationState`, with real decode/file/load and
  negative-control tests. With every proof input frozen, the unchanged scenario
  has an accepted pass: [current-context receipt](../../build/overworld-runs/actor.binding.current-context/20260905T221941Z-2359f7aa839f48870d95.json).
  This proves that binding contract, not the open Ledyba or stutter claims.
- Root owns serial emulator/build access. All owned test cores are stopped.
  Source ROM, `test.sav` and `test.dsv` hashes remain unchanged; the Delta copy
  matches. Tools are ready for use, with prepared setup and unverified drafts
  kept separate from accepted gameplay proof. D1 and the behavior bugs remain
  open. No commit, push or local-main update was made for this tool task.

The [slice definitions](roadmap.md#finite-delivery-slices) contain the required
scope and exit evidence. This table records only work state, not a second list
of acceptance rules. `main` is the coordinating agent, not the Git branch.

| ID | Owner | State | Current evidence | Blocker / next action |
| --- | --- | --- | --- | --- |
| D0 | main | verified | [Current host proof receipt](../../build/overworld-runs/D0.proof-workflow/20260905T084811Z-a188ad1f2c6aaf5a2607.json); scenario validation; three skill structure checks; independent failure-path review and regressions | Host workflow only. Recorder/gameplay evidence remains in D1 and the owning behavior slices |
| D1 | root | active | Package3081; fresh calibration6bc019 accepted and readable. Full dd0260 failed at4,499 observed frames with one30.182ms CPU hitch;1,045 player/764 follower completions before stop. Original thresholds retained; owned session closed | Attribute whole-cycle native-thread/process and sampler costs before another full route. Keep466ab/99a5/dd0260 CPU faults open; no waiting-frame credit or relaxed thresholds. Current Ledyba proof remains required |
| D2 | root | active | Lane projection packaged3081 with8 overlay bytes free. Registered3ed02e resolver proof accepted. Current475317ce transfer proof accepted with separate7a3f4d01 reader control: exact same-follower getter/Begin/Owner bytes and final mounted identity | Check remaining original role-projection requirements; prepared caller transfer does not close Select/Hop or all D2 |
| D3 | main | queued | Ledyba pause and engine stutter remain open. Walk/role guard audit is complete: both full host/source scripts pass with 34 added rejection copies and exact linked Delta entries. The moved chain acknowledgement and trace helper are checked at their actual owners | Obtain real symptom failures before gameplay fixes, then run the current exact role/movement scenarios |
| D4 | main | queued | Hop/Teleport/mount changes need current package and runtime proof | Verify the shared boundary and presentation; close only concrete remaining gaps |
| D5 | main | queued | Motion-identity source check fails: the five-argument boundary bridge still reads the current adapter token; callers do not pass the captured motion identity | Finish the explicit receipt cutover with its stale-receipt test; then verify path advances, transition/rebind, population, and relevant long routes |
| D6 | main | queued | Historical structural results do not establish current ownership | Remove only covered legacy paths; recheck exact byte budgets and affected behavior |
| D7 | main | queued | No final candidate or complete current proof set | Freeze the completed candidate; run all required proof and the final roadmap gate |

States: `queued`, `active`, `source-ready`, `verified`, `blocked`. Source-ready
means the scoped code checks pass; it is not runtime completion. Verified means
the slice's stated evidence is current. A blocked row names the exact missing
dependency and the independent work that can continue.

## Update and handoff rules

Earlier serial run: `build/ledyba-flat-successor-3064.json`, normal Ledyba on
the final flat-clearance planner and corrected successor-pose recorder.
The 328-test proof-workflow host run passed; it does not include the known D2
lane-projection RED. Package call audit:
`build/overlay155-flat-planner-call-audit-1788624125.json`. No source seal was
bypassed; the successful V2 build regenerated it and ran the full package gate.

That 3064 run fails after 212 observed Ledyba frames: the real spawn and nine
8-frame Walks complete, then the selected chain sees a one-frame extra wait.
The live witness is `run-b7ovy92n/1-stdout.log`; it identifies the real wild
species 165 and its complete spawn/40-frame pause. ACK changes the model phase
but leaves the public snapshot `COMMIT_PENDING` until the next tick. Actual
policy inspection therefore delays the chain. The production-body regression
now includes policy inspection and chain readiness and fails before the
same-call snapshot fix. The fix is source-ready, pending the next build.

Route control on 3064 reaches the nurse by all 41 normal steps and the expected
warp. The run fails setup because it waits for an interior party-cache refresh
that does not occur. `run-9n3chsx2/1-stdout.log` proves the nurse task returns
control, but the stale cache causes the test to press A again. Correct the
setup to stop dialogue on that real control boundary and require the fresh,
eligible same-party snapshot after leaving. No route frames count as proof.

`build/actor-controls-flat-3064.json` also fails: no natural reposition starts
within its control budget. It has no render-fault pass. Its receipt separately
rejects a proof-input change made during that run (root added read-only healing
diagnostics). Keep the failed receipt; freeze all proof files during future
serial live runs. No observer-control pass is claimed.

Current 3065 evidence:

- `build/ledyba-ack-phase-3065.json`: 30000 observed frames, 678.008880 seconds
  of runtime, spawn passed, no later moves or chain boundaries. Selected Ledyba
  lands at (553,390); player ends setup at (550,381). Source does not support
  dismissing this as a nine-tile AI distance limit. `audit_delivery_flow` owns
  a bounded read-only probe of the native command gate and random candidates.
- `build/route-controls-healing-fixed-3065.json`: dialogue returns control
  after 29 A taps, all 46 ordinary setup steps complete, but the exit warp from
  (8,18) stops at (8,19) in map69 for the 2400-cycle limit. Zero route frames
  are claimed. `proof_identity` investigates exact exit and world-gate state.
- Root owns the serial emulator. No current process is running at this
  checkpoint. Freeze product and proof files during each accepted live run.

Current D1 investigation: `D1.byte-budget`, owner `main`, roles Wild/Follower/
Mounted (shared package). Main owns product files and serial build/emulator
use. `proof_identity` released the package/import guards in
`scripts/verify_pokemon_move_history_capture.py`; `audit_delivery_flow` released
the import, stock movement, route, and frame-boundary investigations.
`verification_contracts` released coherent Ledyba and unmounted route sampling.
`proof_identity` released immutable full command logs and193 passing host checks.
`audit_delivery_flow` released both actual-body spawn-order and motion-start
host regressions. `verification_contracts` independently reviewed the scoped
start-order and spawn-bind changes. `audit_delivery_flow` released the actual
actor commit-counter regression. `proof_identity` released the early read-only
Y-menu query observer and now investigates Cyndaquil eligibility;
`verification_contracts` investigates the zero-elevation-scale Hop contract.
Main owns product
edits, the shared stock-step helper, runtime fixture, source-audit pins, ledger,
and serial live runs.
Helpers edit shared-runtime sections only under the coordinator's explicit
file/section assignment. Only the coordinator edits this ledger.

Current D1 follow-up: the 3062 normal Ledyba run exposes a repeated public
commit number after its spawn. The actor's 32-bit counter now advances after
accepted publication instead of copying the reset per-motion 16-bit counter.
The exact actor-body regression failed before this edit and passes 64 cases,
1613 assertions, and five production-body rejection controls after it. A
read-only skid observer wrap correction also passes its installed-callback
test; it does not change gameplay.

Both 3061 and 3062 have zero-height Ledyba spawn trajectories: this was not
introduced by the engine-command reorder. The resolved Flying insect override
sets elevation arc scaling to zero, which the editor defines as retaining the
base Hop arc. The shared helper incorrectly removed that base too. Its narrow
fix retains base height while leaving all nonzero scales unchanged; the actual
helper plus real motion renderer checks go RED (seven failures) to GREEN,
including five bad-code controls. The unchanged normal spawn scenario remains
the live witness. Actor code stays in its existing `0x3670`-byte reserve;
Behavior's pre-edit text ends at `0x023C3ECE`, below its `0x023C3F18` state
limit. Neither edit adds an ABI field or changes fixed entry placement.

The preboot route observer now captures all six actual party entries. The
unchanged save has Cyndaquil at zero HP, so the game's rejection is correct.
Prepare it by normal Pokémon Center healing in the disposable session and
require fresh observed eligibility afterward. Do not replace the species,
write HP, force a snapshot, or alter the saved fixture. Its original save
hashes remain unchanged. Build `1788621661.9032052` passed and published
`test3063.nds`; root retains serial emulator/build ownership.

The [lane-corrected 3063 run](../../build/ledyba-actor-lane-repeat-3063.json)
then reached a real 8-frame Walk and commit `1 -> 2`. Its recorder rejected a
same-frame successor because the new plan had already replaced elapsed 8 with
elapsed 0. The corrected observer accepts that final observed pose only with
the same full handle, exact target/origin/logical/render alignment, contiguous
complete travel, and one new commit. It never fills missing samples; skipped
pauses still fail. The source-audit and proof host suite passes 327 tests at
this checkpoint. This remains observer proof, not a passing chain run.

Flat Reposition now submits an explicit flat operation and its actual duration
through the unchanged 48-byte plan. The real caller/planner regression goes
RED to GREEN (11 cases, 54 checks, two bad-code controls), including Hop time
0/1 and an auto-lift-enabled profile. Managed build `1788623291.9937458` fails
because task-6 ends at `0x023BE250`, 16 bytes beyond `0x023BE240`.
`verification_contracts` owns a narrow equivalent-code reduction, checked with
the same compiler into temporary output only; it must not move the reserve.
The last published ROM remains 3063. Normal-input healing is now integrated in
both route recipes; its 27 focused host checks pass, but live preparation is
still pending the next sealed build.

Actor's redundant view restores were removed with preservation/mutation host
proof. The unchanged Field terrain algorithm now has a reserved resident code
home; Field retains its mutable state. Selector uses existing core helpers.
The first retry stopped at the pinned `overlays.mk` hash; only that reviewed
hash was updated. Later links found Runtime text 32 bytes beyond its core,
Wild text 676 bytes beyond its slot, and Mount motion 20 bytes beyond its slot.
Wild's four exact stock accessors and five direct Thumb imports now fit; the
linked fixed-call check passes. Runtime's repeated proposal stores now use one
function body and its core fits. Field's linked state ends at `0x023CCFA9`,
below `0x023CCFD8`; the current package confirms its code/state split.
Mount's private functions were placed in its existing slots, then three
unchanged resident targets received Thumb metadata to remove veneers. Actor's
explicit-outline experiment increased size and was removed; removing the
unreachable phase trace and using exact planner imports made it fit. Runtime
shares the duplicate public-context forwarding body and its boundary now fits.
Build `1788604365.3646998` then exposed a stale Wild callback expectation:
slot 7 now takes a versioned landing value. Both callers and the public typedef
agree. The corrected package check rejects the old private-state callback in
four permanent host tests. The next build passed that gate and exposed the
retired Hop table check in overlay 155. These are build/tool failures, not
external blockers or gameplay failures. No current gameplay witness has run.

The retired Hop table guard has now been replaced with current exact planner
and retirement checks; the temporary candidate passes its 37 rejection
controls and the move-history package verifier. The mount package verifier
still expects Teleport timing logic in Mount instead of its current shared
planner; its reviewer is checking the full routed contract. Runtime preflight
also caught the retired Task6 chain-readiness hook during isolated startup.
The hook now targets the current Wild function with the same one-slot ABI;
isolated runner startup passes. The published ROM remains the old checkpoint
until a complete managed build publishes the new sealed pair.

Build `1788606162.1956968` passed the retired Task6 gate and stopped at the
overlay-153 inventory. Current and last published ROM retain the same 112
history-core calls; the reviewer is checking all 34 shadow/Walk calls instead
of changing the hash without explaining the difference. The three normal
collector files are released with correct retained spawn hooks, complete
travel and pause checks, held travel, and fresh failure screenshots. They are
still planned until their actual fixture/recorder runs. The full host suite's
one failure was the old constant count of 32 pending audits after D2's audit
was completed; its test now compares the exact remaining scenario IDs.

Three required live witnesses are still planned: normal Ledyba chain/pause,
unmounted long-travel cadence, and the live actor/motion recorder control. The
active collector setup-audit queue is exposed by `owctl progress --json`;
review the selected slice first. No normal-play credit comes from a controlled
retry or an unaudited collector. Broader preflight caching is not implemented:
the complete tool/native dependency key has not been proved, so the existing
fresh fixture checks remain in place.

Build `1788607015.783678` is the first complete sealed checkpoint for this
continuation. The overlay-153 audit preserved the 112-call history core and
checked all changed shadow/Walk calls, hidden-state halfword access, and exact
copy/clear callers. The unchanged full build gates pass. The Delta copy hash
matches. Full runtime preflight passes, not only the presence-only doctor.
The first diagnostic command lacked required Python isolation flags and was
rejected before emulator creation; the corrected command ran. Its fresh image
shows Route 29, while the legacy boot predicate reads zero Wild field/runtime
pointers and the public actor list is empty. This is an open startup/observer
boundary failure, not a Ledyba symptom reproduction. The raw save is untouched.

The canonical run `20260905T112329Z-a5a3ef42bfc497980ef2` reproduces the same
startup failure after its fixture gate passes. Two fresh diagnostic boots show
no input response and actor magic/frame zero. Twelve CPU samples remain at
`0x023C9514` with ARM mode selected. The actual Field instruction at
`0x023C9298` is Thumb `BL 0x020E5B44`, while the vanilla reference identifies
that target as ARM `memset`. The previous byte-budget edit replaced working
bridges with raw ARM linker aliases. This is a game regression, not a fixture
or observer failure. Restore calls through the existing resident Thumb bridges
without growing Field, and keep a permanent linked/package rejection check.
The source review confirms the private boot offsets were correct. The product
fix was applied only after the new package invariant rejected all nine wrong-mode
calls in the old ROM. The correction uses zero-storage typed imports to the
existing core bridges and seals the new source/object. Two managed retries
(`1788607984.793289`, `1788608089.2001972`) found duplicate helper definitions.
After the repeated failure, a direct diagnostic link trace proved that the old
`/DISCARD/` rule itself loaded `build/thumb_help.o`, even after Make omitted it.
Removing that rule makes the diagnostic link and all five import/caller/core
checks plus 52 rejection controls pass. The next V2 build must still publish
the sealed ROM before runtime retesting. No gameplay pass follows from this
diagnostic link.

Build `1788608237.448087` passes the complete Field guard and publishes the
matching `test3059.nds` Delta copy. The unchanged normal scenario still fails
before actor initialization. This is new CPU evidence, not a repeat of the
Field failure: `ActorSystem_Zero` now reaches a linker-generated
`__memset_from_thumb` veneer, which enters ARM mode then branches into the
Thumb core helper. The CPU stops at `0x023DEF00`; the caller is
`0x023B6F76`. Audit this exact import class across all overworld clients before
the next edit, then require its new guard to fail on the existing package.

That class audit found 23 wrong-mode bridges in four clients. Zero-storage
Thumb function metadata removes them without changing movement policy. The
permanent guard rejects the old package and checks 134 current callers, their
typed imports, exact core helper bodies, and 40 invalid variants. Field's
separate five-helper guard retains its 52 rejection controls. Actor view and
Field terrain host checks pass. Build `1788609085.430382` then stops at a stale
FAT expectation: removing Selector veneers reduces its image by 52 bytes and
moves the next 512-byte file boundary back by 512 bytes. The revised check
authenticates the linked Selector bytes and derives only the following aligned
file positions; RAM reservations, exact contents, and overlap checks remain.
Four wrong-layout controls and all candidate binary checks pass. A new managed
seal and live startup are still required. A concurrent broad host-suite run
was rejected because its source input path set changed during the build; rerun
it serially after the fixture edit and build finish, without weakening that gate.

Build `1788609816.202878` publishes `test3060.nds` with matching Delta bytes;
full fixture preflight passes. The independent current-image sweep finds no
remaining wrong-mode veneer across all 14 images and 270 hosted core Thumb
symbols. The save boots and moves normally to the right. Its first left tile
is occupied by an active object, not universally blocked terrain. Normal
UP×4 then LEFT×3 bypasses it. The old stock-step helper also waits for command
255, but native idle FACE commands are 0–3. Its new predicate checks current
and previous tile, exact pose center, and native command-ready flags; host
controls reject partial renders and held/unready commands.

The first post-startup normal run fails in the recorder's memory guard:
valid typed public calls use stock DTCM stack buffers. A diagnostic records
the actual policy pointer `0x027E368C` and the unchanged public header. The
reader now permits the exact DTCM non-reserved window for typed buffers only;
engine objects remain main-RAM-only. Range/header negatives and source-audit
mutations pass. Route calibration then catches fences and a house before any
Ledyba claim. The static mistake was a missing 16-byte extra block in
Cherrygrove land data, not absent terrain collision. The reviewed 67-tile
route reaches Route30 and stops new input at real Ledyba acquisition. Detailed
setup attempts remain in `fixtureSetup`; no save/profile/counter was changed.

Run `20260905T123420Z-9df77cd96da78433298e` acquires the correct Ledyba but
rejects the next video cycle. Diagnostic
`build/ledyba-clock-diagnostic-3060.json` shows actor frame641 incrementing
before its engine pose changes, then that pose completing in the next native
cycle with the same actor frame. Stock `main.c` and the packaged ARM9 confirm
two normal VBlank waits and separate main-queue tasks. This is a recorder
boundary fault, not a proved Ledyba stutter. The exact queue-return probe now
has a package preflight check and wrong-queue/call/extent host controls.
Coherent live recorder calibration, its live faults, normal chain/pause, and
the separate unmounted long route remain open. Follower position observed far
behind after transition is a separate unverified game concern, not closed by
this recorder correction.

The full 3060 normal run observed a real spawn and 40-frame settlement, then
no normal motion for 30000 game frames. A separate run caught profile lookup
before actor binding erased its published fingerprint. Binding now precedes
the profile-reading spawn setup; its exact-body regression has five negative
controls. The unchanged 3061 observer run crashed when it recreated DeSmuME
in the same process. Actor and route controls now have separate required
scenario receipts; the failed run remains open, not accepted.

The short 3061 diagnostic finds valid movement candidates and active AI.
At the first new Walk, the preceding Hop is still SETTLING. The custom adapter
sets the native freeze command before admission, then cannot restore it after
ALREADY_ACTIVE rejection. The controller's live RED catches that same command
change in 19 seconds on an identified wild Ledyba. Build3062 moves native
command ownership and sound after admission and restores only this attempt's
Hop prep on failure. This is not a claim that the previous adapter token and
presentation survive all rejections; D5 still owns the explicit receipt gap.
The broader normal chain, unmounted route, and live recorder checks remain
open until current accepted runs pass.

- The coordinator alone updates the current table after an integrated result,
  failed attempt, or handoff. Use generated manifest status for proof; never
  hand-count green tests or copy pass totals into multiple documents.
- Keep one integrated behavior change active. Add a short contract suffix such
  as `D3.chain-pause` inside its row while it is active. Do not duplicate every
  phase or every run as another task list.
- An active contract records its requirement and role, owned files, relevant
  content identity, red/green manifest paths, failure category, attempts since
  new evidence, and one next action. Keep detailed output in the run directory.
- Classify each failure as game, setup, test-tool, host, or unknown. Unknown
  remains unresolved. Preserve the first useful failure and how it was resolved;
  a later green run does not erase an intermittent game failure. The
  [failure-record procedure](verification.md#failure-records) owns disposition
  commands; use `harness` for a test-tool failure in those records.
- A helper handoff uses: `ID; files changed/released; observed facts; evidence;
  unresolved question; next action`. Mark inference as inference. Do not write
  a separate helper roadmap. The coordinator reconciles evidence before closing
  the item or assigning the same files again.
- After two attempts on the same failure with no new evidence, record the
  changed investigation method before another product patch. Waiting on a
  helper is not an investigation; do independent in-scope work or make a clear
  handoff without repeated status polling.
- At a stop or resume point, the table must answer: what is active, what is
  proved, what failed, who owns the files, and what runs next. No transcript
  reconstruction is required.

## Historical source/link reports — not current proof

The notes below were recorded on 2026-09-03 during source changes. They include
conflicting scenario-dependency counts and reports from different intermediate
states. They are retained to locate prior work, not to choose today's proof or
mark a phase complete. Recheck any claim needed for the next slice.

- The catalog contains 35 active scenarios and 27 capabilities. Scenario
  proof-source validation passes with zero private runtime dependencies. This
  validates the proof source only; it is not accepted runtime proof.
- Host proof-gate tests pass: 75 tests.
- Structural legacy-gate tests pass: 49 tests.
- Turn skid, diagonal turn skid, wild Walk, mounted Walk transition, stomp,
  crash, and Cyndaquil step taps have active structured-subject scenarios.
  Current fail-closed validation still blocks the scenarios that retain a
  private runtime dependency. None has run on the final ROM, so none is
  accepted runtime evidence.
- Unmounted wild and follower cadence now have separate S5 contracts. Each
  rejects mounted samples and requires more than 5,000 measured frames, at
  least 16 complete Walk motions, stable public actor identity, continuous
  render/motion timing, terminal engine release, and process-CPU pacing. These
  contracts have not run on the final ROM yet.
- Baseline runtime fixture checks passed for actor, wild-spawn, wild-runtime,
  mount, Walk, Hop/role, helper, field, build-manifest, descriptor, and ROM
  identity. This evidence becomes stale after the current product cutover.
- The structural source/link ownership gate passes all nine capabilities. Its
  linked-client coverage includes all twelve modules and the restored Walk
  overlay 153 image. Package checking was not run, so this is not packaged-ROM
  evidence.
- Walk consumers link to sixteen fixed helper functions from `0x023BF488`
  through `0x023BF9A0`. The old Walk service-table range at
  `0x023BF400..0x023BF487` remains zero. This restores required linked clients
  without restoring a duplicate Walk owner.
- Face-player facing now calls the canonical core owner directly. The duplicate
  Walk-overlay body and its fixed service entry are removed in source, and the
  old `0x023BF468..0x023BF473` slot is reserved as zero. The package proof is
  pending the next managed ROM build.
- Wild movement primitives now come from the canonical behavior resolver and
  are cached with the resolved profile. Species group membership is generated
  into OWSM v3 spawn metadata. The duplicate WPOL resolver and its fixed
  `0x023BF474..0x023BF487` service slot are removed in source; package proof is
  pending the next managed ROM build.
- Hop no longer exports the six-callback task-6 table. Wild owns landing,
  helper-search, and reposition engine glue; Mounted and Wild request Hop
  planning through Actor Motion. ARM source links confirm the retired
  `0x023BD4D8..0x023BD4EF` slot is zero and all four affected overlay budgets
  still fit. Package and runtime proof are pending the next managed ROM build.
- The staged-Hop engine task handle now shares the existing Wild-owned
  144-byte per-slot movement-list allocation. Create, poll, cleanup, and free
  no longer use the cross-overlay pointer table. The structural gate changed
  from two references to `0x023C3F18` to no references, no retired symbol or
  literal, and a zero `0x023C3F18..0x023C3F3F` range. Wild state size, BSS,
  ABI, and allocation size did not grow.
- Overlay 153 no longer reads the Wild custom-jump runtime or names
  `sOverworldWildSpawnState` for native-shadow position. Its value client
  rejects an unloaded overlay and any callback other than the exact fixed
  Thumb entry before the call. The 12-byte request and response carries only
  version, size, slot, encounter generation, active, and base-height values.
  The stock shadow task retains the generation token separately from its
  low-half hidden flag. Wild validates current object, manager, map generation,
  and encounter identity and remains the only runtime owner. The fixed Wild
  entry stays 40 bytes and Wild BSS stays `0x20` bytes.
- Phase 7 Slice 2 replaced tile-step and adapter-call population distance with
  native player logical-coordinate `PATH_ADVANCE`. `PATH_ADVANCE`, `COMMIT`,
  and `FIELD_EVENT` use one non-zero wrap-safe 32-bit sequence and reject
  duplicates, stale fields, and stale sequences. Public
  `Inspect(POPULATION)` returns a value snapshot with a normalized
  `workPending` boolean.
- Phase 7 Slice 3 added the public Warp/Battle world-gate query. One actor scan
  closes the gate for an active transition or any active input owner with a
  reservation or non-terminal motion. Queued actor commands recheck field
  epoch at execution, and queued Wild battles recheck map and encounter
  generations before start.
- Phase 7 Slice 4 resolves retained Wild objects by stable ID from the current
  manager only after the slot's `retainedActorMask` bit and public actor value
  match slot, field, map, encounter, and subject identity. It then validates
  manager membership and object identity before dereference. Any failure makes
  the field transition owner downgrade preserve to discard. Wild Teleport now
  keeps its logical object at the origin until terminal landing.
- Actor Motion now rejects an active transition and a stale request epoch before
  intent mutation, trace publication, planning, or `Begin`. After target-
  conflict validation it overwrites the plan with a fresh non-zero reservation
  identity. Wild and Mount retain that accepted identity, and every boundary
  receipt must match it before it can mutate motion. This closes delayed work
  against a recycled actor slot without growing the fixed Actor request,
  boundary, Mount-state, or Wild-runtime layouts.
- The compatibility entry is ABI v3 and keeps its 32-byte fixed layout. Its
  byte-28 `getContext` target returns the Actor-owned field epoch in the low
  half and map generation in the high half. The retired byte-12 update slot is
  still zero. Wrong-version and wrong-target mutations fail the structural
  ownership gate. If a required transition adapter is unavailable, the field
  driver preserves the previous map marker and retries without a legacy
  transition fallback.
- Current host evidence passed:
  `scripts/verify_overworld_population_model.py`,
  `scripts/verify_overworld_motion_model.py`,
  `scripts/verify_overworld_actor_transition.py`,
  `scripts/verify_overworld_wild_motion_ownership.py`, and
  `scripts/verify_overworld_motion_identity.py`. Their mutation cases reject
  stale population events, false pending state, stale retained handles, a
  missing retained mask bit, incomplete rebind identity checks, request guards
  moved after observable mutation, caller reservation reuse, unauthenticated
  boundary receipts, missing gate rules, and early Teleport relocation.
- Exact ARM links passed for Actor, task-6, Wild Spawns, Wild Runtime, Mount,
  and Wild Helper. Actor code ends exactly at its `0x023BA170` cap (`0x00`
  free). After the native-shadow value cut, Wild Spawns ends at
  aligned address `0x023D7F40` under the `0x023D7FD8` cap (`0x98` free).
  The position hook uses `0x2C` of its `0x44`-byte slot, and the mounted
  diagonal validator uses `0x7E` of its `0x80`-byte slot. This is source/link
  evidence only. No
  packaged-ROM or runtime exit claim is recorded.
- Native-shadow mutation coverage rejects direct ASM or Walk state access,
  value-service bypass, unavailable overlay 149, the wrong exact callback,
  stale object or manager identity, stale map or encounter generations, and
  full-word hidden-state reads or writes. The structural suite, structural ownership
  gate, Wild motion ownership check, exact Walk/Wild/Mount/Field links, and
  move-history source/host fixture gate pass. Packaged-ROM bytes and live
  native-shadow behavior have not been proved on the final ROM.
- Scenario validation passes all 35 active definitions, but there are no
  accepted current runtime manifests. Live proof remains open.

### Historical next-proof order — superseded

This former final-build-first sequence is retained as history. Use the finite
slice order in the roadmap; D1 requires an early checkpoint.

1. Build one final candidate ROM and seal its fixture identity.
2. Validate every active scenario contract.
3. Run every required S3-S5 scenario through `scripts/owctl scenario run`.
4. Run the full roadmap gate and require `"passed": true`.
5. Commit and push only after the final gate passes.

### D1 reader-cost checkpoint — 2026-09-08, historical detail

These checks reduced tool cost, not the open route stutter. The resume page
keeps the latest failing route and current next action; do not rerun this list.

- Native phase v1 used39,212 clock reads/frame. V2 frame/render scopes reduce
  this to at most772 in the live control. Do not restore per-Execute clocks.
- Landing caller authentication scanned linked symbols16 times in the host
  witness. Cached sealed host bounds reduce that to1, with live LR/BL checks
  retained.83 focused checks and independent review pass.
- Host-only identical-copy probe:1,024 intervals, alternating continuous/10ms
  idle, no hitches. `/tmp/ow-host-cadence-nDEzf8/` holds temporary details.
  This did not reproduce the simple idle-wake theory or test native reads.
- Native memory decoder now copies its full buffer once, not per element.
  Six red-before cases and44 host checks pass; not a game timing result.
- Shared `snapshot.probe`:384 equal snapshots at fixed game clocks,718 native
  reads/3,395 bytes each, median~2.4ms.70 tool checks and review pass.
- Spawn baseline/omission pair:120 identical snapshots/244 dispatch records;
  frame851 CPU24.840ms versus21.061ms.120 host checks pass. Both runs remain
  diagnostic and cannot excuse a normal-route hitch.
- Snapshot-local ID scan:189 checks pass; exact pre-change live output hash,
  reads718→462, median2.399→1.779ms. Two paused samples exceeded2x median with
  no game progress. Host cost alone is not proof of a game logic stall.
- Build3088 full route still failed:317 observed frames, one hitch/640 cycles,
  median12.728ms/max25.509ms at851. Snapshot2.200ms/callbacks10.474ms.
  Manifest: `build/overworld-devtools/test-95c97c5fb64a4f679d5082c8b1d19e79/manifest.json`.
