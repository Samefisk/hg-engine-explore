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

**Held actor control**:
An internal Wild actor control mode used while a Pokémon is carried, thrown,
dropped, or released. It suspends autonomous planning without changing the
actor's authored behavior profile.
_Avoid as a synonym_: Picked Up profile, behavior class

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
The session applies the Mounted System profile to the Pokémon's normal selected
behavior, not to its Follower behavior. The session is not itself a profile.
_Avoid as a synonym_: Riding mode

## Behavior

**Profile**:
One named behavior building block with a stable ID, one parent, one kind, one
optional classification, and local field operators. A normal profile
contributes when its application matches. A conditional profile contributes
only when one of its owned conditions is admitted.
_Avoid as a synonym_: Movement config

**Root profile**:
The one complete profile. It has no parent and supplies every field when a
selected profile is materialized.
_Avoid as a synonym_: Fallback layer

**Profile selector**:
An ordered match that selects the initial profile for a subject. Selection is
an authored use of a profile, not a different profile type.
_Avoid as a synonym_: Profile, layer

**Profile application**:
A stable ordered use of one profile. A normal application owns its Pokémon
target. A conditional application has no normal assignment; its condition
entries own their subject pools. System applications are linked by their
runtime owner and cannot be assigned as normal Pokémon layers.
_Avoid as a synonym_: Profile, per-Pokémon copy

**Profile classification**:
The profile's place in composition order. The saved classifications are
Routine, Placement, Capability, Attitude, Modifier, System, and Utility, in
that order. Conditional is independent of classification. An archetype is only
informal shorthand for a complete composition; it is not a saved
classification.
_Avoid as a synonym_: Profile kind, condition type

**Routine**:
The actor's ordinary movement language and rhythm, such as Meander, Sprint, or
Small Bird Hop.
_Avoid as a synonym_: Archetype, root profile

**Placement**:
A reusable spawn or world-placement rule, such as Fly In, Canopy Access, or
Flower Bed. It does not state the actor's ordinary intent.
_Avoid as a synonym_: Routine, encounter terrain

**Capability**:
One reusable ability or permission, such as Teleport, Long Hop, Throw, or Ram.
A conditional Capability owns the condition that makes the ability apply.
_Avoid as a synonym_: Routine, attitude

**Attitude**:
One reusable response or relationship to a target or world fact, such as
Playful, Startled, Ambush, or Skittish.
_Avoid as a synonym_: Personality value, controller state

**Modifier**:
A compatible change to another building block without replacing its main
intent or primitive, such as Waddle.
_Avoid as a synonym_: Capability, controller state

**System profile**:
A runtime-owned role adaptation, such as Follower or Mounted. It is linked by
its runtime owner and cannot be assigned as a normal Pokémon layer. Mounted is
an empty override, so the selected Pokémon's resolved behavior stays inherited
during a mount session.
_Avoid as a synonym_: Role, mount session

**Utility**:
A final support or fallback override, such as Asleep. It composes after all
other classifications.
_Avoid as a synonym_: Capability, controller state

**Conditional profile**:
An override profile whose local operators contribute only while one of its
condition entries is admitted. It has an ordered application identity but no
normal Pokémon assignment. Conditional and normal applications share one
source order, and later values override earlier values.
_Avoid as a synonym_: Motivation, condition group

**Condition entry**:
One independent predicate, subject pool, Vision choice when needed, activation
mode, timer policy, and target query owned by a conditional profile. Entries do
not combine. If more than one entry in one profile is admitted for one subject,
the last listed entry wins.
_Avoid as a synonym_: Layer, state, condition group

**Subject pool**:
The named or inline authored set of Pokémon identities to which one condition
entry can apply. It filters the subject, not the possible target.
_Avoid as a synonym_: Target pool, application

**Named pool**:
A stable reusable Pokémon set that can be referenced by a normal application,
a condition subject, or an actor-target filter. A named pool can contain
explicit members and one match record, but cannot contain another pool.
_Avoid as a synonym_: Profile, recursive group

**Activation mode**:
The lifetime rule for one condition entry. While-true follows current predicate
truth. Timed holds for its duration and cannot retrigger until cooldown ends.
_Avoid as a synonym_: Controller state

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

**Admitted conditional application**:
A conditional profile application selected by the condition evaluator for the
current intent decision. This is a resolver input, not an actor state or lane.
_Avoid as a synonym_: Condition state, behavior lane

**Current Vision**:
The stable Vision resolved at actor bind from Default, normal applications,
and a forced-role profile. Conditional applications are excluded so a profile
cannot change the Vision that activates itself.
_Avoid as a synonym_: Notice range, condition cone

**Custom Vision**:
An inline Vision owned by one vision-based condition. It replaces Current
Vision only for that condition's predicate.
_Avoid as a synonym_: Profile Vision, actor Vision

**Layer**:
One applied profile contribution that can change selected profile values.
_Avoid as a synonym_: Patch, rule row

**Lane**:
One resolved behavior state: Owner or Tired. Mounted control uses the Owner
lane. Native controller-state names are not authoring lanes.
_Avoid as a synonym_: Controller state, mode profile

**Resolved behavior**:
The immutable lanes, captured target, primitives, provenance, and fingerprint
produced for one subject, resolver context, forced layer set, and admitted
conditional application set. Role projection happens afterward.
_Avoid as a synonym_: Effective settings, final config

**Primitive**:
A mechanical action selected from resolved behavior, such as Walk, Hop, Teleport, look, or pause.
_Avoid as a synonym_: Behavior, animation

**Fly In**:
A Placement spawn locomotion that starts an actor offscreen at flying height,
descends to one prevalidated destination surface, lands at that surface's exact
height, and then hands control to the normal Routine.
_Avoid as a synonym_: Long Hop, Hop From Off Screen

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
