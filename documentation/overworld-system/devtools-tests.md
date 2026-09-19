# Checked tests through the shared tools

Workshop `/devtools`, `owctl dev` and registered `owctl scenario run` use one
worker. There is no separate overworld test driver. Host/model/package checks
and battle tests are separate and remain available.

## Run and stop

Apply [session ownership](devtools.md#session-ownership), including both status
checks, before a run. Stop only your owned manual session. Review
[test selection and setup](#select-tests-and-setup) and the matching feature
recipe before boot. Check [service readiness](devtools.md#service-readiness)
for Workshop; use [first use](devtools.md#first-use) if the native bridge is
unavailable or stale. Do not fall back to another emulator.

For registered acceptance, both preflight commands must pass:

```bash
scripts/owctl doctor
scripts/owctl scenario validate
scripts/owctl scenario run <scenario-id> --json
scripts/owctl dev test status --json --summary
```

`doctor` checks ROM/save fixtures, build identity, the debug descriptor and the
shared native backend. `scenario run` performs the current packaged-fixture
checks described in [affected verification](verification.md#affected-verification).
Stop at a failed preflight. Source or package checks do not supply game proof.

Start returns a run ID without waiting for gameplay. Use that exact ID with
`test status`, `test cancel` and `test export` (see each command's `--help`).
Status and Cancel do not wait on the worker lock. Use compact status while
polling; inspect full details when needed. Read the returned terminal manifest
under [acceptance](#accept-a-registered-result). A successful start is not a pass.

After completion or interruption, read both `dev test status --json --summary`
and `dev status --json --summary`. Cancel only the exact owned run with
`scripts/owctl dev test cancel --run-id <run-id> --json`; stop only an owned
manual session with `scripts/owctl dev stop --json`. Confirm that the owned job
and its session have stopped before starting another. Never send manual input
to a test-owned session or stop another owner's worker.

Use `scripts/owctl scenario history <scenario-id> --json` for recorded attempts,
or `scripts/owctl progress --json` when resuming roadmap work. These read saved
results without launching tests or granting new acceptance. Reuse needs the
controller's current-input checks. After a checker-only change, follow
[retained proof recheck](#recheck-retained-proof). Workshop follows the current
job; history inspection cannot cancel a different current job.

For recipe diagnosis, use `scripts/owctl dev test list --json` and
`scripts/owctl dev test start <recipe-id> --json`. The shared service checks the
typed recipe; use the registered scenario for accepted game proof.

## Frame and failure handling

Every action has frame, wall-time and no-progress limits. The run has overall
limits too. A missing completed game update stops native stepping after 120
native cycles; game frames and native cycles are not interchangeable. An
actor wait watches that exact subject, not another actor's movement. A timeout
is a failed observation or setup, not proof of the reported gameplay bug.

Input steps and observation waits require their exact completed-frame count.
A neutral setup wait using a raw meter may end with more than one completed
queue in its last native cycle. Keep and check every dense sample, charge that
physical cycle once, and count every update against the unchanged action/run
limits. These samples may share a native-cycle stamp; they must still have
distinct consecutive completed-frame stamps. Per-frame checks run in order,
so a later ready state cannot hide an earlier failure. This does not permit
input overshoot or missing samples. A retained global field pointer is not
proof that its actors remain live. Before actor reads, the sampler checks the
authenticated stock readiness predicate and field-manager lifecycle. During
unload/init it retains explicit absence rows with bounded lifecycle values;
invalid code, pointers, flags or owner state fail instead of becoming absence.
Absence does not grant arrival, movement or subject credit. Native prepared
operations have their own bounded lifecycle waits plus the job's hard wall-time
deadline and Cancel. Their completed setup-frame cost is charged and checked
when the operation returns; do not assume frame-exact interruption inside a
native teleport or party operation. Setup frames never count as subject proof.

On failure, keep the first failure, CPU/call diagnostics where available, last
coherent state and append-only observation stream. Checked jobs do not capture
screenshots automatically at startup, success or failure. An image transport
failure must not hide a native failure or turn a valid observation into a fail.
Explicit manual capture remains available for the user, outside test proof.
Workshop input/play/status polling must not trigger captures either. All shipped
scenario capture settings are `none`. The structured memory data saved by
`record.start` contain native values/events, not video or screen images.
After two attempts without new evidence, change the observation or setup.
Do not increase a deadline just to keep waiting on the same stalled actor.
The stream retains a worker chunk before checking its frame counts. A rejected
chunk is diagnostic evidence, not evaluated or accepted frames; missing or
extra updates still fail. Do not discard the data needed to explain that failure.

## Storage rules

These defaults are implemented in the shared service, not left to agent memory.
New checked jobs write only `observations.jsonl.gz`, using fast lossless gzip
level1 and compact JSON. Every sample, event, rejected chunk and cleanup receipt
is retained. Compression runs outside native-cycle timing. Replay supports old
plain JSONL too, checks the compressed artifact hash, validates gzip integrity,
and enforces limits on decoded rows. Do not create a second plain export for
normal tests. Manual memory exports remain explicit, not automatic duplicates.
New exports are one lossless gzip JSON artifact (`recording-*.json.gz`); old
plain JSON recordings remain readable.

After the private core closes, the service removes only its exact verified
`game.nds` copy and records `romCopyCleanup` in the session manifest. Source
ROMs, private and source saves, manifests and memory evidence are not removed.
Unknown or changed copies, links and a failed core close retain the copy with
a reason. Historical identity records describe the tested input; a deleted
private ROM path is not retained binary evidence. Current acceptance checks
the source ROM/package hashes rather than requiring disposable ROM copies.

Checked jobs require at least1 GiB free before creating a run. Progress
boundaries stop observation below192 MiB so cleanup and failure evidence have
room to finish. `test-storage-low` is a host storage failure, not a game freeze.
These floors do not reserve disk space against other processes. Do not retry
until space is available; preserve the current terminal status if a full disk
prevented publication. The space guard never deletes files.

Do not retain extra test ROM versions or copy logs for inspection. Preserve
the evidence needed for current claims and the first relevant failure. Removing
evidence reopens that proof gap; a summary is not a substitute. Older stopped
duplicate ROMs can be reviewed with `scripts/prune_overworld_session_roms.py`
(`plan --report <new-path>`, then `apply --plan <path> --journal <new-path>`).
This manual migration tool never removes saves or evidence. New sessions do
not need that cleanup step. Host tests for storage, cleanup, replay integrity
and low-space handling are included in `verify_overworld_proof_gate.py`.

## Select tests and setup

Use the shortest setup that does not bypass the behavior under test. For
movement, cadence and stutter tests, use the shared party-edit and follower
setup tools to make the required Pokémon ready. Read back its HP, identity,
role and settled state before normal movement input starts. Setup frames do
not count toward the movement window. Label the fixture prepared; this does
not prevent it from proving subsequent movement. Do not require nurse healing
or Y-menu input unless healing or selection is the behavior being tested.
Keep those feature tests separate. This supersedes the historical nurse-route
setup requirement in the unmounted cadence and route-control contracts; their
movement, identity, timing and distance requirements remain unchanged.

Order disposable location setup before follower setup. If a later action will
teleport and follower behavior during that transition is not under test, teleport
first and then create or bind the follower. The follower command waits for the
safe release, queue, identity and idle boundaries; do not weaken those checks to
save setup time for a follower that the teleport will discard.

`test.validate` and `test.list` return `setupEfficiency`: setup action count,
prepared-operation count, budget ceilings and warnings. The ceilings are not
run-time estimates. `test.start` refuses the known unnecessary dialogue path
for `unmounted-cadence-v1` before creating a worker. Its typed dialogue waits
must be replaced by checked prepared setup; setup-focused diagnostics remain
available. This check catches the observed mistake, not every possible waste.
Before any run, name the missing evidence and why a retained-data replay or
narrow host check cannot supply it. After a setup failure, fix/replay that
failure before repeating the whole route. Do not shorten real observation
windows, hide faults or weaken movement checks to make a test cheaper.

Evaluate each candidate test, including tests inside a suite, before selecting
it. Identify its current requirement or concrete regression risk, check that
its setup matches the current system, and state what new evidence it adds.
Choose the cheapest sufficient level. Age alone does not make a regression
test obsolete; suite membership or an old roadmap entry does not make it
necessary. Skip unrelated tests for this change. Retire tests of removed
behavior and consolidate duplicate coverage, with a brief reason in the work
ledger and the owning registry updated where needed. A failing current
requirement is not obsolete. Review the touched area now, not the whole
repository before every fix. A final suite must also represent current
requirements, not preserve superseded checks merely to keep an old gate.
For legacy measurement contracts, use [reviewed requirement replacement](verification.md#reviewed-requirement-replacement)
to retain every original requirement while retiring duplicate execution.

For a changed test selection, keep one short decision in the existing work
ledger: test ID, keep/update/skip/retire, current requirement, and reason.
For duplicate coverage, name the replacement test. A scoped skip is not a
retirement and does not close the requirement. Reuse this decision until the
requirement, implementation or test changes; do not repeat a full audit on
every run.

## Keep the feedback loop short

Use [test selection and setup](#select-tests-and-setup) for routine runs.
The details below apply when diagnosing host cost or changing its tools.

After inspecting an actual host CPU outlier, use
`scripts/owctl dev test start diagnostic.unmounted.host-hitch-followthrough --json`
when an early host-only failure prevents observing the unmounted rare-fault window.
This prepared diagnostic copies the normal long route's setup, inputs and budgets.
`diagnosticContinueHostHitches: true` is allowed only with that cadence measurement
and no requirements. The first CPU failure remains latched; latest/worst costs stay
visible. Only host timing outliers continue. Guest queue delays, wrong identities,
metadata misses, invalid observations and normal job limits still stop the run.
The route completion predicate can end collection, but terminal status always fails
and controller acceptance is forbidden. No thresholds or costs are changed. Use the
saved data to locate the game/tool cause, then return to the unchanged registered
test. Do not use diagnostic continuation for an unexplained emulator CPU exception.

Before a host-cost fix, compare the failed interval's guest queue progression,
native dispatch/phase counts and callback costs with matched completed-boundary
intervals. Host CPU includes the observer and is not the DS clock. Keep a host
failure labeled as host timing unless memory data establishes a game delay.
Do not remove checks or move work outside the timed interval to make that cost
disappear. Published samples must remain detached from mutable session caches.
If the measured cost instead exposes a mismatched acceptance claim, record the
scope issue and review the original requirement; do not silently exchange host
and guest claims or relax a threshold. Keep the failure open. The roadmap's D1
checkpoint permits narrow independent proof work with that preserved failure;
it does not permit claiming the behavior fixed or starting a broad integration.

Use the [outcome-first work loop](#outcome-first-tool-work) before adding a
reader, checker, fixture or recorder-control dependency. Tool work serves the
selected game outcome; a new tool is not the next outcome by default.

`profile.owner-reader-control` is the separate native reader calibration for
`profile.follower-mounted-owner-transfer`. Both use the healthy saved Mankey
directly. The control changes/restores one Owner byte without guest execution;
the transfer uses read-only observations. The transfer gate rechecks a separate
accepted control manifest with matching source, ROM, save and reader inputs.
A manual calibration receipt or copied-data rejection cannot replace that
dependency. Neither test grants normal Select input, Hop or movement proof.
For nonraw prepared setup, party/spawn receipts carry the drained trace
events into the evaluator. It checks the full contiguous sequence against the
declared endpoint before normal observations resume. Setup events and frames
earn no assertion credit. A missing event, changed endpoint or trace rollback
fails both the live job and saved-data replay; watermarks alone cannot fill gaps.

`profile.resolve.packaged-rom-parity` is a subjectless S3 service test. One
fixed `resolver.probe` action uses the existing bridge; no nurse, selector or
movement setup is needed. The controller keeps all eight original deployment
measurements, fresh Workshop equality, exact native arguments/returns and
owned-buffer/session cleanup. Seven copied-data controls must fail for their
own reason. Those are evaluator controls, not game observer faults. Its one-
cycle floor counts native cycles containing resolver work and cannot provide
completed-game-frame, actor identity, role-caller or movement-soak credit.

`actor.inspect-current-and-stale` is a separate S3 native facade lookup test.
It binds the existing saved FOLLOWER Mankey, then resolves the bound handle for
one `actor-inspect.probe` action. Checked recipes name the subject, not a raw
handle, and permit no spawn, party edit, movement or menu detour. The native
call uses the current handle and a changed generation through the same facade.
The controller authenticates the package and all four allocation/Inspect/free
call receipts, pins the bound object and generations, compares the exact actor
bytes, and checks stale rejection and cleanup. Its floor counts native Inspect
cycles only. The `controlled-action` result gives no motion, normal selection,
all-role identity or soak credit. Host wrong-data checks and the actual stale
query have distinct scope; neither a manual probe nor an unregistered run
can replace the terminal registered acceptance result.

Saved job manifests use compact JSON without dropping fields. Accepted observer
control manifests must fit the same 8 MiB bound used by dependency lookup.
An oversized control fails publication and retains all failure data; it cannot
be reported accepted and then silently skipped by the next test.

Run the narrow host check for the changed contract first. Replay retained native
evidence before another boot when correcting a reader or checker. A manual
replay is a tool check; [controller recheck](#recheck-retained-proof) can reuse
unchanged capture inputs. At an integration checkpoint, expand host coverage.
Changed game or reader inputs then need the exact live scenario on frozen sources.

The unmounted route can meet a moving object on an otherwise clear tile.
Only the authenticated stock walking collision result `0x2` (object-only)
permits a stationary, unadmitted wait. The receipt must name the same current
player, direction, origin, target and field context. Check the full native
collision function and walking caller against the packaged and live code.
Keep every completed frame, CPU interval and follower check during the wait;
give it no active-movement credit. Allow at most 120 waiting frames and at most
18 frames between collision receipts (the stock bump timer is 17 frames).
An exact clear result ends the wait; existing admission/render/settle limits
then apply, including any unproved delay before the wait. Terrain or mixed
collision masks, absent/stale receipts, changed ownership, moved blocked
poses and already-admitted motion stalls still fail. An unfinished wait
cannot pass. Save these waits separately as `playerCollisionWaits`.
Old failed memory data without this native receipt remains failed; inferred
tile occupancy cannot retroactively excuse it.

Checked steps retain every completed-frame sample, event and native-cycle
interval. They skip the extra endpoint party/terrain scan and do not write a
second copy of the endpoint snapshot beside those samples. Setup, binding,
control cleanup and explicit manual inspection keep their full receipts. Do
not reduce sample coverage or weaken checks to save time.

The optional `threadCpuNs` interval brackets the synchronous
emulator call inside the unchanged process-CPU interval. It can distinguish
current-thread cost from concurrent process work; it does not identify game
code versus reader work or replace/subtract from `cpuNs`. Missing historical
thread values stay unknown. Invalid or out-of-process-bound values fail replay.
Each native-cycle interval can also include `callbackCosts`: bounded current-
thread CPU time in the shared native dispatcher and completed-queue sampler.
Nested callbacks receive exclusive time. These are partial diagnostic costs,
not all emulator work; never subtract them from `cpuNs` or alter hitch limits.
Raw replay checks the scope, sums and cycle bound. A timing failure cannot
replace an earlier native failure. For CPU attribution, use
`devtools.unmounted-cadence-prefix`: the same prepared setup and first two
normal route legs, with the unchanged cadence checks and no claimed roadmap
requirements. It stops at a fault or the prefix end; `long-route-measurement-
incomplete` at that end is expected diagnostic scope, not full-route proof.
Inspect the saved intervals before selecting an optimization or a longer run.

Timed steps also retain `guestDispatches`: opt-in ARM9/ARM7 interpreter
dispatch counts read once after each native frame, outside the CPU timer.
The counter uses the existing native instruction path; it adds no Python hook
or per-instruction clock. Counts exclude redirected instructions and do not
mean retired instructions or elapsed guest time. Failed frames retain partial
diagnostics, never complete proof. Compare these counts with host phase costs
to separate changes in guest work from host execution-time variation. Keep
the CPU limits unchanged; counts do not excuse a hitch. Historical missing
counts remain unknown. Raw replay rejects incomplete or reordered counts.

`hostWorkProbe` times the same64 integer updates immediately before and after
each counted native cycle, outside its existing process/thread CPU brackets.
Both receipts must contain the exact checked work result. This small host-only
probe adds no game frames, input, or acceptance credit. A slower probe supports
host execution-time variation; a fast endpoint probe cannot rule out a slowdown
inside the frame. Never subtract it from CPU costs or use it to excuse a hitch.

`nativePhases` version2 adds native current-thread CPU time and call counts for
one whole-frame scope, software3D frame rendering and software2D scanline
rendering. Render costs are excluded from the frame's `nonRender` total.
The shared timed step enables these fixed scopes and restores their prior
setting afterward. There are no per-instruction or per-Execute-slice clocks;
the retired v1 probe caused about39,000 clock reads per frame. Non-render time
still includes guest execution, DMA, audio and Python callbacks. Compare it with
`callbackCosts`, but do not add the overlapping totals or call the remaining
time pure game work. Unmeasured native work and clock overhead remain outside
the phase totals. Keep the original whole-cycle CPU check unchanged.
Every receipt has a frame sequence and complete/invalid flags. Raw replay
rejects missing phase rows, invalid scopes, sequence gaps and totals larger
than the whole-cycle CPU interval. Historical absence stays unknown. Native
synthetic controls check scope nesting and fault handling; live route control
must still detect its actual injected CPU delay after a bridge change.

Native caller authentication caches only the bounds from its sealed host ELF
symbol table. A new table or entry address refreshes those bounds. Every call
still validates the live return address and BL bytes; field/overlay changes
cannot use cached live code. This avoids a full symbol scan for each height
seed without dropping native landing observations.

Within one non-advancing snapshot, actor identity readers share the fully read
manager ID tuple. The cache is a local value discarded when that snapshot ends,
keyed by the current field, manager, object array and count. Partial scans are
never cached. Flags, matching rows, source identity and object ownership remain
live reads; native callbacks do not reuse this snapshot cache.

For spawn observer cost only, the paired diagnostic recipes
`devtools.spawn-cost-baseline` and `devtools.spawn-cost-omit` use the same short
unmounted prefix. `spawnObserverCost` is allowed only in prepared recipes with
no requirements; the controller refuses acceptance even if registration changes.
After setup, one immutable mode counts the six spawn-detail entry hooks before
scope/code checks. The omit mode skips their complete reader work; it retains
entry registrations, resolver, main sampler, semantic trace, input and health
checks. Metadata and counts are saved in every snapshot and the setup receipt.
Neither trace proves natural spawning or supplies roadmap acceptance. Compare
CPU costs only at matched game clocks with identical input, public actor/player
state and guest dispatch counts. A mismatch is an invalid comparison. Do not
subtract observer costs or change the normal route's timing threshold.

After setup, a checked job calls `observation.prepare` once under its owned
session lock. This removes only empty setup IRQ dispatchers, through the
native binding's public unregister operation. Active listeners and all other
observers remain installed. The pass advances no frames, changes no game
memory, and leaves the CPU and freeze checks intact. Its `observationSetup`
manifest receipt names removed and retained addresses and both clocks. A
partial unregister failure stops the job; it is not retried. Later setup may
reinstall these hooks, but the pass cannot repeat within the same core, which
bounds the native callback allocations. This is test overhead removal, not a
game stutter fix.

During an observation-phase `measurement-complete` wait, the job groups up to
eight frames only while its bound-subject frame floor cannot yet be met. It
caps the group at that floor and returns to single-frame checks afterward.
Setup, stage waits and input completion predicates keep exact single-frame
stopping. The no-progress check runs after each sample, including the raw
cadence path, and each group stops no later than the earliest possible
no-progress deadline. Later movement in a group cannot hide an earlier stall.
This reduces worker calls and progress-file writes, not sampled game frames.
Host controls prove this scheduling; measure a fresh frozen live run before
claiming a wall-time improvement.

Motion measurement waits watch the selected actor's commits, motion phase,
elapsed travel and native position, plus measured completion counts. Facing,
flags, sprite offsets and other actors do not extend that wait. A stationary
authored pause must fit the recipe's declared no-progress budget. Frame clocks
alone are not movement progress.

Player travel waits and held-input steps watch native X/Z travel and tile
admissions. Changing ready flags, movement commands or unrelated context fields
cannot extend their no-progress deadline. A satisfied action predicate on the
deadline frame is completion, not a stall. The shared job host controls test
both stationary bookkeeping churn and real movement/settlement. A `no-progress`
result means the declared action failed its progress contract; it does not by
itself distinguish blocked terrain from a control lock. Use the saved native
state and the scenario's known legal route to make that distinction.

Terminal manifests separate `executionSeconds` from `proofAcceptanceSeconds`;
`elapsedSeconds` includes both. Compare the same scenario and proof contract
before claiming a speed gain. Smaller files do not prove faster emulation.
After the private game session stops, status reports `phase: acceptance` while
the controller checks saved memory data. This is still an active job, not a
game stall or a pass. Wait for that same run's terminal result; do not reboot
the game. `acceptedProof` remains false until those checks finish.

## Outcome-first tool work

Select one game requirement and the next run that can advance it. Reuse its
current setup, accepted measurements and saved memory data before adding code.
Apply the [goal progress rules](roadmap.md#goal-progress-rules) across goal
continuations: test/tool work must resolve a named missing fact, and an existing
symptom-specific failure is the starting point for product diagnosis and repair.
Once the fact is available, return to that repair or its required acceptance;
do not expand the reader, checker, or coverage as a new prerequisite.
For a new observation, retain one bounded real sample through the shared tools
before building its full checker, copied-data controls and acceptance mapping.
If existing readers cannot capture that sample, add only the smallest read-only
seam needed to obtain it. Do not build the whole test stack against invented
field shapes. This diagnostic sample does not grant gameplay acceptance. It can support a
product edit only when it meets the full
[symptom-specific reproduction contract](verification.md#reproduction-before-editing-acceptance-before-closure).

Build shared measurements around stable facts: actor identity, native call
boundaries, completed-frame clocks, raw state, paired poses and motion lifecycle.
Keep the behavior's exact expectations in its contract. Extend an existing
reader or checker when it measures the same fact; do not copy a complete stack
for another behavior name. Different owners or different physical state still
need distinct adapters. For example, Wild crash displacement is not mounted
crash presentation.

Every tool task must name these fields in the current work item or helper
assignment before implementation:

- Blocked game requirement and the missing fact or exact tool failure.
- Exact next run or saved-data replay, its bounds, and the evidence it adds.
- One owner and a review point within30–45 minutes.
- Return point: the game investigation to resume as soon as that check passes.

At the review point, compare progress with that missing fact. Finish a small
in-scope correction, change the method, or report the exact blocker. Do not
silently renew a tool project or add another proof layer. Keep required work
open; the review point is not permission to skip it. Reuse the same task record
instead of creating another plan or log.

After a checker-only fix, replay the unchanged retained stream and its exact
wrong-data controls before another boot. Do not alter old evidence to fit a
new field shape, suppress the first failure, or accept generic incompleteness
as a control's intended cause. A missing native field or changed live reader
still requires new memory data. Use the controller's input and acceptance
checks below; a manual replay pass is not a new game result.

## Recheck retained proof

For rare stutter, first inspect retained guest queue spacing without a new boot:

```bash
python3 -m tools.overworld.cadence_diagnostics build/overworld-devtools/<run-id>/manifest.json
```

This hashes the owned memory data, streams it, and reports consecutive same-field
main-queue frame bins. It grants no acceptance. A1/3 pair may be phase recovery;
do not call each3 a dropped frame. A4-bin gap has a greater-than3-frame elapsed
lower bound only for authenticated normal one-frame melonDS calls, without
sleep or native bridge work. The tool does not authenticate that backend itself.
Its excess-bin total sums eligible pairs across segments, not one continuous
delay. Host CPU time and guest queue spacing are different signals. Follow the
exact reported frame/row and player state before adding instrumentation.

After a checker-only change, run one independent check in a fresh host process:

```bash
scripts/owctl scenario recheck <test-run-id> --json
```

This replays the retained run and every required copied-data control. It starts
no emulator and rewrites no manifest. Its compact `acceptedProof` is the current
controller decision, separate from the original immutable result. Read that
decision before choosing another boot. Missing evidence is not repairable by
recheck, and a new or changed live reader still needs fresh native data.

New preflights store `fixtureProof.proofInputs` with separate `capture` and
`checker` identities, using compact per-root hashes. The full source identity
remains provenance. Capture binds product/build inputs, the collector's local
import dependencies, and the selected actions/recipe. Shared or unclassified
changes fail closed. A pure checker change can reuse the unchanged capture
only after independent replay and all required negatives pass. Older manifests
without these scopes still require their original full source identity; never
invent previous hashes or rewrite old evidence to give it new scopes.

Repeated acceptance within one process uses a bounded32-entry cache. Its key
binds the artifact bytes, ROM/save/debug data, linked objects, current checker
and recipe, plus the reader dependency's current recipe and registry. It keeps
no ROM or memory-data copies. The fresh-process command above does not inherit
that cache. Entries publish only after the whole acceptance tree passes its
final input check. Changed loaded Python code requires a fresh process or an
idle Workshop restart; it cannot be labelled with the new on-disk hash.
Control lookup indexes requirements, parses only new or changed
manifests, and considers the latest64 matching controls, not64 unrelated runs.
Neither mechanism changes the required observations or grants a game speedup.

## Author an executable test

This section owns typed recipe design. Read the matching measurement details
below only for the behavior under test. For a new registered proof requirement,
also follow [scenario registration](#register-an-acceptance-scenario).

Prepared `mount-walk.configure` accepts optional `stompTime` (0..32 frames;
0 disables stomp). It changes only the current bound, idle mounted Owner's
threshold byte, with full-state and clock checks and verified rollback.
Omitting it preserves the threshold and the existing receipt shape. This is
scenario setup, not proof of normal profile resolution, dust or sound.
Existing fixed matrix routes still reject extra setup fields.

Crash arrangement uses named `turning: "locked"` and `crashSound: "wall-hit"`
on that same guarded command. Only the two Walk option bits change; unrelated
bits and all other state remain checked. Do not copy the old standalone
collector's state+0x82 write: it now addresses adapter data. A crash test must
trigger a real blocked movement. The existing `actor.crashPresentation` reader
is Wild-only; mounted shake needs its own mode/elapsed and face-offset readings.

The fixed `walk.stomp.feedback` recipe checks two mounted Cyndaquil moves:
travel time2 at threshold2, then travel time3 at the same threshold. Each move
ends with one native player step, one lifecycle, paired poses and control
return. Native dust allocation, render initialization and sound-start receipts
prove feedback; they do not prove sound from speakers. The separate
`observation.stomp-policy-control` repeats the baseline, then tests the same
reader with threshold255 and exact restoration. It cannot advance afterward.
Both use prepared setup, no Tick timing matrix and no image capture.

Use `.agents/skills/author-overworld-scenario/SKILL.md`. Source recipes live in
`tests/overworld/test-recipes/`; `test.validate` checks the complete typed
contract and `test.save` creates a new file without overwriting one.

The authoritative schema is `tools/overworld/devtools_test_contract.py`.
A recipe declares its expectation source, fixture, mode, subjects, setup,
actions, assertions and budgets. Supported actions use shared step, wait,
assert, bind, teleport, spawn and party operations. A step's optional `until`
predicate stops at the first matching completed frame and releases input.
Use it for a measured target or motion boundary, not a guessed key duration.
Unknown fields, missing observations and stale actor identities fail closed.

For normal walking routes, use `player-step-count` to stop held input at an
observed stock tile admission, then `player-settled-at` to wait for the exact
map/tile, rendered center and stock ready flags. Admission is not completion;
do not count it as finished travel. The previous tile can still be the origin
of a finished held move. Same-frame extra admissions remain visible and must
not be rounded away. `party-field` and `selector-field` inspect coherent public
values, so normal healing and Y selection need no prepared state writes.
For pre-bind readiness, `actor-count` permits `"motionPhase":"IDLE"` on the
same current verified subject candidates. Missing identity/phase fails; an
actor still moving does not satisfy the idle count. Follower ball return is
not an idle test: normal follower AI can resume before the ball returns.

`world.cyndaquil-normal-setup` is diagnostic setup only. It uses the saved
slot-1 Cyndaquil, normal Center/nurse input, normal Y/R selection and a verified
idle follower bind. Its meter records healing first seen inside the Center,
then separately requires a fresh same-Pokémon native HP getter receipt from
normal gameplay. A later selector call may provide that receipt outdoors.
It does not grant the long-route, cadence, CPU-hitch or 5000-frame claims.
Its transition specs explicitly require `automaticSteps:["entry-up"]` and
`automaticSteps:["exit-down"]`. Each named stock step needs exactly one native
receipt, the same live doorway task, the exact origin/target, command and
bounded in-tile pose. Receipt loss, duplication or another admission fails.
The earlier Center-only diagnostic checks landing/control, not these receipts.

`world.cyndaquil-prepared-setup` is the short movement-fixture diagnostic:
check the saved slot-1 identity, edit HP/status, read back HP, select that
follower, wait for IDLE, bind and collect one frame. It does not prove healing,
Y input or cadence. One passing setup cannot clear an intermittent setup fault.
Prepared party/spawn receipts keep excluded setup events and a completed trace
boundary. Pending next-frame events stay queued; the trace is not reset.
Checked jobs retain the full worker receipt, not just the manual UI summary.
The cadence meter accepts these exact saved-Cyndaquil setup commands before
binding, with no movement/CPU credit. Later mutations, changed Pokémon and
missing readback still fail. Ordinary movement checks retain their limits.

`dialogue-state` is a read-only wait over the same completed frame. Its `state`
is one of `idle`, `busy`, `printing`, `page-wait`, `yes-no-ready`, or
`script-button-wait`. The native reader binds the current field task, script
context, printer window and menu owner; stale frames/fields fail. Unknown
ownership cannot satisfy an input wait. `yes-no-ready` means the Yes cursor,
not merely that a menu exists. Read `dialogue.waitIdentity` and release input
after one A edge; require that wait to change before sending another edge.
Never send A during healing, movement, printing or unknown state. A dialogue
result is setup state, not proof of healed HP or accepted follower selection.

Setup `step` and `wait` actions may declare a typed `skipIf` predicate. Use
`actor-present` to stop new route input after the real subject appears. Held
input is released at the previous action boundary; the current tile can finish
normally. Skipped actions retain their actual snapshot and condition. This
cannot skip observation actions, binding, or prepared operations.

The optional measurement declaration
`{"kind":"chain-retry-v1","subject":"ledyba"}` runs the separate controlled
retry witness. Its prepared test first acquires natural Ledyba and proves a
normal spawn Hop and eligible move. The typed `chain-retry` action then denies
one naturally selected action-5 prepared start with the native PROFILE result.
It changes registers only at the authenticated entry, not guest RAM or RNG.
The outer native caller must restore the exact pending action/ticks and cooldown1;
completed-frame memory reads must show an unchanged idle pose, pending action,
commit count and no input/reservation ownership before retry. The same update
can consume cooldown1, so its completed snapshot may read zero. Require the
native parent return with cooldown1, the completed idle frame, then a later
completed frame's retry with cooldown0. Native `data.frame` is the last completed
frame at call time; the outer event frame is its completed publication boundary.
Keep both clocks and their ordered native cycles; never overwrite one with the
other. Missing idle evidence fails at retry, not at the full test deadline. All four
profile-derived legs, native boundaries and terminal control must follow once.
The normal meter keeps its normal-only default; only this checker accepts the
one declared transition to controlled observation. Run
`chain.pause.counts-semantic-moves` after current live reader calibration.
The old forced nine-Walk/fixed-frame rows remain in
[`archive/chain-retry-legacy-measurements.json`](archive/chain-retry-legacy-measurements.json),
not in executable setup. A ported recipe is not an accepted run.

### Acceleration setup and terminal readings

`walk-policy.reset` is prepared setup, never acceleration proof. In a checked
recipe it takes a declared, already bound `subject` name and is limited to the
setup phase. Direct shared commands take the full current subject and all three
generations. The native tool must reject active or staged motion, stale identity,
and missing readiness observations before RESET. It uses the existing public
Walk reducer; it must not write arbitrary momentum or profile values.

The native Walk COMMIT receipt retains the exact lane and before/after policy
bytes. This call returns before the actor acknowledges its logical commit;
join it to the later same-motion commit, finish and control-return events.
Mounted movement uses the player anchor (`anchorPointer`), not the Pokémon's
`engineObject`. Keep both identities. Idle Mounted input ownership remains1;
Wild ownership returns0. These observations and setup support the pending
seven-commit parity scenario; they do not activate or accept it on their own.

`acceleration-parity-v1` declares one Wild and one Mounted subject. Prepared
`acceleration.begin` calls the checked RESET and starts that subject's exact
memory-data window. `acceleration.end` requires seven complete Walks and no
pending motion; it advances no frames. Setup between windows earns no movement
credit. Every frame inside each window remains required. The controller checks
both RESET calls against the packaged service and linked reducer independently
of the motion checker.

For a bounded controlled Wild route, `walk-intent.arm` takes the bound subject,
direction0–7 and a maximum1–600 completed frames. It changes only the direction
argument at the normal Walk entry; profile direction permissions, planning,
collision, timing and acceleration still apply. Busy Walk entry attempts keep
their native arguments and earn no input credit; they are not new admissions.
Only an actual accepted Walk
counts. After seven starts, busy calls still run untouched. Only a new idle
admission returns false to refuse an eighth start. Closing requires the seventh
terminal and the exact subject receipt captured at arm, not its older bind time.
The retained control receipts distinguish refused inputs from completed moves.
This is controlled direction input, not evidence of natural AI direction choice.

Choose fixtures from the complete resolved lane, not frame values alone.
Flying insect/Ledyba has acceleration disabled. Mewtwo's8-frame Owner lane has
no movement. The authored Wild/Mounted Onix lanes instead match at16/3/2 with
acceleration enabled. That pair tests shared acceleration, not Cyndaquil-specific
behavior. Preserve all four original parity measurements and all14 lifecycles;
the fixture correction must not weaken them or alter authored game profiles.

The opt-in Walk-policy reader control changes one counter byte only while the
guest is stopped at COMMIT. It reads clean/bad/restored data through the same
reader, checks all32 original bytes after restore, and returns only the clean
value to normal observations. Any uncertain restore stops the worker. This
control is registered as `observation.walk-policy-control`. Its terminal
manifest must have accepted proof before acceleration uses that reader result;
host tests alone do not establish recorder acceptance. The Onix setup allows
180 frames for the native follower release and mount (155 observed); these
setup frames earn no movement credit.

RESET has two different boundaries. Its guarded native before/after snapshots
remain unchanged call evidence. The outer command returns the first actual
completed field snapshot through the shared sampler, not a raw memory snapshot
with invented completion flags. Startup allows the same or next completed frame
only: unchanged actor/profile/anchor/pose/commit, matching actor-clock advance,
continuous retained events, and no intervening selected motion. It seeds clocks
from that completed frame and grants no movement credit. Its bounded native
profile cache can supply RESET profile binding; source bytes, fingerprint and
override mask still require exact validation. The initial pre-setup field can be
normal, but RESET and measured windows must be prepared.

Exported motion keys and trace maps use JSON-native lists and string keys.
Independent replay must equal the saved evaluation after a JSON round trip.
For consecutive mounted Walks, an exact endpoint may be sampled one boundary
before commit and successor start. Keep that actual endpoint pose. An adjacent
elapsed1 successor must match the full handle, profile, committed origin and
exact linear pose before the recorder can use the prior endpoint as terminal
render evidence. Missing endpoints, elapsed2 starts and skipped frames fail;
the successor pose is never evidence of the preceding target.
Retain rejected initial raw boundaries before stopping, as with later chunks.

The first completed Walk update may already have elapsed1. Keep that raw value,
the preceding settled pose and same-frame native start event; do not invent an
elapsed0 sample. Later samples and terminal events must remain complete. A
ring-overwrite notice with zero unread loss reports replacement of already
retained records, not missing evidence. Real loss or sequence gaps still fail.

The optional measurement declaration
`{"kind":"ledyba-chain-v1","subject":"ledyba"}` in `measurements` enables the
pure shared-stream Ledyba checker. It requires a normal, newly spawned WILD165
subject, the current authored schema/source, a real nested spawn Hop receipt,
and every completed frame from setup onward. `measurement-complete` names that
measurement and requires both its complete behavior and the recipe's bound-subject
`minObservedFrames`. The normal Ledyba witness now observes at least5000 continuous
subject frames and at least three complete selected chain actions. Earlier ready
results do not freeze the meter or stop that longer wait. Keep the measurement
wait: a plain `frame-count` wait watches the global clock, not this actor's motion.
After each fully returned motion, the checker also rejects an open chain longer
than its authored maximum without an observed chance boundary or valid lane reset.
If eligible normal movement returns before all selected reposition legs finish,
the checker fails immediately as `reposition-action-truncated`; later good chains
cannot repair that lost action. A pending action with unfinished legs is not yet
truncated, and stop/turn skids do not count as eligible resumed movement.
The checker excludes spawn and skid/reposition from normal move counts; it
checks the captured lane, observed chance draws, flat skid pose, duration,
facing and terminal control. These measurements alone do not grant S4 proof.
Retain the full shared stream and use the controller's exact acceptance gate.
An explicit policy RESET has no lane state. Only the next real IDLE INPUT may
explain it as a lane change, with the same actor, commit and chain boundary and
no intervening movement or decision. An unresolved reset blocks completion;
a confirmed count, reset or completed-motion error stops the job immediately.
The existing native Walk-policy hook also retains authenticated chain handoff
operations9–13 (take, begin, advance, finish, put). These include rejected
attempts and are diagnostics only: neither return value counts as a move,
chance draw or completed action. They cannot excuse a previous RESET as a later
lane change. Keep these receipts to distinguish stalled retries from missing
updates; a retry receipt alone does not explain landing/surface rejection.
The shared observer also emits one bounded `chain-reposition-attempt` record
per returned native candidate search. It pairs at most eight landing checks,
each with at most one prepared start and one typed motion request with the same
actor and world identity. Only the final start may succeed. `outcomeStage` separates exhausted landing search, rejection before
motion admission, a typed motion rejection and an accepted start. An absent
request is never interpreted as decision0. These are diagnostic stage results,
not proof of physical terrain or a completed skid; full motion checks still apply.
Each prepared start also retains at most one `hopPlans` entry from the actual
public Hop planner: its 48-byte input, decoded origin/target/base heights,
lane, operation, input/output trajectory and typed return decision. The hook
runs only inside that chain start. Caller code, actor identity, input stability
and return order are checked. An early failure with no plan keeps an empty
list; it is not an accepted plan. A motion request without a returned accepted
plan fails observation. This separates path rejection from motion-admission
failure without reading images or treating a legal endpoint as a clear path.
Each landing now retains up to two native surface queries, one terrain-match
result and one occupancy result. These calls are observed inside the exact
landing check, before another actor can move later in the same frame. Surface
hits retain their catalog height value, surface ID/type and node. For Canopy,
that catalog value is the relative tree-top offset; the paired native height
refresh resolves the final support height. A failed query has no initialized
hit. `occupied` and `terrain-permission-rejected` use actual
native return values; `pre-terrain-rejected` and `surface-validation-rejected`
do not pretend to identify an unobserved branch. Nested helper calls are not
counted twice. These readers add no per-candidate object-manager scan.
Version2 attempts also retain the actual four-byte chain result and typed
landing/start decisions. Zero means accepted; explicit `accepted` fields avoid
Boolean inversion. Native command flags at start entry explain an
`ALREADY_ACTIVE` rejection before planning. Missing entry flags cannot justify
that reason. Historical memory data retain their old shape, with no invented
typed reasons.

The Ledyba meter accepts an aborted action only from an explicit native
`ABORT/NO_CANDIDATE`, every enabled unique candidate's structural rejection,
the same actor/profile/world, a successful FINISH handoff and returned native
control. Occupied, busy, reserved or unknown candidates cannot justify abort.
Executed legs still receive all movement checks. `abortedActions` never count
toward the three required complete four-leg actions or replace the5000-frame
floor. Old partial-action failures without this evidence still fail.
The stop boundary need not be an idle frame. A completed fourth skid may share
its terminal frame with the next motion's first elapsed-zero sample. The meter
retains that successor separately and gives it no completed-motion or chain
credit. It requires the same full handle, matching origin/terminal pose and
commit, exactly one current-frame sample and one start receipt. All predecessor
travel, pause and terminal checks still apply. A later or incomplete successor
cannot use this boundary; the full raw stream is retained.

The separate `pool-spawn-v1` measurement checks one normal Wild Ledyba's own
encounter-pool site through its complete first spawn Hop. The registered
`spawn.ledyba-pool-site` now uses the stronger `pool-spawn-surface-v1` below. The normal
route is unchanged; the test does not inject a species or destination.
The finalizer tap retains initialized input bytes before placement and the
successful prepared output afterward. One same-frame, single-use receipt must
match the spawn's exact buffer, slot, world context, encounter and final PID.
The final PID may legitimately differ from the input PID. The winning Owner
layer comes from matched/forced masks, not Active/Tired's combined applied mask.
Only unconditional legacy POOL with no tree-top exception is in scope.
The test compares the incoming site, finalized site and actual completed Hop;
it cannot call a new site correct merely because startup copied that new site.
Controller controls cover missing provenance, changed POOL input, wrong/stale
subjects and each missing start/terminal meaning, including setup-time events.
Its S3 result does not prove physical surface legality, later mobility, chain
actions or visible arc quality. Those remain separate requirements. A Surf
encounter authored as Ledyba must not silently become a land-only test.

The registered `spawn.appear-hop-timing` test checks the separate `APPEAR_HOP`
startup. It uses one prepared native Wild Clefairy spawn and retains the exact
finalized identity, resolved startup mode, engine command order, rendered
same-tile arc, and controller state. The jump, delay, restore, and idle commands
must be contiguous. `CHILL` must start on the first completed idle frame after
restore; the timeout is only a stuck-command fallback. Prepared setup does not
prove natural population selection or other spawn locomotion modes.

The shared spawn observer also records `spawn-landing-height` at the same
encounter's final own target, nested under its spawn Hop. It retains the actual
surface query result, initialized surface-hit bytes only on success, native
height-refresh result and positions, and point-only loaded-terrain provenance
before/after the call. Intermediate height-seeding tiles do not become landing
receipts. Wrong object, encounter, target or changed world/model data fails the
reader. Missing terrain or a failed refresh remains unknown. This receipt alone
does not prove the terminal pose, physical legality or absence of uncatalogued
solid geometry; the matching measurement and live reader controls are required.

`pool-spawn-surface-v1` retains all own-site requirements and adds loaded
metatile permission, authored-surface exclusion, a successful native height
refresh and equality with the same actor's terminal Y. The shared spawn meter
requires the native field-object creation call to use the off-screen origin.
It also requires the elapsed-zero actor and engine render positions to equal
that origin, not the landing target. This rejects a one-frame landing flash
before later path and terminal checks can hide it. Its preflight requires
two separate current calibrations: `observation.live-actor-and-motion-control`
and `observation.spawn-height-control`. Both must pass before the normal
`spawn.ledyba-pool-site` run; they do not supply normal-play credit themselves.

The `live-spawn-height-control-v1` test uses the same normal route. It arms
after boot, before route input. At one authenticated native height-reader
return for the actual Wild Ledyba, it reads clean state, changes only four
native Y bytes by4096, uses the same complete reader, restores those bytes in
`finally`, then reads again. No guest instruction executes between those
reads. A restoration failure exits only the disposable worker even if error
logging fails. Source, object, world, own target, all four tap clocks and the
next completed-frame publication must match the clean height receipt.
After the complete clean spawn, the unchanged surface checker must reject
the measured bad Y for the exact terminal-height reason. Controller replay
also rejects absent/stale subjects, missing fault meaning and changed restored
data. These copied-data checks do not replace the native wrong-Y read.

The separate `live-observer-control-v1` measurement uses the same natural
baseline, then freezes that passing result. In `observer-control` mode only,
typed actions `observer-control` name the bound subject and one fixed fault:
`render-stall` or `inactive-object`. They cannot take an address or raw value.
`measurement-stage` waits for `baseline` or `render-detected`; the final
`measurement-complete` waits for both actual reader rejections. Native writes
are applied before the same completed-frame sampler. Two stalled render frames
and the inactive frame remain in the stream. Only that exact, recorded inactive
fault may explain its current identity failure; other stale actors still fail.
The explicit same-frame cleanup row must prove the owned active bit was restored.
It does not add an observed frame or reset the failed render recorder.

The registered `live-route-control-v1` recipe is a separate calibration of the
unmounted player/follower recorder. It reuses the normal cadence meter for
four completed player moves, a held segment and one complete Cyndaquil motion.
Checked prepared party/follower setup is excluded from that baseline. Its
typed `observer-control` actions permit only `cpu-hitch` followed by
`player-start-stall`: measured process work inside one native cycle, then
live player X/Z held at that admitted step's own origin before sampling.
The unchanged classifiers must detect the exact delayed cycle and start stall;
unrelated failures remain failures. Neither fault earns normal movement credit.
Cleanup releases input and marks the altered session for disposal, not resumed
play. Controller acceptance replays the full memory data and checks the saved
baseline pose, complete follower lifecycle, actual CPU samples, fault receipts
and same-frame cleanup. Nine copied-data controls must fail for their own
identity, lifecycle, CPU, pin or cleanup defect. Only a current terminal
`acceptedProof:true` grants calibration proof. It does not replace the full
route or Ledyba control and cannot satisfy their observation floors.

`world.unmounted.long-travel-cadence` binds a prepared saved Cyndaquil fixture,
then measures normal input without interventions. This exact adapter can prove
normal movement; it cannot prove the setup triggers. Other prepared recipes
remain controlled cases. Acceptance retains all ten original measurements,
including at least5000 actual moving frames,80 tiles,3 cells and2 maps. It
replays every retained frame, rechecks CPU samples, terminal poses, rebinds
and complete crash restoration, and requires a separate current route
calibration. Eight copied-data controls must reject their own subject,
lifecycle, CPU or player-progress fault. The job also records successful
owned-session cleanup; missing or failed cleanup blocks acceptance. A current
registered pass is required; a retained diagnostic replay is not live proof.

The route also stops at the first guest main-queue delay: consecutive authenticated
queue samples in the same idle field context separated by at least four native
frame bins. This proves more than three frame periods between updates, regardless
of endpoint phase. A three-bin/one-bin phase pair alone is not a failure. This
guest clock check is separate from host CPU timing and actor pose checks; passing
either of those cannot hide a missed guest update.

The four-bin check is conservative: zero such gaps does not exclude shorter
delays. Completed queue samples also retain `guestQueueClock`, with exact
ARM9/ARM7 scheduler timestamps from the active native callback. Do not subtract
across CPUs or use host CPU time as this clock. Endpoint reads cannot supply
this field. Invalid clock receipts stop the reader, including during field
absence. `python3 -m tools.overworld.cadence_diagnostics <manifest>` reports exact
ARM9 intervals and the eight longest pairs; missing old clock data is explicit,
not zero delay. The registered unmounted full route also uses the shared exact
clock reducer during acceptance: two consecutive queue intervals must not exceed
5,601,900 ARM9 scheduler ticks (five native periods). Missing clock coverage
fails closed. This is a symptom-specific limit, not a rendered-frame claim or
a universal game-speed rule. The standalone diagnostic cannot grant acceptance.

Keep host process cost and game cadence as separate claims. A new game-cadence
contract must retain the full route, actor checks, freeze detection and exact
queue budget. It may keep host CPU hitches as raw diagnostic data without
claiming host pacing passed. Do not relabel or supersede the old host-CPU
requirement: it remains unproved when that check fails. A diagnostic run that
continues host warnings cannot become accepted evidence for a new contract;
use a fresh registered run after its checker and negative controls are frozen.

For a short timing comparison, `diagnostic.unmounted.queue-clock-prefix` retains
the full route's setup, first16legs, tile-count stops and raw cadence reader.
Its terminal full-route-incomplete failure is expected: this prefix cannot
grant gameplay proof. Generic actor binding cannot substitute for the route
reader across area changes. Do not replace tile stops with timed held input;
the manual route can hit a wall and stop covering travel. Compare the same
recipe, live subject and spawn outcomes as well as measured cost.

The prefix now selects the existing `spawnObserverCost: baseline` diagnostic
mode to observe the stock frame waits. It keeps all spawn readers, movement
inputs, profiles and budgets. The wait probe reads only after queues1307–1310
and1505–1508, plus4639–4644 for the remaining late field-update delay.
`diagnostic.unmounted.queue-clock-full-route-prefix` keeps the full route's
exact setup and first87legs through that window; it is diagnostic only.
`world.unmounted.spawn-zero-stutter` replaces the old
`diagnostic.unmounted.spawn-loop-prefix`. It loads the current `test.sav`
without changes, binds the existing Follower Mankey, and follows the sealed
Route30-to-Cherrygrove route. The strict window starts after the map seam. The
main-loop reader samples the mandatory VBlank-wait return at `0x02000E22` on
every strict update. One interval above two frame times fails immediately. A
complete pass also needs a joined normal search/finalizer pair with matching
attempt, finalization, slot, and map identity, at least2600 strict intervals,
and at least1800 moving frames. The test captures no images.

Its `stock-main-loop-pacing` event measures loop pacing, not visible pixel changes.
The raw `gSystem.frameCounter` resets each loop; it is not a monotonic clock.
Only compare adjacent loops in the same declared window. Correlate spawn calls
by absolute guest timestamps (or their flushed queue frames), not by equating
the actor's local frame counter with the shared completed-queue frame number.
Events own raw history; the probe retains only bounded summary/previous state.
Its `afterQueueFrame` identifies the wait's owning loop; the next
queue publishes the event. These scheduler ticks include interrupts and thread
waits, not just CPU work. Missing or unmatched waits are an observation fault.
Each window also retains ordered marks after display, sound and VWait tasks,
around the main field manager, and before/after the main task queue. These
separate the measured work from the frame waits without changing game code.
Use the saved marks for cause finding. The registered zero-stutter scenario is
the acceptance rule; the stage marks remain diagnostic and are not a fix.

### Cheap spawn-work gate

Spawn, population, destination-mask, profile, or generated-profile changes use
one fixed order. This prevents a long emulator run from finding a source-level
batching error:

1. Run `python3 tools/overworld/test_spawn_refill_budget.py`.
2. Run `python3 tools/overworld/test_spawn_destination_scan.py`.
3. Stop if either extracted-C check finds more than one costly candidate query
   in one update. Fix the production scanner before starting melonDS.
4. Run `population.spawn-work-budget` on the current ROM. Its fixed Route 30
   path must keep the player moving during the scan. Require exactly one
   profile resolution and one metadata/class preparation for the complete
   automatic attempt. Later scan updates must reuse that prepared result. The
   copied repeated-preparation controls and the slow-resumed-finalizer control
   must fail for their matching reasons. The same short run must record every
   stock main-loop wait through the first post-spawn loop. Require zero loops
   above two native cycles and reject ARM9 intervals above the sub-VBlank hook
   margin (`2800950` scheduler ticks), at least 120 in-transit
   player samples, and zero repeated exact player positions during those
   samples. The copied one-late-loop, frozen-position, and missing-post-spawn
   controls must fail for their matching reasons.
5. Run the full unmounted cadence failure window only at the owning integration
   checkpoint and final frozen candidate, or when the short gate fails to match
   the reported symptom.

The destination test covers legacy Pool and profile masks `8`, `448`, `512`,
and `15`, preserves selection/RNG semantics, and includes a known-bad
two-queries-in-one-update control. The live scenario observes one natural
helper-to-explicit-scanner handoff and one complete explicit scan. It rejects
both batched tile queries and repeated full spawn preparation. Repeating
the full deterministic mask matrix in a random live run adds no proof. An idle
route or population count alone cannot pass. A pass belongs only to its ROM and
relevant proof inputs. A later spawn/profile/population edit makes it stale and
an unresolved player report keeps D1 open even when this narrow gate passes.
reopens D1 before more D5 work.

Native receipt counters and cached profiles belong to their completed-frame
watermark. A later paused native endpoint must not replace that watermark.
Missing, reordered or unframed receipts fail the measurement rather than being
discarded to make a route pass.

Checked stepping keeps every complete native sample and event but does not
request an extra paused-end terrain grid or party reread for each chunk.
Manual stepping keeps its diagnostic endpoint. Read an exact terrain point
explicitly when needed; never treat an omitted grid as known terrain. The
stream retains initial/bind/setup boundaries and required native observations;
duplicate stepped endpoint copies are not a second proof source.

A completed frame without a usable field is retained as `fieldAvailable:false`
with `fieldAvailability` reasons and native observation/clock data. It contains
no cached actors, player, party or terrain. `completedGameFrames` includes it;
`observedFieldFrames` does not. This is missing field evidence, not permission
to pass a transition. The service clears stale field-owned values, and the
memory-data ring retains the absence without inventing actors. Identity
comparisons cannot bridge that gap. Ordinary checked evaluators still reject it.

The implemented `unmounted-cadence-v1` measurement has one narrow exception:
sealed `setupTransitions` can name exact setup actions, departure and arrival
map/tiles, and a1–600-frame bound. The meter requires a live departure task and
the exact settled arrival. This is allowed only before follower binding;
missing-field frames earn no actor, travel or motion credit. Wrong data or a
missing arrival fails. Live jobs and controller replay feed the same raw-record
path one frame at a time, so a later frame cannot satisfy an earlier predicate.
Neither this integration nor its host fixtures grant gameplay acceptance.
The checked prepared setup plus normal long-route recipe, live route controls
and exact registry activation remain required before the planned route
scenarios can run. Healing and selection interaction tests remain separate.

The native semantic ring holds only16 events. The shared recorder observes the
authenticated writer's return and drains half-full bursts into a bounded host
queue. It does not change the game ring size or sample actor pose early. Pending
events are published only at the next completed main-task-queue frame, with
their original actor-frame clock retained. The final frame drain still detects
missing hooks, resets, changed filters and stopped windows. Installed callback
tests cover multi-ring bursts, missed callbacks, no completed frame and stop.

Bind the actual species, role and full generation-safe handle before measuring.
An actor must be attached and its engine identity verified. If natural spawning
is the claim, declare spawn acquisition and observe the new actor; explicit
spawn is prepared setup and cannot prove natural spawning. A replacement of the
same species is not the same subject. Prepared setup never becomes normal play.

Keep an unverified recording draft as design input. Add typed assertions with
an independent expectation source, validate, then run the checked recipe.
Source recipes are executable; registration is a separate proof decision.

## Register an acceptance scenario

1. Put the typed recipe in `tests/overworld/test-recipes/`. Use
   `scripts/owctl dev test validate --file <recipe.json> --json`; use direct `dev test start`
   for recipe diagnosis only. Per-action and overall wall/frame/no-progress
   limits are required.
2. Put its reviewed scenario in `tests/overworld/scenarios/`, following
   [scenario contract](verification.md#scenario-contract),
   [scenario-v1.schema.json](../../tools/overworld/schemas/scenario-v1.schema.json)
   and a nearby accepted scenario. Set adapter `devtools-test` and name the
   checked recipe, exact subject, role, proof level and measurements.
3. Bind capabilities in `tools/overworld/system_features.yaml` and exact
   requirements in `tools/overworld/runtime_proof_registry.json`.
   `tools/overworld/control.py` owns dispatch; `validation.py` owns contract
   validation. Retain the controller acceptance check and keep unported
   requirements pending in `runtime_proof_migration.json`.
4. Run `scripts/owctl scenario validate`. A planned contract remains a gap until
   its adapter and execution are complete. Run the registered scenario through
   [verify-overworld](../../.agents/skills/verify-overworld/SKILL.md) for acceptance.

Keep recipe, scenario and measurement code in source. Update the owning feature
recipe when coverage changes. For duplicate retirement, use
[reviewed requirement replacement](verification.md#reviewed-requirement-replacement).

## Accept a registered result

Read the terminal job manifest at the exact returned path. Acceptance requires
both `passed: true` and controller-owned `acceptedProof: true` for the exact
registered requirement. A start receipt, direct recipe/evaluator pass, setup
receipt or exported draft is not accepted proof. Planned or unported coverage
is a gap; another scenario or actor role cannot stand in for it.

Check the ROM/save/source and backend identity, scenario and requirement,
measured subject, required measurements, observed frames and retained artifact
identities. Use the final ROM built from the final product source. Relevant
product, build, fixture, observer or scenario changes stale proof; a
content-preserving commit or documentation edit does not. S4 needs the exact
native presentation measurements. Screenshots never supply game proof or
become an agent test step. Use [intermittent coverage](verification.md#intermittent-reports)
for S5 or repeated reports.

Report scenario ID, run ID, manifest path, ROM/save identity, measured species
and generation-safe subject where applicable, result and exact missing proof.
For a failed run, use [failure records](verification.md#failure-records).
Keep the necessary failed and passed artifacts under [storage rules](#storage-rules);
when handing off work, update the existing [resume record](verification.md#progress-and-handoffs).

## Evidence and acceptance

For routine result checks, use [accept a registered result](#accept-a-registered-result).
The details here describe retained observations and adapter-specific proof.

`actor.binding.current-context` uses the `actor-binding-context-v1` meter.
Its read-only public `getContext` return hook is enabled after `record.start`
completes, so every enabled return belongs to retained memory data. It selects
one visible natural Wild Rattata without filtering out context mismatches,
then requires that same actor's subsequent complete Walk. Existing or same-frame
motion earns no credit. The bound is 900 post-boot frames / 4096 native cycles.
Reader host checks exercise wrong returns and identities through the actual
callback; controller replay checks missing returns and Walk events. These host
controls are not live fault injection or general movement/transition proof.
The initial row retains the `record.start` event prefix and its starting frame.
Validate semantic events inside that boundary and native boot events through
its endpoint; seed sequence counters without frame, assertion or motion credit.
Native visibility uses `BIT_VANISH` from `map_events_internal.h`; the separate
`SINGLE_MOVEMENT` bit must not reject an actor when it starts moving.

Jobs write `build/overworld-devtools/test-*/manifest.json`, progress, normalized
recipe, append-only compressed `observations.jsonl.gz`, and fault artifacts.
Keep the evidence needed for current claims and investigations under the
[storage rules](#storage-rules); deleted evidence cannot remain accepted proof.
Diagnostic recording rings remain bounded; they cannot stand in for a complete
long test. Continuous checked streams retain every sampled frame beyond the
diagnostic ring limit. S5 still needs at least 5000 observed subject frames in
one uninterrupted session. S4 needs current, claim-specific native presentation
measurements. Screenshots are optional human-view attachments and never proof;
missing or unrelated images cannot affect acceptance. See
[memory-backed proof](verification.md#memory-backed-proof) for required readers.
The current identity adapter accepts S3 and continuous S5 identity only; it
rejects S4 and does not prove chain, skid, spawn cadence or smooth movement.
The exact Ledyba S4 adapter separately checks all six original claims/seven
measurements and required-event meaning-deletion
controls. Its preflight finds and independently rechecks a current accepted
`observation.live-actor-and-motion-control` run before starting the normal
`chain.pause.ledyba-normal-profile` scenario. Missing calibration stops before
boot. Both run through `scripts/owctl scenario run`; their checked recipes and
original requirements remain registered separately. Executable does not mean
passed, and neither control result supplies unmounted cadence proof.

`passed` describes execution of the typed test. `acceptedProof` grants only the
exact registered requirements after controller checks of the current package,
ROM/save/source identity, complete observations, exact subjects, and negative
controls. A generic tool smoke can pass without granting gameplay proof.
`tools/overworld/runtime_proof_migration.json` preserves unported requirements;
pending is not complete. Never restore an old driver to make one pass.

## Maintain the boundary

### Opt-in mounted callback reader

`mount-pacing.arm` takes a full current Mounted subject and `maxFrames`1–1200.
Use `scripts/owctl dev command mount-pacing.arm --args '<JSON>'`; the subject
comes from checked live inspection, never a species-only label. No hooks exist
before arm. The read-only reader checks packaged function bytes and the current
actor, field, source, player anchor and Pokémon object at each callback.

The shared event queue receives `mount-pacing-presentation` after
`OverworldMount_SyncPresentation` and `mount-pacing-player-step` after the actual
`OverworldMount_PlayerStepBridge`, not tile admission. Each retains entry/return
native clocks, both object poses including all three offset axes, and verified
avatar flags/move states. Native callback clocks are not completed game frames;
the shared queue supplies that separate label. The ARM header test anchors
avatar offsets. The reader never repairs a mismatched pair or edits guest state.
At each completed main queue it also reads the final pair and actual held keys,
retaining only `latestCompletedPose`. This detects a later overwrite after sync.
Callback gaps use native return cycles; dense motion checks use completed frames.

`mount-pacing.calibrate` is an explicit observer control, not a movement test.
In a paused private session it reads a valid pair, changes only the mount's
position-X by one fixed-point unit, requires the same reader/checker to reject
it, and restores the exact bytes. Clocks, registers and identity must not change.
A restore fault aborts that private core. The receipt stores clean/bad/restored
memory data; a calibrated session cannot supply ordinary pacing proof. Close it
and start a fresh session for gameplay. No address or value arguments are allowed.

`mount-pacing.close` removes only its owned hooks and returns the unchanged
completed snapshot. Limits are1200 completed frames and4096 callbacks; a
missing callback still reaches the frame deadline. One arm per session,
failed-arm cleanup and normal core disposal prevent leaked hooks. Receipts stay
compact; events are retained once in the shared stream. Source tests are in the
normal proof gate. The `mounted-frame-pacing-v1` pure evaluator retains all nine
original rows and separates seven Right Walks from the recovery tile. Typed jobs
require one held-Right action until the seventh start, neutral completion, then
one separately scoped Right recovery and close. At a key edge, only the first
completed queue may retain the previous exact memory key mask: stock main polls
before that queue. Keep this sample and every pose/timing check. A stale press
must be idle and cannot start motion; a stale release must belong to the already
active Walk and cannot start an extra motion. A second stale sample fails.
Zero-loss ring wraps are retained diagnostics, not gaps; unread loss, unknown
streams, missing sequences and changed watermarks still fail.
For a two-frame successor tile, keep the prior motion's actual endpoint from
the preceding queue. The new elapsed1 sample already crosses its own logical
boundary; it cannot replace the prior endpoint in the recorder.
The registered `mount.movement.frame-pacing` recipe requires a current accepted
`observation.mount-pose-control` dependency and retains all nine original rows.
Host replay and diagnostic calibration alone do not grant S4 acceptance.

### Natural Wild Walk clear reader

`wild-walk.arm` takes a full current Wild Rattata19 subject and `maxFrames`
1–1200. It adds only an owned entry/return hook for the packaged
`OverworldWildSpawns_ClearCustomJumpLocal` function. The shared queue retains
the exact subject, native clocks, active byte, motion mode and object flags
before and after the call. An idle actor alone is not a clear receipt.
`wild-walk.close` removes those hooks without advancing the game.
The function can also run before motion while already clear. Keep that exact
unchanged, idle receipt in a separate list; it supplies no terminal-clear credit.
The raw reader count includes every call. The movement count requires one
active Walk to become clear after its actual commit.

The exact Walk witness binds the requested native spawn using its own final
spawn receipt and landing point. An older Pokémon of the same species is not
the requested subject. Setup does not grant natural-spawn credit. After setup,
the game selects its own Walk with neutral input; the observer neither forces
direction nor changes profile values or timers. Retain every completed-frame
sample, including elapsed0 and the actual elapsed4 endpoint, one logical
transition, native commit/clear/finish/control receipts, and terminal idle.

`wild-walk.calibrate` belongs only in a separate observer-control session after
a real Walk clear. It changes the current active byte from0 to1 while the guest
is paused, reads that fault through the same reader and unchanged checker,
then restores the exact byte in `finally`. It verifies the owner, registers
and clocks. A failed restoration stops the private core. This receipt grants
no movement credit. Normal Walk acceptance requires zero guest memory writes.
Host checks and diagnostic data do not grant runtime acceptance; the registered
controller must replay all rows and reject their required wrong-data controls.

`scripts/verify_overworld_devtools_only.py` and its mutation tests reject the
retired files, imports, execution routes, data registrations and active advice.
Keep that check in the normal host suite. Historical evidence may describe old
runs, but must be explicitly marked historical and cannot be an active route.
Extend the common worker/observer or typed evaluator for a missing capability.
Do not create a second bootstrap, native loop, input driver or hidden test mode.
