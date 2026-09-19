# Conditional Profiles Implementation Plan

Status: Implementation in progress. The legacy runtime stays authoritative
until the CP7 cutover gate passes.

## Implementation status

| Slice | State | Evidence and next action |
| --- | --- | --- |
| CP0 | Complete | Baseline schema, catalog, catalog tests, resolver goldens, actor view, and spawn lifecycle pass. The migration inventory reports 1,746 classified findings, zero unclassified findings, seven activeProfile references, and two legacy conditional states. |
| CP1 | Complete | Catalog V3 owns profile kinds and condition entries. Generated storage V78 emits fixed profile-owned condition records. V1/V2 remain read-only migration inputs. |
| CP2 | Complete | The portable evaluator covers while-true, timed duration, cooldown, refresh, player and actor targets, overlap order, stale targets, terrain/speed, and frame wrap. Its fixed result includes per-application winners and one final target. |
| CP3 | Complete | The 44-byte request and 276-byte result support explicit conditions. Ordered resolver tests, 15 goldens, and host/package fixtures prove the new one-pass path. Legacy callers remain on the compatibility mode. |
| CP4 | Complete | The role adapter prepares bounded condition entries at bind, clears them with actor identity, evaluates at the idle decision boundary, resolves in shadow mode, and emits armed-only trace facts. The old path still owns visible behavior. |
| CP5–CP8 | Not started | Workshop authoring, catalog migration, cutover, deletion, and live acceptance remain. |

This plan changes who owns alert and active behavior. It does not design a
general condition language.

## Outcome

Replace the old Alert-to-Active state path with conditional override profiles.
A conditional profile owns the condition that activates it. Active conditional
profiles compose with normal override profiles in one ordered list.

The completed system has these properties:

- An override profile can be normal or conditional.
- A conditional profile has one or more independent condition entries.
- Each condition entry can use a different subject Pokémon pool.
- Conditions do not combine with each other. If more than one entry for one
  profile is active for the same subject, the last listed active entry wins.
- Active conditional profiles stack field by field. The later application in
  the shared application list overrides the earlier value.
- The old Active lane and the old attentive state do not exist.
- The Workshop Active tab does not exist. The Alert tab becomes the condition
  editor.
- The controller checks conditions before each new intent. It does not interrupt
  an accepted motion.
- A condition can observe the player, another Pokémon, terrain, or another
  bounded world fact.
- A condition can be targetless. A target-required condition cannot activate
  when no valid target exists.
- One active condition entry captures at most one target.
- A timed condition has a duration and a cooldown. Cooldown starts when the
  condition triggers. It cannot retrigger during cooldown.
- A timed activation remains active for its duration if the triggering fact
  becomes false.
- When cooldown ends and the condition is still true, it triggers again,
  selects a fresh target, and restarts duration and cooldown.
- A while-true condition has no held duration. It applies only while true.
- Existing profile migration is a later delivery slice. The migration mapping
  is not decided by this plan.

## Non-goals

- Do not add Boolean condition groups, nested AND/OR rules, or condition
  scripting.
- Do not add new chase, flee, or battle behavior only to prove this system.
- Do not change Tired behavior unless the migration inventory finds a hard
  dependency.
- Do not let a condition interrupt an accepted Walk, Hop, Teleport, skid, or
  presentation action.
- Do not put world pointers, actor storage, timers, or target search inside the
  portable Behavior Resolver.
- Do not keep the old conditional-state mechanism as a second long-term system.
- Do not decide every old Active-profile migration before the new seam is
  proved.

## Target ownership

| Owner | Owns | Must not own |
| --- | --- | --- |
| Named behavior catalog | Profile kind, ordered applications, condition-entry definitions, pools, duration, cooldown, and target query definition | Live timers, actor handles, world pointers |
| Catalog generator | Validation, fixed-size generated tables, stable IDs, bounds, and host metadata | Runtime condition truth |
| Behavior Condition Evaluator | Subject-pool match, condition truth, timer state, cooldown state, target choice, one captured target per active entry, and reduction to the final target in shared application order | Profile field composition, world pointers, or motion execution |
| Behavior Resolver | Ordered field composition, normalization, target-source validation, fingerprint, and provenance | World search, timer updates, target search, or actor lifecycle |
| Wild or Follower controller adapter | The idle intent boundary, bounded world observation, evaluator call, resolved behavior use, and conversion to one intent | Mid-motion cancellation or direct profile mutation |
| Actor Motion | Validation, reservation, execution, and terminal completion of an accepted intent | Conditions, profile ordering, or target search |
| Workshop | Authoring and preview of the same catalog contract | A separate save format or private resolution rules |

