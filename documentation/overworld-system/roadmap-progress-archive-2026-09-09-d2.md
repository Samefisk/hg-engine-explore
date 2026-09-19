# D1/D2 checkpoint — September 9

ROM3095 unchanged. No ROM build, save edit, commit or push. All owned sessions
closed; automatic cleanup removed private ROM copies. No images captured.

## Accepted native results

- Ledyba reader: `test-ae1cda5e751e4cdebb13f12f18b59be9`,1233 frames,132.189s.
- Normal Ledyba: `test-f9721619d7e347b9a314b06d8acf2e99`,5007 bound frames,
  488 eligible moves,589 complete motions,40 intervals,25 actions,zero errors.
  Natural own-site spawn and chain/pause only;317.305s.
- Actor binding: `test-67078dea37294416944876d4eb1c5e53`,57 frames,51.471s.
- Packaged resolver: `test-7075ab14de9749bbb6b48c381a44975f`,seven public
  service requests;46.611s. Native-call proof, not gameplay frame credit.
- Owner reader: `test-aee665411b0d4998ae83165cbccf44e5`,one frame,53.105s.
- Owner transfer: `test-acd7ed366b804ad6b6312fa9d0e93d68`,one frame,64.179s.
- Public Inspect: `test-8ab04dcc2cc14169a15b9ddfb8e8cab8`,56.588s;
  current/stale native lookup, not movement proof.

Each exact manifest is `build/overworld-devtools/<run-id>/manifest.json`.
All terminal manifests have passed and acceptedProof true. D2 still needs
`mount.begin-current-follower`; it was not launched after the user's stutter report.

## Tool failure and fix

Owner control44bb260 failed before boot,8.450s,zero observations: scoped proof
required a JSON measurement table even for existing controller-owned contracts.
`proof_inputs.py` now delegates missing-table validation to the existing exact
registration validator. No dummy contract, changed gameplay threshold or blanket
exception. Registry, missing values and controller source remain hashed.
Two actual-recipe regressions failed before the fix.34 host checks now pass,
including rejection of changed evaluator, requirement, claims, hash, mode and
subject. Independent review found no blocking issue. Unchanged readeraee665
then passed. Original failed manifest is preserved, not rewritten.

## D2 host checks

These existing commands passed with python3; no separate plain resolver rerun:
feature table --check, behavior schema, behavior catalog --check, behavior
resolver --rule-removal-control, Workshop authoring, actor view, lane projection,
command sequence, spawn profile lifecycle, actor binding observer, and
`scripts/verify_pokemon_move_history.py --rom test.nds`.
Canonical command paths are in the D2 check entries of system_features.yaml.
Resolver control executes seven actual-C cases and detects the removed rule.
View:672 Fill/224 Sync cases; lanes:252 Fill/252 Sync; spawn lifecycle:26 cases.
These are host/package checks, not substitutes for native caller proof.

## Reopened rare unmounted stutter

User reports that rare unmounted stutter remains. Earlier route56b995 stays
narrow passing evidence; it does not resolve the new failure window.
No new game patch or blind repeated route was started.

Saved Ledybaf97216 observed intervals under unchanged classifier(2000,250000):
10088 cycles,median11.487ms,max35.932ms,183 flagged cycles. Diagnostic only;
the Ledyba acceptance contract does not claim player pacing.
First flagged frame1188 follows two spawn finalizations at1186. Worst frame2829
has a chain attempt;3437/3445 each have three attempts and four motion endings/
starts. Player remains unmounted at map34(552,376),six Wild actors and Mankey
Follower; no nearby inspected map/stream change. Native callbacks contribute
19.232ms of35.932ms at2829; do not subtract this and call the rest pure guest CPU.
Useful zero-based memory rows:357,563,639–641. Artifact SHA256:
`15573ef6eb7056ab6ee12bc9e3380450f2347d9a6ab33c24a152da7dfb089791`.

Completed-game-frame grouping:4823 groups have2 native cycles,57 have1,
127 have3,and frame1309 has4. No missing completed-frame samples. This grouping
is a lead, not yet a VBlank deadline measurement: authenticate boundary phase
and stock main-loop waits before interpreting it as a missed game update.
Reference: `.codex-reference/pokeheartgold/src/main.c:108–135` and system.c.
## Guest queue diagnosis — next continuation

The new read-only command is in `devtools-tests.md#recheck-retained-proof`.
It verifies artifact hashes and streams data; it creates no ROM/session/evidence
copies. Unit checks cover phase recovery, missing samples, setup/context changes,
clock regression, artifact identity and repeat immutability. It is in the host gate.
Independent review confirms the conditional bound for this normal melonDS path;
artifact hashing alone does not authenticate arbitrary historical backends.

Route56b995 has four same-field, no-script queue gaps of4 native frame bins:
2981→2982(6426→6430),3080→3081(6626→6630),3965→3966(8404→8408),
5537→5538(11561→11565). Under normal one-frame melonDS calls, each means
greater than3 frame periods between completed main queues. This is independent
of host callback time. The old route checker did not check this spacing; its
old accepted result cannot resolve rare stutter. Ledyba has one such gap1309→1310.
Route diagnostics:5836 eligible pairs,one context break,bin counts1:483,2:4822,
3:527,4:4. Ledyba:5006 pairs,no breaks,1:56,2:4822,3:127,4:1.

All four route gaps contain spawn work, not chain-only work:
-2982:two failed FinalizePreparedSpawn calls; second spans6429→6430.
-3081/3966:failed then successful slot1 Hoothoot163; prepared work spans the
  last two bins. Cyndaquil is already walking.
-5538:successful slot6 Pineco204; player east/Follower walking.

Gap ARM9 dispatch totals are1,613,785/1,673,540/1,710,874/1,513,948 versus nearby
normal pairs691,354/778,127/740,452/742,375. Surface queries reach175 calls at6429
and240 at6629/8407/11564. No CPU-time subtraction was used.
Current symbols:QuerySurface0x023ce334,DoesAllowedTileMatch0x023cf0ca,
SpawnOne+0x6c0x023d305c,ResolveObjectLandingHeight0x023cf680.
`TryPickSpawnDestinationMask` at wild-spawn source15538 scans17²−7²=240 tiles,
calling DoesAllowedTileMatch and its surface lookup on each distance-eligible
candidate. Duplicate finalization can repeat that scan in one game update.

Next: make this queue-spacing failure a permanent checked-route rejection,
then bound attribution to this search before the product patch. Preserve candidate
order, reservoir RNG, exact spawn surfaces and own-Pokémon destination semantics.
Do not use a timing-threshold relaxation, mounted movement patch, blind long
route repeat, or old six-reader omission experiment. No game code changed yet.
User location/time detail remains requested, not a blocker to this retained lead.

### Spawn-search reduction and stronger queue check

The shared route meter now stops on `guest-main-queue-delay` at four native
bins between consecutive same-context queue completions. Missing control data
fails closed. Three/one phase recovery remains allowed. Replaying the original
route56b995 through the controller-owned checker fails at2981→2982, before the
minimum route floor. Original evidence and manifest remain unchanged.

Actual production-C host fixtures preserve33 candidate/occupancy/RNG cases and
147456 terrain-mask/surface decisions. No-FRONT masks previously made289 front
lookups per search; they now make zero. No-CANOPY masks skip only native canopy
fallback, never the catalogued surface veto. Both efficiency bounds are durable
tests in the host gate. Independent review found no selection/RNG change.

ROM3096 built through Workshop in73s, with its unchanged45056-byte Wild file
slot and32-byte BSS. Candidate SHA256:
`b74117043acdf4f59592e615b316eff1a22fa98ec38510127ed694c2709875c4`.
The earlier route readera2f404 passed on3095; current3096 reader/route checks
are pending. Do not claim rare stutter fixed from the host parity tests.

Reader3096 `test-eb30e07715274cb9bddee35d8aa0805c` failed at bind769:
`unknown-crash-layout-code`. The StartCrash function's PC-relative calls moved
after the unrelated spawn edit; full-byte hashes reject the reader before
movement can run. Session81n9_ouj closed successfully. Harden the existing reader
to validate named call targets separately from invariant instruction bytes;
do not accept an arbitrary new digest or label this setup failure a game pass.
70 focused host tests passed (two retained-artifact tests skipped); these do not
substitute for the pending live route. Delta3096 SHA matches the built ROM.

