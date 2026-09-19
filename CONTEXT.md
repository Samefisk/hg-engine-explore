# hg-engine Explore Context

This glossary defines the shared language for the overworld Pokémon system. Use these terms in code, plans, traces, scenarios, and reviews.

## Identity and control

**Subject**:
The Pokémon identity and authored facts used to resolve behavior. It includes species, form, level, personality, and party or encounter identity.
_Avoid as a synonym_: Entity, unit

**Actor**:
One logical overworld mover with one identity, one control mode, and at most one active motion.
_Avoid as a synonym_: Sprite, `MapObject`, mon

**Actor handle**:
A generation-safe token that identifies one actor and is validated against its field, map, and encounter identity. It cannot address a recycled slot or retained engine object.
_Avoid as a synonym_: Slot ID, object pointer

**Role**:
The source of control for an actor: Wild, Follower, Mounted, or Scripted.
_Avoid as a synonym_: Actor type, movement type

**Authority**:
The actor state that owns logical position, motion phase, and terminal completion. Authority exists in both the ROM and host model.
_Avoid as a synonym_: Main sprite, master object

**Engine anchor**:
The engine object used for camera, terrain, and stock field integration. During current mounted movement, the player `MapObject` is the engine anchor and also renders the rider.
_Avoid as a synonym_: Authority, dependent presentation

**Dependent presentation**:
A sprite or effect that mirrors authority and never owns motion. The mounted Pokémon object is a dependent presentation; rider graphics are presentation state on the player engine anchor.
_Avoid as a synonym_: Second mover, synced object

**Mount session**:
The period in which the current follower and player are bound into one mounted actor under rider input.
_Avoid as a synonym_: Mount profile, riding mode

## Behavior

**Profile**:
One named behavior definition with a stable ID, one parent, one kind, and local
field operators. A normal profile always contributes when its application
matches. A conditional profile also owns the entries that can activate it.
_Avoid as a synonym_: Mount profile, movement config

**Root profile**:
The one complete profile. It has no parent and supplies every field when a
selected profile is materialized.
_Avoid as a synonym_: Fallback layer

**Profile selector**:
An ordered match that selects the initial profile for a subject. Selection is
an authored use of a profile, not a different profile type.
_Avoid as a synonym_: Profile, layer

**Profile application**:
An ordered target and match that applies one profile's local operators. A
profile can be used by more than one application.
_Avoid as a synonym_: Profile, per-Pokémon copy

**Conditional profile**:
An override profile whose local operators contribute only while one of its
condition entries is active. Conditional and normal applications share one
source order and later values override earlier values.
_Avoid as a synonym_: Motivation, Active profile, attentive state

**Condition entry**:
One independent predicate, subject pool, activation mode, timer policy, and
target query owned by a conditional profile. Entries do not combine. If more
than one entry in one profile is active for one subject, the last listed active
entry wins.
_Avoid as a synonym_: Layer, state, condition group

**Subject pool**:
The authored set of Pokémon identities to which one condition entry can apply.
It filters the subject, not the possible target.
_Avoid as a synonym_: Target pool, application

**Activation mode**:
The lifetime rule for one condition entry. While-true follows current predicate
truth. Timed holds for its duration and cannot retrigger until cooldown ends.
_Avoid as a synonym_: Active state

**Captured target**:
The one player or generation-safe actor selected when an entry activates. A
target-required entry cannot activate without one. A stale captured target ends
that activation.
_Avoid as a synonym_: Object pointer, target slot

**Duration**:
The number of actor-system frames that a timed condition remains active after
it triggers.
_Avoid as a synonym_: Stamina

**Cooldown**:
The number of actor-system frames after a trigger during which that condition
entry cannot trigger again. Cooldown starts at the trigger.
_Avoid as a synonym_: Rest state

**Active conditional application**:
A conditional profile application admitted by the condition evaluator for the
current intent decision. This is a resolver input, not an actor state or lane.
_Avoid as a synonym_: Active lane, attentive state

**Layer**:
One applied profile contribution that can change selected profile values.
_Avoid as a synonym_: Patch, rule row

**Lane**:
One resolved behavior state: Owner or Tired. Mounted control uses the Owner
lane. The legacy Active lane is removed by the conditional-profile cutover.
_Avoid as a synonym_: Chill/Active/Tired speed, mode profile

**Resolved behavior**:
The immutable lanes, captured target, primitives, provenance, and fingerprint
produced for one subject, resolver context, forced layer set, and active
conditional application set. Role projection happens afterward.
_Avoid as a synonym_: Effective settings, final config

**Primitive**:
A mechanical action selected from resolved behavior, such as Walk, Hop, Teleport, look, or pause.
_Avoid as a synonym_: Behavior, animation

## Motion and world state

**Intent**:
A requested semantic action without collision results, engine side effects, or presentation changes.
_Avoid as a synonym_: Engine command, move

**Candidate**:
One possible target considered while planning an intent.
_Avoid as a synonym_: Fallback move

**Motion plan**:
A validated origin, target, duration, traversal policy, facing policy, and commit policy.
_Avoid as a synonym_: Jump data, held movement

**Motion**:
One execution of a motion plan from start through commit or cancel.
_Avoid as a synonym_: Step, animation

**Path advance**:
An authoritative tile-boundary crossing inside a motion. It updates logical location, terrain streaming, and distance consumers without completing the movement decision.
_Avoid as a synonym_: Step, intermediate commit

**Commit**:
The one terminal result produced by a completed movement decision. Chain counts, acceleration, landing effects, and eligible warp checks use commits, not path advances, render frames, or stream-anchor changes.
_Avoid as a synonym_: Step, landing callback

**Travel time**:
The exact frame count for one Walk tile. A smaller value is faster.
_Avoid as a synonym_: Speed, speed tier

**Encounter terrain**:
The encounter source category: Land, Surf, Headbutt, or Fishing. It selects encounter pools and is not a traversal surface.
_Avoid as a synonym_: Allowed terrain, surface

**Traversal permission**:
A lane policy that permits destination kinds such as land, water, canopy, player-relative targets, or authored elevated surfaces.
_Avoid as a synonym_: Encounter terrain, physical surface

**Physical surface**:
An occupancy layer with identity and height at a map location, including native ground, water, canopy, or another authored layer.
_Avoid as a synonym_: Encounter terrain, traversal mask

**Field epoch**:
A generation value that invalidates retained field, map-object, and presentation references after context changes.
_Avoid as a synonym_: Map ID check

**Rebind**:
Attach an existing logical actor to replacement engine presentation objects after a field-context change.
_Avoid as a synonym_: Respawn, reload

## Proof and diagnosis

**Decision**:
An accepted, rejected, or retryable result with a stable reason code.
_Avoid as a synonym_: Boolean result, failure

**Trace event**:
A bounded semantic record of a behavior, motion, lifecycle, or world decision.
_Avoid as a synonym_: Debug print, memory dump

**Scenario**:
A deterministic arrange, act, and assert description that can run against a model or the ROM.
_Avoid as a synonym_: Repro script, screenshot test

**Parity**:
Equality of one named shared contract across roles or adapters. Parity does not require identical AI intent or identical presentation.
_Avoid as a synonym_: Same behavior