Mounted player control does not evaluate autonomous conditions. A follower can
evaluate conditions when it is acting as a follower. Mount setup continues to
snapshot resolved follower behavior through the normal mount seam.

## Current seam to replace

Agents must verify this inventory before editing. These names describe the
current tree and give CP0 its starting points.

| Current area | Current owner or shape | Planned destination |
| --- | --- | --- |
| Named catalog | data/overworld_behavior_profiles.json contains activeProfile references, top-level conditionalStates, and default Active runtime bindings | Profile kind plus condition entries; no separate Active binding or conditionalStates list |
| Generated catalog | data/OverworldWildBehaviorData.c and include/overworld_wild_behavior_data.h emit conditional-state links and Owner, Active, and Tired data | Fixed conditional-profile definitions and condition-entry tables; Owner and Tired behavior only |
| Resolver context | OverworldWildBehaviorContext contains subject and terrain/class facts but no actor-world observation | Keep the resolver value-only; pass active conditional application bits and target bindings from the evaluator |
| Resolver output | OverworldWildBehaviorProfile contains Owner, Active, and Tired lanes; BehaviorResolveResult reports conditional and applied masks | Owner and Tired output, ordered conditional application provenance, and resolved target source |
| Runtime state | Wild runtime keeps movement spot state, emote timers, Active steps, and spot cooldowns | Presentation state plus fixed per-actor condition timer and captured-target state |
| Runtime transition | Alert checks lead through Emoting into Active; OverworldWildSpawns_GetBehaviorStateLane selects Owner, Active, or Tired | Emote can remain presentation; every completed action returns to the idle decision boundary |
| Workshop | scripts/overworld_behavior_profile_viewer.py has separate Alert and attentive/Active editing paths | One Conditions tab backed by the shared evaluator and resolver |
| Proof map | tools/overworld/system_features.yaml splits profile composition, profile state, alert, and chase claims | One named condition-evaluation owner plus updated profile and presentation claims |

The current generated OverworldWildBehaviorConditionalState and the current
terrain/speed resolver logic are compatibility inputs. They are not the target
condition model.

## Target data flow

~~~text
Named profiles and ordered applications
              |
              v
Generated conditional-profile and condition-entry tables
              |
        actor bind or spawn
              |
              v
Prepare the bounded entries that can apply to this subject
              |
       next idle intent boundary
              |
              v
Condition evaluator
  - reads bounded world observations
  - updates each entry's trigger, duration, and cooldown state
  - selects the last active entry for each conditional profile
  - captures zero or one target for that selected entry
              |
              v
Active conditional application mask plus one resolved target and its source
              |
              v
Behavior Resolver iterates the shared application list once
  - normal application: apply when its selector matches
  - conditional application: apply when its selector matches and it is active
  - later values override earlier values
  - validates the winning condition and target-source provenance
              |
              v
Resolved Owner and Tired behavior, target, fingerprint, and provenance
              |
              v
Role controller -> intent -> planner -> Actor Motion
~~~

The micro-level check is the controller's existing request for a new intent.
An actor with an accepted motion does not run another decision. Chained
movement runs the check before it asks for the next chain intent.

## Frozen decisions before runtime cutover

These decisions are now part of the architecture contract for Slice CP4.

1. Invalid captured target during held duration.
   A stale required target ends that complete condition activation. No
   target-dependent or targetless field from that entry remains active.
2. First supported condition kinds.
   The fixed first set is player noticed, Pokémon noticed, and terrain/speed.
3. Timer clock.
   Timers use the public actor-system frame. Expiries use unsigned half-range
   comparison and do not decrement once per frame.