Crash reader hardening completed: only the two reviewed Thumb BL displacement
fields are normalized. Both targets must match exact named ELF symbols and
packaged/live bytes. All remaining Start bytes/state offsets and Restore's old
digest stay pinned. The reviewed3096 normalized layout does not assert missing
3095-byte parity. Eight focused checks passed, plus a current overlay149 smoke:
Start0x023ced78/72, Restore0x023cd4c8/76, Ensure0x023cecf4/64, state0x023df9c8.
Inputs frozen before fresh reader `test-f29875ece5434f518e6cdca3008e0620`.

Reader f29875 passed/accepted in56.902s,31 observed frames; session-r77lpyi6
closed successfully. Unchanged full route `test-ec0bfa2d6db64108857871e97cda91d0`
started on3096. Its terminal result is still required.

Route ec0bfa failed after189 observed frames,70.989s; session-gyc34au6 closed.
Failure is host CPU sample347: game941/native2331,25.643ms vs12.2245ms median.
Detection958/959 is not the spike frame. Same baseline941:17.245ms and334370
ARM9 dispatches; current333116. Both have the same actors/events. Current
callbacks11.503ms, including snapshot5.063ms vs prior2.220ms; wall44.832ms.
No nearby spawn work or four-bin guest gap: frames939–943 all have two bins.
This points to host/reader cost, not proof of a product regression or its cause.
Keep the failed manifest. No thresholds or game code changed for one unchanged
repeat `test-414e73064f0e446d9442c6276eaaf23d`. If the same host failure repeats,
switch to a bounded reader-cost measurement rather than another blind route.

Repeat414e73 also failed only the original host CPU gate, after958 observed
frames/107.721s; session-trf3y3yx closed. Its peak is game843/native2132,
23.344ms, versus final11.518ms median. Detection1727/1728 is later because
the running median changes. Context/rebind work and36 Walk observations occur
at the peak. GC is only0.161ms; neither run's peak is explained by large GC.
No new game edit or timing relaxation followed this second host failure.

Existing `snapshot.probe` ran32 reads in owned session-v3k43_71, paused at
frame713/native1869. All snapshots equal, clocks unchanged,463 native reads/
2435 bytes per iteration. CPU min1.337ms, median1.465ms, max2.850ms on identical
work. Artifact `build/overworld-devtools/session-v3k43_71/snapshot-probe-ebab8343e603.json`,
SHA256 `1d0de8c4beded260ccf41612e8976c57da9ec1032c8ad6b786ceb0f8fe7c159f`.
It is diagnostic only, excludes native hooks/publication/copy, and does not
explain the entire route peak. Session stopped after the probe.

Next bounded action: use the shared manual recorder for a guest-timing diagnostic
through the existing unmounted route's old spawn windows. Retain host CPU faults
as faults; do not keep restarting the full checked route before those windows.
This diagnostic cannot close S5 or D1. Separate noisy host cost from actual guest
queue spacing before any further product patch or formal proof-rule change.

### ROM3096 guest red and call-timing diagnostic

Shared prepared session-jdc5h64g used checked Follower155 and map67 setup,
then normal unmounted input on a bounded rectangle. Source recipe:
`tests/overworld/recipes/diagnostic.unmounted.spawn-queue-delay.json`.
Record before input; loading a recipe does not retain prior memory samples.
Initial216 frames had no guest gap. The next511 snapshots, frames1104–1614,
contain1208→1209/native2892→2896 with unchanged field context and taskPointer0.
Artifact: `build/overworld-devtools/session-jdc5h64g/recording-5a44cbb40129.json`.
1818 events, no truncation or identity failure. Session stopped after export.
Natural Hoothoot163 slot3 is created at1209; existing slot0 starts a normal Hop.
The failed SURF Tentacool72 attempt is POOL with input[-1,-1], so it exits before
destination-mask search. A WATER-only scan shortcut would not fix this case.
No new product patch followed that false lead.

Added read-only `guest_clock()` to the shared melonDS bridge and inclusive
entry/return timing for spawn finalization, destination search, creation,
startup motion and landing height. Search receipts retain parent finalization,
world and destination mask. Raw ARM9 scheduler ticks include waits/IRQs; they
are not host time or active CPU cost.64 Python tests and native no-ROM clock
tests pass. Rebuilt shared library only; ROM remains3096. Live timing follows.

Live guest-clock session-jxh3e8xt reproduces exactly1208→1209/native2892→2896.
`recording-4e132174a2f1.json` in that session has556 snapshots/1732 events,
no truncation/failures; SHA25636890cc02bb5094f3a4a490403f275cbc9bf9c59324b45108e0d6dbb6d4260cc.
At1209: failed Tentacool finalizer101831 ticks; Hoothoot search330659 ticks
within finalizer442903; SpawnPrepared532398, including startup jump131300 and
landing height525. Nested spans are not added. Both attempts and creation are
same-queue work. Session stopped. Follower155 verified; normal unmounted input.

Candidate: replace Runtime QuerySurface's linear sorted-model search on cache
miss with binary exact-match search. Validator already requires unique sorted
IDs. Cache, per-tile checks, candidate order and RNG unchanged. The first
lower-bound form and unsigned variant both exceeded fixed core reserve by12B.
Disassembly showed avoidable terminal lookup; exact-match form removes it.
No linker limit or stable entry moved. Actual full-C host oracle covers132161
cases, all65536 land IDs cold/warm, real model hit data/native ground, missing
models, invalid queries and block/context changes; at most8 probes per miss.
Registered in host gate.90 focused cadence/spawn/probe tests also pass.

**Trial rejected after live evidence.** ROM3097 built in66s, SHA256
ee501cf66080e15619cbdcbe7ff024624bef1307d30724fd8480e13a636cc064.
Same setup/input in session-337essx0 reproduces1208→1209/native2892→2896.
Artifact `recording-352b25252747.json`, SHA256
36716deb18c80849ff499b809f900f04b4fd47726a0356e2fbbba9825a874ac7,
556 snapshots/1732 events, no truncation or identity failure. Search334454
ticks versus330659 baseline; SpawnPrepared532879 versus532398. Host parity
did not imply useful game performance. Removed the binary-search trial and
its trial-only fixture/gate entry. Do not repeat this optimization blindly.
Session stopped. Restored build3098 passed in72s; ROM and Delta copy match
baseline3096 SHA256b74117043acdf4f59592e615b316eff1a22fa98ec38510127ed694c2709875c4.
No changed game behavior is retained from this trial. Source saves unchanged.

Next observation: existing BehaviorResolver receipts now get guest timing
only inside finalization/creation.70 observer/backend/probe host tests pass;
that added scope has not yet run live. Restart idle service, no ROM build.
Do not reuse prepared profiles blindly: frame1209 seq933 is terrain0,
fingerprint1872851127; startup seq936 is ROOFTOP0x40/fingerprint1583707637;
startup seq937 returns to terrain0/fingerprint1872851127. The destination
and off-screen origin genuinely select different overrides. Complete request,
data identity and owner binding must match before any future reuse proposal.
The prepared value also omits fingerprint/layer masks; preparation and later
metadata form handling differ. No profile-cache edit was made.

## Spawn metadata capacity — ROM3099

Scoped resolver red: session-9j14kef0/recording-13b54f5abedb.json,
SHA2569bfa2bc3a058854c54b95b0b7495f67353eff6726019be5cbafa45f28c662586.
Resolver calls take19740–30082 inclusive guest ticks, not the whole spawn cost.
Scoped metadata/class/create red: session-_9rd1blw/recording-e7c0bbbe1618.json,
SHA2568400cdf8895e4041d056b6413b633fdab723bed5287ea9149ae15037c5eafcbe.
Both retain386 dense snapshots and gap1208→1209/native2892→2896 on3098.
Native metadata72/163 base-form calls returnFALSE in44–45ticks; stock personal
archive fallbacks then run. Generated metadata is17988bytes, exceeding the
loader's16384-byte guard. The failed attempt latches unavailable metadata.

3099 shares a32768-byte cap between runtime and generator, while allocating
only actual blob size. Generation/verification reject overflow before writing.
Five actual-C capacity/lookup/failure/cleanup tests pass, including the old-cap
negative. Combined78 host checks pass1.007s. Independent review found no defect.
Existing cleanup was already correct; no cleanup rewrite or profile reuse.
Native scoped metadata/class/create receipts now expose the cause; the cadence
checker rejects observed base-form metadata misses instead of waiting for a hitch.
Architecture/devtools contracts and host-gate registration updated.
Workshop build3099 passed86s; Delta SHA matches test.nds:
3a973d7c855bdf01e986c597b318e0bcc3979c338b77305cb7897077f66f7b63.

