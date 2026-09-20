---
name: design-overworld-behavior
description: Design or refine hg-engine overworld Pokémon behavior from reusable profile layers. Use when the user asks how a Pokémon should move, requests a full behavior or one archetype, capability, attitude, or style trait, or wants a behavior made ready for personal playtesting. Use author-overworld-profile for the later catalog edit and mechanical proof.
---

# Design overworld behavior

Design the smallest clear behavior that makes the Pokémon feel alive. Match the
scope the user requested: a full behavior, one layer, advice only, or an
implemented and testable iteration. Do not add the other layers when the user
asked for only an archetype, capability, attitude, or style trait.

## Use the layer model

The complete root profile is always present. It supplies valid values, so an
override profile does not need to be complete. Do not call an archetype the
root or base profile.

Compose behavior in this design order:

1. **Archetype** — exactly one. It gives the Pokémon its normal movement
   language and rhythm. Examples include Bird, Flying insect, and Scavenger.
2. **Capabilities** — zero or more. Each grants one substantial, reusable thing
   the Pokémon can do when the game finds it appropriate. Examples include
   Throwing, Aggressive Ram, and Canopy Hopper. A capability does not need to
   own its trigger.
3. **Attitude** — zero or one at a time. It says what the Pokémon wants and how
   it relates to the player or world: aggressive, avoidant, curious, and so on.
   No attitude layer means neutral.
4. **Style traits** — zero or more compatible traits. They change how the
   chosen behavior is performed. For example, Rash can make an Aggressive
   approach faster and less careful.
5. **Follower/Mount** — runtime role layers. Apply them after the Pokémon's
   normal archetype, capabilities, attitude, and style traits so the role can
   adapt the composed behavior for following or mounting without becoming the
   Pokémon's normal identity.
6. **Modifiers** — reserved for later small numeric changes derived from facts
   such as stats, size, or nature. The current authoring context does not expose
   the agreed inputs or rules. Do not invent or author this layer yet.

Keep profile applications in this same order: archetypes first, then
capabilities, attitudes, style traits, Follower/Mount, and modifiers last. A
later layer may refine an earlier result, so do not append a capability after
an attitude merely to avoid moving an existing application. The resolver uses
the application array order; profile definition order does not compose the
behavior. Keep a conditional helper beside the layer that owns it.

Profiles compose only through their local operators. A parent supplies
authoring inheritance; profile applications create the behavior stack. One
resolved field has one value. When two desired ideas need the same field,
choose the result that best sells the Pokémon instead of describing both as
simultaneously active.

The layer model is the design target, not a claim that every current profile is
already cleanly separated. Inspect a reused profile's local operators. Preserve
its established result unless the requested behavior needs a split; do not
turn ordinary behavior work into an unrelated taxonomy cleanup.

### Conditions and lanes

Design the Owner and Tired results. There is no Active lane. A conditional
profile changes the same resolved Owner/Tired behavior only while one of its
owned conditions is active. Entries inside one profile are independent and the
last listed active entry wins. Different conditional profiles compose in normal
application order.

Decide whether a response is while-true or timed. For timed responses, choose
duration and cooldown separately. Choose whether the condition targets the
player, one matching Pokémon, or no target. The controller evaluates at the
next intent boundary and never interrupts an accepted motion.

### Archetype

Assign the closest existing archetype first. Create another only when a useful
group of Pokémon has no convincing home. Keep the roster conservative, but do
not force a clearly homeless group into a poor fit.

An evolution normally keeps its archetype. Change it only when its body, role,
or movement identity changes enough that the old movement language no longer
fits. Do not use evolution stage itself as a movement modifier.

Treat the current `nervous-scavenger` profile as the Scavenger archetype. The
stable ID retains its old wording for compatibility; the displayed name is
`Scavenger`. Its alert, spawn, and lane-link values are established archetype
behavior, not a reason to split it during an unrelated request.

### Capability