4. Target binding precedence.
   The evaluator treats a captured target as an override value. The last
   active application with a target supplies the final target. A later
   targetless profile does not erase it. The resolver receives and validates
   that one target, its condition, and its source application.
5. Binary compatibility.
   Catalog storage is V78 and semantic fingerprints remain V77. The resolver
   request is 44 bytes and the result is 276 bytes. The old 256-byte result
   prefix keeps its exact offsets during migration. Host, package-parity, and
   observation adapters use the new request extent explicitly.

## Delivery rules

- Keep every slice buildable and reviewable.
- Add compatibility reads only when they make the next slice reversible.
- Generate C tables and host metadata from named source. Do not hand-edit
  generated records.
- Use fixed arrays and generated maxima. Do not allocate per frame.
- Prepare applicable condition entries at actor bind or spawn. Do not scan the
  full catalog for every intent.
- Keep semantic tracing dormant unless it is armed.
- Freeze schema and resolver interfaces before runtime and Workshop agents
  start parallel work.
- Do not delete the old path until shadow comparison and migration are green.
- Preserve unrelated working-tree changes.

## Slice CP0: Freeze the baseline and make the migration inventory

Outcome: agents can measure the old system and can name every consumer that
must move.

Dependencies: none.

Primary files:

- [data/overworld_behavior_profiles.json](../../data/overworld_behavior_profiles.json)
- [behavior schema](../../tools/overworld/behavior_schema.json)
- [authoring schema](../../tools/overworld/schemas/behavior-authoring-v2.schema.json)
- [resolver](../../lib/overworld/overworld_behavior_resolver.c)
- [wild runtime](../../src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c)
- [Workshop](../../scripts/overworld_behavior_profile_viewer.py)
- [feature manifest](../../tools/overworld/system_features.yaml)

Steps:

1. Run the current catalog generation check, schema check, resolver golden
   corpus, actor-view check, and spawn-profile lifecycle check. Record exact
   commands and results in the task handoff.
   Use this baseline command set unless the scripts change first:

   ~~~sh
   python3 -B scripts/generate_overworld_behavior_schema.py --check
   python3 -B scripts/verify_overworld_behavior_schema.py
   python3 -B scripts/generate_overworld_behavior_catalog.py --check
   python3 -B tools/overworld/test_behavior_catalog_v2.py
   python3 -B scripts/verify_overworld_behavior_resolver.py --force-host-build
   python3 -B scripts/verify_overworld_actor_view.py
   python3 -B scripts/verify_overworld_spawn_profile_lifecycle.py
   ~~~
2. Add one read-only inventory script. It must report:
   - every activeProfile reference and default Active binding;
   - every profile that supplies attentive or Active-lane fields;
   - every runtime branch and state field that enters or reads Active;
   - every current conditionalStates entry;
   - every Workshop, host adapter, package, trace, and test consumer;
   - every numeric enum or binary record whose meaning will change.
3. Make the report machine-checkable. Give each item one class:
   condition input, profile response, presentation-only state, compatibility
   adapter, migration data, test, or dead code.
4. Fail the report when an item is unclassified. Do not use a hand-maintained
   source list as the scanner's only input.
5. Save the reviewed migration decisions in this plan or a linked temporary
   migration table. Do not make generated output the source of truth.

Proof:

- Baseline checks are green before code changes.
- The inventory has no unclassified production consumer.
- The inventory identifies all current Active profiles and all old
  conditional-state entries.

Exit gate: an independent reviewer can select any Active or attentive symbol
and find its planned destination.

## Slice CP1: Add the catalog contract

Outcome: named authoring data can express normal and conditional profiles
without changing live behavior.

Dependencies: CP0 and the first supported condition-kind list.

Steps:

1. Update [CONTEXT.md](../../CONTEXT.md) and
   [architecture.md](architecture.md) with these terms:
   conditional profile, condition entry, subject pool, activation mode,
   captured target, duration, cooldown, and active conditional application.
   Mark the old Active lane as migrating until CP7.
2. Add a profile kind to the named catalog. Use two values only: normal and
   conditional.