Fixed short route: session-o5rkipmx/recording-01d73f247887.json,
SHA25603fdc096a33e06ffb2569f38176fb699a4ec914fd22fab69f9f0a8198f7c67f1.
Same saved prepared Follower155, map67(543,393), same cardinal inputs/endpoints.
386 snapshots, no truncation, zero guest queue delays; all measured metadata
calls returnTRUE. Spawn1209 creation276497ticks vs532398 before. Root stopped
the session; private ROM removed. This diagnostic does not close rare stutter.
Doctor and all52 scenario validations pass. Current reader7fe1c0 started;
terminal reader and full long-route acceptance remain required.

Current reader test-7fe1c0ebef6b4dcc802a7ea84db2dcd1 accepted31frames in71.902s;
manifest ROM hash matches3099; session-ez61_949 closed without errors.
Unchanged route test-2e2c71601ccf4760b65cdbf08ebf44d6 failed127observedframes
in79.532s. Failure is host-process-cpu-hitch: sample166/259,30.093ms against
13.707ms median, reported at897 after batched check. Retained interval locates
actual cost at completedGameFrame851/native2150. ThreadCPU30.088ms, wall32.501ms;
dispatches ARM9626051/ARM738818. Native exclusive phase costs: nonRender26.123ms,
3D2.686ms,2D1.196ms. Selected callbacks12.964ms; these are inside nonRender,
not additive. Snapshot2.076ms, pending-copy1.382ms; multiple native observers
and240 surface/268 query callbacks also contribute. GC0.206ms. No threshold
was relaxed and no gameplay delay may be inferred solely from host CPU.
Memory artifact observations.jsonl.gz SHA256
a098ed8bfb88c3d2468d37c1dbb84fb203444ef86f69f288db43fda8f1403969.
Session-eoziskxc closed without errors. Next use this retained frame's guest
receipts and quiet-frame comparison to separate game work from observer cost;
do not repeat full route blindly or claim rare stutter fixed.

## Full rare-window diagnostic — unchanged ROM3099

Retained2e2c71 sample848–853 has queue cycles2144/2146/2148/2150/2151/2154;
no missed-queue witness. All851 timed spawn calls stay native2150. Matched
completed-boundary frames800–850 medianCPU15.526ms, selected callbacks5.334ms.
Independent review agrees: host cost is real, but not proof of a guest stall.

Added explicit diagnosticContinueHostHitches to prepared requirement-free cadence
tests. Default registered test is unchanged. First host failure latches even if
later median changes; latest/worst costs are retained. Other failures stay
immediate. Finish always fails, and controller rejects acceptance before cache
reuse. Diagnostic recipe copies the original setup/actions/budgets; host test
enforces parity. Seven focused tests and independent review passed; full contract
module27tests passed0.090s. All52 scenario validations and live diagnostic recipe
validation pass. No ROM build, game edit, threshold change or screenshots.

Live test-1d846807718446a0bbfb7966deb7c41f used ROM3099, unchanged test.sav,
same7setup/257route actions, and normal input after prepared follower setup.
322.797s;5690observed/5428activeframes,85tiles/3cells/2maps,1357player motions,
958follower motions. routeWindowReady TRUE. Finished failed/not accepted as
required, retaining first host failure detected897(actual interval851).
Pure replay of all5690saved snapshots has zero guest_queue_delay witnesses.
All110measured spawn-metadata returns succeed. Host spikes:

| Game frame | Process CPU | Selected callbacks | ARM9 dispatches |
| --- | --- | --- | --- |
|851|28.452ms|12.140ms|626051|
|5497|31.018ms|14.517ms|591121|

Manifest and observations.jsonl.gz are under that test directory; memory artifact
SHA2560a93be53223fef125e52d499b02aec535e9536e79d769e51c24f6e6916de0a5f,
27416418bytes. Session-uo6pxwri closed without errors; no extra ROM retained.
The rare game-update symptom was not reproduced in this full window, but this
diagnostic is not registered acceptance or repeated intermittent coverage.
Next address the measured observer cost at851/5497, preserving all observations
and host thresholds, before another unchanged acceptance run. Do not re-run the
old six-reader omission experiment or expand the diagnostic into a new test stack.

## Host-cost scope review and copy safety

Source review: stock main.c waits on VBlank around print/render work; host
process CPU is not its clock. verification.md's claim-scope section explicitly
separates host CPU pacing from emulated frame pacing. Yet registry requirement
legacy.unmounted-long-travel still requires zero normal-route-process-cpu-hitches,
enforced by route_cadence_proof.py. Independent review concludes that this gate
is useful tool-health data but not a necessary/sufficient ROM-stutter witness.
No acceptance contract or threshold changed. Ordinary reviewed replacement
cannot silently exchange a host claim for a guest claim; any future scope
correction must be explicit and preserve failures, original contracts and all
gameplay coverage. Existing zero >=4-native-bin delays is conservative and does
not prove absence of every smaller variation.

Copy investigation:64 copies of retained851 snapshot(35601serializedbytes)
measured deepcopy median1065895ns, JSON round-trip553354ns. This is a diagnostic
on already-JSON data, not proof that live objects can be stringified safely.
Independent ownership review rejects bare pending_samples.append(value):
returned final samples would share latest_frame/latest_party and native getter
receipt dictionaries. Moving the same clone out of the measured cycle only
moves its attribution, not total cost. No copy shortcut or game patch retained.
The narrow speed delta cannot justify another full route by itself.

## Resume D2 without a misplaced mount prerequisite

Independent scope audit: roadmap D2 requires packaged resolver/facade evidence
and one real motion trace. Real Y/Select plus a Hop belongs to D4 mount/input
lifecycle, and remains open there. Capability actor.system spans several slices;
its scenario list also includes detach/transition, so membership alone cannot
turn those into D2 prerequisites. D1 remains open with its buildable observable
failure checkpoint; only narrow independent proof resumes, not broad integration.

Rechecked test-67078dea37294416944876d4eb1c5e53 using scenario recheck. Controller
rejects changed game/reader/action inputs; no game started or manifest changed.
Doctor and52scenario validations pass. Unchanged actor.binding.current-context
then ran as test-1906978cacd84cfba935e116b1446926 on ROM3099.
Accepted57frames in58.615s; one natural Wild Rattata(species19, PID2979735209),
handle65536, object36386556 in current manager, one full subsequent Walk.
Requirement legacy.actor-binding-current-context; mismatch/identity errors0.
Manifest acceptedProof/passed TRUE, source ROM SHA3099 matches. Session-zio6vkuv
closed without errors. No product build/edit. Next current-input checks for
remaining resolver/facade/Owner transfer/control evidence, refreshing only stale
proof. D2 is not yet declared complete. Test guide now records causal host/game
cost classification and detached-snapshot safety, without changing thresholds.

## D2 verified checkpoint on ROM3099

All four remaining retained rechecks (7075ab/8ab04d/aee665/acd7ed) rejected
changed capture inputs without starting a game or rewriting their manifests.
Doctor and52scenario validations pass. Refreshed only those exact tests:

| Test run | Current accepted scope | Elapsed |
| --- | --- | --- |
|test-5b754d91b8614df0971e6a62a7b43305|Seven packaged resolver calls equal fresh Workshop bytes/provenance|64.755s|
|test-ec4e70b2fea74b7a94c61f2c604671e1|Current native Inspect returns saved follower; stale generation rejected|57.812s|
|test-ca64b760804343f4b59f8b0b7aa9fcd3|Owner byte reader fault/restoration calibration|57.027s|
|test-e6837362e5314435add001c17ed6ffe8|Saved Mankey Follower getter transfers through Begin to mounted Owner|77.526s|

Each terminal manifest has passed/acceptedProof TRUE, exact3099 SHA and closed
private session without errors. Source saves preserved; no game edits or build.
Resolver/Inspect clock units are native call cycles, not motion frames. Owner
calibration/transfer each observes one bounded interface result, not a soak or
normal Select/Hop proof. Binding190697 supplies the separate real Walk trace.

Helper ran10host-only checks with /usr/local/bin/python3, all pass in~15s:

