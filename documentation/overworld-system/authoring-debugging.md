# Overworld Authoring and Debugging

## Goal

An agent should be able to answer five questions with one control surface:

1. What profile did this Pokémon resolve?
2. Why did each layer apply?
3. What intent and candidates were considered?
4. Why did motion start, wait, reject, commit, or cancel?
5. What is the first difference between wild and mounted behavior?

## Direct task routes

Use the matching row for a small source task. Function names are search targets
inside the linked file; they remain useful when line numbers change. The check
column selects an existing check for a change, not a required suite for a
question. Host checks do not grant game proof.

| Task | First source and named owner | Focused check from the repo root |
| --- | --- | --- |
| Explain condition activation, duration or cooldown | [Membership and conditions](#membership-and-conditions); `timingNote` in [profiles.js](../../tools/overworld-viewer-v2/static/profiles.js); `OverworldBehaviorCondition_EvaluateEntry` in [condition predicates](../../lib/overworld/overworld_behavior_conditions.c) and `OverworldBehaviorCondition_EvaluatePrepared` in [condition runtime](../../lib/overworld/overworld_behavior_condition_runtime.c) | `python3 -m unittest tools.overworld.test_behavior_conditions` |
| Find why a condition waits before it takes effect | `OverworldWildSpawns_ResolveConditionsAtIntentBoundary` and its call before ordinary cooldown in [Wild adapter](../../src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c) | `python3 -m unittest tools.overworld.test_behavior_conditions.BehaviorConditionTests.test_idle_pause_condition_boundary_semantics` |
| Change profile labels or field controls | `fieldLabel`, `fieldLabelForProfile` and `renderFieldControl` in [profiles.js](../../tools/overworld-viewer-v2/static/profiles.js); field definitions in [behavior_schema.json](../../tools/overworld/behavior_schema.json) | `python3 -m unittest tools.overworld.test_workshop_profile_building_blocks`; for schema changes, `python3 scripts/verify_overworld_behavior_schema.py` |
| Trace a profile save | `/api/v2/commit` in [server.py](../../tools/overworld-viewer-v2/server.py) → `transactional_commit` in [reliability.py](../../tools/overworld-viewer-v2/reliability.py) → `apply_profile_catalog_changes` / `write_behavior_catalog` in [catalog adapter](../../scripts/overworld_behavior_profile_viewer.py) | `python3 scripts/verify_overworld_workshop_authoring.py` and `python3 scripts/generate_overworld_behavior_catalog.py --check` |
| Trace normal or conditional resolution | `/api/v2/resolve` in [server.py](../../tools/overworld-viewer-v2/server.py) → `resolve_context` / `resolve_conditional_preview` in [reliability.py](../../tools/overworld-viewer-v2/reliability.py) → `BehaviorResolver_Resolve` in [shared resolver](../../lib/overworld/overworld_behavior_resolver.c) | `python3 scripts/verify_overworld_behavior_resolver.py --rule-removal-control` |
| Find build start, progress or failure | `/build` in [server.py](../../tools/overworld-viewer-v2/server.py) → `start_build_job` in [reliability.py](../../tools/overworld-viewer-v2/reliability.py) → `run_build_job` / `build_status_payload` in [build adapter](../../scripts/overworld_behavior_profile_viewer.py) | Read `/build-status`; for source hash or size errors use [build diagnosis](../agent-workflows/build-diagnosis.md) |

## Workflow available today

Start the Workshop from the repository root:

```bash
OPEN_PAGE=0 scripts/keyboard-maestro-start-overworld-viewer.sh
```

Open <http://127.0.0.1:8766/>. `/api/v2/resolve` calls the portable C resolver
that the ROM uses. All profile saves go through the named authoring catalog at
`data/overworld_behavior_profiles.json`. The Workshop regenerates the compact
C compatibility data after each save.

For game diagnosis, use the same Workshop's `/devtools` page or its agent CLI:

```bash
scripts/owctl dev help --json
scripts/owctl dev status --json --summary
scripts/owctl dev inspect --json
```

Follow [overworld-devtools](../../.agents/skills/overworld-devtools/SKILL.md)
to start and own the session. Choose the source save explicitly and check its
identity; the tools support raw melonDS `.sav` without changing the source.
The former standalone runtime scripts and bootstrap helpers are removed.
Use [checked shared-tool tests](devtools-tests.md), not another driver.

## Agent control workflow

For an interactive disposable session, use the shared
[live development tools](devtools.md). Workshop `/devtools` and `owctl dev`
share setup, input, inspection, terrain, recording and recipes. Debug-created
setups remain prepared; recording exports and scenario drafts are not proof.
Use [the scenario-authoring skill](../../.agents/skills/author-overworld-scenario/SKILL.md)
to turn a recorded failure into a permanent test. Stop the owned dev session
before a build or accepted scenario; do not claim a requested action happened
until the observed result confirms it.

`scripts/owctl` is the host facade for readiness, scenario contracts, trace
decoding, and affected verification.

```bash
scripts/owctl doctor
scripts/owctl scenario list
scripts/owctl scenario validate
scripts/owctl scenario run mount.detach-restores-control --dry-run
scripts/owctl scenario run mount.detach-restores-control --json
scripts/owctl trace decode tests/overworld/traces/semantic-trace-v1.json
scripts/owctl verify affected
scripts/owctl verify affected --run
```

For a focused C build or overlay size check, use the
[exact build target and toolchain](../agent-workflows/build-diagnosis.md#overlay-size-and-toolchain).

Scenario runs and affected verification write identity-bearing run manifests
when they execute. A scenario with status `planned` is a contract only and
cannot be reported as runtime proof.

Registered `scripts/owctl scenario run` requests a shared devtools test job.
The start receipt is not a pass. Read its live status and terminal manifest.
Only the controller's `acceptedProof: true` grants registered claim credit.
Offline evidence replay cannot replace a current claim-bearing run.

### Adapter maintenance and offline evidence

The details below are for registered adapter or decoder work, not live session
control. Use `owctl dev inspect`, `terrain` and structured memory data for live
observations. Image/video capture is off by default; only an explicit user
request or manual Capture click requests an image. A devtools export is not
interchangeable with accepted evidence.

`actor-state.bin` is a raw dump that starts at the generated descriptor's
`state.address`. Use `--base 0x02000000` for a full ARM9 memory dump. The actor
commands read the public snapshot mirror and trace ring through
`build/overworld-system.debug.json`; they do not contain overlay-private
offsets. `inspect` and `trace` also accept the JSON written by `actor capture`.

A scenario can use the semantic adapter instead of a private-offset runner.
Reusable evidence is version 2 and must name the scenario, seed, and exact ROM
and save hashes that produced it. Scenario execution rejects missing or stale
provenance instead of assigning the current files to an old capture.

The adapter selects exactly one actor and the declared number of complete motion
windows. `motionWindowCount` defaults to one. Required events are an ordered
subsequence in every selected window. Forbidden events are checked in every
selected window. Evidence fails when the number of matching windows differs or
when matching windows belong to different actor identities.

```json
"adapter": {
  "kind": "actor-observation",
  "checks": [
    "trace-window-complete",
    "terminal-result",
    "no-commit-after-cancel",
    "control-returned"
  ]
}
```

Run that adapter with reusable evidence:

```bash
scripts/owctl scenario run <scenario-id> --evidence build/actor-observation.json
```

The adapter checks required and forbidden semantic events, then runs the named
public invariants. Free-text invariant prose is not executable. Each invariant
must exactly match a registered entry in
`tools.overworld.validation.ACTOR_INVARIANT_CHECKS`, and the adapter must name
all checks registered for it. The run manifest records the evidence path, size,
and hash.

`trace-window-complete` fails closed unless the trace was cleared, did not
overwrite, its bounded capture window finished, and its actor and event filters
included the selected motion contract. A snapshot taken while the trace is
still armed is diagnostic data, not reusable scenario proof.

## One source model

The generated field schema lives in `tools/overworld/behavior_schema.json`.
Its generator emits matching ROM and host metadata. Named values live in
`data/overworld_behavior_profiles.json`. This named JSON catalog is the sole
editable behavior-profile source. Catalog V5 has `profiles`, `pools`, and one
ordered `applications` collection. The root profile is complete. Every other
profile has a stable ID, one parent, one kind, one classification, and only its
local field operators. A field operator is `replace`, `relative`, `divide`,
`atLeast`, `atMost`, or a supported combined relative bound. Numeric fields
accept `/2` in the same text input that accepts `-2`. Division takes the earlier
value, divides it by a positive integer from 1 to 127, rounds down, and clamps the
result to the field's valid range. It composes in the same application order
as subtraction. Modes and enum fields do not accept division.

The PB0 manifest at
[`profile_building_blocks_target_v1.json`](../../tools/overworld/fixtures/profile_building_blocks_target_v1.json)
freezes both the exact V4 source inventory and complete target inventory. The
checker accepts the untouched source or the complete target and rejects a
partial mixed catalog.

### Profile building-block model

The saved classifications and composition order are:

1. Moods
2. Routine
3. Style
4. Placement
5. Follower
6. Capability
7. Attacks
8. Attitude
9. Follower/Mount
10. Modifier

Later matching applications override earlier fields. The Workshop groups by
classification, auto-sorts the groups, and preserves manual order inside each
group. A normal application may have a disabled empty target to remain
unassigned in the editor. Condition subject pools still require members or all.
Attacks is an order group, not an implicit attacking switch. Conditional is
independent of classification. An archetype is only
design shorthand for a complete composition; it is not authored data.

The exact target catalog is owned by the
[architecture catalog table](architecture.md#1-behavior-schema). In compact
form it is:

- Moods: Angry (empty, unassigned, with no fields or conditions).
- Routine: Scavenger, Sprint, Floaty Bounce, Small Bird Hop, Erratic Flutter,
  Meander, Hop Around, Idle, Lurk, Drowsy Wander, Perch, Rest.
- Style: Waddle.
- Placement: Fly In, Canopy Access, Rooftop Access, Flower Bed, Swimmer.
- Capability: Teleport, Stalker, Long Hop, Canopy Hop, Find
  Throw Cargo, Find Throw Position, Heavy Stomp, Water Runner.
- Attacks: Throw Held Actor, Ram, Basic attack (disabled), Ambush, Stomp Slam,
  Throw Away From Player.
- Attitude: Startled, Find Playmate, Playful, Skittish,
  Seek safety.
- System: Follower, Mounted. Follower uses the early `follower`
  classification; Mounted keeps the later `follower-mount` classification.
  System marks runtime ownership and does not force late composition.
- Utility: Asleep.

`Default` is the one complete root and is not an application. Teleport is
the first Capability. Perch follows the ordinary Routines. Startled precedes
Skittish. The Player notice entry is last inside Find Playmate. Follower, Mounted, and
Asleep are runtime-linked and cannot be assigned normally.

Selectors choose a complete materialized base profile. Most select `Default`;
Mankey, Primeape, and Annihilape select `Rooftop Access`, a Placement that
inherits Default and enables Land plus Rooftop. Other species differences
come from reusable applications. The rooftop base adds no application slot;
all current application assignments and their order remain unchanged. Authoring uses
Behavior and Movement Style names. The generator can lower them to legacy
binary field names while compatibility storage remains.

The frozen composition changes are:

- Teleport and Stalker use the same direct member list.
- Current small birds use Small Bird Hop plus Fly In. A large-bird redesign is
  outside this catalog change.
- Flying insects use Erratic Flutter and Fly In.
- Bellsprout, the Oddish line, and Sunflora use Meander, Waddle, and Startled.
- Sunkern, Cherubi, and both Cherrim forms use Hop Around and Startled.
- Weepinbell, Victreebel, and Carnivine use Lurk, Ambush, and Rest. Lurk retains
  Idle's settings with Behavior set to Chase; Idle remains unassigned. Active
  Ambush warns and makes a fast Hop contact deal 20 player HP damage and a
  one-tile Jump knockback. A knockback may cross an overworld Pokémon; walls,
  scripted tiles, and non-Pokémon objects still block it.
- Find Playmate uses the Playful Pokémon pool for subjects and compatible
  actor targets. It captures one target for420 frames with430-frame cooldown,
  approaches that same target, inherits Movement Style and sets Chain Pause
  Action to None. A valid first capture keeps its full identity and source.
  Playful requires `requiresAppliedProfile: find-playmate` and
  `bound-target-distance`0..1 against that exact capture. These checks form
  one conjunction; a nearby different Pokémon cannot satisfy it. Playful is
  While true, has no entry emote/wait, and keeps its existing hop and effect
  fields. An expired timed binding can be captured anew on a later admission.
- Skittish uses the Baby Pokémon subject pool for Wild fear of the player
  and other Pokémon. A pickup claim does not activate a response. Seek safety
  uses that same subject pool for Follower fear of other Pokémon and for damage
  to the Follower itself. Its sight condition captures the Pokémon that caused fear,
  but its visible Next to player movement target uses the actual player as the
  safe destination. The damage condition captures Player directly. It inherits
  Movement Style, limits travel time to at most4 and shows the Anguish face.
  Both responses explicitly set Chain Pause Action to None.
  The Notice entries use Current Vision, nearest Wild/Follower Pokémon,
  100% chance and the existing960-frame duration/970-frame cooldown. These
  are visible initial values, not fixed baby-controller rules. The self-damage
  entry uses the same duration and cooldown without a Vision check.
- Skittish also uses the shared `subject-damaged` event for all Wild species.
  Its explicit role excludes Followers and Mounted actors. It captures Player,
  moves Away from Player for960 frames with970-frame cooldown, inherits
  Movement Style and sets Chain Pause Action to None.
- Snorlax uses Drowsy Wander for uneven two-to-six-step Walk bursts, variable
  step time, long look-around stops, and no immediate backtracking.
- Golem, Rhydon, Snorlax, Tyranitar, Aggron, Groudon, Torterra, Hippowdon,
  Rhyperior, Mamoswine, and Regigigas use Heavy Stomp. Each completed Walk tile
  emits stomp dust and the stock ledge-hop landing sound without changing its Routine,
  target, speed, or pause. The profile's shared population key limits these
  Pokémon to one active Wild spawn across species.
  Stomp Slam captures one Object of interest and locks its landing tile at
  launch. Its Slam Hop rises for12 frames, hangs for4 and drops for4, with
  peak24 in Q4 height units. Only the exact bound target may occupy a landing
  tile, and that tile must still pass normal terrain, surface and clearance
  checks. This exception never permits another object or deals damage by
  itself. Shared speed-gated contact deals20 HP with a two-tile Jump knockback.

The Workshop main tabs are Conditions, Spawn, Behavior, Movement Style,
Vision, and Tired. Native controller-state names do not appear as authoring
tabs. Chill, Active, and Attentive are not authoring concepts.

Ordinary Walk has no pause after each tile and no per-tile pause variance.
Those pauses read as lag. A Walk Movement Chain is either disabled or contains
at least two moves. A deliberately slow Routine can break the no-pause rule
only with a visibly intentional pause and a playtest; a one-move Walk chain is
never used. Hop chains are separate and can contain one move.

A Movement Chain can own several pause actions. Its action chance is one gate
for the whole set. When the gate passes, the runtime picks one set action at
random. `PAUSE` is an idle chain action, not a per-step Walk pause. Meander uses
Look around and Pause with a 50% action chance, so each action keeps an expected
25% share while `walkPause` and `walkPauseVariance` stay zero.

### Membership and conditions

A normal application owns a named or inline Pokémon target. A conditional
application has an ordered identity but no authored target. Its profile owns
the ordered condition entries, and each entry owns its own named or inline
subject pool. A System application is linked from its runtime owner rather than
assigned to Pokémon. Entries are independent. The last admitted entry in one
profile wins; different conditional profiles still compose in application
order. Tired references use stable application IDs.

Applications have an Enabled checkbox. Omission means enabled. A disabled
application retains its saved profile, ID, settings and deck order; the compiler
omits its runtime row and owned condition rows. It uses no activation-mask bit.
Runtime-bound or Tired-referenced applications cannot be disabled. Basic attack
uses this switch while its experimental fields and condition remain saved.

### Catalog capacity

The full compiled catalog uses 16-bit global application IDs. It has no global
32-application mask or separate 64-entry Tired tail. Enabled applications and
required Tired links keep their authored order and stable authoring IDs.

The compiler builds a sorted candidate bank for each species, plus a fallback
bank for unlisted species. A bank stores borrowed 16-bit global IDs in catalog
order. It filters only fixed species membership; role, class, group, terrain,
level, form, shiny status and other live predicates still run in the shared
resolver and condition evaluator.

Each subject can have at most 32 candidate applications and 32 prepared
condition entries. The compiler names any subject and applications that exceed
these limits; it never truncates them. Runtime masks and public one-byte source
slots refer to this subject's bank. Private provenance and metadata use the
full global ID. Never shift a global ID into a 32-bit mask.

Cooldown tint, spawn limits, Tired links, target bindings and Hop Arc records
use their global metadata before mapping to a current subject bank. A shared
spawn-limit key stays shared across species. No actor copies the full catalog
or keeps bank pointers across area teardown.

`Basic attack` is an experimental Capability for every Pokémon. It is currently
disabled by its application switch and condition's0% trigger chance; its members
and fields stay saved. Both must be enabled for the experiment to run.
When enabled, its Custom
Vision has range one and adjacent awareness, so it selects the nearest Pokémon
on any of the eight adjacent tiles. Its optional Custom Vision same-tile
awareness is also on, so another Pokémon on its tile still meets the condition.
This option is off when omitted; other profiles keep their prior Vision.
While that condition is true, it uses
one-tile Hop Chase toward the captured Object of interest with inherited
Hop time, and enables collision damage. Knockback remains inherited. Held and
recovering subjects cannot start it. Other later applications can still win
individual fields through the normal composition order.
Face movement and Return after move are enabled. It hops at the target, then
hops back to the captured start tile. The return skips the wait between hops.
Its existing Movement Chain values add one passive Pause after the pair:
one move, no movement variance,100% Pause, base40 and variance40 produce20–40
native frames. Hop pause remains zero to avoid a second wait.

Return after move is a shared Movement Style checkbox for ordinary autonomous
Walk and Hop. It uses the same motion engine and time/style for the return,
then consumes the ordinary movement/chain pause once. The captured origin is
permitted even when it is outside the forward destination mask, but world
blockers, support and other actors still apply. A blocked return gives control
back; a temporary reservation can retry in at most two distinct Actor frames.
A Field or actor change, held control, capture, despawn or hit cancels it.
Spawn entry, intermediate staged travel, forced knockback and Mounted control
do not start return pairs.

One condition captures at most one target. It selects no target, the player, or
one compatible actor. While-true activation follows predicate truth. Timed
activation owns duration and cooldown; retrigger restarts duration and cannot
occur during cooldown. All conditions can activate or end during ordinary
autonomous movement. The current profile, target and damage settings update
then. The accepted move finishes with its original plan; alerts and a new
heading wait for the next legal intent.

`notice-player` checks player Vision but can capture an actor from a separate
named target pool. That actor search covers eligible Wild actors on the active
map and has no Vision-distance limit. An optional facts gate requires every
listed `all` fact and forbids every listed `none` fact. `actor-facts` uses the
same gate without a Vision check. `player-damaged` reads an accepted player HP
collision and captures that exact physical Pokémon source from its actor pool.
It has no Vision, chance, or range fields; its optional facts and while-true
activation use the same generic condition owner. A thrown hit identifies the
colliding Cargo, not its thrower. The current facts are reserved cargo, held
cargo, valid throw line, and recovery. These are observations, not profile
names or private controller phases.

`subject-damaged` reads an accepted HP loss by the exact subject being
evaluated. It has no Vision, chance or range fields, and can capture Player
or use no target. Its pending event belongs to the full prepared actor identity;
damage to another actor or to Player does not satisfy it. It uses the ordinary
activation and cooldown rules and consumes the event only on admission.

A named pool has a stable ID, display name, one match, and either all matching
actors or explicit members. It
can be reused by a normal target, a condition subject, or an actor-target
filter. It cannot reference another pool. `Baby Pokémon` supplies Skittish
subjects. `Playful Pokémon` supplies both Playful subjects and compatible actor
targets. `Throw-capable Pokémon` supplies all three Throw condition subjects;
`Throw cargo` selects any eligible Wild actor. Teleport and Stalker use direct
memberships rather than a synthetic pool.

### Vision and control ownership

Vision-based conditions select Current Vision or own an inline Custom Vision.
Profiles own stable Current Vision fields. Current Vision is cached from
`Default`, normal applications, and a forced-role profile. Conditional
applications are excluded, so a profile cannot alter the Vision used to admit
itself. The default is a three-tile, 90-degree forward cone with awareness of
all adjacent tiles and solid-terrain occlusion. Custom Vision can also use
straight lines ahead or all four cardinal lines. Cardinal lines ignore facing
and retain range, cardinal alignment, and solid-terrain occlusion.

Fly In is a Placement, not a Hop tuning bundle. It descends from offscreen
flying height to the exact prevalidated destination surface and then returns
control to the normal Routine. Hop From Off Screen remains a separate
eight-tile effect.

Pickup, carry, throw, drop, cancel, and release use internal held actor control.
There is no Picked Up profile or behavior class in the target model. Raw native
controller-state names remain diagnostic compatibility values only; they are
not Workshop tabs, lanes, or classifications.

Find Throw Cargo uses Chase toward its captured actor and `Pick up condition
actor` on reach. Find Throw Position uses Chase toward a legal launch tile
for its resolved aim and the authored Throw range. Throw Held Actor selects
windup and launch;
its `attacking`, minimum impact speed, and collision damage belong only to
the launched flight. The existing linked Tired behavior handles recovery.
None of these profiles selects a hidden `PICKUP_THROW` sequence.

Follower sight and accepted Player damage are separate visible conditions in
Find Throw Cargo. Sight captures the exact noticed Pokémon; damage captures
the exact physical Pokémon that lowered Player HP, with no Vision requirement.
Both can activate Find Throw Cargo during ordinary autonomous movement,
before the next legal pickup intent. They do not interrupt accepted movement
or replace held Cargo.
A shared valid-Interest condition keeps Find Throw Cargo and its halved travel
times active while the bounded reachable query is Pending. Wild Cargo uses
`usesBinding: trigger` as a prerequisite and remains a separate actor. Follower
Cargo uses `usesBinding: object-of-interest-itself` to capture that exact Object
of interest; option3 requires Cargo capture and an actor target. Reachable
pickup, accepted movement completion, target loss, and recovery remain shared.

The Follower-only Throw Away From Player attack sets target14,
`PLAYER_AWAY_THROW_LINE`, while Cargo is held. Find Position searches only if
the current tile has no safe throw endpoint. The aim first follows the outward
Player-to-carrier vector at the authored range, including unequal X/Z offsets.
The four existing cardinal directions remain fallbacks. Release latches the legal
endpoint at exactly the authored Throw range, then checks that same endpoint
and its support height against the current Player position before launch. The
landing must be legal and farther from Player; a failed recheck cannot silently
retarget it. Sight and damage use the same pickup, carry, position-search and
flight path. Wild Throw keeps Player as Object of Interest and throws a separate
Cargo toward Player. Normal following resumes after recovery and cleanup.
Wild throws can aim at any tile offset within their existing Manhattan range
(the sum of the two tile distances). Away throws keep their existing maximum-axis
range. The shared flight checks every crossed tile, then uses the exact saved
endpoint and support height. Facing remains cardinal and does not limit aim.

`data/OverworldWildBehaviorData.c` and
`include/overworld_wild_behavior_data.h` are generated ROM-compatibility
outputs. Do not edit their profile arrays, indexes, or counts by hand. Use the
Workshop or edit the named JSON catalog, then regenerate the compatibility
files:

```bash
# Generate C and header compatibility data from the named JSON catalog.
python3 scripts/generate_overworld_behavior_catalog.py

# Check that generated C and header data match the named JSON catalog.
python3 scripts/generate_overworld_behavior_catalog.py --check
```

Generation is one-way: named JSON to C/header compatibility data. The
generator does not import positional C data into the catalog. Workshop saves
update the named JSON catalog and regenerate the same compatibility files.

The catalog shape is documented by
`tools/overworld/schemas/behavior-authoring-v5.schema.json`. The generator
also validates field names, stable IDs, parent cycles, references, matches,
members, pools, classification order, operators, and fixed-layout counts before
it writes output.

The generated C still contains class snapshots and ordered override tables.
Those are ROM compatibility layouts, not authoring profile types. Generation
materializes selected profiles and emits only local operators for profile
applications. This keeps overlapping and relative applications in the same
order as the authored catalog.

`lib/overworld/overworld_behavior_resolver.c` is the canonical composition
implementation used by the ROM and `/api/v2/resolve`. It compiles for ARM and
as `build/overworld_behavior_resolver_host`. It returns the resolved lanes,
mechanical primitives, fingerprint, and ordered provenance. The Workshop V2
endpoint decodes that result for display. Authoring changes storage only; they
do not create a second composition implementation.

The resolve endpoint accepts the complete resolver context. In addition to
species, level, terrain, and shiny state, agents can pass
`forcedOverrideMask`, `activeConditionalApplicationMask`, condition winners,
the resolved condition target, and `behaviorClass`. The Workshop condition
preview prepares world facts and calls the same portable evaluator before it
calls the resolver. Values can be integers or known C symbols and flag
expressions. Omit `behaviorClass`, or use `auto`, to run class rules.

`activeConditionalApplicationMask` is a compatibility API field name. It means
the set of conditional applications admitted for this intent decision; it does
not name an authored state or lane.

`scripts/verify_overworld_behavior_resolver.py` runs the committed golden
corpus through both single and batch Workshop adapters. It also checks that the
ROM overlay and host tool compile the same resolver source and that the actor
service publishes those callbacks. This is source and host proof. A packaged
ROM run is still required before claiming live parity.

## Resolution explanation

A resolution explanation must show:

- Subject and field context.
- Default and every application in source order, with classification.
- Applied, skipped, and conditionally admitted profiles.
- Normal assignment, condition subject, named-pool, and System-link reasons.
- Each changed field with old value, operator, and new value.
- Winning condition entry, Current or Custom Vision source, captured target,
  and Tired profile selection.
- Normalization changes.
- Mechanical primitives.
- Final fingerprint.

Example:

```text
SPECIES_MAREEP / Wild / Land

Root: Default
Routine 06: Meander                  APPLIED by normal membership
  Subject: SPECIES_MAREEP
  Vision: Current Vision from Default + normal applications
  Target: Player

Owner.behavior: Meander -> Notice presentation
Owner.target: None -> Player

Fingerprint: 4d2a7e91
```

Mounted is a System profile, not a profile type or resolver role. Current mount
begin resolves the same subject with the forced `Mounted` application,
snapshots the resolved Owner lane, then selects the rider-input controller.
Mounted explicitly sets Movement Chain to Off and applies its visible speed
settings. It is applied to the Pokémon's normal selected profile, not on top
of Follower. Fields without local overrides stay inherited from that selected
profile. Follower's chase and land-only rules remain limited to
the unmounted follower. The Mounted controller takes rider input in place of
AI target choice; the resolved profile controls movement timing and chain
actions. Changing Mounted's chain setting changes the resolved chain; the
controller has no separate rule that forces it Off.

## Stable observation

`OverworldActorSnapshot` exposes:

- Actor handle and field epoch.
- Subject identity and role.
- Authority, engine-anchor, and dependent-presentation generations.
- Selected lane.
- Resolved behavior fingerprint and matched layer IDs.
- Controller state and last intent.
- Motion kind, phase, origin, target, elapsed, and duration.
- Logical and rendered positions.
- Input ownership and target reservation.
- Stream anchor and loader-busy state.
- Last plan decision, commit sequence, and cancel reason.
- Population scheduler state when requested.

`scripts/generate_overworld_actor_system_debug.py` emits snapshot layout,
fixed entries, enum IDs, symbols, and offsets to
`build/overworld-system.debug.json`. Live adapters must read that descriptor
instead of adding private offsets.

`tools.overworld.actor_probe.capture_observation` is the shared Python adapter
for live emulator drivers. Give it a memory reader with the interface
`read(address, size) -> bytes`; it returns the same evidence document as
`scripts/owctl actor capture`. Boot and input control stay separate from
public observation decoding.

A live driver arms one exact window with
`configure_runtime_trace(read, write, descriptor, ...)`, performs its input,
then calls `finish_runtime_trace(...)` before `capture_observation(...)`. The
write callback runs only while the emulator is paused between frames. Both
helpers use the versioned public trace header and generated descriptor; they do
not know actor-system private offsets. The shared devtools recorder uses these
observations through its worker. Checked tests consume that same stream.
There is no retained standalone collector path. Missing measurement coverage
remains pending in the migration map, not inferred from a successful tool call.

## Semantic trace

The observation module uses a fixed-size binary ring. It contains
no strings and allocates no memory per frame. A host decoder maps stable
event and reason IDs to names.

`ACTOR_DETACHED` is a terminal release when an actor disappears during a
motion. It replaces a separate cancel/control-return pair because no actor or
input claim remains after detach.

Core events:

- `ACTOR_ATTACHED`
- `ACTOR_DETACHED`
- `CONTROL_REBOUND`
- `PROFILE_RESOLVED`
- `LANE_CHANGED`
- `INTENT_CREATED`
- `CANDIDATE_REJECTED`
- `PLAN_ACCEPTED`
- `MOTION_STARTED`
- `STREAM_WAITING`
- `STREAM_ADVANCED`
- `PATH_ADVANCED`
- `LOGICAL_COMMIT`
- `WORLD_EFFECT`
- `PRESENTATION_SYNCED`
- `MOTION_FINISHED`
- `MOTION_CANCELED`
- `CONTEXT_CHANGED`
- `ACTOR_REBOUND`
- `CONTROL_RETURNED`
- `MOUNT_PRESENTATION_POSITION`
- `MOUNT_PRESENTATION_STATE`

Each event stores sequence, frame, actor handle, role, event ID, reason ID, and two event-specific values. Trace filters select actors, event groups, and duration. Unarmed tracing has near-zero work.

Mounted skid presentation publishes one adjacent position/state pair for each
motion sample. `MOUNT_PRESENTATION_POSITION` stores the packed player and
follower logical coordinates. `MOUNT_PRESENTATION_STATE` stores both objects'
current/next facing values plus elapsed time, duration, motion kind, locked
facing, and logical/render equality flags. Host proof rejects missing elapsed
samples, unequal coordinates, changed facing, incomplete pairs, and a motion
kind or duration that differs from `MOTION_STARTED`.

Every trace header also stores the oldest sequence, next sequence,
overwritten-event count, active filter, and field epoch. A scenario warns or
fails when its required event window was overwritten.

## First-divergence report

Wild and mounted parity compares only shared contracts:

- Resolved Owner profile.
- Candidate ordering and target validity.
- Travel time, arc, facing, acceleration, and skid.
- One logical commit.
- Path-advance, player-step, and streaming counts where the role uses them.

It does not compare AI intent selection or rider presentation.

```text
FAIL mounted.walk.accelerate

Profile parity: PASS
Plan parity: PASS
Commit parity: FAIL at tile 4

Wild:    LOGICAL_COMMIT -> CONTROL_RETURNED
Mounted: LOGICAL_COMMIT -> pendingStep retained

First divergence:
Mounted executor did not release the movement-end boundary.
```

This report is the normal diagnosis artifact. For presentation or engine gaps,
add checked native memory/event observations through shared devtools. Screenshots
are optional human-view attachments, never test proof. Follow
[memory-backed proof](verification.md#memory-backed-proof).

## Accretive change rule

Every change adds reusable knowledge in the smallest durable form:

- New profile field: schema entry, generated metadata, resolution vector, feature-map link.
- New locomotion: planner contract, trace events, model scenario, ROM integration scenario.
- Fixed bug: scenario that fails before the fix and names the violated invariant.
- New engine fact: adapter contract or cited historical note, not an unexplained offset in a verifier.
- New failure mode: stable reason code and decoder text.

Do not add long narrative attempt logs for ordinary work. Keep short failure evidence only when it prevents a likely repeated experiment, then link it from the owning feature.

## Agent resource policy

Use the least expensive proof that can reject the change:

1. Schema and source validation.
2. Portable resolver or motion-model scenario.
3. Package and ABI verification.
4. One focused accepted `owctl scenario run`.
5. Fresh checked native presentation and input measurements through shared
   melonDS tools. Screenshots are off by default and never proof. Do not take
   over the user's separate melonDS window; use the owned disposable session.
6. Long soak only for transitions, streaming, population, or lifecycle races.

Stop at the first failed layer. Decode the semantic trace before opening broad source areas.