3. Add an ordered conditions list to a conditional profile. Each entry needs:
   - stable entry ID;
   - subject-pool selector;
   - one condition kind and its typed parameters;
   - activation mode: while-true or timed;
   - duration and cooldown for timed mode;
   - target requirement and one bounded target selector when needed.
4. Validate these invariants:
   - root profiles cannot be conditional;
   - a conditional profile has at least one condition entry;
   - a normal profile has no condition entries;
   - entry IDs are unique within the profile;
   - duration and cooldown values are in generated bounds;
   - target-required kinds define a target selector;
   - overlapping subject pools are valid and keep source order.
5. Generate fixed-size profile, condition-entry, subject-pool, and target-query
   tables. Generate maxima and static size assertions.
6. Keep a temporary reader for old conditionalStates data. Emit it into the new
   representation so the runtime still behaves as before. Mark this reader for
   deletion in CP7.
7. Bump the authoring and generated-catalog versions. Update the host decoder
   and schema snapshots in the same change.
8. Add generator tests for valid overlap, invalid normal-profile conditions,
   missing target selectors, bounds, stable ordering, and round-trip output.

Proof:

- Old named data produces semantically equivalent resolver results through the
  compatibility path.
- New fixture data can express two conditional profiles and multiple condition
  entries with different subject pools.
- Reordering condition entries changes only their generated precedence.

Exit gate: runtime and Workshop agents can consume one frozen generated
contract without inventing local fields.

## Slice CP2: Build the portable condition evaluator

Outcome: a pure, bounded module decides which conditional applications are
active and which target each one captured.

Dependencies: frozen CP1 records and timer decision.

Steps:

1. Add a private portable condition-evaluator module beside the behavior
   resolver. Its public values must not contain FieldSystem, LocalMapObject, or
   overlay pointers.
2. Define a generation-safe target reference with three forms: none, player,
   and actor handle. Actor handles must include enough identity to reject a
   reused slot.
3. Define a bounded observation view for the supported condition kinds. The
   role adapter builds this view from public actor snapshots and typed player
   facts.
4. Store independent runtime state per prepared condition entry:
   previous truth if needed, active-until, cooldown-until, and captured target.
5. Implement while-true mode:
   - evaluate current truth;
   - require a valid target when the kind needs one;
   - apply only while true;
   - capture one target when the entry becomes active;
   - keep that target until the entry becomes false or the target-invalid
     policy ends the activation.
6. Implement timed mode:
   - on a valid trigger, capture one target and set duration and cooldown
     expiries;
   - keep the activation through duration even if truth becomes false;
   - reject retrigger while cooldown is active;
   - when cooldown has ended and truth is true, capture a fresh target and
     restart both expiries;
   - if cooldown is shorter than duration, a valid retrigger restarts duration;
   - use wrap-safe clock comparisons.
7. Evaluate entries independently. For each conditional profile, expose only
   its last listed active entry and target.
8. Return a bounded active-application bitset and target-binding array. Return
   semantic reasons for trace mode only.
9. Add host tests for:
   - while-true enter and leave;
   - timed hold after truth is lost;
   - cooldown rejection;
   - refresh after cooldown;
   - duration restart;
   - fresh target on refresh;
   - no target, no activation;
   - overlapping condition entries, last active entry wins;
   - two profiles active at the same time;
   - stale actor target;
   - frame-counter wrap.

Proof:

- Tests use no engine or overlay process.
- Maximum work is bounded by generated prepared-entry and actor limits.
- Memory size for one actor is stated and guarded by static assertions.

Exit gate: the evaluator can replay a table of observations and produce stable
activation, timer, and target results.

## Slice CP3: Change resolver input and ordered composition

Outcome: the resolver composes normal and active conditional profiles in one
source-order pass.

Dependencies: CP1; CP2 result shape is frozen.

Steps:

1. Add the active conditional application bitset, overall winning condition,
   and final target provenance to the private resolver request.
2. Stop deriving active conditions from terrain and speed inside the resolver.
   Keep the old derivation only in the temporary compatibility adapter.
3. Replace the current normal-pass-then-conditional-pass behavior with one
   pass over the shared application list:
   - apply a matching normal application;
   - apply a matching conditional application only when its active bit is set;
   - preserve existing field operators and later-wins behavior.