```
scripts/generate_overworld_feature_table.py --check
scripts/verify_overworld_behavior_schema.py
scripts/generate_overworld_behavior_catalog.py --check
scripts/verify_overworld_workshop_authoring.py
scripts/verify_overworld_behavior_resolver.py --rule-removal-control
scripts/verify_overworld_actor_view.py
scripts/verify_overworld_actor_lane_projection.py
scripts/verify_overworld_actor_command_sequence.py
tools/overworld/test_actor_binding_observer.py
scripts/verify_overworld_spawn_profile_lifecycle.py
```

Coverage:67schema fields,7actual-C resolver cases/removal control,896actor-view
cases,504lane cases, command replay/cancel,4binding tests,26spawn/profile
lifecycle cases and wrong-state controls. Independent source/requirement review
maps Phase0 canonical docs/skills, Phase1 descriptor/snapshot/trace/facade,
Phase2 schema and one resolver, Phase3 adapters/anchor/command semantics to this
evidence. No remaining D2 source obligation found. D2 checkpoint verified; this
does not complete every cross-slice actor.system scenario or the roadmap.

D3 next is one bounded mounted Crash reader sample through existing crash.arm,
not another full matrix/stomp refresh. Current idle Cyndaquil155, checked wall
terrain, locked turning and wall-hit sound. Need actual stationary32-frame
crash/shake/sound1536/restoration/recovery. No checked Crash recipe/evaluator or
live reader control exists yet; obtain one real sample before building that
stack. D1 host/game claim-scope issue stays open before broad integration.

## Rare unmounted stutter reconfirmed — short-delay coverage gap

User again reports rare unmounted stutter. Read-only rerun of
`python3 -m tools.overworld.cadence_diagnostics build/overworld-devtools/test-1d846807718446a0bbfb7966deb7c41f/manifest.json`
hash-validates the retained data in about2seconds. No emulator boot, images,
ROM build, product edits or acceptance changes.

The histogram is634 one-bin,4409 two-bin and645 three-bin intervals; no >=4.
Separate continuous segments matter: frames770–842 have72pairs/net+1;
frames843–6459 have5616pairs/11242bins/net+10 against two bins per queue.
Under complete normal RunFrame accounting, endpoint phase uncertainty is less
than one bin, so it cannot explain the latter excess. This is a diagnostic
lead, not exact per-pause timing or a causal proof. The former phrase "no guest
gaps" meant only no individual >=4-bin gaps; it did not exclude smaller delays.

Independent review identifies persistent drift candidates1309/1507 first.
Their retained cycle intervals contain complete native dispatch/phase reports
but not scheduler timestamps at each queue completion. The shared backend
already exposes guest_clock(); add that read at the existing queue boundary
only if retained call data cannot resolve the timing. Keep host CPU costs
separate, preserve failed manifests and thresholds, and do not repeat the same
long route until the observation can distinguish short delays. D1 stays open.

## Exact queue clock — host and first live sample

The existing authenticated main-queue callback now reads guestQueueClock using
the melonDS native scheduler clock, before field/control reads. Both available
and absent field samples retain a detached receipt. Invalid version, running
state, scope, unsigned64 timestamp or native exception latches sample_error;
endpoint snapshots cannot manufacture a queue timestamp. No ROM edits.

47host checks passed in0.050seconds: test_devtools_queue_clock,
test_devtools_runtime.CompletedFieldAvailabilityTests,
test_devtools_field_availability and test_devtools_sampler_costs.

Root-owned session-h6nk01oj used3099/test.sav, prepared only party1 HP21/status0
and Cyndaquil Follower155/PID2046726716. Idle identity verified at800, map33,
player585/406; no mount. New clock readback is live, running and version1.
record.start rejected maxEvents6000 before mutation; retried within documented
4000bound. Commands UP64/NONE8/LEFT160/NONE8/UP40/NONE8/LEFT104/NONE8
reached585/396 then576/396 and remained blocked. This duration-only path is NOT
the typed route and cannot prove normal travel; do not repeat it. Use existing
player-step-count/player-settled-at actions next.

Retained recording-b136318d46cb.json in session-h6nk01oj:
SHA256856b45170f9a6d7f26aea22e6938d0f6e67f7753dccad4c8b3f528ed267eb47d.
403snapshots801–1203,1443events, no drops/truncation.402 consecutive clockpairs,
median2242518.5ARM9ticks; largest moving pair836–837 is3006460ticks/3nativebins
at585/398→585/397. This proves the transport reads finer timing, not the cause
or exact displayed pause. Recording stopped/exported; private session closed.

Source investigation finds240unused metatile reads for surface-only mask448
(ROOFTOP|SIGNPOST|MAILBOX) in the normal destination scan. DoesAllowedTileMatch
uses surface queries alone for that mask. Candidate-order/RNG/occupancy parity
must be proved before removing reads; same-input native timing must show benefit.
No product change made. Keep this lead separate from a proved stutter fix.

## ROM3100: cheaper surface-only search, remaining delay preserved

Prefix recipe initially omitted the full raw cadence reader. Run
test-eb9cd144e22e43a8ba14dad002a35aec failed at842/72observedframes when generic
binding rejected the old follower fieldEpoch. This is a test setup fault, not
a game failure. Restored original unmounted-cadence-v1 and diagnostic host-hitch
continuation; no binder, movement or threshold change. Prefix parity checks
exact7setup+32actions against the full route. Its expected final full-route
incomplete result is diagnostic-only, never accepted proof.

Unchanged baseline test-eed4945c5f554b3a8a94ee90006e2013 on3099 completed39actions,
768observed/724activeframes,85tiles/3cells/2maps,133follower motions in47.685s.
Both actors terminal and no pending recovery; only full-route completeness
fails.766exact clockpairs: median2239950.5ticks, max3235915(846–847);1505–1506
has3172707ticks and1307–1308 has3109685ticks despite only TWO native bins each.
Observations SHA7dc50e9df8b211996b14b94b6f6269d2ff8402f0a568cdbe3870a6acfe4b95f4.

Actual-C test first fails15surface-only masks:240metatile reads rather than0.
Four other checks pass, including chosen candidates/occupancy/RNG traces and
147456matching decisions. Independent source review verifies vanilla terrain
lookup reads loaded data without loading it. Product edit skips only unused
GetMetatileBehaviorAt calls for nonzero masks wholly inside SURFACE_ALL.
Zero/mixed/native masks keep their original reads. All5scan tests now pass;
the count check covers all1024masks. Exact-clock diagnostic12tests also pass.

Workshop build3100 passed54s, runAfterfalse. Source and Delta/test3100.nds SHA
cbdad736ba27818585b77db5bb1c8349b36bc59cf5398eeae8e73a17518ecdad match;
test.sav and test.dsv hashes remain unchanged. Doctor passes.
Same prefix test-5c8eb778b2474a74b27836bec6fc7b2b completes the same39actions,
768/724frames and133follower motions in48.203s, with the same expected incomplete
terminal result. Observations SHA11a3460fc46102513e6daf512ea3a955445039a3bbec6d56da2ded5dcb62c4f2.

| Search frame | ARM9 ticks3099 | ARM9 ticks3100 |
| --- | --- | --- |
|847|306547|209279|
|851|311893|217136|
|1241|292143|199316|
|1308|374697|302984|
|1407|283612|188462|
|1506|344522|265031|

All six have identical frame, mask448, finalization ID, success/failure and
destination bytes. Cost falls19.1–33.5%, but cumulative excess remains+4bins
and max queue interval only falls3235915→3138492ticks. This proves the narrow
cost reduction, NOT a complete rare-stutter fix. Next isolate remaining queue
work/wait timing before another broad soak or speculative optimization.
All private sessions closed without errors; no images or extra ROM history.

## Remaining delay: saved search time is repaid by the following interval

Hash-verified3099/3100 prefixes have1307→1309 totals5638513/5638508ARM9ticks.
At1308 the saving71687ticks is followed by71682extra ticks at1309.1505→1507
totals5643265/5643301:79630saved then79666added.1307→1343 still exceeds the
two-VBlank pace by1114719ticks in both runs;1505→1537 by992871/992875.
Same context/owner throughout. This is not a whole-pause improvement.

Next bounded shared probe: entry/return clocks of the two stock VBlank waits,
plus the branch counter. No global wait hook or new emulator driver needed.
Static resolution against base/arm9.bin, build/arm9.bin and3100 packaged ARM9:

