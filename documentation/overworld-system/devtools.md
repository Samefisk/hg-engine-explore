# Live development tools

Checked tests now run through these same tools. Use
[run and stop](devtools-tests.md#run-and-stop) for registered test execution;
read [test authoring](devtools-tests.md#author-an-executable-test) only when
creating or changing a recipe. The former standalone test method is
removed, not retained behind a redirect.

Use this interface to set up and inspect a disposable game session. The
Workshop page at `http://127.0.0.1:8766/devtools` and `scripts/owctl dev` use the
same service. Neither controls the user's melonDS window.

This is the default live agent workflow, replacing the old headless bootstrap
playbook. Enter through [overworld-devtools](../../.agents/skills/overworld-devtools/SKILL.md),
use [author-overworld-scenario](../../.agents/skills/author-overworld-scenario/SKILL.md)
for a permanent test, and [verify-overworld](../../.agents/skills/verify-overworld/SKILL.md)
for accepted proof. The [task policy](../../AGENTS.md#build-and-test-requests)
includes relevant builds and tests without special user wording.

## Session ownership

Read `scripts/owctl dev status --json --summary` and
`scripts/owctl dev test status --json --summary` before starting, reusing,
resetting or stopping a session. One coordinator owns live control. A checked
job owns its private session; use its run ID for job control, never manual input.

Status has no human/agent owner field. Establish ownership from this task's
start receipt or the coordinator's explicit handoff of that session ID. Record
that ID in the active work item. Readiness, port and species do not prove
ownership. If an active session's owner is unknown, continue read-only work and
ask before replacing it. Reuse an owned session only when its ROM/save identity
and normal/prepared mode fit the task.

Use the pinned melonDS worker through this service. Do not use DeSmuME, restore
standalone drivers, or clear game flags/patch arbitrary memory to make setup
pass. Finish missing shared backend support before live tests. Check
[service readiness](#service-readiness) before live control, including reuse
of an owned session. Use [first use](#first-use) when the bridge needs setup.

Start copies both source ROM and save. Preserve the user's melonDS window,
`test.sav`, `test.dsv`, and backups; never replace, convert or delete them.
Stop only your manual session with `scripts/owctl dev stop --json` before a
build, fresh test, or task completion. Leave it running only when continued
live use was requested. Confirm it stopped. For a checked job or interruption,
use [run and stop](devtools-tests.md#run-and-stop), including its cleanup check.
Do not stop unrelated emulator processes. Keep artifacts under
[storage rules](devtools-tests.md#storage-rules).

## First use

The shared worker uses the pinned melonDS core, not an installed emulator app.
Build its native bridge once, and rebuild it when its source changes:

```sh
python3 -B tools/overworld/melonds_native/build.py
```

See [native transport](../../tools/overworld/melonds_native/README.md) for tools,
pinning and memory-hook checks. Preflight checks the bridge source and binary
hash; a missing or stale build fails rather than starting another emulator.
Run manifests include that native identity. Old emulator results are history,
not proof for melonDS. The user's melonDS app and saves remain separate.

## Service readiness

On entry and after service-source changes, check
`GET http://127.0.0.1:8766/api/v2/health` for `ok:true`,
`service:"overworld-viewer-v2"`, `apiVersion:2`, and `restartRequired`.
If Workshop is unavailable, start it with
`OPEN_PAGE=0 scripts/keyboard-maestro-start-overworld-viewer.sh`, then check health.
Check `GET http://127.0.0.1:8766/build-status` before a restart. If health reports
`restartRequired`, wait for any build to finish and stop only your dev session.
Do not restart another owner's active session. Then use Workshop's restart
action or:

```sh
curl -fsS -X POST http://127.0.0.1:8766/restart-server \
  -H 'Content-Type: application/json' -d '{}'
```

Read health again and require the current code with `restartRequired:false`.
A running service must not mix loaded Python code with changed files.

## Start an owned session

After ownership and readiness checks, use the current command contract:

```sh
scripts/owctl dev help --json
scripts/owctl dev command catalog --args '{"kind":"species","query":"mankey"}' --json
scripts/owctl dev start --rom test.nds --save test.sav --json
scripts/owctl dev status --json --summary
scripts/owctl dev inspect --json
```

Images are off by default. Setup, stepping, play, polling and checked tests do
not capture a screen. Only the user's manual Capture click or an explicit
request to capture an image should use `scripts/owctl dev capture --json`.
For live spawn-cost diagnosis, pause a prepared session and use
`scripts/owctl dev command spawn-cost.probe --args '{"mode":"baseline"}' --json`.
Then collect bounded memory data with normal input. This read-only mode records
refill, complete attempt, helper, archive, finalizer and creation guest costs.
Native archive costs include raw caller and argument registers even outside
a spawn call, so later sprite/model loading is visible. Join observed NARC
open/close handles to read calls; do not infer archive IDs from pointers or
add nested inclusive costs together as if they were separate time.
It also reads the fixed post-VBlank-wait boundary for the next3600 updates,
starting where it is enabled rather than at a scripted route's frame numbers.
It does not grant accepted proof, skip spawn work or modify game memory.
The completed3110–3112 L-button split is historical evidence only. Its
temporary gates are removed from normal ROMs and from the observer. Do not
restore or use them as an acceptance test. It isolated the legacy Land/Surf
position scan as sufficient to cause the reported stutter. The production scan
now resumes at most16 candidates per game update. That limit alone is not proof: use
`spawn-helper-cost` memory data to require one profile/metadata/class preparation
for the whole attempt, no repeated preparation on resumed updates, and the later
prepare/create path.
For remaining CPU work outside those calls, use the same paused prepared session:

```sh
scripts/owctl dev command cpu-work.start --args '{"maxNativeFrames":600}' --json
# Apply the bounded normal input being investigated, then read the result:
scripts/owctl dev command cpu-work.read --json
```

This optional native counter is off by default and stops after its declared
1..1200 native frames. It keeps aggregate instruction counts and the top16
raw64-byte program-counter bins per native frame. It does not capture images,
copy another ROM, write guest memory or issue input. Native frames are not
game updates; correlate their queue endpoints with the loop-clock events.
Counts identify hot code, not elapsed time or a stutter verdict. Bins may span
function or overlay boundaries: match code identity before naming an owner.
The same probe counts native GetMonData caller/field pairs (at most128 distinct
pairs), without storing Pokémon contents or making synthetic getter calls.
The read returns a compact saved artifact and never grants accepted proof.
Images are never agent test proof. `record.start`/`record.stop` save structured
memory and event data, not video; the UI labels these as memory data.

`help` returns the versioned command fields and bounds. JSON responses contain
`ok`, `session`, and either `result` or `error {code,message,details}`. An error
exits the CLI with code 2. Agents should use `scripts/owctl dev status --json --summary`
between actions. `--summary` changes only printed output, not the command. It
keeps exact actor IDs, identity checks, motion, clocks, errors and operation
receipts. It omits raw actor internals, image data, and tile/event lists; all
omissions are named in `outputView`. Retained native resolver profiles keep
their count, fingerprints and small fields, but omit lane, result and request
bytes. Terrain counts cover only reported cells, not full map or route coverage.
Omit `--summary` for the full response. Neither view is behavior proof. Download
a recording artifact only when its detail is needed.

Start copies **both** ROM and save into a new `build/overworld-devtools/session-*`
directory before opening the emulator. This also isolates the core's automatic
battery writes. The manifest keeps the source and copy hashes. No operation
exports a prepared save over the user's save.
After a successful core close, the service removes its verified private ROM
copy automatically. It keeps source ROMs, all saves and test evidence; a
changed or unknown copy is retained with a cleanup reason. New checked logs
are lossless gzip files. See [storage rules](devtools-tests.md#storage-rules).
Boot uses short A presses to reach the saved field. Once the field is reached,
a stalled actor clock fails setup with field, pause and task memory data.
Boot must not press B or X to clear the stall. Such recovery could hide the
fault under test. A failed boot is not a passed movement test.
The worker also checks the packaged stock `Heap_Free` entry. A NULL argument
stops observation with its caller, stack pointer and frame. Stock HeartGold
dereferences an allocation header even for NULL; the shared emulator must not
silently pass a call that stops ARM9 in melonDS. This check does not change
guest memory or registers and does not replace fixed-build runtime proof.
On macOS, these are copy-on-write files with separate file IDs, not hard links.
Changing either file leaves the other unchanged. Other file systems fall back
to normal copies; the manifest records the method. A full disk still reports
an error rather than using a shared writable input.

## Collect a bounded reproduction

Name the actor role, question, trigger and bounded observation. Inspect the
actual actor and map before acting; a configured species is not proof of a
live subject. Read [test selection and setup](devtools-tests.md#select-tests-and-setup)
before a run and [memory-backed proof](verification.md#memory-backed-proof)
for the state needed by the claim. Keep logical and rendered positions,
completed game frames and native cycles, and unknown versus blocked distinct.

Record before the trigger. Retain the exact subject, normal/prepared mode,
ROM/save identity, relevant frames, errors and artifact paths. Use bounded
`step` input; `play` is free-running observation and `pause` holds the owned
session. Held-key duration alone cannot prove an exact number of moves.
Use `status --summary` between actions, and full inspection only for needed
detail. Image capture or inspection is never an agent test step. Call saved
structured observations "memory data", not video.

For a runtime fix, the [reproduction contract](verification.md#reproduction-before-editing-acceptance-before-closure)
defines sufficient pre-edit evidence. Missing identity or samples remain gaps.
For a CPU or queue fault, inspect the [first-fault data](#automatic-runtime-fault-detection)
before another run; do not wait out the full scenario limit. Use
[control and recovery](#agent-control-and-recovery) for timeouts and retries.

## Drive and inspect

```sh
scripts/owctl dev step 30 --keys RIGHT --json
scripts/owctl dev step 30 --json
scripts/owctl dev terrain --radius 6 --json
scripts/owctl dev terrain --x 558 --z 373 --radius 0 --json
scripts/owctl dev inspect --handle 131072 --json
scripts/owctl dev play --json
scripts/owctl dev pause --json
```

Use a handle from the **current** inspection, not the example above. A missing
actor is an error. Check species, role, full handle, current field/map context,
engine membership, and presentation before using it as a test subject. A sprite
or selected species label alone is not that proof.
The native spawn `active` byte includes the active bit plus aggro/pending
flags. Identity accepts the defined live combinations1,3,5,7, not only1;
inactive values, flags without the active bit and undefined bits remain invalid.

Full actor snapshots include `crashPresentation`: the same-frame native shake
timer, saved base X/Z, and checked object/actor owner. Timer zero is reported
too. `known:false` gives a code/layout/owner gap; it is not an inactive effect.
The reader checks the current packaged code and native layout. Use these
fields to separate a crash shake from a wrong movement endpoint, not a general
position tolerance. The cadence check retains the raw pose and requires the
complete countdown and restoration; see [memory-backed proof](verification.md#memory-backed-proof).

The UI separates the DS image, actual actor list, and tile grid. The grid shows
engine-loaded terrain; it is not a guessed pixel overlay. Logical, rendered,
origin and target positions stay separate. Unknown state is shown as unknown,
not converted into a pass or a blocked tile. The actor's last decision is a
reported decision, not proof that it is the cause of every later wait.

Screenshots are for optional human viewing, never test proof. Read the live
terrain/height, actor and presentation data instead; do not infer tree or roof
support from pixels. Follow [memory-backed proof](verification.md#memory-backed-proof)
and extend a bounded shared reader when the necessary value is not available.
`terrain --x <tile-x> --z <tile-z> --radius 0` reads one exact map tile from
memory without moving the player or taking a screenshot. Supply both coordinates;
omit both to center on the player. Its native-cycle and last completed-game-frame
clocks identify a paused endpoint, not a new completed-motion observation.
The tile attribute proves only its decoded fields, not tree/roof support height.

The `dialogue` field in status/inspection is a bounded memory read from the
last completed game update. It reports script/printer/menu ownership, state,
reason, and a `waitIdentity` for a known input wait. It never reads text from
an image. `page-wait`, `yes-no-ready` (Yes cursor), and `script-button-wait`
can accept one A edge. Release the key and wait for the old wait identity to
change before another press. Other states do not request input. Unknown or
stale ownership must be investigated, not treated as a prompt. Use the typed
`dialogue-state` predicate in checked recipes. HP and Y selection still need
their independent current native observations; dialogue completion is not
healing proof. No field means no retained dialogue from the old map.

The normal nurse route uses nested `CallStd` contexts. The reader accepts at
most three contiguous contexts with checked IDs, field/task owners, parent
wait callbacks and wait bits. Only the leaf context may own an input wait.
Arbitrary parallel scripts remain unknown. Rejected script observations retain
the already-read context count, pointers and wait mask for diagnosis.

For a door task that keeps waiting while the main queue runs, use `diagnostics`.
Its `fieldControl.fieldLifecycle` reads the field-ready flag first, then the
owned stock field manager's execution/phase state and terrain exit condition.
This distinguishes a retained ready field from an active terrain shutdown
wait. Code, owner or pointer mismatches remain unknown. It is a bounded paused
memory read, not a completed-frame measurement or an automatic control-lock
verdict. Pair it with the saved task chain and the exact failed route.
The adjacent `fieldCleanup` diagnostic reads the current transition, selector,
ready-task map and helper ownership flags. It requires the owning overlays,
defining ELF symbol layouts and matching live/package code before reading
state. It is a paused memory check, not an observed cleanup return value.
Missing ownership or code/layout mismatch remains unknown.

For a suspected observer-cost spike, pause the owned session and use
`scripts/owctl dev command snapshot.probe --args '{"iterations":128}' --json`.
This repeats the actual memory snapshot reader without game advances or writes.
It saves per-read CPU/wall costs and native read counts, and requires equal
snapshots and unchanged game clocks. The bounded result is diagnostic-only;
it cannot accept a gameplay timing claim or dismiss a failed route.
The command response contains only the probe invariants, timing rows and
artifact record. The saved artifact keeps the complete worker result, including
pending diagnostic events that are not part of the compact response.

`step` is bounded and releases all keys afterward. `play` advances without keys;
`pause` stops at a completed worker command. Read operations do not advance the
game. The native frame count and emulator cycle count must stay distinct.
For a manual step with keys, the tool first checks that the stock keypad poll
read the requested mask. Only subsequent completed updates count toward the
requested held-input duration. An initial partial update is retained in the
actual frame count and memory data, not hidden or credited as input. A missing
poll fails within the step bound. Neutral waits and the checked job's continuous
input chunks keep their exact completed-frame counts; their per-frame stop
predicates are unchanged.
The UI keeps Pause or Stop if a screen capture is in progress. Stop takes
priority; another manual capture and keyboard input wait until that control
request finishes. This does not retry the earlier command.

## Set up a scenario

These operations mark the session **prepared before execution**, including a
failed attempt. They cannot create normal-play spawn or input proof.

```sh
# Numeric map ID, map tile X/Z, stock facing: 0 up, 1 down, 2 left, 3 right.
scripts/owctl dev teleport 34 550 381 --facing 1 --json
# Replace/create party slot zero through the game data functions.
scripts/owctl dev party 0 --species 56 --level 10 --json
scripts/owctl dev spawn 56 --role mounted --slot 0 --json
scripts/owctl dev spawn 165 --role wild --level 5 --json
```

Teleport uses the normal field transition and loader, not coordinate writes.
Its receipt keeps a read-only tail of at most 64 stock `Heap_Free` entries for
that ScriptWarp. Each row has the freed pointer, header heap ID, resolved heap
handle, caller LR and owned ScriptWarp state. An invalid read or handle is a
fatal command failure; the observer never repairs or simulates the free.
`walk-policy.reset` is a narrow prepared tool for an idle Wild or Mounted actor.
Use `dev command walk-policy.reset --args '<JSON>'` with `subject` set to the
full current selection returned by the shared tools, including all generations.
It checks staged movement, engine poses, released keys and the live public
reducer before RESET. Unknown staged data is a refusal, not idle. The receipt
keeps native before/after policy data; resetting chain and momentum is setup,
not evidence that acceleration works. Checked recipes use a bound subject name
instead of saved handles. See [acceleration setup](devtools-tests.md#acceleration-setup-and-terminal-readings).

`mount-walk.configure` is bounded prepared setup for a current idle mount.
Pass the full current `subject`, required `directionMode` (0 cardinal, 1 both,
2 diagonal only), optional `travelTime` (1–32), and optional `stompTime` (0–32).
Optional `turning` is `free` or `locked`; `crashSound` is `none` or `wall-hit`.
Those fields change only their own bits in the idle Owner lane's Walk options.
They neither force a crash nor change other options. Omitted fields also keep
the previous receipt shape, so existing fixed recipes are unchanged.
Stomp time0 disables feedback; other values select the frame threshold. Omitted
fields keep their current values. With travelTime it sets initial and fastest travel
time to that value and disables acceleration for the test case. It changes only
the private mount session's lane, not profile files, party data or saved data.
It refuses busy/staged movement, held input and stale ownership. The receipt
keeps exact before/after bytes and zero-frame setup; a failed write must restore
the original bytes or close the private core. It never grants gameplay proof.
Checked tests require a prepared fixture and bound subject name; only fixed
matrix/stomp routes can reconfigure between their declared completed moves.
Use this for exact timing and corner fixtures; normal-profile tests must not use it.

`stomp.arm` takes the current mounted Cyndaquil `subject` and `maxFrames`
(1–3000). It records the mounted feedback call and its nested dust allocation,
render initialization and sound-start result. Paired positions come from the
normal completed-queue reader. `stomp.close` removes its hooks without game
advances. These are prepared diagnostic tools, not accepted stomp proof or
proof of sound from the speakers. The registered `walk.stomp.feedback` test
checks one2-frame move at threshold2, then one3-frame move without feedback.
It requires separate accepted `observation.stomp-policy-control` evidence;
source registration alone does not prove either result.
`stomp.calibrate` is terminal: after a real completed policy call and idle
recovery, the same reader must reject threshold255 and restore all184 state
bytes, poses, binding, input, registers and clocks. The expected failure stays
latched; the reader closes and the session permits no later game advance.

`walk-corner.probe` takes only the full current mounted Cyndaquil `subject`.
It asks the same native collision function used by Walk about the four side
tiles, and the native landing service about the four diagonal destinations.
The bounded receipt identifies corners with an open destination and exactly
one blocked side. It checks the whole native function bodies, owner, profile,
poses and game-frame count during the eight calls. Reaching/leaving the native
bridge is setup; the endpoint is not a zero-time gameplay action. Loaded terrain
alone cannot prove these collision results. This probe earns no movement credit.
Idle flags are checked before bridge arrival; the full flags are then frozen
at native query entry and checked after every call. The receipt retains both
boundaries. A change inside the eight-call batch fails.

Use `walk-corner.arm` with that full `subject` and `maxFrames` (1–600), then
normal input, to observe actual strict diagonal calls and only the nested side
and landing checks that occurred. It hooks the shared function body, not only
the external-call veneer: internal Walk calls bypass that veneer. The native check can stop at its first blocked
side; a skipped second side or landing is unknown, not open. `walk-corner.close`
takes no arguments, retires the reader's hooks and advances no game frames.
Both commands are prepared diagnostic tools. Their receipts and memory data
are not accepted corner-test proof without the exact registered evaluator.

The current package uses the typed `Walk_DiagonalRejection` body. The reader
retains its raw candidate flags and the derived allowed/blocked value; it does
not invent a semantic rejection event. Older packages retain an explicitly
labelled BOOL receipt. Both code paths use whole-function authentication.
`walk-corner.calibrate` is a terminal policy-reader control: after a real corner
call and idle recovery it changes only the mounted allowance byte to zero,
reads through the same checker, and restores it. It checks all184 state bytes,
registers, ownership and clocks. It allows no later gameplay, only close.
Run `observation.corner-policy-control` separately before accepting
`walk.diagonal.corner-block`. The control proves policy reading, not collision
outcomes; the normal test must still observe actual native collision calls.

`walk-matrix.arm` takes the current mounted Cyndaquil `subject` and a
`maxFrames` bound from1 to4096. It reads actual `OverworldMotion_Tick` entry
and return values for that actor, including moves that finish in one frame.
Each native call is emitted once in the shared event stream. Snapshot status
keeps bounded counts, not another copy of the growing sample history.
`walk-matrix.close` retires its hooks without advancing the game and verifies
the returned boundary. `walk.cardinal.frames-1-32` runs the fixed65-case route:
cardinal and diagonal times1–32, then diagonal-only rejection and recovery.
Each case uses its actual native elapsed0..N−1 and one complete lifecycle.
Zero-time idle lane changes are checked byte-for-byte, not credited as play.
Diagonal completion retains one neutral queue for the normal pending player-step
receipt; the next lane change must still prove the adapter is fully idle.
Run `observation.walk-matrix-state-control` first. Its separate two-case window
ends with `walk-matrix.calibrate`: the same native reader must reject phase255,
then restore all52 bytes, registers, clocks and ownership without execution.
No gameplay can follow calibration. This checks phase reading, not an injected
timing fault. Registration alone is not acceptance; both current checked jobs
must pass. Never manufacture elapsed0 from a completed-frame observation.

CPU intervals retain each clock's reported precision in `cpuClockResolutionNs`.
Only the diagnostic thread/process comparison permits two endpoint rounding
errors per clock. Raw process CPU values and all pacing limits stay unchanged.
Old intervals without precision data retain the strict comparison.

Party changes use the game's encrypted-data, stat and move-history operations.
The private call buffer belongs to the field memory pool (heap 11). The tool
checks its field owner, code and guard before use, and drops it before that
heap is destroyed. It does not reserve space in the small default heap.
Prepared party setup also uses field memory for five stock temporary buffers:
growth data (404 bytes), moves (164), personal data (44), stats (44), and mail
(56). Each change checks the exact native call, size, thread, field and lifetime.
The receipt records each allocation and native free, including nested buffers.
This does not change data or stat math. Normal game allocations are not
redirected. A memory check must pass before that setup runs; incomplete cleanup
closes the disposable session.

For the follower-to-mount profile transfer only, opt in with spawn argument
`"profileDiagnostics":"owner-transfer"` on follower or mounted setup.
Two temporary, read-only native taps retain the exact follower getter result
and mount Begin input/stored Owner lane, with current subject and field checks.
They are off for ordinary setup and movement. Each session permits16 capture
windows and128 receipts per window; owned hooks are removed afterward.
Receipts remain diagnostic until the controller compares the exact transfer
with resolved expectations. They do not prove normal Y/Select input.
The separate `"profileDiagnostics":"owner-transfer-control"` option applies
only to mounted setup. It tests the reader against one changed Owner byte in
the disposable core, restores that byte before guest execution resumes, and
reads the restored state again. Its receipts are reader calibration, never
normal transfer or movement proof. Ordinary `owner-transfer` remains read-only.
Wild setup uses the real prepared-encounter lifecycle. Follower and mounted
setup use fixed native selection and mount calls. They select an exact party
slot and wait for its release to finish; mounted setup uses that current
follower and the normal profile resolver. They do not automate the Y menu.
Use `step` with Y in a fresh normal session to test the menu itself.
Follower/mounted setup defaults to read-only IRQ-code write guards without
the expensive instruction-by-instruction IRQ trace. Normal CPU/main-queue
health checks remain active. For an unresolved interrupt fault only, request
`releaseDiagnostics:"irq"` through the shared command, for example:

```sh
scripts/owctl dev command spawn --args '{"species":155,"role":"follower","slot":1,"releaseDiagnostics":"irq"}' --json
```

The receipt declares the selected coverage. This option is not valid for Wild
spawns. Do not enable it for routine movement setup or extend test deadlines
to pay for an unrelated trace.
A command must return the observed result, not only that it was requested.
Spawn form, level, X and Z apply to wild actors. Follower/mounted setup uses
the party slot's existing data; use `party` first to change those values.

Busy native tasks, moving actors, invalid targets, missing overlay identities,
or a changed ROM cause a clear rejection. Do not clear game flags to make a
command pass. Finish the normal action, inspect the reason, or reset.

## Repeat a setup

For the existing native actor lookup, use `scripts/owctl dev command
actor-inspect.probe --args '{"handle":CURRENT_HANDLE}' --json --summary` with
the numeric handle from current inspection. This requires a settled player
and a verified current actor; it never selects a replacement subject.
The prepared probe authenticates the public facade and initialized actor state,
then calls native Inspect with the current handle and a changed generation.
Only its owned heap11 buffer is written. It retains the exact query, returned
snapshot, current actor bytes and native call receipts, and checks cleanup.
This is diagnostic lookup evidence, not accepted motion, role or roadmap proof.

For the nine fixed resolver deployment cases, use
`scripts/owctl dev command resolver.probe --args '{}' --json --summary`.
It requires a quiescent field and a successful natural resolver discovery in
the current field/heap. It marks the session prepared, authenticates the live
service and blob, then uses the existing field-return bridge and one owned
8,000-byte heap11 buffer. Each result retains full result bytes and ordered
provenance; guards, input bytes and heap ownership are checked before native
cleanup. There are no caller-supplied addresses or requests. The receipt gives
no accepted proof: compare it with fresh Workshop results and use the registered
controller before claiming deployment parity. It gives no natural actor,
follower or mounted movement credit.

```sh
scripts/owctl dev recipe save mankey-route --json
scripts/owctl dev recipe list --json
scripts/owctl dev recipe load mankey-route --json
scripts/owctl dev reset --json
scripts/owctl dev stop --json
```

A recipe stores checked commands in `tests/overworld/recipes/`. Saving does not
replace an existing recipe. To submit an explicit recipe, use `command
recipe.save --args` with `{name,recipe}`. Its version-1 data has `schemaVersion`,
`mode` and `actions: [{op,args}]`; only `step`, `teleport`, `spawn` and `party`
are permitted. A normal recipe permits only normal key input.

Consecutive successful steps with no keys can share a saved recipe step,
up to the command's frame limit. Key press/release edges and setup order stay
unchanged; raw command events stay separate. A failed or truncated command
history cannot be saved as an implicit recipe. Supply an explicit reviewed
recipe when retaining only selected setup actions.

Recipe load starts a **new worker process** from the original source save,
then runs the actions in order. The first reply reports `started`, not success.
Read `status` until `session.recipe.state` is `completed` or `failed`. It stops
at the first failed action and names that action. Stop/reset remains available
between bounded actions. Reset also replaces the process; it does not clear selected flags
inside an old emulator. A recipe is a setup, not a saved-state claim.

## Record, then make a test

### Automatic runtime fault detection

Every post-boot normal advance checks ARM9 mode at each native-cycle end.
`arm9-abort` or `arm9-undefined` stops on the first observed fault. The shared
session also stops with `main-queue-stalled` after120 native cycles without a
completed main task queue. That deadline spans small commands; another `step`
cannot reset it. Host pause consumes no native cycles. Explicit owned native
tool calls exclude only their own cycles and cannot clear an earlier fault or
erase a pre-existing no-progress interval. Waiting for the native entry is
normal game time: exclusion starts only at the authenticated takeover point.

The first failure retains CPU registers, native cycle, last completed frame,
field/task state and the last coherent snapshot before teardown. It stays
latched: further input cannot resume the failed core. Inspect that diagnostic
artifact, resolve its caller or blocked state, and record the next check before
starting another run. Do not wait for the scenario's full wall/frame limit.
During a prepared follower release, a rate-limited `prepared-release-progress`
stderr receipt retains the latest completed frame, native cycle, ARM9 state,
IRQ/write counts and cached selector frame. Worker timeouts retain these lines
in `workerTail`. They distinguish observed progress from a stale pre-command
snapshot; cached selector state and a progress receipt are not setup proof.
Build and test preflight also reject Walk helper placement that violates the
actual input ELF alignment, including literal-pool errors hidden by a core
that tolerates invalid memory reads.

These checks detect CPU exceptions and a stopped main queue. They do not claim
every input lock or individual actor stall. Actor clocks can validly stop for
menus, field tasks and service gates; stationary Pokémon can be in an authored
pause. Use exact motion/control contracts and their bounded predicates for
those cases, not screenshots or position alone.

```sh
scripts/owctl dev record start --json
scripts/owctl dev step 120 --keys RIGHT --json
scripts/owctl dev record stop --json
scripts/owctl dev record export --json
scripts/owctl dev scenario-draft ledyba-pause \
  --expectation 'The selected Ledyba completes its authored chain pause.' --json
```

The recorder retains a bounded recent window and reports dropped frames and
events. Export retains the original session identity, mode, actual subjects,
inputs, native observations, and command failures. Missing samples remain gaps.
Spawn finalization, destination search, object creation, startup motion and
landing-height receipts include `guestTiming`: authenticated ARM9 entry/return
scheduler ticks and their difference. Search receipts identify the exact parent
`SpawnOne` attempt and destination mask. Existing profile-resolution receipts also
include timing when nested inside spawn preparation/creation, not in unrelated
per-frame resolution. Scoped `spawn-metadata`, `spawn-class-selection` and
`spawn-object-create` receipts expose return values and the first four raw
argument registers for call-cost attribution; they do not claim full object
or profile-output validation. Cadence tests fail on an observed base-form
metadata miss rather than waiting for its fallback I/O to produce a hitch.
These read-only clocks do not advance the
game. They include IRQ work and waits, not just active CPU work. Do not add
nested inclusive spans, subtract ARM7 from ARM9, or use host callback time as
guest time. A missing/invalid live clock fails the observer; old evidence without
this field cannot supply per-call timing. Use these bounded receipts to locate
spawn-related queue delays before another product patch or full-route repeat.
Do not infer a stall from standing still, or a motion commit from changed pixels.
Each complete snapshot can contain up to1,048,576 serialized UTF-8 bytes.
The snapshot window is also capped at117,964,800 bytes; it drops whole oldest
rows and reports those drops. Large terrain/identity data are not silently
removed to fit. These diagnostic limits do not replace checked-job streams.

Recording arms the existing public native trace at a completed game update.
It records actual intent, rejection, logical commit, motion completion, and
context events. Trace overflow, reset, and expiry are explicit notices, not
invented events. The current native schema has no separate pause-selected event;
use the reported policy state for that detail. The trace has a bounded native
window and does not silently re-arm after it expires.

The draft is explicitly `planned`, `unverified`, and `acceptedProof:false`.
Use `command scenario.draft --args` to include a full current `subject` record.
In the UI, select a verified actor before creating a draft. The form refreshes
the inspection and checks the full identity again. A changed or missing actor
is rejected; it cannot silently switch to another Pokémon of the same species.
The draft names missing expectation sources, incomplete windows and observer
checks. It never activates a scenario or issues an accepted receipt.

To turn the draft into proof, use
[author-overworld-scenario](../../.agents/skills/author-overworld-scenario/SKILL.md)
and [verification.md](verification.md): write
the exact observable and forbidden result, validate the recorder with a known
bad observation, then run the permanent scenario with `owctl scenario run`.
Prepared setup cannot prove that Y selection or a natural off-screen spawn
works. Test those triggers through normal input in a fresh normal session.

## Agent control and recovery

- One service owns one serial worker. The shared lease prevents overlapping
  sessions and builds. A checked job owns a fresh private session in this service.
- Pass a stable `requestId` when retrying an uncertain request. The recent reply
  cache returns the same result without repeating the action; a changed command
  with that ID is rejected. It retains 128 replies; an older ID is rejected as
  expired, not run again. After 10,000 distinct IDs, Stop, status and help
  remain available, but new session work is blocked until Workshop restarts.
  Emergency Stop keeps one stable reply, so retrying it cannot stop a later
  session. A server restart ends this in-memory cache.
- A transport timeout means unknown outcome. Read status before another action.
  A worker/native-call timeout closes that owned worker. Reset boots a fresh one.
- A large error keeps its full details in the command response and a session
  artifact. The event ring stores a short summary and that artifact's path/hash.
  If the disk write fails, the event says so; it must not hide the original
  error or stop owned-worker cleanup. Recipe failures retain native details too.
- Native call failures retain CPU state and bounded, read-only call/interrupt
  checkpoints before closing. These are diagnostics, not proof that the game
  or the requested setup completed. A closed session cannot keep recording.
- Apply [session ownership](#session-ownership) for stopping and cleanup. Keep
  the manifest and native memory data that explain a failure. Preserve any
  user-requested image separately; it is not proof.
- Change the inspection method after two attempts with no new evidence. A failed
  setup is not a gameplay pass, and a diagnostic recording is not roadmap credit.

## Code owners

`tools/overworld/devtools_contract.py` owns command shape and bounds.
`devtools.py` owns session lifetime, copies, serialization and provenance.
`devtools_runtime.py` owns emulator access and the checked native operation
bridge. `devtools_records.py` owns bounded records, recipes and draft generation.
`devtools_cli.py` and Workshop are clients; they contain no second game policy.
`devtools_trace.py` reads the existing native event ring and reports gaps.

`devtools_native.py` and `devtools_engine.py` are the shared native transport;
they contain no scenario driver. `devtools_observer.py` installs checked,
read-only callbacks before boot and ties their receipts to complete game frames.
`devtools_jobs.py` executes typed `devtools_test_contract.py` recipes through
the same commands; its status/cancel lock is independent of a native call.
`devtools_insight.py` explains current observations and saved first differences.

Use `explain` with a current handle for the observed profile fingerprint,
resolved lanes with units, decision and missing coverage. It does not infer a
missing profile from source configuration. `events` reads a bounded recent
tail; `checkpoint` saves state and `compare` finds the first exact JSON
difference between two returned relative artifact paths. A difference is a
diagnostic, not a gameplay regression verdict.

These tools add no movement controller, resolver, spawn policy or game clock.
Native setup is confined to the disposable session. Its fixed operation bridge
is not a general memory/PC/script execution endpoint.

## Check the tools after a change

The normal host proof suite includes command, copy isolation, trace decoding,
records, recipes, CLI and HTTP checks. Host fixtures do not prove live setup.
For a tool change, run the relevant host checks and the real tool smoke at the
stable integration point. Instructions-only changes need skill/link and command
checks, not a new ROM build or repeated full live suite:

```sh
python3 -B scripts/verify_overworld_proof_gate.py
python3 -B scripts/verify_overworld_devtools_session.py \
  --save test.sav --output build/devtools-live-check.json
```

The proof-gate command always means the full host suite. It rejects the old,
misleading `--host-only` argument instead of silently starting that suite. For
a narrow feedback loop, select one or more listed modules explicitly, for
example:

```sh
python3 -B scripts/verify_overworld_proof_gate.py \
  --test tools.overworld.test_spawn_destination_scan
```

The live check refuses an existing session, uses copies, checks actual actors
and native party readback, and stops only its own session. Its output must not
already exist. It reports diagnostic tool coverage, not accepted game behavior.
If a setup fails, retain that failure and fix the tool or name the game-state
blocker. Do not remove the failed check to obtain a green result.
