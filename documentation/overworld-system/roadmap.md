# Overworld Actor System Roadmap

## Objective

Make the overworld Pokémon system easy to extend and cheap to diagnose without changing current game feel during migration.

The migration wraps, observes, compares, switches, and deletes. It is not a full rewrite.

## Scope and current state

Phases 0–8 below define the full required outcome. They are not a claim that
the current branch passes. Keep current state only in
[`roadmap-progress.md`](roadmap-progress.md), a short resume page with one work
table. Detailed results belong in manifests; past investigations belong in the
linked archive, read only when needed. Neither historical notes nor this page
replace current proof. Follow [record ownership](verification.md#progress-and-handoffs).
The capability and proof requirements remain in
`tools/overworld/system_features.yaml`; `scripts/owctl verify roadmap` remains
the final completion authority.

Use the finite delivery slices below to finish the existing work. Do not start
another rewrite, discard useful code, or postpone required behavior as cleanup.
An already satisfied requirement needs current evidence, not reimplementation.

## Phase 0 - Canonical system map

- Define one vocabulary.
- Define one architecture, frame order, ownership model, and invariant set.
- Define one proof ladder and feature map.
- Route agents and historical documents to the canonical entry point.

Exit gate: a new agent can find the current owner, target owner, required roles, and proof level without reading attempt logs.

## Phase 1 - Observe current behavior

- Add a read-only, versioned compatibility snapshot with stable semantic fields.
  Its private storage adapter can change in later phases.
- Add the minimum generation-safe actor handle and field epoch required by
  that snapshot. These identifiers remain stable through later storage changes.
- Add a filtered fixed-size semantic trace ring.
- Generate `build/overworld-system.debug.json` with ABI versions, enum IDs, symbols, and snapshot offsets.
- Create the first declarative scenarios from explicit intended contracts.
  Known bugs start as failing scenarios and never become accepted baselines.
- Create the machine-readable feature/impact manifest at
  `tools/overworld/system_features.yaml` and generate the human table from it.
- Add `scripts/owctl trace`, `scenario`, `doctor`, and `verify affected` as one host facade.
- Use Workshop `/devtools` and `scripts/owctl dev` as that facade's live control
  surface: inspect, input, terrain, teleport/party/spawn setup, record and replay.
  The [agent skills](README.md#read-order) connect discovery to permanent
  scenarios and accepted proof. The former standalone drivers are removed;
  all execution uses bounded [shared test jobs](devtools-tests.md).
- Add descriptor-driven `scripts/owctl actor inspect`, `actor trace`, and
  reusable semantic scenario evidence. Preserve every old requirement in the
  migration map as pending until its shared-tool witness is implemented and proved.

Exit gate: a control lock, wrong target, wrong speed, presentation split, or stream wait can be explained from one bounded trace without private offset hunting.

## Phase 2 - One schema and one resolver

- Define a named Behavior Schema with field path, type, unit, bounds, lane, operators, and feature ID.
- Generate the compact C layout, masks, editor metadata, validators, migration metadata, and trace labels.
- Extract profile composition into portable C.
- Compile the same resolver for ARM and host tools.
- Add golden resolution vectors and ROM/host parity.
- Make the Workshop use the canonical resolver.
- Keep the current binary blob as generated compatibility output.

Exit gate: deleting a profile rule from the portable resolver makes both ROM and Workshop resolution fail in the same tests. No second resolver remains. Packaged-ROM parity is required before runtime completion is claimed.

## Phase 3 - Actor facade and compatibility views

- Put the existing lifecycle behind `Apply`, `Tick`, and `Inspect` without changing behavior.
- Add `ActorView` adapters over `OverworldWildSpawnState`, its runtime sidecar,
  and the separate player engine anchor. Do not move storage yet.
- Bind mount handles to the player anchor, follower actor, field epoch, map
  generation, and encounter generation.
- Make command and cancel paths idempotent with typed reasons. Commands use a
  strictly increasing wrap-safe sequence; in-window duplicates replay their
  acknowledgement and older out-of-window commands fail as `STALE_SEQUENCE`.
- Keep old state behind internal adapters only while a capability is migrating.

Exit gate: one actor snapshot can read all movement ownership and lifecycle
state without exposing the underlying parallel arrays.

## Phase 4 - Motion Plan and shared Walk

- Introduce `Intent`, `Candidate`, `MotionPlan`, `Decision`, `PathAdvance`, and `Commit` around the working Walk path.
- Add the deterministic world fixture and host executor.
- Move wild Walk to the shared planner/executor.
- Compare old and new semantic traces before switching.
- Move mounted Walk to the same executor with actor authority, the player
  engine anchor, and mounted presentation.
- Centralize acceleration, skid, stomp, crash, facing, diagonal collision, streaming, and commit effects.
- Delete the duplicated mounted and wild Walk ownership paths.

Exit gate: exact Walk and all feedback pass wild/mounted parity. Only role intent and presentation differ.

## Phase 5 - Hop and Teleport

- Move Hop planning into the Motion Module.
- Reuse the shared executor for duration, arc, streaming, commit, cancel, pause, and presentation.
- Move Teleport through the same lifecycle with visibility policy as data.
- Preserve specialized candidate rules for ledges, canopy, diagonal fallback, and fixed/per-tile timing.
- Remove separate custom-jump and mount-motion ownership once scenario parity passes.

Exit gate: Walk, Hop, and Teleport share one motion state machine and terminal event contract.

## Phase 6 - Roles, chains, and Ram

- Move wild, follower, chain, and player input decisions behind role controllers.
- Keep mounted control as a rebind of the current follower actor to rider input.
- Make chain movement consume semantic commits only.
- Express Ram as a Walk-intent controller policy with locked direction, acceleration, stomp, crash, and battle reactions.
- Remove AI-only fields from mounted runtime state. Do not remove them from the resolved profile.

Exit gate: a new role adds one controller or presentation adapter without copying motion code.

## Phase 7 - World lifecycle and population

- Centralize path advances, target reservation, surface occupancy, warp gates,
  and battle gates. Streaming and distance consume path advances; terminal
  reactions consume commit.
- Centralize field transition suspend, canonicalize, rebind, resume, and discard.
- Make population consume time, actor commits, and field events explicitly.
- Prove fast Walk, long Hop, Teleport, cardinal and diagonal streaming, and mid-motion transitions with soak scenarios.
- Replace direct retained pointers with handle and epoch validation where practical.

Exit gate: no movement type has a private map-transition or terrain-streaming protocol.

## Phase 8 - Delete legacy surfaces

- Consolidate migrated parallel arrays into one coherent actor slot only after
  Walk, Hop, Teleport, roles, and lifecycle ownership have moved.
- Remove redundant Walk entry structs and oversized helper callbacks that expose private mechanics.
- Remove duplicate host resolver code and positional authoring logic.
- Remove legacy state arrays and compatibility paths after each capability moves.
- Replace implementation-string tests with facade-level scenarios where their old target no longer exists.
- Move superseded attempt documents to the archive after every live feature has an owner and scenario.
- Keep fixed-address thunks only where ROM layout still requires them.

Exit gate: deleting the actor system facade would reveal substantial hidden complexity; deleting an adapter removes only engine-specific detail.

## Change order and risk controls

- Observe before moving ownership.
- Move one locomotion and one role at a time.
- Require semantic equivalence by default until a behavior change is explicitly
  intended. Require byte equality only when binary layout is explicitly unchanged.
- Never keep two live motion owners as a fallback.
- Do not mix a schema migration with a motion migration in the same change.
- Do not claim parity from static source checks.
- Preserve the user's current game feel unless a separate behavior change is requested.

## Finite delivery slices

These IDs partition the existing work; they do not add product scope. A slice
may contain small contract changes, but only one integrated behavior change is
active at a time. Each row has one coordinator in the progress ledger. The
feature manifest supplies exact checks, scenarios, roles, and proof levels.

| ID | Outcome and phase coverage | Required capability scope | Exit evidence |
| --- | --- | --- | --- |
| D0 | Trustworthy proof and resume state; Phase 1 workflow repair | Per-run evidence, content identity, failure records, test-design checks | Host rejection checks and evidence inspection; no gameplay claim |
| D1 | Early buildable checkpoint before further broad cutovers; Phases 1, 4, 6 | Real Ledyba spawn/chain/pause and reported whole-engine stutter, including unmounted play | Current packaged ROM; every automatic spawn-destination scanner obeys the per-update terrain-query budget; short current-ROM spawn-work witness; normal-play witness or preserved symptom-specific failure with a bounded next investigation |
| D2 | Schema, resolver, facade, and observation; Phases 0–3 | `actor.system`, `profile.composition`, `profile.state` | Model/ABI checks and exact packaged resolver/facade scenarios; one trace explains a real motion outcome |
| D3 | Shared Walk, roles, chain actions, and Ram; Phases 4 and 6 | `walk.exact`, `walk.acceleration`, `walk.skid`, `walk.feedback`, `walk.diagonal`, `walk`, `walk.momentum`, `chain.movement`, `chain`, `alert`, `chase` | Exact timings, complete natural chains, direction/skid/stomp/crash and role parity; unmounted and mounted pacing measured separately |
| D4 | Shared Hop/Teleport and mount presentation/lifecycle; Phases 3 and 5 | `hop`, `hop.ledge`, `teleport`, `mount.lifecycle`, `mount.presentation` | Cardinal/diagonal/ledge, arc/spin/pause, fixed/per-tile time, one mounted motion, detach/control scenarios |
| D5 | One world lifecycle and bounded population; Phase 7 | `world.streaming`, `world.transition`, `world.warp-gating`, `population`, `spawn`, `battle`, `terrain`, `battle.capture` | Path/stream boundary, transition/rebind, terrain, spawn, warp, battle/capture, and relevant continuous soak scenarios |
| D6 | Remove remaining legacy surfaces; Phase 8 | All migrated capabilities and structural ownership checks | Public replacement covers each deleted private assertion; exact linked/package bytes, overlay limits, and affected behavior still pass |
| D7 | Frozen release candidate; all phases | Every required capability, scenario, role, and proof level | Full required proof on the sealed candidate and `scripts/owctl verify roadmap --json` reports `passed: true` |

D0 precedes new accepted proof. D1 precedes more broad ownership changes;
only code needed to get a buildable, observable checkpoint can come first.
D2–D5 reuse existing completed work and finish one contract at a time. Delete
each replaced path when its counterpart passes; D6 closes remaining deletion
work, not a second wholesale migration. D7 keeps the original full exit gate.
An early checkpoint can preserve a real failure, but that is not a passing
behavior result. Keep its owning behavior item open and address it before the
next broad integration.

## Goal progress rules

A roadmap goal delivers the selected game outcome. Tests, readers, and proof
registration support that outcome; their count is not game progress. A goal
continuation resumes the current source question or fix, not a new test plan.

- Reuse the existing failing witness when it measures the reported symptom.
  Inspect its retained evidence and the responsible production path first.
  Once evidence supports a scoped correction, implement it and run the same
  witness on the fixed build. Do not require a new test or broader coverage
  merely because a new turn, helper, or goal continuation has started.
- Before adding test/tool code, name the missing fact that prevents this fix
  or its required acceptance. If current observations already answer it, return
  to production work. Optional coverage and general tool cleanup wait until
  the selected game outcome is delivered.
- After two consecutive goal turns spent only on test/tool work, or at the
  existing 30–45-minute review point, reassess before another tool edit. Inspect
  the product cause using current evidence. Continue tool work only for a
  concrete missing fact that still blocks the next product decision or required
  acceptance, with one bounded correction and its return action recorded in
  the existing work item. A renamed tool task does not reset this review.
- Distinguish a diagnosis gap, an implementation gap, and an acceptance gap.
  A broken acceptance checker does not prevent independent source diagnosis
  or a scoped fix supported by an existing symptom-specific failing witness.
  Keep the proof gap open and complete required checks before claiming a fix.
- Report the game result or cause learned, what changed in product code, and
  the exact remaining gap. For a tool-only turn, state the blocked fact it
  resolved and the next product action. Reuse the current ledger; do not add a
  separate tracking system. Never force a speculative product edit to meet a
  turn limit, weaken a test, or mark the goal complete with required work open.
- Treat spawn-work pacing as shared D1/D5 proof. A change to spawn search,
  population refill, behavior profiles, destination masks, generated profile
  data, follower Hop planning, or Hop landing validation reopens D1 until the
  extracted-C checks and short current-ROM spawn-work witness pass again. A
  population count or a pass from an older ROM cannot preserve this result.

## Work loop and stopping rules

1. Select one open contract under a slice ID. Record its owner, affected roles,
   requirement, proof, and bounded next action in the ledger before editing.
2. For a runtime bug, preserve a measured reproduction before the fix; an
   existing scenario or bounded shared-devtools recipe is sufficient to start.
   Finish durable registered proof before closure, under
   [reproduction and acceptance](verification.md#reproduction-before-editing-acceptance-before-closure).
   For a refactor, preserve a passing reference and compare
   semantic results; do not invent a failing bug baseline.
3. Check the exact production adapter and its caller, not only the portable
   reducer. Before changing an overlay, record the current linked size, hard
   cap, affected fixed entries, and where the change will fit. Do not grow an
   interface first and try to find space afterward.
4. Use narrow host/ABI checks while editing and focused ROM proof at a stable
   contract boundary. Use the affected set at integration checkpoints; do not
   rerun the whole branch after each patch. See the
   [verification ladder](verification.md#verification-cost-and-checkpoints).
   If missing observations or slow repeated work delay progress, improve the
   shared devtools as part of the slice. Measure setup, execution and checking
   cost before changing the path. Prefer bounded native point/event reads and
   retained-stream replay; screenshots never supply test proof. Preserve actor
   identity, normal triggers, failure sensitivity and required observed frames.
   Apply the [outcome-first tool loop](devtools-tests.md#outcome-first-tool-work):
   one real bounded sample precedes the full checker stack. Each tool task names
   its blocked game requirement, exact next check, owner, review and return point.
   For a spawn/profile/population change, run both extracted-C scan-budget checks
   before the ROM. Stop on a batched candidate query. A query cap alone does not
   prove pacing: the same automatic attempt must resolve its profile and prepare
   metadata/class only once, then reuse that work on every resumed scan update.
   Run the short spawn-work scenario on the current candidate and require its
   repeated-preparation and slow-resumed-finalizer controls to fail. Keep a player-reported hitch open until
   the user checks that exact current `test.nds`; tool evidence cannot override
   an unresolved report. Then continue D5 work.
5. Save the result and next action. After two attempts at the same failure
   with no new evidence, stop patching and change the method: trace a boundary,
   isolate a production adapter, inspect the vanilla reference, or narrow the
   reproduction. A retry needs a new hypothesis or changed condition.
6. Close the contract when its agreed evidence passes. Reopen it only for an
   unmet requirement or concrete regression. Record optional improvements
   below; they do not block this migration.

Use a bounded investigation question and a review point, normally within
30–45 minutes. That limit is a point to change method, hand off, or state an
exact external blocker; it is not permission to abandon required work. Measure
actual build/run cost at D1 before giving a delivery estimate. Long soaks cover
the reported failure window and trigger conditions, not an arbitrary test count.

The coordinator owns the current ledger and integrates shared code. Helpers get
an ID, bounded question, owned files, and expected evidence. Independent
investigation and review can run in parallel; overlapping writers cannot.
Use the [handoff format](verification.md#progress-and-handoffs).

## Deferred ideas

These are compatible with the architecture but are not migration prerequisites:

- Expanded surface graph for roofs, bridges, cliffs, and flight.
- Effect-owned Pokémon presentation above occluding geometry.
- More scripted actor roles.
- A graphical trace timeline inside the Workshop.

They must use the same schema, actor, motion, world, presentation, and verification interfaces. They must not create a parallel system.