| Site | Address |
| --- | --- |
|Counter branch|0x02000DF4|
|Conditional wait entry/return|0x02000DFE /0x02000E02|
|Mandatory wait entry/return|0x02000E1E /0x02000E22|

Existing main queue return is0x02000DEE. gSystem0x021D110C, frameCounter+0x30
(0x021D113C), reset0x02000E28 after mandatory return. Require r4==gSystem at
branch and r0==r1==1 at call entries. OS_WaitIrq ARM target0x020D0E6C.
Authenticate loaded and packaged ranges against expected bytes before taps:
0x02000DA6/2bytes=2f4c;0x02000E64/4bytes=0c111d02;
0x02000DF4/54bytes SHA337b3f60a1e691670118490d97192703f490fcff5232b2a6d1067f138bba59cd;
0x020D0E6C/116bytes SHAeb2d22331914c2668b42876093b57b22613db856cb82c72c66b91517a00eb1c8.
Capture only windows1307–1310 and1505–1508 in the same typed prefix. Read clock,
frame sequence, queue number and counter; waits include IRQ/thread scheduling,
not just CPU work. Source anchors main.c113–124, system.c20–24 and NitroSDK
os_irqHandler.c11–20. Live equality and this probe remain unperformed.

## Live stock wait probe — rare unmounted report remains open

Shared diagnostic baseline now adds five read-only call-site taps only in the
eight fixed windows above. Other sessions remain unchanged. Packaged/live code,
system pointer, call arguments, stack, monotonic unsigned clocks and matched
wait pairs are checked. QueueF wait data is published atF+1. No guest writes.
Independent review found and corrected bool-version/unsigned-clock validation.

First run7705e4 stopped at the first emitted wait event: its log envelope lacked
setupMode. This was a tool fault, not a gameplay pass. Its original manifest
and observations are retained, SHA256
ceb8d8a99469b427cb012771dc85b102e59f24ccd1e78d29287e5c9e024a085a.
The reader now uses NativeObservation._queue with actual native tap clocks.
The unchanged cadence validator rejects the saved bad event and accepts the
new installed-reader event in host checks. No validation was weakened.

Corrected run `test-c32ea5f7dd684daa9277f4a3babbc23a` on3100:48.693s,
39actions,768observed/724active frames,85tiles/3cells/2maps,133follower motions.
The live subject is FOLLOWER Cyndaquil155/PID2046726716, never Mounted.
All8wait cycles complete; zero pending hooks, failure or guest writes. As before,
the short route terminal-fails long-route completeness and final acceptance;
it is not a soak or stutter-fix proof. Observation SHA256:
04f81143b749efc9a419a60afba6cb0f0209dde35a32920309624729bc0ad086.

| After queue | Queue interval ticks | Branch counter | Mandatory wait ticks | Wait return to next queue ticks |
| --- | --- | --- | --- | --- |
|1307|3037998|1|790732|2246610|
|1308|2600510|2|1114100|1485980|
|1309|2352710|1|754094|1597930|
|1310|2138531|1|642400|1495701|
|1505|3093077|1|725043|2367604|
|1506|2550224|2|993106|1556688|
|1507|2180286|1|683386|1496214|
|1508|2218435|1|743948|1473889|

All conditional waits are absent. Queue intervals match prior3100 exactly,
as do all six destination-search costs/results. The probe did not alter guest
timing. Extra work after the mandatory wait crosses the next video boundary;
the following mandatory wait retains that delay. This does not show a faulty
double-wait or identify one wholly responsible function.
At1308, finalization342608 + prepared282869 =625477inclusive ticks. At1506,
failed finalization29329 + successful304826 + prepared273278 =607433ticks.
Nested search302984/265031 is already inside those totals; do not add it again.
Remaining post-wait work still needs attribution before another optimization.
The prior binary model-lookup trial was slower; do not blindly repeat it.

57 focused host tests pass; doctor, scenario validation and devtools-only
retirement guard pass. Both private probe sessions closed; copies removed by
normal cleanup. test.sav/test.dsv hashes unchanged. No product edit, ROM build,
commit, push, screenshot or video in this investigation turn.

## Stock main stages — recovered September10 checkpoint

Run `test-90bbe2a783b34ab5a1cdac90409949df` completed the same16legs in48.772s,
768observed/724active frames, with only expected short-route incompleteness.
All8windows include authenticated post-wait stage marks. Observation SHA256
9fc20474b82d06ef2c560a72d0e76ebe9239a2d472fe98b50df916dd3a2a0eb0.
Session-q8bybeq6 closed with no errors. No new ROM build or product change.

| After queue | Display callback | Sound | VWait tasks | Input/network | Field manager | Main task queue |
| --- | --- | --- | --- | --- | --- | --- |
|1307|63190|5772|1167|15034|1089054|1072297|
|1308|63190|5772|1167|15034|1096518|304203|
|1309|63190|5772|1167|15962|1176958|334785|
|1310|63190|8982|999|15062|1097600|309772|
|1505|65266|5774|999|15122|1149139|1131208|
|1506|63190|8982|999|15045|1088601|379775|
|1507|65266|6245|999|14981|1081627|327000|
|1508|63190|5942|1167|14896|1082760|305838|

Units are inclusive ARM9 scheduler ticks. Each row also contains96ticks for
OS_GetTick between manager and queue; raw events retain that separate stage.
Spikes are in main-task work; display, sound and manager costs do not explain
the extra cost. Spawn finalization/creation accounts for most, not all, of the
extra queue work. Next check: whether existing spawn lifecycle supports a safe
bounded split without changing identity, own destination, eligibility or RNG
selection. No split is implemented or approved as correct by these timings.
58focused probe/observer/recipe host checks passed; independent stage-address
review found no defect. This remains diagnostic evidence, not accepted proof.

## ROM3101 — ordinary spawn split, remaining rare delay

Ordinary spawns now prepare once, then create on the next maintenance update.
The stored encounter, profile and own destination are used without a second
roll. Context, manager, slot generation, surface, occupancy and saved-shiny
checks cancel stale work. Followers retain their direct selection path.
Small spatial/guard functions occupy checked existing overlay tails; no memory
limit grew. The build caught an unsafe memcpy veneer; the typed Thumb bridge
fixed it before the successful3101 build (80.068s). ROM and Delta SHA256:
`1fcaf2bf817913b7557b08f6b6e50813f4e803c05244ac54a62113bc586e41f0`.
83focused observer/queue/cadence checks,14tail checks,7actual-C spatial checks,
and the606-file devtools boundary check passed.

- Short unchanged route `test-53ddbeb79ca44c819a3cd9e80b6f4e70`:768frames,
  85tiles,133follower moves; five successful ordinary creations, same count as
  red90bbe2. Worst two-queue delay5643301→5190782ticks. Only intentional
  full-route incompleteness failed. Session ndntw2e_ closed without errors.
- First full attempt `test-a3894f97707d43589aefc8c709ca3886` stopped at preflight:
  old live control stale, zero game frames. Fresh detector control
  `test-5c0b68da7b9043d7a5cc4fd6c712563b` accepted with31frames; it detected
  injected CPU hitch and player-start stall and restored control.
- Full `test-189cb8f6f20f48d69972ce8401b75588`:5758frames,264actions,
  300.434s. Existing acceptance passes, but retained exact-clock check fails:
  5617013ticks >5601900 over queues4641–4643 (`route-087-settle`, map67).
  No spawn event occurs at4639–4644; player step925 is admitted at4642 from
  (555,394) to(555,393). Four wild Hoothoot163 are idle; Cyndaquil155 is an
  unmounted follower. Session0hztvnej closed without errors.

D1 is **not closed**. Existing acceptance missed the two-queue fault; promote
the exact-clock check, then use bounded stock-stage probes on this unchanged
route before another product patch. No screenshot evidence or mounted test.
The split preserves each prepared identity, not all future RNG interleaving:
AI can draw between stages. Source saves remain unchanged; private ROMs closed.

### Late field-update witness

`test-5d769f312ea94829a935d62e46431d02` reaches queue4645 in172.784s;
only expected diagnostic route incompleteness fails. Sessionvg3ixfeh closes
without errors. Exact two-queue delay is unchanged at5617013ticks: the added
read-only probes do not change the guest result. After queue4641, field-manager
cost rises from1114487 to2028423ticks, while main-queue cost is330653ticks.
Display, sound and VWait stages remain normal; no optional extra wait runs.