A capability owns only the fields needed to grant and tune its substantial
mechanic or movement permission. It does not own general attitude or ordinary
movement rhythm. Keep small gestures inside the archetype, attitude, or style;
do not create profiles such as `Mareep electric hop` or `Startle hop` merely to
hold one small flourish.

Canopy Hopper is a capability. Its base application only grants canopy terrain
permission. Its conditional child owns the Hop primitive and its canopy Hop
tuning. For entry, resolve that child against the chosen canopy destination
before normal ground collision can reject the tree. This leaves the Pokémon's
normal land primitive and land Hop tuning unchanged. It does not own general
chase, spawn, population, attitude, or ordinary movement rhythm.

### Attitude and style

Attitude owns intent, targets, attention, and the response to the player or
environment. It may tune travel time, stamina, pauses, and similar intensity,
but it must preserve the archetype's movement primitive. Skittish can speed up
a bird's hops; it cannot turn the bird into a walker.

Only one attitude is active. A conditional attitude can replace the normal
attitude while its condition holds, then normal resolution returns when the
condition ends. Capabilities and compatible style traits remain. A trait such
as Rash can stack with Aggressive because Rash is style, not a second attitude.

## Design the behavior

1. Write one short motion sentence that names the feeling and the key visible
   behavior. Example: “Mareep moves in calm grazing bursts and gives one small
   hop when startled.”
2. Inspect the subject's current resolved behavior and provenance. Do not infer
   its result from profile names alone.
3. Choose the closest archetype. Add only the requested capabilities, attitude,
   and style traits that support the motion sentence. Keep Follower/Mount after
   those layers and modifiers last.
4. Tune the clear center of the behavior first: primitive, target, movement
   chain, travel time, pause, and response. Preserve the archetype primitive
   when tuning attitude or style.
5. Refine with the existing chance and variance fields only after the main
   rhythm feels right. Use one or two useful sources of variation, such as
   chain length, chain pause, or travel-time variance. Variation should remove
   repetition without becoming a visible gimmick.
6. Remove fields and layers that do not help sell the motion sentence. One
   excellent cue is better than several weak cues.

For field meaning, units, bounds, lanes, and operators, read the relevant entry
in [`behavior_schema.json`](../../../tools/overworld/behavior_schema.json).
Remember that a smaller travel time is faster.

## Author the design

For an implementation request, read and follow
[`author-overworld-profile`](../author-overworld-profile/SKILL.md). Use the
named catalog, selectors, applications, and resolver proof from that skill.
Keep the application's order consistent with the full layer model and inspect
the final Owner and Tired lanes plus condition and target provenance. If a
requested behavior needs a mechanic that the
profile schema or runtime does not support, name that product gap; do not fake
it with an unrelated field.

Correct resolution proves what the game received. It does not prove that the
movement feels natural. Prepare a ROM that the user can play before asking for
aesthetic feedback.

## Prepare each user-test iteration

For an ordinary land Pokémon, use the Workshop's reversible **Route-only
encounter** on Route 29 to make the subject the only enabled encounter. Keep
the source encounter entries as the saved baseline. Load and follow the
available `hg-engine-delta-build` skill for the test ROM, then tell the user
where to go and what motion to watch.

If the behavior needs water, rooftops, canopies, or another feature absent from
Route 29, select the earliest practical natural map that contains it. Keep the
test simple for the user. Do not change the behavior merely to make Route 29
support it.

Leave the temporary route-only encounter active across feedback rounds. Apply
the user's feedback to the same motion sentence and repeat the authoring,
proof, build, and playtest handoff. This is an iteration ready for review, not
a finished behavior.

When the user accepts the behavior:

1. Clear the temporary route-only encounter.
2. Rebuild the normal ROM.
3. Confirm the requested resolved behavior and required profile proof still
   pass, and that no test encounter setup remains.

If the user takes over before acceptance, state the exact temporary encounter,
map, ROM, and remaining proof gap. The user is the final judge of whether the
motion sparks joy.