4. Validate the evaluator's final target against its active source application
   and condition. The evaluator has already preserved an earlier target across
   a later targetless application.
5. Add the winning condition-entry ID and target-source application ID to
   provenance and the fingerprint input.
6. During migration, keep the old Active-lane output adapter. Do not let new
   code use it.
7. Update native adapters, golden corpus encoding, Workshop host decoding, and
   package parity fixtures for the request and result version.
8. Add resolver cases for:
   - normal, conditional, normal order;
   - two active conditional profiles that write different fields;
   - two active conditional profiles that write the same field;
   - target replacement and targetless preservation;
   - no active conditional profile;
   - selector mismatch despite active condition;
   - fingerprint and provenance stability.

Proof:

- The ordered-stack tests fail if the resolver restores the old two-pass
  algorithm.
- Host and packaged resolver results agree for the new request version.
- The resolver still has no world lookup, timer, or actor lifecycle dependency.

Exit gate: every conditional result can be explained from application order,
active bits, and provenance alone.

## Slice CP4: Add shadow runtime integration

Outcome: the live role controller evaluates the new system at the correct
decision boundary without changing visible behavior.

Dependencies: CP2, CP3, and all required runtime-cutover decisions.

Steps:

1. At spawn or actor bind, prepare only condition entries that can apply to the
   subject. Cache catalog IDs, not world pointers.
2. Add fixed per-actor condition runtime storage. Clear it on despawn, field
   epoch change, identity change, and slot reuse.
3. Build the bounded observation view after motion and commits are advanced,
   before the idle controller requests its next intent.
4. Evaluate conditions once for that intent request. Chained movement must
   return to this same boundary before its next intent.
5. Validate captured actor targets against the current actor handle and field
   epoch before use.
6. Resolve the new Owner behavior and target in shadow mode. Continue to drive
   the old Alert, Emoting, and Active path.
7. Add an armed semantic trace record with:
   subject, condition entry, truth, trigger result, duration state, cooldown
   state, target handle, active application mask, and resolved target source.
8. Add a host or live comparison adapter that maps the old result and the new
   result to one small semantic form: no response, alert presentation, chase,
   flee, or ordinary owner behavior.
9. Fix every unexplained mismatch. Expected migration mismatches must have a
   named catalog mapping in CP6, not a silent allow-list.
10. Measure worst-case prepared entry count and decision work. Keep full-catalog
    scans out of the frame loop.

Proof:

- No visible behavior changes while shadow mode is active.
- An accepted motion completes even if a condition changes during it.
- The next chained intent sees the new condition state.
- Stale targets fail closed.
- Trace work is absent when tracing is not armed.

Exit gate: representative old alert and Active behaviors have explained shadow
parity, and the new path meets frame and memory bounds.

## Slice CP5: Repurpose the Workshop

Outcome: the Workshop authors and previews the canonical conditional-profile
contract.

Dependencies: frozen CP1 schema and CP3 resolver request.

Steps:

1. Add a normal or conditional toggle to override-profile editing. Do not allow
   roots to become conditional.
2. Repurpose the Alert tab as Conditions.
3. Add ordered condition-entry editing for:
   subject pool, condition kind, typed parameters, activation mode, duration,
   cooldown, target requirement, and target selector.
4. Support add, remove, duplicate, and reorder for condition entries.
5. Show that entries in one profile do not stack. Mark the last active
   overlapping entry as the winner in preview.
6. Add preview inputs for observation facts, current time, active duration,
   cooldown, and candidate targets. Feed these values to the shared host
   evaluator and resolver.
7. Show shared application order, applied profiles, overridden fields, winning
   condition entry, and target source.
8. Remove the Active tab. Show old Active-lane and attentive values only in the
   read-only migration report until CP6 completes.
9. Round-trip named JSON without changing unrelated profile order, IDs, or
   selectors.
10. Add UI model tests for toggle validation, entry order, overlapping pools,
    timer fields, target requirement, preview provenance, and save/reload.

Proof:

- A profile authored in the Workshop passes the command-line schema and catalog
  checks without repair.
- Command-line generation and Workshop preview return the same ordered result.
- The Active tab does not exist.