Retained step413 at2506 and step925 at4642 are512steps apart. Vanilla
`field/field_control.c` updates friendship every128steps and loops the party;
`pokemon.c` can skip each walking update with a random coin. This is a lead,
not a cause claim. Probe the existing call before editing product code:
`MonApplyFriendshipMod` ARM9 `0x0206FE90` (rom.ld), walking caller return
`0x021E7942` (Thumb LR+1). Read-only reference/binary mapping also identifies
FieldSystem_Control `0x0203E15C`, ProcessStep `0x021E7628`, UpdateDaycare
`0x021E788C`, HandleDaycareStep `0x0206CD1C`, UpdateFriendship `0x021E78E4`,
CalculateFriendship `0x021E790C`. Authenticate packaged/loaded code in the
shared observer; do not infer runtime cost from these addresses alone.

### ROM3102 — friendship cost and current game-clock result

The read-only native probe `test-61ed7104ecf342adb4cd7614835e2442` confirms
six walking friendship calls in the late field update:691126 inclusive ARM9
ticks in total. The walking-only wrapper now holds the native Pokémon lock
once around the unchanged friendship function. It keeps the original random
decision, arguments and rules. Native party validation precedes this normal
walking path; the wrapper is not a general unchecked party entry point.

The34-byte wrapper fits the existing Field overlay tail. Physical BSS addresses
stay fixed; packaged zero-filled BSS precedes the tail, and loader BSS is zero.
Shared metadata and package checks cover this layout. Three build attempts
exposed old file-boundary assumptions before the final build passed. ROM3102
and its Delta copy share SHA256
`1c35e25472a706a3908ccb8279816e14cafd367ccb211e5d2f4f903733face48`.
Focused wrapper/layout tests and package checks pass; independent source/ABI
review found no defect on the normal walking path.

- Detector control `test-1cc12f9271ff44e595479a067bf9d2fb` accepted on3102.
- Old host-CPU contract runs `test-cd4dc1bf1f8f4bd38f2646437d2aa5fa` and
  `test-4aa8baefa18b49aca09e76131ab15b59` fail after64 and191frames. Preserve
  these failures; they are not passing game-cadence tests.
- Full diagnostic `test-b8443d3b94354628bf063ca7fa3cdd2a` continues host CPU
  warnings:5758 observed/5428 active frames,85tiles,1004follower motions and
  clean terminal flags. Worst two-queue game cost5534349 is below5601900.
  The known4641–4643 window falls from5617013 to4496827ticks. All six final
  recorded party values, including checksums, match189cb8. This comparison
  does not claim a byte-for-byte match of all game memory.

All owned sessions closed without errors; source saves remain unchanged.
The full diagnostic is **not acceptance**. A separate current game-cadence
contract is required, with the same movement/identity/freeze checks and exact
game-clock budget. Keep the old host-CPU claim unproved and its data intact;
do not replace its row in place or widen the game budget. Next: freeze the
new contract, then obtain its fresh checked full-route result.

### User retest — ROM3102 stutter remains

The user opened `test.nds` and reports the stutter is just as bad, with strong
correlation to spawn work and no apparent stutter when spawn work is absent.
This contradicts closure of the original report. The separate game-cadence
contract is source-ready, not accepted, and cannot close D1. No final run of
that contract was started. The queue budget is an incomplete symptom witness.

Retained stock-wait data from5d769f has an exact fixed-return interval of
3361140ticks at queue4642, versus2240760 for its adjacent loops. Its native
`gSystem.frameCounter` is2 versus1. This separates a real late main loop from
phase changes at the queue-end sampling point. Add a small read-only fixed
VBlank-return reader, then use the existing short spawn route on3102.

Source lead, not a cause claim: `TryRefill` can attempt Headbutt, Fishing, the
preferred Land/Surf terrain and its alternate within one maintenance update
when prior attempts fail. The3101 split separates successful preparation from
creation, but does not split these failed attempts. Compare actual per-loop
timing with all spawn-attempt receipts before the next product edit.

### Fixed-loop reader — current failed refill reproduced

The baseline-only `devtools_main_loop_probe.py` reads the authenticated
post-mandatory-wait site `0x02000E22`. It has one read-only callback, bounded
windows and bounded retained state; events own the raw history. The native
counter resets atE28. Root caught a false host fixture (0→0 rather than a real
counter decrease), made it3→2, observed the failure, then removed the invalid
counter monotonicity check. The focused reader/wait/observer checks passed;
after adding the failed-refill window,61 host checks passed.

- `test-a36d26afa7a94fe0930b6aa8a1ffabbc`:52.099s,768 observed frames and761
  fixed-loop samples. Five successful creations and one failed refill keep
  normal 2-VBlank pacing. Queue843 has a 4-VBlank area-change loop. This short
  prefix does not reproduce the later spawn stutter. Sessionk7hvxlqn closed.
- Retained b8443d shows lasting slips near failed refills3571 and5667; this
  selected a bounded later window without another full acceptance run.
- `test-007553a240204f71a9d3dec6a99834a0`, recipe
  `diagnostic.unmounted.spawn-loop-prefix`:132.624s,2828 observed frames;
  normal setup and126 original actions through route063-settle. Queue3571
  takes3361140ticks/3VBlanks while adjacent loops take2240760/2VBlanks.
  Both spawn finalizations fail (312309 and29809ticks); no creation occurs.
  The owning stage row is afterQueue3570: field-manager1091056ticks and
  main-queue1214325ticks, versus roughly330000 queue ticks nearby.
  Session08y8kir8 closed without errors. Only intentional diagnostic
  full-route incompleteness/final assertions fail; no acceptance is claimed.

Use absolute guest clocks or flushed event frames to join calls to loops.
Actor-local frame3148 at this fault is not shared queue3571. Maps are
Cherrygrove67 and Route30=34 (vanilla constants); the current witness is in
Cherrygrove, one of the user's confirmed locations. The user also reports
other spawn areas and asks to verify the final ROM before closure.

Next: account for the refill cost outside finalization. Source
`TryRefill` inlines `ReconcileFollowerSelection`; selection eligibility and
`FollowerMatchesSelection` repeat native Pokémon data reads. Timed helper
calls can separate that cost from the terrain retries. No further product
patch has been made. ROM3102 remains the failing candidate, not a fixed build.

### September10 — ROM3103–3105 and rejected route reruns

-3103 follower matching uses one native read lock after selector eligibility
  validated the mon checksum. Exact identity/order/unlock tests pass; independent
  lock review found no defect. The unchanged diagnostic run
  `test-ad115a3eab7a4a3f97f79c6af07d3dfe` still has3VBlanks at queue3571.
  Queue work falls1214325→1174511ticks;135.395s,2828frames. Not a fix.
- User rejected further route-test reruns. Use bounded shared live memory
  measurements; do not reuse the old route as the next required action.
-3104 splits ordinary refill attempts across updates: Headbutt/Fishing gates
  once per series, then preferred and alternate Land/Surf in order. Alternate
  retains its original slot. At most one SpawnOne/update; no AI/timer skip.
  Context aborts clear pending work; queued successes count toward density delay.
  RNG interleaves with other actors across updates; global sequence parity is
  not claimed. No new spawn destinations, population limits or rates.
- Fixed Wild text limits required direct Thumb calls to the same native mon,
  player-coordinate and metatile entries. No limits were enlarged.
-3104 built, but bootstrap `session-g_o611b4` failed because the compiler
  inlined the now single-call SpawnOne symbol.3105 marks it noinline, builds
  and boots; this was a reader boundary failure, not gameplay acceptance.
-3105 SHA256 `fd5a2f25c4971119b731722cb32ebdb9addd70c8ae10f24cb50780cdc6bbf338`;
  `test.nds` and Delta test3105.nds match. User reports the issue remains.
- Live `session-6cflg4w3`: Cherrygrove604frames,12ordinary attempts,
  max361931ticks; mask search277276, encounter data copy2099. Initial follower
  attach makes a3VBlank loop with TryRefill1583403ticks.
  [Memory data](../../build/overworld-devtools/session-6cflg4w3/recording-e69f5a0e5b24.json).
  Route30/Cherrygrove885frame data reached4000events: partial scope, not a pass.
- Live `session-7qnxbw13`: extra call/stage measurements show initial follower
  creation1586078ticks; normal actor frame task at most732803ticks in the next
  short travel window. Area boundary1097 costs2960252ticks in native field
  update;1351 costs2027237 in queue work without FrameMovementTask running.
  [Memory data](../../build/overworld-devtools/session-7qnxbw13/recording-7cb79b124073.json).
  An earlier late2209 has new Walk intents but no SpawnOne call. These are
  distinct remaining leads, not proof that all stutter has one cause.
