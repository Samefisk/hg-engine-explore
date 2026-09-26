---
name: design-overworld-behavior
description: Design or refine hg-engine overworld Pokémon behavior by composing reusable Routine, Placement, Capability, Attitude, Style, Follower/Mount, and Modifier profiles. Use for a full Pokémon behavior, one reusable behavior block, a conditional response, or a playtest-ready design. Use author-overworld-profile for the later catalog edit and mechanical proof.
---

# Design overworld behavior

Design the smallest clear composition that makes the Pokémon feel alive. Match
the user's scope: advice only, one reusable block, a complete composition, or
an implemented playtest iteration. Do not add unrelated blocks.

Use the terms in [`CONTEXT.md`](../../../CONTEXT.md). Read the target catalog
and authoring rules in
[`authoring-debugging.md`](../../../documentation/overworld-system/authoring-debugging.md#profile-building-block-model)
before naming a new block.

## Compose building blocks

The complete `Default` root is always present. It supplies valid values. Each
override profile should express one visible idea and use one classification:

1. **Routine** — ordinary movement language and rhythm. Examples: Meander,
   Sprint, Small Bird Hop, and Idle.
2. **Placement** — spawn or world-placement rule. Examples: Fly In, Canopy
   Access, and Flower Bed.
3. **Capability** — one reusable ability or permission. Examples: Teleport,
   Long Hop, Throw, and Ram.
4. **Attitude** — one reusable response or relationship. Examples: Startled,
   Playful, Ambush, and Skittish.
5. **Style** — a compatible change to how movement looks. Waddle is a Style.
6. **Follower/Mount** — a System-owned role adaptation.
7. **Modifier** — a final small or System-owned override. Asleep is a
   Modifier.

Applications use this order. Later matching profiles override earlier values
field by field. Manual order inside one classification is meaningful. A
complete Pokémon design can use several blocks from one classification when
their fields and visible purposes are compatible.

An archetype is only informal shorthand for the final composition. It is not a
saved classification. Do not create a large profile merely because the whole
composition needs a name.

Conditional and System are badges, not classifications. Follower, Mounted,
and Asleep are visible System profiles, but they cannot be assigned as ordinary
Pokémon layers. Mounted is an empty override and inherits all fields from the
selected Pokémon profiles. Being carried is internal held actor control; it is
not a profile.

## Keep one visible idea per block

A block can own several fields when they support one visible result. Sprint can
own fast Walk, acceleration, skids, and its occasional forward Hop because they
together produce one running Routine. Long Hop owns only long-Hop tuning, so it
can combine with Scavenger without copying that Routine.

Do not hide spawn, reaction, tired, and ordinary movement rules in one large
profile. Split them by visible responsibility. Reuse an existing block when it
already expresses the requested idea.

Profiles compose only through local field operators. One resolved field has
one value. When two ideas write the same field, inspect the application order
and choose the intended winner. Do not describe both values as simultaneous.

## Design conditional behavior

A conditional profile owns every fact needed to activate it:

- its ordered condition entries;
- each entry's subject pool;
- its predicate and Vision choice when needed;
- while-true or timed activation;
- duration and cooldown for timed activation;
- no target, the player, or one compatible actor.

It has no normal Pokémon assignment. The Workshop derives its faded overview
members from the union of its condition subject pools.

Condition entries in one profile are independent and do not stack. If several
entries are admitted, the last listed entry wins for that profile. Different
conditional profiles still compose in normal application order. One condition
captures at most one target. A timed trigger restarts duration when it
retriggers, and it cannot retrigger during cooldown. A changed condition takes
effect at the next intent boundary; accepted motion finishes.

Use a named pool when the same Pokémon set has a real reused meaning. Use an
inline pool for a one-off set. A named pool can be used by a normal assignment,
a condition subject, or an actor-target filter, but it cannot contain another
pool. `Baby Pokémon` and `Playful Pokémon` are shared pools. Teleport and
Stalker keep direct membership lists; do not create a synthetic spectral pool.

## Use Vision consistently

Vision is one shared actor service. The standard Vision is a three-tile,
90-degree forward cone with adjacent awareness, blocked by solid terrain.
Actors do not block sight.

Use **Current Vision** by default. It is resolved from `Default`, normal
applications, and a forced-role profile when the actor binds. Conditional
applications are excluded, so a conditional profile cannot change the Vision
that activates itself.

Use **Custom Vision** only when one condition needs a deliberate exception.
The custom value belongs to that condition and does not change the actor's
Current Vision. Vision is evaluated at intent boundaries, not each frame.

## Respect Placement and control ownership

Fly In is a Placement for birds and flying insects. It begins offscreen at
flying height, descends to a prevalidated destination, lands at that surface's
exact height, and then hands control to the normal Routine. It is not a long
Hop and has no per-profile timing controls.

Hop From Off Screen is the separate eight-tile Hop effect used by blocks such
as Floaty Bounce and Long Hop. Do not use it to imitate flight.

Held actor control owns pickup, carry, throw, drop, cancel, and release. Do not
design a Picked Up profile or behavior class.

## Design the behavior

1. Write one short motion sentence that names the feeling and key visible
   action. Example: “Mareep meanders calmly, notices the player, then resumes
   grazing.”
2. Inspect the subject's current resolved behavior and provenance. Do not infer
   behavior from names alone.
3. Select the smallest existing Routine and any needed Placement, Capability,
   Attitude, or Style blocks.
4. For each conditional block, choose its subject pool, predicate, Current or
   Custom Vision, activation lifetime, and one target source.
5. Check conflicts in classification and manual application order. Confirm the
   intended later writer for every shared field.
6. Tune the main rhythm first: primitive, target, travel time, chain, pause,
   and response. A smaller travel-time value is faster.
   For Walk, keep the per-step pause and pause variance at zero. A pause after
   every tile reads as lag. If a deliberately slow Routine needs a pause, make
   it long enough to read as an intentional stop and prove that feel in play.
   Do not use a one-move Movement Chain with Walk: use no chain, or at least
   two moves. This rule does not apply to Hop chains.
   A Movement Chain can select several pause actions. One overall chance
   admits the set, then one selected action runs at random with equal weight.
   With `N` selected actions, each action's approximate chance is the overall
   chance divided by `N`. If a second action should keep the first action's old
   frequency, double the overall chance when the result is at most 100%.
   Meander is the reference: `Look Around` plus `Pause` at 50% gives about 25%
   Look Around, 25% Pause, and 50% no action. A lone `Pause` keeps its legacy
   always-run behavior. Use `Pause` for an idle stop; do not use the per-step
   Walk pause for this rhythm.
7. Add chance and variance only when they remove visible repetition. Remove
   fields and blocks that do not support the motion sentence.

For field meaning, units, bounds, lanes, and operators, read the relevant entry
in [`behavior_schema.json`](../../../tools/overworld/behavior_schema.json).

## Author and prove the design

For an implementation request, read and follow
[`author-overworld-profile`](../author-overworld-profile/SKILL.md). Use the
named catalog, ordered applications, resolver provenance, and focused proof.
Inspect the final Owner and Tired lanes, admitted conditions, captured target,
Current Vision source, and field winners. If the schema or runtime lacks the
needed mechanic, name that product gap instead of imitating it with an
unrelated field.

Correct resolution proves what the game received. It does not prove that the
movement feels natural. Prepare a ROM that the user can play before asking for
aesthetic feedback.

## Prepare each user-test iteration

For an ordinary land Pokémon, use the Workshop's reversible **Route-only
encounter** on Route 29 to make the subject the only enabled encounter. Keep
the source encounter entries as the saved baseline. Use the available
`hg-engine-delta-build` skill for the test ROM, then tell the user where to go
and what motion to watch.

If the behavior needs water, rooftops, canopies, or another feature absent from
Route 29, use the earliest practical natural map that contains it. Do not
change the behavior only to fit Route 29.

Keep the temporary route-only encounter across feedback rounds. Apply feedback
to the same motion sentence, then repeat authoring, proof, build, and playtest.

When the user accepts the behavior:

1. Clear the temporary route-only encounter.
2. Rebuild the normal ROM.
3. Confirm the requested resolved behavior and required profile proof still
   pass, and that no temporary encounter setup remains.

If the user takes over before acceptance, state the exact temporary encounter,
map, ROM, and remaining proof gap. The user is the final judge of feel.