Exit gate: all new conditional-profile data can be authored without editing raw
JSON, and the Workshop has no private resolution rule.

## Slice CP6: Migrate existing data case by case

Outcome: every current Active profile and old conditional state has an explicit
new home.

Dependencies: CP0 inventory and CP1 through CP5.

Steps:

1. Regenerate the CP0 inventory against the latest tree.
2. For each old activeProfile reference, record:
   - old selecting profile or application;
   - old alert or transition condition;
   - old Active response fields;
   - new conditional profile;
   - new condition entry and subject pool;
   - expected target rule;
   - expected duration and cooldown mode;
   - parity proof.
3. Ask for a product decision only when old data does not define one of these
   values or when two mappings would create different visible behavior.
4. Convert current terrain/speed conditionalStates entries to condition entries
   on conditional profiles.
5. Move attentive movement and reaction fields into the response fields of the
   matching conditional profile. Do not preserve an attentive lane.
6. Keep emote timing or presentation state only when presentation still needs
   it. It must not own profile activation.
7. Migrate one behavior family at a time. After each family, run catalog,
   resolver, Workshop round-trip, and semantic parity checks.
8. Include at least one current chase family, one flee family, one
   presentation-only alert, and each current terrain/speed conditional state.
9. Stop adding old-format records after the first family migrates.
10. Finish with an inventory report that has no unmapped source data.

Proof:

- Every migrated behavior has a before-and-after semantic fixture.
- Field provenance names the new conditional application.
- Migration does not change unrelated normal profile order.
- Tired behavior remains unchanged.

Exit gate: old Active and conditional-state data can be deleted without losing
an authored behavior.

## Slice CP7: Cut over and remove Active and attentive state

Outcome: the new evaluator and normal Owner/Tired resolution are the only live
behavior path.

Dependencies: CP4 shadow parity, CP5 authoring, and complete CP6 mapping.

Steps:

1. Switch Wild and Follower idle decisions from the old Alert-to-Active path to
   evaluator output, resolved behavior, and resolved target.
2. Keep Emoting only as a presentation lifecycle when required. On completion,
   return to the normal intent boundary; do not enter an Active lane.
3. Remove Active from public actor-view lane projection.
4. Remove the Active lane from resolved profile storage, primitives, lane
   enums, resolver steps, generated schema metadata, package records, host
   decoders, and Workshop models.
5. Remove attentive field names and aliases after the last migrated catalog
   record is gone.
6. Remove activeProfile and defaultActiveApplication from named authoring data,
   authoring schema, generator, generated C, and runtime bindings.
7. Remove the old top-level conditionalStates source and compatibility reader.
8. Remove runtime Active transition functions, state branches, counters, and
   cooldown fields that the evaluator replaced.
9. Bump every changed ABI or serialized version. Make old-version rejection
   explicit.
10. Run the CP0 inventory in forbidden-symbol mode. Allow references only in
    migration history and this plan.
11. Have an independent reviewer inspect ownership, stale-target handling,
    timer wrap, list ordering, data-size bounds, and adapter versions before
    final live proof.

Proof:

- Production source has no Active-lane, attentive-state, activeProfile,
  defaultActiveApplication, or old conditionalStates consumer.
- One trace explains condition, target, profile application, intent, and motion
  without reading a legacy state.
- Old-format packages fail with a clear version error.

Exit gate: disabling or deleting the legacy adapter cannot change runtime
behavior because no production caller reaches it.

## Slice CP8: Accept the feature and update agent routes

Outcome: host, package, live runtime, pacing, and agent documentation all prove
the same contract.

Dependencies: CP7 and a frozen candidate ROM and catalog.

Steps:

1. Add registered acceptance scenarios for:
   - ordered stacking of normal and conditional applications;
   - independent overlapping condition entries;
   - timed hold, cooldown, and refresh;
   - one target selection and fresh target on retrigger;
   - player target and another-Pokémon target;
   - condition change during motion taking effect at the next intent;
   - stale target rejection;
   - Wild and Follower parity where both roles support the condition.
2. Update the feature manifest. Give condition evaluation one clear owner.
   Remove Active-lane claims from profile.state and update alert ownership to
   condition evaluation plus presentation.