- All manual sessions above closed; private ROM copies removed by the service.
  Source saves unchanged.74Python boundary/service tests and61reader/refill
  tests pass, but no gameplay closure is claimed.
-18:25UTC: bounded CPU instruction-counter tool underway; max1200nativeframes,
  no screenshots or writes. Root owns service/Python; refill_remainder native
  implementation. Review/return to the game fix by18:45UTC, no broad tool suite.

### September10 —3106/3107, cold I/O ownership and next fix

-3106 changes the native party move query: first egg read validates checksum,
  then one acquired lock covers four ordered move getters. Both exits release
  only that lock.700 randomized host cases and worst-case lock/read checks pass;
  assembled replacement100bytes fits the original112byte native slot.
- Matched482native-frame CPU samples:3105
  [before](../../build/overworld-devtools/session-0zph0lcr/cpu-work-read-37b63895c459.json)
  has166677126dispatches;3106
  [after](../../build/overworld-devtools/session-r2bsmpkf/cpu-work-read-4d6740f17924.json)
  has146162944 (12.3%less). Crypto bins fall49406728→28430448. Counts are
  dispatched instructions, not time or a stutter verdict. The late loop remains.
-3107 unrolls the spawn checksum four bytes at a time, still excluding only
  bytes32–35.393228cases (all sizes0–32768, four alignments, three patterns)
  match an independent byte sum. Six metadata host tests pass. Typed direct
  native archive calls keep the fixed overlay size; no lifetime changes.
- The archive-lifetime binary checker now accepts authenticated direct Thumb
  calls as well as indirect native calls. It still requires both exact guarded
  destructors and cleared owned handles. Positive/negative self-tests, retained
  package checks and the fresh3107 Workshop build pass.
-3107 first follower cost1583839→1355102ticks, but queue818 still3VBlanks.
  [Cherrygrove memory](../../build/overworld-devtools/session-uu8s4yvl/recording-56bfd3ed2bbb.json),
  SHA256 a99639cd2e76c246dba838fea09e05e153416aee72f40f5180f5b92fbc250839.
  [Route30 memory](../../build/overworld-devtools/session-uu8s4yvl/recording-94e2366bde2f.json),
  SHA256272a84dcde5b74a8ae3ff68833eca8a8057b7438d21a25a9293b32af52a7e304;
  five late loops, no dropped events. Diagnostic scope; no accepted proof.
- Extended the opt-in shared baseline reader with seven authenticated native
  archive entry/return costs and raw caller/argument registers. It has no guest
  writes, images or guessed archive-handle identity.46observer tests pass.
- [Cold I/O memory](../../build/overworld-devtools/session-336fyxyk/recording-cce6390c4dad.json),
  SHA256540186aa31794b450a79129e98b4ba5a03ba5aecc248a3b7793732d9b5230e30:
  queue818 loads ARC28/member19 (17988bytes,298450ticks), member17
  (14016bytes,235897ticks), then follower sprite454 (92944ticks). Caches and
  object creation share the same update. This selects the next product change.
- [Route30 short I/O memory](../../build/overworld-devtools/session-336fyxyk/recording-27b4b8a0681f.json):
  two natural Ledyba creates at1174/1210 cost203854/50583ticks; first loads a
  model, second reuses it. No image or forced species was used.
- The next [DOWN200 sample](../../build/overworld-devtools/session-336fyxyk/recording-96741bb18bc4.json)
  has one late loop1295. Its [CPU data](../../build/overworld-devtools/session-336fyxyk/cpu-work-read-6fa8e42cb0aa.json)
  identifies native BlitBitmapRect4Bit (0201CF80–0201D03C; vanilla bg_window.c)
  and CARD reads during a map-header/UI change. Do not call that an ordinary
  SpawnOne stall. These are short live diagnostics, not the rejected route test.
-19:20UTC: all manual sessions closed. New source warms metadata and behavior
  in two distinct refill updates before automatic creation; pending maintenance
  is retained and the normal timer/RNG is untouched. Three host checks pass.
  Build pending; the fixed Wild slot needed same-ABI direct native archive and
  gender calls, not a larger memory limit. No gameplay closure is claimed.

### September10 —3108 short native recheck, user verification next

- Fresh Workshop build passed and copied test3108.nds. Both source/Delta hashes
  are239c55e9f833ba1d8c386773cebe7b58e8a2d3c29372f9190efa6948dd5067e1.
  Build-open preference remains off. No commit/push; current branch preserved.
- [Cherrygrove memory](../../build/overworld-devtools/session-ok1l3eet/recording-eb942b5e7cc6.json),
  SHA2563c724773eb5eea25c08d7be52d669089f6979240e10dfa3dec16c76492d3dfe0:
 121loop intervals, no interval above2VBlanks. Metadata loads at1277
  (whole refill482820ticks), behavior at1278 (289981), follower at1279
  (582292); before3107 grouped cost1355102ticks caused3VBlanks. Normal wild
  Hoothoot/Pidgey spawned; player moved555→551 at y399 under LEFT120.
- [Route30 memory](../../build/overworld-devtools/session-ok1l3eet/recording-8eac1ae40120.json),
  SHA2567a5f4c7301e1a29a113260412f02f190ec1999ff28c5e97d5fde9f4bcd649fe9:
 142loop intervals; metadata1477, behavior1478, follower1479 (583943ticks),
  natural Ledyba spawning and movement. No late spawn update. One3VBlank map-load
  update1475 occurs before warmup; this remaining pause is not erased from the
  report. Player moves y381→374 under UP140. No missing/truncated events.
- These are bounded live diagnostics with current memory identities, not an
  accepted whole-stutter scenario. Timelines/RNG differ after yielding; no
  identical random sequence is claimed. User must still check the reported feel
  in3108; D1 stays open. Do not rerun the rejected long route test.
- All owned sessions closed and private ROM cleanup completed by the service.
  test.sav and test.dsv hashes remain unchanged. Prepared follower setup took
 511queueupdates before teleport; logged as a separate setup-cost papercut,
  not a gameplay pass or a new broad tool task.

### September10 —3109 final candidate and review correction

- Helper review found3108 could force a normal refill at warmup phase2 before
  the population scheduler requested one.3109 forces only phases0/1 (data
  attempts). Phase2 returns to the real maintenance dispatcher. The helper
  checked the correction; no concrete defect remains in this bounded path.
- The host check now compiles the actual frame dispatch slice as well as
  TryRefill. Active actor + phase2 + no request yields NONE; pending DESPAWN
  stays DESPAWN; phases0/1 do not consume pending work. All three host tests
  pass. No artificial phase3 or extra RNG/timer event remains.
- Fresh3109 Workshop build passed. test.nds and Delta test3109.nds both hash
  3017b850efffc277edbfc4835343d04a55800d1d2e82de1b080a70d0a09cca98.
- [Final Cherrygrove data](../../build/overworld-devtools/session-6eypg9wp/recording-9455604470d9.json),
  SHA256a657ef5fbafc32ae7daa16b104a06eaeed0316c756ff414bde23b8f5f48eac0f:
 121loops, none above2VBlanks. Metadata1276, behavior1277, follower1280
  (582051ticks), natural wild Hoothoot present. LEFT120 still moves the player.
- [Final Route30 data](../../build/overworld-devtools/session-6eypg9wp/recording-44c8fa10539c.json),
  SHA25644944fd2b58274b02fb0e2ea0df73eb28d62c83c5511af5868d5c0f206615d22:
 142loops; metadata1476, behavior1477, follower1480 (583528ticks); natural
  wild Ledyba present and player y381→374. No late spawn update. The same
  pre-warmup map-load pause remains at1474 (3VBlanks, no actor frame advance).
- No dropped/truncated events in either sample. Both are diagnostics, not
  accepted whole-stutter proof. Ask the user to verify3109 before closing D1.
  All owned sessions closed; saves unchanged; no commit/push or main-base check.

### September10 —3110 isolates new wild work; user A/B pending

- User reports3109 still stutters and asks to isolate the issue. No further
  performance fix or rejected long route test.3110 is a temporary diagnostic,
  not a stable/fixed checkpoint: hold raw L outside menus/throws (button mode0)
  to skip ordinary wild preparation, queued commit and help-child creation.
  Release resumes the normal path. Existing actor motion, followers, shared
  cold data, despawn/reveal and streaming remain enabled. No speed change.
