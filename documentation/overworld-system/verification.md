# Overworld System Verification

## Execution authorization

Use the repository [build/test policy](../../AGENTS.md#build-and-test-requests)
for authorization. This guide owns proof requirements, not a separate permission gate.

## One agent workflow

Choose the entry skill for the task:

- [overworld-devtools](../../.agents/skills/overworld-devtools/SKILL.md): observe
  and reproduce through the shared worker.
- [author-overworld-scenario](../../.agents/skills/author-overworld-scenario/SKILL.md):
  create or repair a permanent witness when existing coverage is insufficient.
- [verify-overworld](../../.agents/skills/verify-overworld/SKILL.md): run an
  existing registered scenario and check acceptance.

Read only the relevant sections of this guide. An unchanged test needs the
[run path](devtools-tests.md#run-and-stop) and
[acceptance rule](devtools-tests.md#accept-a-registered-result), not the full
measurement-design material. Interactive control and checked jobs use the same
worker; the former standalone collectors remain removed. Keep missing shared
measurements as explicit gaps.

## Reproduction before editing; acceptance before closure

Before a runtime fix, preserve a reproduction that measures the reported
symptom, its ROM/save identity, relevant actor identity, trigger, expected
result, actual result, and bounded replay steps. Reuse an existing scenario.
When no sufficient scenario exists, a bounded shared-devtools recipe and its
memory data can supply this baseline. Setup failure or an unmeasured timeout
cannot. A supported product correction may start at this point; permanent
registration, a new checker, and its full control suite are not prerequisites
for the product edit.

Repeat the same trigger and measurement after the fix. Keep the expected
result and thresholds unchanged. Before closure, retain a durable regression
scenario or invariant and obtain the required registered controller acceptance
on the final ROM. If a checker is completed later, evaluate the preserved
pre-fix data against the same symptom assertion where those data permit it.
If required baseline data are missing, report that exact gap and obtain them
through the shared tools; never manufacture a red result or relax acceptance.
Diagnostic success alone does not prove that the bug is fixed.

Read the production path before extending measurement tools. Add only the
missing observation needed for the next decision. Once it is available, return
to the product fix. A proof-tool gap blocks the associated acceptance claim;
it does not block independent diagnosis or a correction supported by the
preserved reproduction. The [goal progress rules](roadmap.md#goal-progress-rules)
apply across turns and helper handoffs.

## Proof rule

Static shape is not runtime behavior. A verifier that checks source text, an ABI table, or an instruction address can prove packaging, but it cannot prove movement feel, exact completion, control release, or presentation synchronization.

Every claim names its proof level:

| Level | Proves | Typical tool |
| --- | --- | --- |
| S0 Schema | Data shape, units, bounds, generated agreement | Schema validator |
| S1 Model | Resolver, planning, timing, path-advance, commit, and reason semantics | Deterministic host scenario |
| S2 Package | Overlay size, address, entry, ABI, and ROM packaging | Existing static verifiers |
| S3 ROM | Real engine objects, streaming, transitions, input, and lifecycle | `owctl scenario run` |
| S4 Presentation | Sprite placement, arc, spin, effects, and control feel | Current native presentation poses, effect/sound receipts and frame timing checked by the accepted scenario |
| S5 Soak | Rare races and cumulative state leaks | Bounded repeated ROM scenario |

`scripts/verify_overworld_actor_transition.py` proves the deterministic host
state machine and checks that the field, wild, and throw-helper adapters use
the typed callback slots. It rejects the former map-header callback and
negative-slot presentation commands. This is S1 and source-contract proof; it
does not replace the S3 transition scenario.

A change uses all levels that match its risk. S4 means measured presentation,
not image interpretation. Screenshots supply no proof at any level.

## Memory-backed proof

Image/video capture is off by default. Only an explicit user request or manual
Capture click requests an image; test jobs, setup, input and play must not.
Structured memory/trace data are not video. Say "memory data" in user reports
to distinguish them from images. Shipped scenarios set `capture` to `none`;
the frozen migration history retains old metadata, not an active capture path.

Screenshots are optional artifacts for the user to view. An LLM must not use
them as evidence for any test claim, including actor presence, terrain type,
height, landing, smooth motion or lack of a bug. Opening an image is not a
verification step. Missing or misleading screenshots cannot change acceptance;
a screenshot cannot supply a missing native measurement.

Use the shared devtools to read the smallest claim-specific live state:

- Terrain: loaded block identity, tile attribute/behavior, collision and the
  resolved encounter/movement permissions. Keep unknown separate from blocked.
- Height or tree/roof support: the live surface/model identity and checked
  native ground-height result, bound to that point and current world context.
  Tile attribute high bits are not an elevation value. A logical tile or an
  actor's own rendered Y alone cannot establish its expected support surface.
- Presentation: same-actor native render poses, offsets, facing, visibility,
  effects/sound calls and complete game-frame timing. A logical motion plan
  alone does not prove that its presentation was applied.
- Spawn and mobility: the same encounter's own input/final site, completed
  landing, then an eligible completed move by that exact live actor.

Authenticate readers against public layouts or stock/native code. Bind each
receipt to the actor when applicable, the map generation, point and observation
boundary. Test stale/wrong identity, missing data and deliberately incorrect
behavior through the same reader. A copied-data check tests the evaluator only.
Missing observations remain explicit proof gaps. Build or improve the shared
reader when a gap blocks progress or repeated inspection is slow; do not add a
separate emulator driver or substitute image guesses. Prefer bounded point or
event reads over full-map/per-frame scans. Use this section when adding proof
requirements or maintaining agent skills.

For the normal Walk crash shake, rendered position and the motion endpoint
are separate values. Read the same actor's native shake timer and saved base
position, including timer zero. A supported effect needs an exact completed
Walk, a base at its target, the source-defined offsets, a dense countdown and
exact restoration before acceptance. Keep the original rendered samples and
the checked effect separately. Do not add a position tolerance or infer an
effect from a matching offset alone. A missing owner, timer, or restoration
is a proof gap or failure, not a valid endpoint.

A same-object area handoff may restore a pending crash shake early. The
checker must retain this as `transition-restored`, not a full countdown.
Require adjacent completed-frame observations, ordered context-change and
rebound receipts, unchanged subject and terminal motion, the exact restored
X/Y/Z pose, and cleared timer/base metadata. A changed map or a zero timer
alone cannot prove restoration. Controller replay must match the restoration
to that route's retained handoff and recheck the raw pose.

## Scenario contract

Scenarios are declarative data under `tests/overworld/scenarios/`.

Each scenario contains:

- Stable ID and capability IDs.
- ROM/save fixture and deterministic random seed.
- Capability and actor-role expectations through the feature map.
- A reviewable input and lifecycle event sequence.
- Stop condition and frame budget.
- Required decisions, commits, poses, and trace events.
- Forbidden events and invariant violations.
- Proof level and cost tier.
- Native observation and retention policy. Optional human-view screenshots
  never supply acceptance evidence or become a required test step.

Every run writes a manifest containing product-content identity, source
revision for provenance, ROM hash and build manifest ID, save hash, scenario
revision, debug-descriptor version, emulator and version, random seed, proof
level, start time, and result. Evidence without this identity is not reusable
proof. A content-preserving commit or documentation-only edit must not stale
gameplay evidence. Relevant product, build, fixture, observer, or scenario
changes must stale it. Each run keeps its own evidence; a later run must not
overwrite files referenced by an earlier manifest.
Each command also keeps its complete stdout and stderr in run-owned artifacts,
including failures and timeouts. The manifest links their sizes and hashes;
short output tails are navigation aids, not the complete failure record.
Read the linked output when the summary does not explain a failure. A passing
receipt cannot be reused if either complete stream is missing or changed.

Use [reproduction and acceptance](#reproduction-before-editing-acceptance-before-closure)
for a runtime fix and [intermittent reports](#intermittent-reports) for repeat
coverage. The [verification skill](../../.agents/skills/verify-overworld/SKILL.md)
routes these requirements to registered execution.

A species-specific S3 claim must prove that species is a live actor in the
current map. The scenario verifies the species, active spawn slot, current
`MapObjectMan` membership, object ID, map ID, script ID, encounter generation,
actor handle, and presentation attachment. An actor-observation scenario also
declares a structured `subjects` contract. The controller checks the public
snapshot count, current field epoch, generation-safe handle, presentation, and
that the selected motion belongs to that subject. Its negative control removes
or changes the subject and must fail. A second controller-owned negative
control removes a required semantic behavior event and must also fail. For an
off-screen spawn, it also proves the real spawn motion reaches its valid
target and returns control. Move From Off Screen proof must also show that the
origin is between1 and16 cardinal tiles from its selected spawn tile and at least four tiles
beyond the current player-relative inclusive8-by6 view, and the fixed spawn tile is only a target substitution in the normal
Owner destination trip. A missing eligible origin must reject the spawn; an on-screen
fallback fails.
Static acceptance rejects a separate entry scheduler or completion path and
rejects entry-only changes to Walk pause, Movement Chain, stamina, tired
effects, turn skid, battle rules, or previous-tile policy.
Changing only a test label, profile buffer, or expected species value is not a
species-specific runtime test.

A role-specific claim cannot use a different actor role as evidence. An
unmounted Wild claim must observe a `WILD` subject, and an unmounted follower
claim must observe a `FOLLOWER` subject. Either claim fails if the selected
subject is `MOUNTED`, even when the species and movement profile match. Do not
turn a whole-engine stutter report into a mounted-only claim without evidence.

The feature manifest separates supported roles from required live role proof.
`roles` lists the roles that a capability supports. Optional `roleProof`
entries name the exact runtime proof level and roles that must have accepted
live witnesses. A structured scenario subject supplies its measured motion
actor role. A lifecycle scenario can also declare a scenario `roleProof`
witness, but only by naming a registry measurement that has a fixed string
expectation for that role. Contract validation rejects an unknown claim,
missing measurement, non-runtime adapter, or role expectation mismatch.
Static checks never create live role credit. This keeps the supported
`Scripted` role possible while no production Scripted caller exists, and it
prevents mounted evidence from satisfying the unmounted Wild or Follower soak.

The trace ring is bounded. A scenario selects only the events needed for its
claim and stops after the required terminal result. Its selected event set and
frame budget must fit without overwrites. An overwritten event, a motion that
has only started, or a stop condition based on helper-call count is incomplete
proof.

The command adapter currently owns engine setup and executes the event and stop
contract. Actor-observation adapters also bind that contract into an execution
receipt. Assertions remain semantic and declarative.

S4 executable scenarios must name `rendered-motion`, `frame-pacing`, or
`feedback-effect` and check their native observations. Screenshots are optional
human-view attachments; no PNG presence, content or freshness grants proof.
Keep sealed native evidence from earlier runs. S5 scenarios must use
a bounded minimum and maximum of at least 5000 frames. Their receipt records
each iteration's positive frame count and non-empty evidence hash. Contract
validation rejects weaker declarations.

## Intermittent reports

One green run cannot clear an intermittent bug. Use an accepted S5 scenario
with at least 5000 observed subject frames in one continuous emulator session,
or repeat the accepted S3/S4 scenario over the reported failure window.
Separate boots cannot be added together to meet the S5 floor. Setup and
observer-control frames do not supply subject proof. Report every attempt,
including failures. Keep the bug open if any required repetition fails; use
[failure records](#failure-records) for the limited review of pre-game failures.

## Design the test before the run

Write the behavioral claim before its measurement code. Name the requirement
or verified vanilla reference that supplies the expected result. Do not copy
the current implementation's formula as an independent expected result.
Use the [outcome-first loop](devtools-tests.md#outcome-first-tool-work) to obtain
one bounded real memory sample before building the full checker stack. Reuse
shared measurements and tie each missing tool seam to the next game check.

Each feature recipe records the exact actor and role, resolved profile and
starting state, actions, observable result, forbidden result, stop condition,
frame budget, cleanup, and evidence limit. A missing required starting actor or
invalid fixture is a setup failure, not a pass or a reproduction of the motion
bug. If the scenario tests spawning, failure to create the expected actor after
the declared trigger is the behavior failure; do not dismiss it as setup.

The scenario's `verification` record stores the claim's `kind`,
`expectationSource`, `actor`, `trigger`, `observable`, `setupAudit`,
`setupMutations`, and `limits`. Audit the selected collector's setup and
callbacks before marking an executable case's `setupAudit` complete. List
mutations before and during observation. `pending` is an open review gap, not
normal-play credit. A planned recipe is design only: audit its collector again
before activation, even if the planned no-mutation recipe says `complete`.
Audit the cases needed for the next slice first; do not make every remaining
setup audit a prerequisite for the early checkpoint.

Keep these proof types distinct in the recipe and result:

Prepared fixture data and forced behavior are different. Healing party data,
selecting a follower or placing the player through checked shared setup may
establish a movement fixture. That fixture can prove later normal movement
with unchanged timers and profile rules, but cannot prove natural healing,
selection, placement or spawning. Do not require those unrelated interactions
for a movement claim. Record setup and readback separately from measured play.

| Test type | Arrangement | What it can prove |
| --- | --- | --- |
| Normal play | Declared fixture/seed; normal resolver and timing after setup | The user behavior under those conditions |
| Controlled case | Explicitly forced retry, boundary, or fault | The response to that condition; not normal cadence |
| Observer control | Deliberately wrong behavior presented to the real recorder, with the checker held fixed | That the recorder and checker detect that failure |

Controller-owned changes to copied evidence, such as deleting a subject or a
semantic event, remain useful **evaluator controls**. They prove checker
sensitivity only. They do not prove that the live recorder sees the fault.
When adding or changing a recorder, pair its valid observation with a small
known-bad observation through the same recorder. Prefer an existing failing ROM
scenario or a disposable production-boundary fixture; never change the shipped
ROM just to manufacture a passing test-of-test claim.

Run the two live recorder controls as separate scenarios:
`observation.live-actor-and-motion-control` checks Ledyba identity and rendered
motion; `observation.live-route-control` checks the unmounted follower/player
route and native-cycle cost recorder. Both need their own positive baseline
and fault detection, and both are required by the roadmap gate. Each command
owns one disposable session through the shared devtools. The current native
transport is being replaced with melonDS; the historical DeSmuME results must not be labeled melonDS
proof. Never destroy and recreate this core in one process. Do not reuse a
fault-injected session for normal-play proof or add control frames to it.

For a runtime fix, use [reproduction and acceptance](#reproduction-before-editing-acceptance-before-closure).
For an ownership refactor, use passing baseline/parity evidence instead. For a
test-tool fix, use a known-bad receipt or fixture that demonstrates the tool
defect. Do not retroactively invent a pre-fix gameplay failure.

For a native ABI observer, anchor event IDs, argument order and memory ranges
to the public header or compiled native function, not matching constants copied
into both the evaluator and its synthetic fixture. Keep a control that rejects
the old wrong interpretation. Before another boot after a tool fix, replay the
retained stream to its first useful boundary. Diagnostic replay alone does not
grant acceptance; use the controller's current-input checks to decide reuse.
Changed live readers or missing native data need a fresh run. Completed-motion proof failures
must stop the checked job when known, rather than wait out its frame budget.

Scenario setup must use the selected Pokémon's own resolved spawn location and
landing rules. Never substitute another Pokémon's destination or swap species
while retaining an old spawn pose. Bind the native prepared encounter, startup
origin/target and live object to the same species, personality and generation.
Check its actual landing surface before crediting later motion; a tree, roof,
flower bed and ground tile are not interchangeable. An intentional invalid
landing test must be a separate rejection/control case, not a normal fixture.

Normal Ledyba proof must observe a live Ledyba's normal off-screen spawn and
resolved chain count, complete eligible moves, pause duration/action, and
visible movement. Forcing a chain, clearing cooldown, or overriding timing
during measurement makes that a controlled case. Four reposition motions and
control return alone do not prove the authored natural chain interval. Keep
that limited test, but do not use it to close the broader report.

Capture the expected chain/pause fields before the interval and keep them
immutable. A normal AI lane change can alter alertness or stamina without
altering those measured fields. Each policy call must still match a complete
lane from the captured resolver result and the same fingerprint, and every
measured field must match the captured expectation. Keep its lane bytes and
matching resolver indexes in the receipt; do not silently learn new expected
counts from a later call or use a raw AI state as a resolver-lane index.

The unmounted route fixture preserves the saved Cyndaquil's identity. Use
shared prepared HP/status and saved-follower commands in the disposable
session, with native party readback and live actor binding. Do not require
nurse dialogue or Y-menu input for this movement-only claim. Retain the setup
receipts and drained event boundary; setup contributes no movement frames.
Preserve source saves, movement profiles and normal timers. Selection and
healing interactions have separate tests when those interactions are claimed.

A stutter witness needs whole-game frame timing over the route and trigger
conditions in the report. Record the actual duration and observed frame count.
Short repeated walks and a mounted-only soak do not cover long unmounted
travel or area-loading behavior. The 5000-frame S5 floor is a minimum, not a
claim that every intermittent failure window is covered.

`world.unmounted.spawn-zero-stutter` is the player-visible spawn-stutter gate.
It loads `test.sav` without edits and binds the existing Follower Mankey. After
the Cherrygrove seam, it samples every mandatory main-loop wait during the
sealed walking route. A frame counter, native-cycle interval, or scheduler
sequence above `2` fails at once. Zero late loops is the only pass. The full
fixed run must also contain natural spawn work; a no-spawn route cannot pass.
The search and finalizer must join on attempt, finalization, slot, and map
identity. A successful actor spawn is not required because a rejected placement
scan can still cause the hitch.

## Feature map

The validated machine-readable source is
`tools/overworld/system_features.yaml`. It owns source patterns, checks,
scenarios, documents, roles, and minimum proof. The table below is generated by
`scripts/generate_overworld_feature_table.py`. Do not edit it by hand.

Contract validation also checks proof feasibility. Every exact level in a
capability's `minimumProof` must be supplied by at least one linked check or
scenario. A capability cannot enter the catalog with a proof requirement that
its own graph can never satisfy.

<!-- BEGIN GENERATED OVERWORLD FEATURE MAP -->

| Capability | Owner | Roles | Minimum proof |
| --- | --- | --- | --- |
| Resident actor facade (`actor.system`) | Actor facade | Wild, Follower, Mounted, Scripted | S0, S1, S2, S3 |
| Profile composition (`profile.composition`) | Resolver | Wild, Follower, Mounted | S0, S1, S3 |
| Exact Walk (`walk.exact`) | Motion Module | Wild, Follower, Mounted | S1, S2, S3 |
| Walk acceleration (`walk.acceleration`) | Motion Policy | Wild, Mounted | S1, S3 |
| Turn and stop skid (`walk.skid`) | Motion Policy | Wild, Mounted | S1, S3 |
| Stomp and crash (`walk.feedback`) | Motion reactions | Wild, Mounted | S1, S3, S4 |
| Diagonal Walk (`walk.diagonal`) | Motion planner | Wild, Mounted | S1, S2, S3 |
| Hop (`hop`) | Motion Module | Wild, Mounted | S1, S3, S4 |
| Ledge Hop (`hop.ledge`) | Motion planner | Wild, Mounted | S1, S3 |
| Teleport (`teleport`) | Motion Module | Wild, Mounted | S1, S3, S4 |
| Chain movement (`chain.movement`) | Role controllers | Wild, Follower, Mounted | S1, S3 |
| Mount lifecycle (`mount.lifecycle`) | Mounted role adapter | Follower, Mounted | S2, S3, S4 |
| Mounted presentation (`mount.presentation`) | Mounted presentation adapter | Mounted | S3, S4 |
| Terrain streaming (`world.streaming`) | World adapter | Mounted | S3 |
| Field transition (`world.transition`) | World lifecycle | Wild, Follower, Mounted | S3, S5 |
| Warp gating (`world.warp-gating`) | World reactions | Mounted | S3 |
| Wild population (`population`) | Population module | Wild | S1, S3, S5 |
| Conditional profile activation (`condition.evaluation`) | Behavior Condition Evaluator | Wild, Follower | S0, S1, S3 |
| Shared Current and Custom Vision (`vision`) | Vision service | Wild, Follower | S0, S1 |
| Owner and Tired behavior lanes (`profile.state`) | Behavior Resolver | Wild, Follower, Mounted | S0, S1 |
| Condition-triggered presentation (`alert`) | Role controllers (presentation) | Wild, Follower | S0, S1 |
| Spawn policy (`spawn`) | Population module | Wild | S0, S1, S3 |
| Battle profile policy (`battle`) | World reactions | Wild | S0, S1 |
| Terrain policy (`terrain`) | World adapter | Wild, Follower, Mounted | S0, S1, S3 |
| Walk profile policy (`walk`) | Motion Module | Wild, Follower, Mounted | S0, S1 |
| Walk momentum profile (`walk.momentum`) | Motion Policy | Wild, Mounted | S0, S1, S2 |
| Chain profile policy (`chain`) | Role controllers | Wild, Follower | S0, S1, S3 |
| Chase profile policy (`chase`) | Role controllers | Wild, Follower | S0, S1 |
| Battle and capture handoff (`battle.capture`) | World reactions | Wild | S2, S3 |

<!-- END GENERATED OVERWORLD FEATURE MAP -->

## Baseline scenario set

The scenario catalog includes:

- `profile.resolve.override-order`
- `profile.resolve.follower-mounted-parity`
- `walk.cardinal.frames-1-32`
- `walk.diagonal.corner-block`
- `walk.turn-skid.control-release`
- `chain.pause.counts-semantic-moves`
- `hop.cardinal-and-diagonal`
- `hop.mankey-visual-arc`
- `spawn.appear-hop-timing`
- `hop.ledge-up-and-down`
- `hop.mounted-single-motion`
- `teleport.wild-lifecycle`
- `teleport.fixed-and-per-tile`
- `mount.begin-current-follower`
- `mount.detach-restores-control`
- `mount.transition-mid-motion`
- `world.streaming.cardinal-held-route`
- `mount.movement.frame-pacing`
- `world.streaming.path-advance`
- `warp.blocked-mid-motion`
- `world.transition.wild-invalidation`
- `world.transition.follower-rebind`
- `population.land-surf-separation`
- `battle.capture.wild-handoff`

Use `scripts/owctl scenario list` for the current catalog; do not maintain a
second count here. A scenario cannot be reported as live proof until it passes
on the current candidate. Every executable runtime adapter declares
measured claims and is checked through `scripts/owctl scenario run`. A direct
runner exit is diagnostic only.

Every past high-impact bug should map to one of these scenarios or add a narrower permanent scenario.

## Stable observation assertions

Scenarios assert on the `Inspect` snapshot and semantic trace, never on private implementation arrays when a public semantic field exists.

Required invariant assertions:

- No actor has two motion owners.
- Authority, engine anchor, and dependent presentation have the expected relation.
- No stale actor handle or field epoch is dereferenced.
- Each accepted intent has one terminal result.
- Each motion has ordered path advances and at most one terminal commit.
- A staged Walk retains its Walk kind until its terminal actor boundary.
- Every tile of a staged multi-tile Walk has one start, one finish, no cancel,
  one control return, and a successful terminal Walk call before the next tile.
- A staged Walk remains Walk on every tile; its continuation cannot change to
  Hop when only one tile remains.
- A staged path cannot start its next tile before the actor's authored settle
  pause ends. A lane that no longer supports Walk or Hop clears the path.
- A deferred chain action starts only after the previous shared motion returns
  control; a busy boundary keeps the action pending.
- No commit occurs after cancel.
- A finished mounted Walk receives its genuine stock END before world-gate
  filtering. The actor receipt is one-shot; a deferred ordinary field step is
  retained until stream acknowledgements open the gate. It must run once before
  a successor Walk. Mid-travel, Hop, Teleport and stale-field signals cannot
  supply this Walk receipt; detach drops any retained field step.
- Input ownership returns after finish or cancel. Actor detach is also a
  terminal release because the actor and its input claim no longer exist.
- Chain and acceleration counters change only for eligible commits.
- Path advances and stream anchors do not skip required tile updates.
- Warps do not fire during ineligible motion phases.
- All target reservations are released.

## Verification cost and checkpoints

Use the smallest proof that can settle the current question without weakening
the final gate. Use these checkpoints:

Stop the ladder at its first failed layer, preserve the evidence and resolve
that failure before continuing.

1. During an edit, run the relevant host behavior and production-adapter checks.
   Source strings are packaging/shape checks, not behavior tests.
2. At a stable contract boundary, check exact ABI/link limits, build a candidate
   when needed, and run the focused accepted ROM scenario.
3. At a slice integration checkpoint, inspect and run the affected proof set.
4. At the frozen release candidate, run all required scenarios and the full
   roadmap gate. Product edits reopen affected proof before a new final gate.

`scripts/owctl progress --json` is a read-only summary of recorded scenario
results: recorded-pass, failed, stale, untested, or planned. It starts no build,
static tests, or emulator. Use it to resume and select work, not to claim final
acceptance. A cached result is usable only when all relevant inputs match; the
existence of an old green result is not a cache key.
After a checker-only edit, use [retained proof recheck](devtools-tests.md#recheck-retained-proof)
in a fresh host process before another boot. New scoped manifests separate
capture inputs from checker inputs; old unscoped manifests remain fail-closed
against their full original source identity. Do not rewrite their history.

Do not run the whole dirty-branch affected set after every small patch. Record
the chosen capability and exact checks for the active contract, then use the
broader affected graph at a stable checkpoint. Measure actual build and run
cost at the early checkpoint; do not optimize test cost by omitting required
roles or triggers.

## Affected verification

The `tools/overworld/system_features.yaml` manifest maps:

- Source paths and symbols.
- Profile fields and schema entries.
- Actor roles and adapters.
- Trace event groups.
- Scenarios and proof levels.
- Documentation contracts.

`scripts/owctl verify affected` compares the working diff to that manifest and
prints the selected proof set. Add `--run` to execute the ready checks from the
lowest cost to the highest cost.

S3-S5 checks never run as raw `exit-zero` commands in this workflow. Affected
verification routes them through their claim-bearing scenarios. It stops when
a runtime check has no active scenario that executes that check's exact
registered runner. It also runs the host proof gate whenever runtime proof is
selected.

Before any S3-S5 emulator command, `scenario run` executes
`scripts/verify_overworld_runtime_fixture.py`. This gate requires the current
Make target, sealed build manifest, packaged ROM, actor and mount package
checks, built actor overlay, and generated debug descriptor to agree. A stale
product source or ROM stops the scenario before gameplay evidence is collected.

`scripts/owctl verify roadmap --json` is the permanent roadmap exit gate. It
does not start an emulator. It audits every scenario and capability, reports
all planned scenarios, requires exact runner-matched coverage for every S3-S5
runtime check, requires every exact level in each capability's `minimumProof`,
and rejects actor-scoped S3-S5 adapters without structured actor-observation
subjects. It also runs the static runtime-fixture preflight and records the
final ROM, sealed build manifest, debug descriptor, and actor-overlay identity.
It rejects active collectors whose `setupAudit` is pending. Review these in
their delivery slice, not as a prerequisite to every early checkpoint.
Observer-control scenarios remain required recorder proof but cannot supply
gameplay capability, actor-role, or runtime-check credit. Any reported gap
makes the command fail.

## Reviewed requirement replacement

Retire duplicate legacy checks only when an implemented replacement covers
every original measurement. Keep the original record, contract hash and history
in `tools/overworld/runtime_proof_migration.json`. Set its status to `superseded`
with `tests: []` and a `review` containing `reviewer`, `reviewedAt` (`YYYY-MM-DD`),
`reason` and `coverage`. Each coverage row names `claim`, `measurement`,
`replacementRequirement`, `replacementClaim`, `replacementMeasurement` and its
`reason`.

The validator requires each original measurement exactly once. The replacement
must have the same verification kind and claim, and the same exact measurement
contract except its name. Replacement chains must have no cycle and end in
ported, registered shared tests. The proof gate follows those replacement
requirements and still needs their accepted runs. A review is not game proof.
This removes repeat tests, not the behavior requirement. It cannot weaken a
threshold, delete a requirement, or dismiss a runtime failure. Use the separate
[failure-record rules](#failure-records) for failed runs.

## Failure records

Keep failed and passed evidence in their run directories. Record every attempt
relevant to an intermittent report. A later pass does not erase a same-candidate
game failure.

The coordinator records each failure as game, setup, harness, host, or unknown
in the current work item. Unknown stays open. Review resolution is restricted
to controller-proven failures before gameplay: `fixture-preflight` or
`collector-launch`. It needs the cause, a review artifact, and a current accepted
replacement with the exact same candidate and scenario identity:

```bash
scripts/owctl runs resolve <failed-manifest> --category setup \
  --reason <explanation> --evidence <review-file> \
  --replacement <passed-manifest> --reviewer <name> --json
```

Use `harness` or `host` instead of `setup` only when the review proves that cause.
The command records a separate review in
`documentation/overworld-system/failure-dispositions.json`; it does not edit
the original result. Runtime timeouts, crashes, missing receipts, and observed
failed behavior claims cannot be dismissed by this route, even if no claim
fields were captured. Missing evidence does not prove a host fault. Keep those
failures open and investigate the game/recorder boundary. A product fix needs
its symptom-specific regression witness and repeat coverage. The
[work ledger](roadmap-progress.md) holds the next action, not another copy of
test output.

## Progress and handoffs

Keep three distinct records:

- `roadmap.md` owns scope and completion rules. Do not copy changing status into it.
- `roadmap-progress.md` is a short resume page, roughly100 lines: one work table,
  active issue, latest evidence links, next action and session ownership.
- Immutable run manifests own detailed results. An archive holds past investigations;
  read it only when a named failure needs that history, not at every resume.

The coordinator replaces stale state after an integrated result or handoff.
Do not prepend a new checkpoint, add a second table, or paste test output.
Keep one active contract's role, owner, relevant files, evidence links, failure
class, attempts without new evidence and one next action. Classify failures as
game, setup, test-tool, host or unknown; unknown remains open. Preserve unresolved
failures as links even after a later pass. Use the failure-record procedure for
formal dispositions; a shorter log cannot close a requirement.

Move useful resolved investigation notes to the archive, preserving their links;
prefer existing manifests over another prose account. Do not duplicate detailed
results or hand-count pass totals. Reuse a recorded test-selection decision until
its requirement or inputs change. Keep the main page short by replacing state,
not by dropping scope or hiding failures.

Helpers return `ID; files changed/released; observed facts; evidence; unresolved
question; next action`. The coordinator reconciles this into the one table.
After two attempts without new evidence, record the changed method before another
patch. At resume, read the page and recheck live session ownership and relevant
manifest identities. Read only the linked detail needed for the next action.

## Current proof limits

The current `scripts/verify_overworld_mount.py` is strong package and ABI proof. Much of it checks fixed addresses, entry layout, source patterns, and instructions. It does not by itself prove smooth control, exact per-frame interpolation, terrain streaming over time, or safe repeated detach.

The current Walk verifiers protect timing policy and several source-level invariants. They do not yet prove all frame boundaries across wild and mounted roles for values 1 and 32.

The former standalone scenario backends and their bespoke input loops are
removed. [Checked test jobs](devtools-tests.md) use the shared devtools probe,
generated debug descriptor and semantic events. The migration map retains all
old requirements as explicit gaps until a registered shared-tool witness covers
them. A setup recipe or evaluator pass alone does not grant accepted proof.

The public host probe has three commands:

- `scripts/owctl actor inspect <capture>` reads public actor snapshots.
- `scripts/owctl actor trace <capture>` reads the semantic trace ring.
- `scripts/owctl actor capture <memory> --scenario-id <id> --rom <rom>` with
  `--save <save> --seed <seed> --execution <receipt>` and
  `--output <evidence>` creates reusable input for an `actor-observation`
  scenario adapter without runtime claims.

The generated descriptor owns all state addresses, strides, capacities,
public structure formats, and enum IDs used by these commands. A descriptor
and runtime image mismatch is invalid proof.

Actor-observation evidence is accepted only when its explicit ROM, save, seed,
scenario, and descriptor identity match the requested scenario. Required and
forbidden events apply to one uniquely selected actor motion window and retain
their declared order. Every invariant string must map to registered executable
checks; unsupported prose keeps the scenario invalid.

## Runtime proof claims are fail-closed

An executable S3, S4, or S5 scenario must declare the player-visible facts it
proves in `adapter.claims`. The shared scenario runner accepts the command only
when its JSON result contains measured `proofEvidence` for every declared
claim. A successful process exit, `passed: true`, or `proofClaims: true` is not
sufficient.

Each claim contains one or more measurements. The shared runner calculates the
result from `actual`, `expected`, and an optional operator. Valid operators are
`eq`, `ne`, `lt`, `lte`, `gt`, and `gte`.

```json
"proofEvidence": {
  "frame-pacing": [
    {
      "name": "maximum-callback-gap",
      "actual": 2,
      "expected": 2,
      "operator": "lte"
    }
  ]
}
```

Every measurement needs a unique name and a registry-owned acceptance rule.
The registry supplies a fixed expected value, a bound, or a named validator.
An empty or zero self-equality is rejected. The accepted measurements are
copied into the run manifest. When one scenario uses more than one command,
every command must prove the full claim set.
`tools/overworld/runtime_proof_registry.json` binds every runtime script and
scenario to that exact set. An unregistered runtime script cannot bypass the
session, measurement, frame, or artifact gate.

Use the narrowest applicable claims: natural input, live actor identity,
logical commit, engine boundary, rendered motion, frame pacing, control
release, collision decision, profile resolution, terrain selection, streaming
path, world transition, population bounds, feedback effect, or host CPU pacing.
A scenario must measure the layer named by its claim. Logical coordinates
cannot prove rendered motion. End points cannot prove frame pacing. A forced
private counter cannot prove natural input.

Host CPU pacing is separate from emulated frame pacing. It uses
`time.process_time_ns()` around each real emulator frame and a registry-owned
repeated-hitch threshold. Wall-clock samples can remain as diagnostic output,
but they are not accepted proof because unrelated host scheduling can change
them. An unmounted actor regression needs an unmounted wild or follower subject;
mounted samples cannot satisfy that role-specific claim.

Coherent actor/render sampling and native-cycle pacing use separate clocks.
The [sampling rules](../../.agents/skills/verify-overworld/references/scenario-measurement.md#sampling-constraints)
define the authenticated stock frame boundary and normal-input setup checks.
Do not infer one game update from one emulator cycle.

For a runtime bug, follow
[reproduction and acceptance](#reproduction-before-editing-acceptance-before-closure).
A measured shared-devtools reproduction can support the product fix. Durable
registered proof is required before closure. The fixed run must prove the same
measurements without changing or weakening them.

The old failed grass-only full-scan soak is obsolete. The legacy
`OverworldWildHelper_TryPickSpawnPosition` path checks at most16
distance-eligible tiles in one game update. Its extracted production-source
host check proves the16-check bound, the unchanged logical16-candidate attempt,
cursor order, and unchanged output on rejected tiles. This result does not
cover the separate profile destination-mask scanner.

## Spawn-work budget and proof freshness

Every automatic spawn-destination scanner shares two pacing limits. It performs
at most16 expensive candidate terrain queries in one completed game update. It
also resolves the profile and prepares spawn metadata/class only once for the
complete attempt; every resumed update reuses that prepared result. The limits
apply to legacy Pool selection and explicit profile masks, including Pool (`8`),
Bird (`448`), Flower (`512`), and mixed land/Surf (`15`). Cursor state may resume
on later updates, but final row-major reservoir selection, occupancy checks, RNG
calls, failure output, and all eligible candidates must stay unchanged.

Use both extracted-C checks before a ROM run:

```bash
python3 tools/overworld/test_spawn_refill_budget.py
python3 tools/overworld/test_spawn_destination_scan.py
```

The destination-budget checker includes known-bad controls with13 candidate
queries in one update and repeated profile preparation on a resumed update.
Both controls must be rejected for their matching reason. A product check that
still batches queries or repeats preparation is a real red result; do not label
it a checker failure or skip it to reach a live test.

After the host checks pass, run the bounded
`population.spawn-work-budget` scenario on the current ROM. Its fixed route
crosses the map seam from Route 30 into Cherrygrove. Its strict window starts on the
first completed update after that seam and keeps the player moving through the
scan. It must observe one natural helper-to-explicit-scanner handoff, one
complete explicit scan,
exactly one profile receipt for the attempt, completed game-update boundaries,
zero terrain-matcher queries on setup, exactly 20 resumed batches, no update
above the 12-query cap, no resumed finalizer above its guest-work
budget, and one successful prepared encounter actor on the next update. That actor
must use its normal Fly In from the retained off-screen origin to the
retained target. The test measures every main loop from the first strict
post-seam update through the loop after actor creation. Zero
late loops is the only pass: `gSystem.frameCounter` must stay at or below `2`,
native-cycle and frame-sequence intervals must stay at or below `2`. The ARM9
clock cross-check allows only the sub-VBlank hook offset and must stay below
`2800950` ticks. It must also record at least
120 post-seam in-transit player samples, with an exact sub-tile position change
on every one. One late loop or one frozen in-transit position fails the test
even when
all spawn-work counters pass. The extracted-C
checks own the full 240-candidate matrix and selection/RNG parity. The live
scenario is
the short current-candidate gate. The longer intermittent cadence run still
supplies the full failure-window proof at integration and final release.

The short budget scenario does not close a player-visible stutter report. Run
`world.unmounted.spawn-zero-stutter` on the same current `test.nds` and
`test.sav`. Its unmodified Continue state and existing Mankey are part of the
contract. Do not replace the follower, heal a party member, refill population,
or otherwise prepare the save. It binds Mankey's current source-checked
resolved profile. Separate movement scenarios own Hop and Movement Chain
timing; a valid profile pause does not fail the spawn-stutter gate. The gate
also rejects an explicit destination scan over21 frames. Population-count
behavior stays in the separate population scenarios. One loop above two frame
times is a red result, even if candidate and preparation budgets pass.

Changes to spawn search, population refill, behavior profiles, destination
masks, generated behavior data, or the live observation/capture path stale the
D1 result. A checker-only change needs an independent retained-data recheck and
its controls. Reopen D1 and the related D5 population proof. A population
count, surface result, helper-only check, or old ROM run cannot preserve pacing
proof. The feature manifest owns these dependencies so `verify affected`
selects them. Do not restore the old false-return soak or its one-call full-scan
assumption. The slow-resumed-finalizer copied control must also fail for its
work-budget reason. A passing tool gate does not close a current player report. Keep D1
open until the user checks the same current `test.nds` and reports the result.

The old combined mounted diagonal stress is also obsolete. Its runner changed
cardinal-only Cyndaquil into a diagonal five-frame Walk profile in memory.
Current diagonal streaming proof must use an authored diagonal actor; the
registered Ledyba path covers both public stream axes. Keep Cyndaquil streaming
proof cardinal and use its resolved authored profile.

## Completion gate

A migrated capability is complete only when:

1. The feature manifest names one owner.
2. Its shared contract has a model scenario.
3. Engine-specific behavior has a focused ROM scenario.
4. Mounted and wild parity is checked where the contract is shared.
5. The old implementation path and implementation-specific tests are removed.
6. The canonical docs, project verification skill, and trace decoder match the
   shipped interface.