3. Regenerate the feature table and all catalog/schema/package snapshots.
4. Run the smallest host checks first:
   schema, catalog, evaluator, resolver golden corpus, actor view, role
   controllers, spawn profile lifecycle, and package parity.
5. Build one candidate ROM through the project build route.
6. Run the registered live scenarios on that exact ROM.
7. Because profile data and generated catalog code changed, rerun the extracted
   C scan-budget checks and the short spawn-work scenario.
8. On the same current test ROM and unchanged Continue save, run
   world.unmounted.spawn-zero-stutter with the existing Mankey. Do not prepare
   party, follower, spawn, or population state. Zero late loops is required.
9. Update architecture, authoring-debugging, verification, the profile-authoring
   skill, scenario-authoring skill, and Workshop help. Remove migration wording
   after cutover.
10. Record final commands, exact ROM identity, scenario results, generated-data
    status, and remaining limits in the handoff.

Proof:

- Host and packaged resolver results match.
- Registered scenarios prove the user-visible timing and target rules.
- The current ROM passes the required spawn-work pacing gates.
- A new agent can find the condition owner, authoring route, live proof, and
  failure reason from the system README.

Exit gate: all checks above are green, generated files are current, no legacy
runtime consumer remains, and the canonical docs describe the implemented
system rather than this proposal.

## Safe agent split

Use one integration owner. It owns interface freezes, generated-artifact
updates, cutover order, and final proof.

Work can split after CP1:

| Agent | May own | Must wait for |
| --- | --- | --- |
| Catalog agent | Named schema, generator, generated C contract, catalog tests | CP0 inventory |
| Evaluator agent | Portable condition evaluator, target value, host tests | Frozen CP1 records and timer decision |
| Resolver agent | Request/result change, ordered pass, provenance, golden corpus | Frozen CP1 IDs and CP2 result shape |
| Workshop agent | Editor model, preview adapter, round-trip tests | Frozen CP1 schema and CP3 request |
| Runtime agent | Prepared entries, observations, shadow call, controller cutover | CP2 and CP3 interface freeze |
| Migration agent | Profile JSON and migration fixtures, one family at a time | CP4 shadow comparison and CP5 editor |
| Reviewer | Read-only ownership and blast-radius review | CP6 complete, before CP7 deletion |

Do not give two agents the generator or generated files at the same time.
Runtime and Workshop agents must not add private schema fields. Freeze the
candidate catalog, generated tables, and ROM before final live proof.

## Verification matrix

| Claim | Cheapest proof | Final proof |
| --- | --- | --- |
| Later applications override earlier fields | Resolver unit and golden case | Packaged resolver parity |
| Conditions in one profile do not stack | Evaluator overlap test | Registered overlap scenario |
| Multiple conditional profiles do stack | Evaluator plus resolver test | Live two-profile scenario if visible |
| Timed activation survives lost truth | Evaluator clock test | Registered timed scenario |
| Cooldown blocks retrigger | Evaluator clock test | Registered timed scenario |
| Retrigger gets a fresh target | Deterministic candidate fixture | Registered actor-target scenario |
| No target means no target-required activation | Evaluator test | Live target-loss scenario |
| Current motion is not interrupted | Controller host test | Next-intent live scenario |
| Resolver is world-independent | Dependency and type review | Host/package parity |
| No stale actor target is used | Handle-generation test | Despawn or reuse scenario |
| Active and attentive are removed | Inventory forbidden-symbol check | Independent review |
| Workshop matches runtime | Round-trip and shared-host preview test | Saved catalog package parity |
| Profile change did not regress spawn pacing | Extracted-C budget checks | Short spawn-work and zero-stutter scenarios |

## Resume and handoff format

At the end of every slice, leave one short record with:

- current slice and exit-gate state;
- files changed;
- generated files refreshed;
- checks run and exact result;
- frozen interface or data version;
- unresolved decision, if any;
- first safe next action;
- whether the old runtime path still owns visible behavior.

An agent resuming this work must read this plan, the current architecture
contract, the CP0 inventory, and the latest handoff. It must not infer progress
from file presence alone.