- An uncreated ordinary candidate is canceled on hold so the commit-first
  dispatcher cannot starve other maintenance. Saved shinies remain intact;
  help-child counts are retained. Refill keeps its density-scaled schedule.
  Explorer checked L conflicts; menu selection, Player Ball controls and L=A
  are excluded from the comparison. Raw key read does not edit logical input.
- Fixed Wild memory limit still fits. Same-ABI MapObject_IsSingleMovementActive
  call alias matches include/map_events_internal.h and rom_gen.ld0205F648.
  Four host refill checks (compiled production function and source guards),
  plus47shared observer tests pass. Observer authenticates gate code and return
  against native raw input; copied wrong return is rejected. No memory writes.
- Fresh Workshop build started1789076396.587275, passed in76seconds; source
  test.nds and Delta test3110.nds SHA256 both
  526a44a260e0e7bf98fa78cf147786444b673faa7145749042e1ecfa8ecb31d4.
  Open preference stays off. No commit/push; preserve dirty branch.
- [Switch memory data](../../build/overworld-devtools/session-svd41u6t/recording-9abb8fd4da72.json),
  SHA2563e410536e7149bc1e08314e80142591b2ec514d971f67f34365363e2d5234480.
  Same-save Continue boot, direct Route30 teleport, no party/follower edits.
  Normal80, L+UP80, L+DOWN80, UP120. No images.362snapshots,2456events,
  no dropped/truncated data. Five gate returns true while held,13false while
  released; no SpawnOne/finalization/object-create during held frames842–1001.
  New wild object creation resumes at1004. Bound Ledyba3010708691 moves
  x542→554 during first held leg; follower2920357538 and player move too.
- The return leg crosses an area boundary. This sample verifies the switch,
  not a matched-location stutter comparison or a freeze/stutter fix. User
  should repeat a small same-area walk loop released/held/released. If only
  held removes stutter, split preparation versus creation next; otherwise
  inspect still-enabled work. Remove temporary gate before normal acceptance.
  All sessions closed; verified private ROM removed; source sav/dsv unchanged.

### September11 —3110 human result and narrower3111 split

- Human A/B on3110: stutter stops while L holds all new wild-spawn work and
  returns intermittently after release. This supports a new-wild-work cause;
  it does not yet distinguish destination search/preparation from object
  creation. User suspects viable-tile scanning.
-3111 changes one variable. While L is held, normal refill selection,
  destination search, metadata/profile preparation and queue scheduling run.
  The queued result is consumed before engine object creation. Help-child
  object creation also waits. Release restores the normal creation path.
  Existing actors, followers, despawn/reveal and streaming remain enabled.
- The native observer keeps the authenticated raw-L/return measurement but
  labels this as object-creation isolation. The host test compiles the real
  refill function and requires a successful queued candidate under L. Source
  checks reject a gate in TryRefill, SpawnOne or destination search.51 narrow
  host tests pass. No fix claim.
- During the first live split check, the destination-search observer remained
  empty. Its scope expected FinalizePreparedSpawn to own the search, but current
  production calls the search before that function, inside SpawnOne. The shared
  observer now binds the search to a unique authenticated SpawnOne attempt.
  Its host control rejects an unowned search and checks inclusive timing. This
  is a tool fix; it changes no game state.51 checks pass after correction.
- Fresh Workshop build started1789078965.309123 and passed in77seconds.
  test.nds and Delta test3111.nds both SHA256
  7875cc76447b1151c097d5b0095bb9d3187eeed3fd610230e386bb198f806c59.
  Open remains off. No commit/push or main check.
- [3111 split memory data](../../build/overworld-devtools/session-mlzdgema/recording-e10eaf3ffa39.json),
  SHA2564d0f9410c7502fdcac0c4060c5071ffe1c107b123535558d8485c9b2c88aa168:
  same save, Continue, direct Route30 location. L held320frames, then released
  for160. Ten real helper preparations and nine SpawnOne attempts ran under L;
  no SpawnPreparedEncounter/object-create ran. Raw gate returned paused seven
  times. Release produced object creation at frame1084.482snapshots,2287events,
  no dropped/truncated data or definite failure. Both sessions closed and
  verified private ROMs removed; source saves unchanged.
- Route30's observed encounters retain legacy Pool position. Its preparation
  calls the helper's budgeted candidate scan: a17x17 reservoir (289positions,
 240 distance-eligible) and at most16 eligible tile checks per attempt, with a
  retained cursor and stride73. The later profile-mask scan correctly recorded
  zero calls in this sample. The human3111 comparison will decide whether this
  preparation block or later object creation owns the intermittent stutter.

### September11 —3111 human result and scan-only3112 split

- Human A/B on3111: stutter still occurs while L keeps destination search and
  encounter/profile preparation active but prevents object creation. This
  rules out later engine-object creation as the main cause. The remaining
  interval is the helper's legacy viable-tile scan or later preparation.
-3112 changes one variable. `OverworldWildHelper_TryPrepareSpawn` always runs
  `TryPickSpawnPositionForTerrain`; with raw L held it returns immediately after
  that call. Encounter data, profile resolution, finalization, queueing and
  creation do not run. Release uses the unchanged full path, including the
  existing Land/Surf fallback when the first position scan has no result.
- A compiled host check verifies: held L performs one position call and no
  encounter/copy call; released L completes a normal position hit; released
  Land keeps its no-position fallback; released Headbutt still rejects a
  missing position. The shared observer authenticates both raw key states and
  rejects a copied wrong return.52 narrow host tests pass; diff check passes.
- Fresh Workshop build started1789122328.180235 and passed in61seconds.
  test.nds and Delta test3112.nds both SHA256
  162f214cae0f3a82444644b8587eaa2136024c17d7a267c5478316f64406d765.
  Open remains off. No commit/push or main check.
- [3112 scan-only memory data](../../build/overworld-devtools/session-4phxq8pp/recording-263ce626987c.json),
  SHA25603699b97aebcba925047cad7e7b0c1ea50d62514ca016495a3a43ae823d2cefc:
  same save, direct Route30 location, L held320frames then released160. The held
  interval contains16 complete helper attempts and16 authenticated scan gates,
  all paused=true/raw511. It contains no archive, metadata, class-selection,
  finalization, prepared-spawn or object-create event. The released interval
  contains nine full helper/finalization paths and one object creation.482
  snapshots and2267events were retained with no drop, truncation or definite
  failure. The session is closed and its private ROM removed; save unchanged.
- Human A/B on3112 is now the only needed result. If stutter remains under L,
  the legacy tile scan is the cause. If it stops, later encounter/profile
  preparation is the cause. This ROM is diagnostic and cannot accept D1.

### September11 — scan cause confirmed and bounded in3113

- Human A/B on3112: stutter still occurs while L runs only the legacy position
  scan. The scan is sufficient to cause the hitch. Later encounter/profile
  preparation and object creation are not required.
- The temporary L isolation code and observer labels are removed. The helper
  now returns `POSITION_PENDING` after one eligible Land/Surf terrain callback.
  The caller retains the terrain, slot and remaining count, then resumes on the
  next game update. One logical attempt still permits16 candidates. Preferred
  and alternate terrain order, chance gates and the final fallback are retained.
  Help-child position searches use the same one-candidate update budget.
-88 focused host tests pass. Population, spawn-profile lifecycle, occupancy,
  object-access and flying-insect checks also pass. The normal Workshop build
  started1789124778.123339 and passed in64seconds. `test.nds` and Delta
  `test3113.nds` both have SHA256
  `acd420d49af2abf96401066b5df244d129bd6997748f1f0c39d93da840a20878`.
- [3113 bounded-scan memory data](../../build/overworld-devtools/session-qxhytvxo/recording-9302216911ab.json.gz), SHA256 `733aef95a4c220ccdc099091fe89f5a2ef16adab8949bdb7ac971418c9886182`:520 normal updates after prepared same-map setup.98 helper calls occur on98 unique observed frames; the maximum helper-call increase is one between consecutive observed frames. Eight complete destination/preparation/finalization/object-create paths ran, population reached five wild actors, and native observation reports no pending calls, dropped native events or definite failures. This is diagnostic support, not a human stutter verdict.
- The qxhytvxo session is closed and its private ROM copy was removed. The user
  must check normal3113 in melonDS before D1 can be accepted.
