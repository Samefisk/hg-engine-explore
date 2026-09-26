# Profile Building Blocks Implementation Plan

Status: Product implementation and PB9 proof closure are complete. PB10 user
acceptance remains open; the final agent normal-play check passed.

This plan starts from the completed conditional-profile system. It does not
repeat the old Active/attentive cutover in
[conditional-profiles-implementation-plan.md](conditional-profiles-implementation-plan.md).

## Outcome

Make the profile catalog a small set of reusable building blocks. A Pokémon is
defined by composing those blocks, instead of selecting one large behavior
archetype.

The completed system must have these properties:

- `Archetype` is a design shorthand for a composition. It is not a saved
  profile classification.
- Each saved profile expresses one visible idea.
- Profiles are classified and applied in this order:
  `Routine`, `Placement`, `Capability`, `Attitude`, `Style`,
  `Follower/Mount`, `Modifier`.
- Later matching profiles still override earlier profiles field by field.
- Manual order is preserved inside each classification.
- Conditional and System are separate badges. They are not classifications.
- A conditional profile has no normal Pokémon assignment. Its conditions own
  the subject Pokémon.
- Named pools can be reused by normal assignments, condition subjects, and
  actor-target filters.
- Vision is one shared actor service. Normal profiles can set a Pokémon's
  current Vision. A vision-based condition can use that current Vision or an
  inline custom Vision.
- The Workshop contains no user-facing Chill concept. Conditions, Spawn,
  Behavior, Movement Style, Vision, and Tired are main tabs.
- The current catalog is decomposed without changing unrelated species
  membership.
- `design-overworld-behavior` and `author-overworld-profile` teach the same
  model that the product enforces.

## Completion definition

The work is complete only when all of these are true:

1. The V5 authoring model, generator, Workshop, runtime, and generated output
   agree on classification, named pools, conditional ownership, and Vision.
2. The target catalog manifest fits the 32-application runtime limit and the
   generated catalog matches it exactly.
3. Every legacy profile in the migration table below is deleted, renamed, or
   decomposed as specified.
4. Picked Up is internal actor control state, not a behavior profile or class.
5. Fly In lands at the validated destination surface height and Hop From Off
   Screen uses eight tiles.
6. Host checks, ROM ABI checks, overlay-size checks, affected registered
   scenarios, spawn-work pacing, and zero-stutter proof pass on one current
   ROM.
7. The user can inspect the new catalog in the Workshop and playtest the named
   behavior examples.

## Current implementation record

The V5 catalog, generator, resolver, condition runtime, shared Vision, behavior
primitives, Fly In, held actor control, Workshop, catalog migration, docs, and
profile skills are implemented. The catalog has 30 applications in the frozen
seven-class order. The 11-member Heavy Stomp expansion has focused resolver,
spawn-work-budget, and zero-stutter proof on `test3313.nds`, SHA-256
`1df627b0d618d8a0c0a8fb845e31b3dea0f016f325f477129b73b8dd9e4e5023`.
It is newer than the full acceptance record below.

The last fully accepted proof ROM is `test3309.nds`, SHA-256
`870d45195b500ceaffea3ab39fad1792d19c2277a112f637018284fb6f01edf2`.
It proves the preceding 27-application catalog, not Heavy Stomp. On this ROM:

- packaged resolver parity passed with accepted proof;
- the packaged condition evaluator passed with accepted proof;
- the live Wild condition controller passed with accepted proof;
- all seven feature scenarios passed with accepted proof: Notice Player,
  Stalker, Playful, Startled, Fly In, Waddle, and held-control resume;
- owner-reader, follower/mounted owner transfer, spawn-height control, and
  Appear Hop passed with accepted proof after their current actor/recorder
  prerequisites were refreshed;
- both extracted spawn-budget suites passed;
- `population.spawn-work-budget` passed with accepted proof;
- `world.unmounted.spawn-zero-stutter` passed with accepted proof and zero
  late loops across 2,640 observed frames.

The final agent normal-play session used the unchanged Continue save in normal
mode with ordinary input only. The follower kept up, Wild actors moved and
spawned naturally, Notice Player released back to routine movement, actor
identity and presentation stayed valid, and native observation reported no
error or dropped events. This is an agent playtest, not the PB10 user
acceptance decision.

## Non-goals

- Do not add Boolean condition trees or a scripting language.
- Do not add recursive named pools.
- Do not redesign large birds in this work.
- Do not add per-profile Fly In timing or presentation controls.
- Do not give Stalker a special Vision shape.
- Do not copy old per-species Notice Player timing differences.
- Do not rewrite the resolver's field-composition algorithm.
- Do not remove the current 32-bit conditional-application mask in this work.
- Do not redesign Tired as a general state machine. It remains a lane that
  selects a reusable Routine profile.

## Frozen design contract

### Profiles and order

- The root `Default` profile remains complete, visible, and editable.
- One non-root profile has one classification and one visible purpose.
- A profile can contain several fields when those fields support the same
  visible purpose.
- The resolver keeps one shared ordered application list.
- The Workshop groups that list by classification and preserves drag order
  inside each group.
- Saving auto-sorts the groups. Direct JSON that violates group order fails
  validation.
- Known precedence constraints are explicit:
  - `Notice Player` is the first Capability.
  - `Startled` is before `Skittish`, so sustained Skittish flight wins.
  - the player condition is last inside `Playful`, so the player wins when
    both Playful conditions are active.
- All other within-group order comes from the checked target catalog manifest.

### Conditional ownership

- Each condition is independent. Conditions in one profile do not stack.
- If several conditions in one profile are active, the last active condition
  wins for that profile.
- Different conditional profiles stack in normal application order.
- One condition captures at most one target.
- A timed trigger restarts its duration when it retriggers.
- It cannot retrigger during cooldown.
- Accepted motion completes. A changed condition affects the next intent.
- A conditional profile has an ordered application identity but no authored
  target. The generator lowers that identity to the current disabled runtime
  target until the ROM storage format is changed for another reason.
- The Workshop derives a conditional profile's faded Pokémon overview from
  the union of all condition subject sets.

### Named pools

The V5 catalog adds top-level named pools with:

- a stable ID;
- a display name;
- one match record;
- zero or more explicit members.

The first named pools are `Baby Pokémon` and `Playful Pokémon`.

- `Baby Pokémon` replaces the empty Baby Pokémon profile and is used by
  `Skittish`.
- `Playful Pokémon` is used both as Playful's subject set and as its compatible
  actor-target filter.
- Teleport and Stalker list their members directly. They do not use a synthetic
  spectral pool.
- Inline one-off pools remain valid.
- A pool cannot contain another pool.
- Named pools are expanded by the generator. They add no ROM lookup or runtime
  storage model.

### Vision

The initial shared Vision is:

- a 90-degree forward cone;
- three tiles of range;
- one-tile adjacent awareness;
- blocked by solid terrain.

Adjacent awareness covers all eight neighboring tiles, including tiles behind
the observer. Actors do not block sight. The observer and target tiles are not
treated as blockers. Invalid or unloaded terrain fails closed.

Vision follows these ownership rules:

- `Default` supplies the standard Pokémon Vision.
- Normal profiles can override Vision fields.
- Conditional profiles cannot override the current Vision used to trigger
  conditions. This prevents a profile from changing its own trigger.
- At actor bind, the controller resolves and caches the stable current Vision
  from `Default`, normal applications, and any forced-role profile. Conditional
  applications are excluded.
- A condition selects `Use current Vision` or owns an inline custom Vision.
- The player uses the same Vision service and the same initial defaults. Player
  tuning is not a profile-authoring feature in this slice.
- Conditions and behavior planning consume the same visibility result.
- Visibility is evaluated only at intent boundaries.
- Geometry rejects targets outside the cone before occlusion work.
- Occlusion traces only the short line to a candidate. It does not scan every
  tile in the cone.
- Actor search remains bounded by the current ten-actor world view.

### Workshop

The main tab order is:

1. Conditions
2. Spawn
3. Behavior
4. Movement Style
5. Vision
6. Tired

The Conditions tab uses this card order:

1. **Who can trigger this**: named pool, one-off pool, or all matching actors.
2. **Trigger**: notice, cannot be seen, terrain, speed, or another supported
   bounded fact.
3. **Vision**: current or custom, shown only for a vision-based trigger.
4. **Activation**: while true, or timed duration and cooldown.
5. **Target**: none, player, or one compatible actor.

The deck shows:

- one small classification icon and subtle classification tint;
- a separate conditional badge;
- a separate System badge where required;
- clear section headings for each classification;
- normal members at full opacity;
- condition-derived members at reduced opacity.

There is no Chill tab or Chill copy in the UI. V5 authoring names use
`Behavior` and `Movement Style`. The generator can lower those names to the
existing binary fields during the compatibility period.

## Current baseline and constraints

The implementation starts from these measured facts:

- The authoring source is catalog V4 and
  `tools/overworld/schemas/behavior-authoring-v4.schema.json`.
- The catalog contains 32 profiles and 27 ordered applications.
- The condition mask permits at most 32 applications, so there are only five
  free bits before cleanup.
- Conditions already run at intent boundaries and only cause a new resolution
  when the active application mask changes.
- The resolver already composes normal and active conditional applications in
  one ordered pass.
- The condition world view contains subject facing, but does not yet contain
  player facing or candidate-actor facing.
- The Workshop already puts Conditions first, groups by classification, keeps
  stable order inside a group, and shows condition-derived Pokémon as faded
  icons. Preserve these parts.
- The authoring skill and parts of `tools/overworld/system_features.yaml`
  still refer to the removed V2 schema. Fix those routes before agents edit the
  catalog.
- `Picked Up` is still hard-coded as behavior class index 3 in the resolver and
  is read in both Wild overlays. It cannot be deleted as a data-only change.
- Distance 16 currently acts as a hidden "offscreen spawn Hop" switch in the
  Hop planner. The implementation must replace that magic-distance rule with
  an explicit spawn-entry intent before changing the distance to eight.
- Fly In and several behavior gaps touch
  `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
  Those edits must be serialized or owned by one integration agent.

## Target data flow

```text
V5 catalog
  profiles + ordered applications + named pools
                  |
                  v
      validation and deterministic expansion
                  |
       +----------+-----------+
       |                      |
       v                      v
normal profile set      prepared conditions
       |                      |
       v                      |
stable current Vision         |
       |                      |
       +---------> bounded visibility service
                              |
                    next intent boundary
                              |
                              v
                  active applications + target
                              |
                              v
                 existing ordered resolver pass
                              |
                              v
                 behavior planner -> actor motion
```

## Target catalog migration

The migration keeps existing species membership unless this table says
otherwise. The exact member lists and final application count are frozen in a
machine-checked manifest during Slice PB0.

| Current item | Target item or composition |
| --- | --- |
| Default | Keep as the complete root. |
| Aggressive Chase root | Delete. Move its selectors to Default plus reusable blocks. |
| Aggressive Ram root | Delete. Move its selectors to Default plus Ram. |
| Test root | Delete. Move its selector to Default. |
| Picked Up root/class | Replace with internal held actor control state, then delete the profile and class. |
| Teleport Stalker | `Teleport` normal Capability plus `Stalker` conditional Capability. |
| Canopy Hopper | Rename to `Canopy Access`, Placement. |
| Canopy Hopper · On Canopy | Rename to `Canopy Hop`, conditional Capability. |
| Throwing! | Rename to `Throw`, conditional Capability. |
| Playful! | `Playful`, conditional Attitude. |
| Floaty Bounce | Keep as a Routine. It keeps shortened Hop From Off Screen. |
| Bird | `Small Bird Hop` Routine. Its members also receive `Fly In`. |
| Flying Insect | `Erratic Flutter` Routine plus `Fly In` and `Notice Player`. |
| Gentle Grazer | `Meander` Routine plus `Notice Player`. |
| Runner | Rename to `Sprint`, Routine. |
| Skittish | Keep as a conditional Attitude. Use one Baby Pokémon pool condition and remove the Igglybuff timing exception. |
| Forced Asleep | Rename to `Asleep`, Modifier with a System badge. It is used by Sing and cannot be assigned normally. |
| Flower | Rename to `Flower Bed`, Placement. |
| Bird Rooftop | Rename to `Perch`, conditional Routine. Preserve its current behavior. |
| Scavenger | Keep as `Scavenger`, Routine. |
| Hopping Scavenger | Delete the composite. Give its members `Scavenger` plus `Long Hop`. |
| Follower Pokémon | Keep as `Follower`, Follower/Mount with a System badge. It cannot be assigned normally. |
| Aggressive Ram Boost | Rename to `Ram`, conditional Capability. |
| Default Active | Replace with `Notice Player`, conditional Capability. |
| Default Tired | Replace with shared `Rest`, Routine selected by Tired. |
| Baby Pokémon profile | Delete. Replace it with the Baby Pokémon named pool. |
| Swaying Plant | Delete the composite. Split its members as listed below. |
| Swaying Plant Active | Replace with `Startled`, conditional Attitude. |
| Swaying Plant Tired | Delete. Use shared Rest. |
| Ambush Plant | Replace with `Idle`, Routine. Members are Weepinbell, Victreebel, and Carnivine. |
| Ambush Plant Active | Replace with `Ambush`, conditional Attitude. |
| Ambush Plant Tired | Delete. Use shared Rest. |

The plant split is:

- Bellsprout and the Oddish line: `Meander` + `Waddle` + `Startled`.
- Sunflora: `Meander` + `Waddle` + `Startled`.
- Sunkern, Cherubi, and both Cherrim forms: `Hop Around` + `Startled`.
- Weepinbell, Victreebel, and Carnivine: `Idle` + `Ambush` + `Rest`.

The target ordered application manifest contains 30 entries:

1. Routine: Scavenger
2. Routine: Sprint
3. Routine: Floaty Bounce
4. Routine: Small Bird Hop
5. Routine: Erratic Flutter
6. Routine: Meander
7. Routine: Hop Around
8. Routine: Idle
9. Routine: Drowsy Wander
10. Routine: Perch
11. Routine: Rest, linked from the Tired tab
12. Placement: Fly In
13. Placement: Canopy Access
14. Placement: Flower Bed
15. Capability: Notice Player
16. Capability: Teleport
17. Capability: Stalker
18. Capability: Long Hop
19. Capability: Canopy Hop
20. Capability: Throw
21. Capability: Ram
22. Capability: Heavy Stomp
23. Attitude: Startled
24. Attitude: Ambush
25. Attitude: Playful
26. Attitude: Skittish
27. Style: Waddle
28. Follower/Mount: Follower
29. Follower/Mount: Mounted
30. Modifier: Asleep

Perch is after the ordinary Routines because it is a terrain-specific Routine.
Notice Player is before every specialized Capability. Startled is before
Skittish. This exact list is the starting PB0 target manifest; changing it
requires a design review, not an incidental drag operation.

New reusable blocks are:

- `Fly In`, Placement;
- `Long Hop`, Capability;
- `Hop Around`, Routine;
- `Drowsy Wander`, Routine;
- `Waddle`, Style;
- `Heavy Stomp`, Capability;
- `Notice Player`, conditional Capability;
- `Stalker`, conditional Capability;
- `Startled`, conditional Attitude.

## Behavior contracts to preserve or add

| Block | Required behavior |
| --- | --- |
| Notice Player | On first notice, show an exclamation, face the captured target, pause for one short presentation cycle, then resume the Routine. It does not chase or flee. One shared timing replaces old per-species timing. |
| Stalker | While the player cannot see the subject, move toward the tile behind the player. When the player can see it, the profile stops applying and the base Routine resumes at the next intent. Use current Vision. |
| Playful | Timed Attitude. Detect either the player or one nearby actor in Playful Pokémon. The player entry is last. Show a heart, approach and move around the captured target, stop before collision, move faster than the base Routine, and use `HOP_IN_PLACE` on about 60% of chain pauses. |
| Startled | On notice, show an exclamation and repeatedly retreat from the captured target for 44 frames. Cooldown is 164 frames. Preserve the actor's current locomotion. |
| Skittish | Sustain flight from the captured target. Use the Baby Pokémon pool and one shared 960-frame duration and 970-frame cooldown. |
| Throw | Own its detection, angry emote, captured target, and existing throw action. Use current Vision. |
| Ram | Own its detection, angry emote, charge, and existing collision battle behavior. It owns no Routine, Spawn, or Rest values. |
| Ambush | Preserve the current short plant ambush, but make it an Attitude over the Idle Routine. |
| Perch | Preserve current Rooftop/Signpost/Mailbox behavior. Only ownership and naming change. |
| Long Hop | Own only the long-Hop values. It applies after Routine, so order cannot remove it. |
| Waddle | Add horizontal walking sway only. It does not change speed, direction choice, or reactions. |
| Drowsy Wander | Walk in uneven two-to-six-step bursts with changing step time, long look-around stops, and no immediate backtracking. |
| Heavy Stomp | Emit the existing stomp dust and sound for every completed Walk tile. It does not change the Routine, speed, target, or pause. |
| Sprint | Preserve fast Walk, acceleration, skids, and occasional forward Hop as one Routine. |
| Fly In | Start offscreen at flying height, descend to a prevalidated destination, land exactly on its surface, then hand control to the normal Routine. |

Relative Playful speed changes must be bounded. Lower Walk and Hop travel-time
values make movement faster; neither can underflow its valid runtime minimum.

## Delivery graph

```text
PB0 baseline and manifest
          |
          v
PB1 V5 authoring structure
   |         |          |
   v         v          v
PB2 Vision  PB4 Fly In  PB5 Picked Up/class cleanup
   |
   v
PB3 behavior primitives
   \         |          /
    +--------+---------+
             |
             v
       PB6 Workshop UI
             |
             v
       PB7 catalog migration
             |
             v
       PB8 docs and skills
             |
             v
       PB9 integrated proof
             |
             v
       PB10 user playtest
```

PB2, PB4, and PB5 can start after the V5 structural contract is frozen. PB3
depends on the Vision API. PB4 and PB3 must not edit the Wild-spawns overlay at
the same time.

## Implementation slices

### PB0 — Freeze the baseline and target manifest

**Outcome:** Agents have one reviewed inventory and do not infer the migration
from profile names.

**Steps:**

1. Record the current catalog version, 32 profiles, 27 applications, class
   bindings, application order, profile fingerprints, generated ABI versions,
   overlay sizes, and representative resolved outputs.
2. Repair stale routes that point to `behavior-authoring-v2.schema.json`; they
   must point to the real current schema before V5 exists.
3. Add one machine-readable target manifest for:
   - final profile IDs, names, classifications, and badges;
   - final application order;
   - old-to-new profile mapping;
   - direct species membership and named-pool membership;
   - expected deleted profiles and class bindings;
   - required precedence constraints;
   - expected application count, which must be at most 32.
4. Make the manifest checker fail for an unknown source profile, a missing
   source profile, duplicate destination, order violation, or count overflow.
5. Select representative resolution fixtures for normal composition,
   conditional overlap, Tired, Follower, Picked Up, plant split, bird split,
   Teleport/Stalker, and Playful.

**Primary files:**

- `data/overworld_behavior_profiles.json`
- `tools/overworld/system_features.yaml`
- `.agents/skills/author-overworld-profile/SKILL.md`
- a checked fixture under `tools/overworld/fixtures/`
- its checker under `tools/overworld/`

**Exit gate:** The baseline and target manifest both validate, the target fits
the mask, and no product behavior has changed.

### PB1 — Add the V5 authoring structure

**Outcome:** Ownership changes in authoring without forcing a resolver rewrite.

**Steps:**

1. Add `behavior-authoring-v5.schema.json`.
2. Replace the classification enum with the seven target classifications.
3. Add top-level named pools. Accept a pool reference or an inline pool in:
   - a normal application target;
   - condition subjects;
   - an actor-target filter.
4. Reject recursive pool references, unknown pools, duplicate IDs, and empty
   accidental targets.
5. Change the application schema:
   - a normal profile application requires a target or an explicit link/System
     binding;
   - a conditional profile application contains only ID and profile;
   - System profiles use explicit system-owned bindings and cannot be assigned
     through the normal Pokémon editor.
6. Remove condition-subject references to another application's target. A
   condition owns its pool directly or by named-pool reference.
7. Add authoring names for Behavior and Movement Style. Keep binary field
   lowering in the generator until the runtime rename slice.
8. Make the generator expand pools and lower conditional application identity
   to the existing disabled runtime target.
9. Add V4-to-V5 migration support. Use one deterministic migration command
   with dry-run output, explicit input/output paths, unknown-input failure, and
   an idempotence check.
10. Keep generated storage unchanged unless a later Vision field requires a
    deliberate version bump.

**Primary files:**

- `tools/overworld/schemas/behavior-authoring-v5.schema.json`
- `scripts/overworld_behavior_profile_viewer.py`
- `scripts/generate_overworld_behavior_catalog.py`
- `tools/overworld/test_behavior_catalog_v2.py` or its renamed successor
- `tools/overworld/test_conditional_profile_migration.py`

**Proof:** Schema negatives, V4-to-V5 fixture migration, second-run no-op,
generated-output parity for an unchanged representative catalog, and resolver
goldens.

**Exit gate:** A V5 catalog can express the full target model, while the same
V4 behavior still generates byte-equivalent runtime profile data.

### PB2 — Add shared bounded Vision

**Outcome:** Pokémon and the player use one visibility rule that conditions and
planners can share.

**Steps:**

1. Add a portable Vision value and evaluator. Prefer
   `include/overworld_vision.h` and `lib/overworld/overworld_vision.c`. Keep it
   free of `FieldSystem`, live actor pointers, and profile lookup.
2. Add default range, cone, and adjacent-awareness fields to the behavior field
   schema and root profile.
3. Reject Vision field operators on conditional profiles.
4. Extend the condition world view with player facing and candidate-actor
   facing. Keep actor handles stable and bounded.
5. Provide a typed solid-terrain occlusion query in the runtime adapter. The
   adapter supplies simple visibility facts to the portable condition
   evaluator; it does not pass `FieldSystem` through that seam.
6. Evaluate cone membership first, then trace only to viable candidates.
7. Cache current Vision from Default, normal applications, and the forced-role
   profile at bind/rebind. Exclude conditional applications.
8. Add condition Vision mode: current or custom inline.
9. Replace legacy notice-range shapes with shared Vision for migrated profiles.
   Retain compatibility decoding only for old imported data.
10. Add the inverse relation required by Stalker: target cannot see subject.
11. Publish one reusable visibility result for condition evaluation and
    behavior planning.
12. Measure worst-case work for ten actors at one intent boundary and assert a
    fixed upper bound.
13. Use reserved profile-record bytes for the small Vision value if possible.
    Preserve the current 72-byte profile record unless a measured ABI change is
    necessary.

**Primary files:**

- new `include/overworld_vision.h`
- new `lib/overworld/overworld_vision.c`
- `include/overworld_behavior_conditions.h`
- `lib/overworld/overworld_behavior_conditions.c`
- condition adapter and Wild/Follower world-view producers
- `tools/overworld/behavior_schema.json`
- condition and packaging ABI tests

**Proof:** Portable geometry tests for all facings, cone edges, adjacent
awareness, occlusion, invalid targets, player/actor parity, and inverse
visibility; adapter tests for facing capture; ABI size assertions; measured
bounded work.

**Exit gate:** One current-Vision condition and one custom-Vision condition
produce the same result in host preview, packaged evaluator, and live adapter.

### PB3 — Fill the behavior primitive gaps

**Outcome:** The new blocks can be composed without adding one-off controller
states.

**Steps:**

1. Generalize actor-target movement so a captured actor uses the same planner
   path as the captured player where the action permits it.
2. Add retreat-from-captured-target planning that repeats at each intent until
   the timed profile ends and preserves the actor's locomotion.
3. Reuse `OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER` and the existing player-
   adjacent mask with only `BEHIND` enabled for Stalker.
   If that tile is unavailable, do not fall back to a direct chase.
4. Add `HOP_IN_PLACE` as a chain pause action. It must not advance logical tile
   position or consume a forward reservation.
5. Add safe relative Walk-time and Hop-time operators, or reuse existing
   bounded operators if they already cover both fields.
6. Add the walking-only Waddle presentation hook.
7. Extract Long Hop values from Hopping Scavenger.
8. Confirm that Notice Player can face and pause without selecting chase or
   flee movement.
9. Route Throw, Ram, Ambush, Perch, and Playful through captured targets and
   the ordinary condition boundary.

**Primary files:**

- portable planner modules where possible
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- behavior schema and portable reducer tests
- condition-controller and actor-motion tests

**Proof:** Host tests for target actor selection, no-collision stopping,
repeated retreat, behind-only destination choice, accepted-motion completion,
in-place Hop terminal state, Waddle scope, and bounded speed modifiers.

**Exit gate:** Each new primitive has a direct host proof and no profile in the
target manifest requires a private runtime state machine.

### PB4 — Add Fly In and shorten old offscreen Hop

**Outcome:** Flying actors descend onto the exact validated surface. Hop From
Off Screen becomes the separate short-Hop effect.

**Steps:**

1. Add a Fly In spawn locomotion/state. Reuse offscreen-origin selection,
   startup ownership, and terminal cleanup from Hop From Off Screen.
2. Validate and store the destination and its surface height before selecting
   the origin.
3. Place the origin offscreen at flying height.
4. Add a distinct shared motion kind for Fly In and use the current motion
   sampler with independent start and target heights, zero Hop arc, and a
   monotonic linear descent.
5. Permit travel over ground, water, walls, and lower surfaces. Validate only
   the landing destination for placement.
6. Enforce these terminal invariants:
   - destination surface height is the only landing-height source;
   - descent offset is relative to that height;
   - terminal offset is exactly zero;
   - actor and sprite final Y equal the validated landing surface height.
7. Extend the existing spawn-height observer and retained measurement to
   distinguish Fly In from Hop From Off Screen.
8. Add Fly In host/source checks and one registered uneven-height landing
   scenario.
9. Replace the Hop planner's hidden `distance == 16` spawn-entry test with an
   explicit spawn-entry flag. Prove that an ordinary eight-tile Hop does not
   receive spawn-entry clearance rules.
10. Only after that separation and Fly In both pass, change Hop From Off Screen
   distance from 16 to 8 and update its test.
11. Do not expose per-profile Fly In timing or presentation fields.

**Primary files:**

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- spawn constants and generated field schema
- `tools/overworld/test_spawn_hop_origin.py`
- spawn-height observer, measurement, and proof files
- one registered Fly In scenario and feature-map claim

**Proof:** Host lifecycle tests, valid/invalid landing tests, uneven-height live
proof, exact final-height receipt, eight-tile old-Hop check, and overlay-size
comparison.

**Exit gate:** A bird and a flying insect Fly In and land at exact height; a
Floaty Bounce actor still uses the now-eight-tile Hop From Off Screen path.

### PB5 — Move Picked Up out of behavior selection

**Outcome:** Held actors are controlled by actor ownership, not a fake profile
or magic class index.

**Steps:**

1. Add an internal held/control mode to the Wild actor record.
2. Move every Picked Up guard from profile/class checks to that control mode.
3. During pickup, set held mode before autonomous planning is stopped.
4. During throw/drop/cancel/despawn, clear held mode on every terminal path.
5. Keep a temporary compatibility mapping for old saves or in-flight runtime
   state if required by the current actor lifecycle.
6. Remove the resolver's hard-coded class index only after all call sites use
   held mode.
7. Delete Picked Up from runtime-owned class validation, generated class order,
   and the catalog.
8. Map Aggressive Chase, Aggressive Ram, and Test selectors to Default plus
   applications, then delete those root classes.

**Primary files:**

- Wild spawns and helper overlays
- `lib/overworld/overworld_behavior_resolver.c`
- generated behavior header/data
- catalog validation and class-binding tests

**Proof:** Pickup, held idle, throw, drop, cancel, rebind, and despawn tests;
resolver class-order tests; no remaining product reference to Picked Up or the
three deleted classes.

**Exit gate:** Held actors behave the same, and Default is the only selectable
root behavior class.

### PB6 — Finish the Workshop for the frozen V5 model

**Outcome:** A user can author the target model without knowing storage rules.

**Steps:**

1. Update Workshop load/save and server validation to V5.
2. Keep Conditions first and add the final main-tab order.
3. Remove all Chill labels and explanatory text.
4. Add Routine and Placement; remove Archetype.
5. Add minimal icons, subtle tints, and clear section headings for all seven
   classifications.
6. Auto-sort sections while preserving manual order inside a section.
7. Remove profile-level assignment controls from conditional profiles.
8. Add named-pool choose/create/edit controls and one-off pool controls.
9. Show condition-derived Pokémon at reduced opacity in the deck and overview.
10. Add current/custom Vision controls inside vision-based condition cards.
11. Add the main Vision tab for normal profile defaults and overrides.
12. Show and enforce System ownership for Follower, Mounted, and Asleep.
13. Keep every save round-trippable through the Python validator and generator.

**Primary files:**

- `tools/overworld-viewer-v2/static/profiles.js`
- `tools/overworld-viewer-v2/static/v2.css`
- `tools/overworld-viewer-v2/server.py`
- `scripts/overworld_behavior_profile_viewer.py`
- Workshop authoring and conditional-preview tests

**Proof:** DOM/unit tests for tab order, labels, grouping, stable order,
classification change, conditional membership, badges, named pools, Vision
mode, System locks, and save/reload round-trip.

**Exit gate:** The target manifest can be created, reordered, saved, reloaded,
and generated only through the Workshop without hidden manual repair.

### PB7 — Run the deterministic catalog migration

**Outcome:** The live catalog contains the agreed building blocks and no legacy
composites.

**Steps:**

1. Run the V4-to-V5 migration in dry-run mode and compare its report to the PB0
   target manifest.
2. Migrate one representative family first: Scavenger plus Long Hop. Resolve
   target and nearby non-target species before and after.
3. Run the migration on the full catalog.
4. Add the Baby Pokémon and Playful Pokémon pools.
5. Split Teleport/Stalker, birds/Fly In, plants, and all other entries exactly
   as listed in the migration table.
6. Put Notice Player first in Capability order.
7. Put the player condition last inside Playful.
8. Put Startled before Skittish.
9. Keep Follower, Mounted, and Asleep visible but System-owned.
10. Regenerate compatibility output once from the final source.
11. Run the migration again. It must make no change.
12. Review every changed membership, field operator, Tired link, condition,
    order position, and deleted ID against the manifest.

**Primary files:**

- `data/overworld_behavior_profiles.json`
- generated behavior data and header through the generator only
- V5 migration fixture and target manifest

**Proof:** Migration report, no-op second run, generator check, exact manifest
check, resolved before/after fixtures, and a non-target fixture for each family.

**Exit gate:** No old profile remains, no species is lost or added by accident,
the application count is within 32, and all target compositions resolve in the
required order.

### PB8 — Remove stale terms and fix agent routes

**Outcome:** Humans and agents see one current model.

**Steps:**

1. Update `CONTEXT.md` with Routine, Placement, current Vision, named pool,
   System badge, and composition-as-archetype.
2. Update `architecture.md` with the new ownership and data flow.
3. Update `authoring-debugging.md` to V5 and remove contradictory application-
   owned condition text.
4. Update the system README route to this plan and the final authoring model.
5. Update `tools/overworld/system_features.yaml` from dead V2 schema paths to
   V5 and register new proof owners.
6. Update `tools/overworld/runtime_proof_registry.json`, existing scenario
   contracts, and test recipes that hard-code Default Active, Ambush Plant
   Active, Runner, old condition IDs, a 16-tile offscreen Hop, or the old lack
   of Pokémon targets.
7. Rewrite `design-overworld-behavior`:
   - design one visible block at a time;
   - compose archetypes from blocks;
   - use the seven classifications and their order;
   - put assignment in normal applications and subjects in conditions;
   - use named pools only for real reuse;
   - use current Vision by default and custom Vision only when behavior needs
     it;
   - hand catalog edits to `author-overworld-profile`.
8. Update `author-overworld-profile` for V5, named pools, System ownership,
   condition-owned membership, the new order, and the current proof commands.
9. Update `author-overworld-scenario` for shared Vision, actor targets, Fly In,
   and current scenario IDs and proof owners.
10. Keep the completed conditional-profile plan as history. Add a short pointer
   to the new contract; do not rewrite its completion record.
11. Remove or rename remaining user-facing Chill, Active, attentive, old
   Archetype-classification, Default Active, Forced Asleep, and state-named
   profile wording.
12. If internal C field names still say Chill, either rename them mechanically
    with byte-equivalent generated output or record them as compatibility-only
    storage names. Do not let them remain current domain terms.

**Proof:** Link check, feature-map validation, skill path audit, repository term
search with an explicit historical/compatibility allowlist, and one dry-run
behavior-design handoff that reaches the correct V5 files.

**Exit gate:** Following either profile skill cannot lead an agent to V2, to an
Archetype classification, to normal membership on a conditional profile, or to
the old Chill/Active model.

### PB9 — Integrated verification

**Outcome:** One current ROM proves the composed system and its pacing.

**Host and package checks:**

```bash
python3 scripts/generate_overworld_behavior_schema.py --check
python3 scripts/verify_overworld_behavior_schema.py
python3 scripts/generate_overworld_behavior_catalog.py --check
python3 scripts/verify_overworld_workshop_authoring.py
python3 scripts/verify_overworld_behavior_resolver.py --rule-removal-control
python3 tools/overworld/test_behavior_conditions.py
python3 tools/overworld/test_behavior_condition_adapter.py
python3 tools/overworld/test_devtools_condition_controller.py
python3 tools/overworld/test_condition_packaging_abi.py
python3 scripts/verify_overworld_spawn_profile_lifecycle.py
python3 scripts/verify_overworld_motion_model.py
python3 tools/overworld/test_spawn_refill_budget.py
python3 tools/overworld/test_spawn_destination_scan.py
python3 scripts/generate_overworld_feature_table.py --check
python3 scripts/verify_overworld_proof_gate.py
scripts/owctl scenario validate
```

Run the focused Workshop, catalog, resolver-condition, Vision, behavior-
primitive, Fly In, pickup, and landing tests added by the earlier slices. Run
the broader affected host set once at this stable integration point.

Each runtime slice must inspect its link map at the first successful link. Do
not defer all overlay-size checks until final integration.

Then:

1. Build one current ROM through `hg-engine-delta-build`.
2. Record overlay and heap changes against PB0. Do not accept an unexplained
   overflow or a second per-actor scan buffer.
3. Run these existing registered proofs on that same ROM where applicable:
   - `profile.resolve.packaged-rom-parity`;
   - `profile.condition.packaged-rom-evaluator`;
   - `profile.condition.live-wild-controller`;
   - `profile.follower-mounted-owner-transfer`;
   - `observation.spawn-height-control`;
   - `spawn.appear-hop-timing`;
   - affected Hop, chain, and landing scenarios.
4. Add and run permanent registered scenarios for facts not covered by those
   tests:
   - Notice Player presents once, pauses, and returns to its Routine;
   - Stalker stops advancing when seen and resumes its Routine;
   - Playful chooses one actor or the player and does not collide;
   - Startled retreats for the timed window;
   - Fly In lands at exact uneven surface height;
   - Waddle changes only walking presentation;
   - Picked Up uses internal control state and resumes correctly.
5. Because profile, generated data, spawn, and landing changed, run
   `population.spawn-work-budget` on the current ROM after both extracted-C
   checks.
6. On the same `test.nds` and unchanged Continue save, run
   `world.unmounted.spawn-zero-stutter`. Zero late loops is required.
7. Retain the terminal manifests and record the exact ROM/save identity.

**Exit gate:** Every required manifest has both `passed: true` and
`acceptedProof: true`; the generated catalog is current; overlay/heap budgets
are accepted; no reported player-visible hitch remains on that ROM.

### PB10 — User playtest and closure

**Outcome:** The design is useful, not only mechanically correct.

Give the user one ROM and a short playtest list:

- a standard Pokémon notices the player, pauses, and returns to its Routine;
- a Stalker approaches only while outside player Vision;
- a Playful Pokémon plays with the player and a compatible Pokémon;
- a Baby Pokémon remains Skittish;
- a plant shows the correct Waddle, Hop Around, or Ambush composition;
- a bird and flying insect Fly In and land at the correct height;
- Floaty Bounce keeps the short offscreen Hop;
- Follower, Sing/Asleep, pickup, throw, Ram, Rest, and Tired still work.

Fix any observed mismatch in its owning slice, repeat the smallest host proof,
then rebuild and repeat the affected registered scenario. Re-run spawn-work
pacing for any profile, generated-data, spawn, destination, or landing change.

**Exit gate:** The user accepts the catalog organization and the named behavior
examples on the same verified ROM.

## Agent ownership

Use one integration owner. Generated files and the final catalog are
single-writer files.

| Agent | Owns | Starts after | Must not edit |
| --- | --- | --- | --- |
| Integration owner | target manifest, final application order, generated output, integration, final proof | PB0 | none |
| Schema/generator agent | V5 schema, validator, pool expansion, migration command, schema tests | PB0 | final catalog membership |
| Vision agent | portable Vision, condition world-view changes, Vision tests | PB1 contract | Workshop and catalog |
| Behavior agent | target planning, retreat, behind, in-place Hop, Waddle, speed bounds | PB2 API | Fly In while spawn agent is active |
| Spawn agent | Fly In, landing-height proof, eight-tile old Hop | PB1 contract | behavior edits in the same overlay until handed off |
| Control-state agent | Picked Up internal mode and class removal | PB1 contract | catalog migration |
| Workshop agent | V5 UI, tabs, cards, groups, badges, pool and Vision controls | V5 and field enums frozen | Python runtime projection rules |
| Catalog agent | V5 source migration against the target manifest | PB2–PB6 complete | generated output by hand |
| Docs/skills agent | canonical docs, feature routes, profile design/authoring/scenario skills | interfaces stable | product behavior |
| Independent reviewer | contract, order, membership, ABI, pacing, and proof audit | before PB7 and before closure | shared files |

PB3 and PB4 must use separate commits and run in sequence because they share a
large Wild overlay. Freeze generated inputs before final ROM proof. Do not let
an agent regenerate over an unreviewed catalog change.

## Review checklist for every slice

- Does this change one owner, or create a second source of truth?
- Does it preserve the root profile and normal composition order?
- Can it exceed 32 applications or ten observed actors?
- Can a condition change the Vision used to trigger itself?
- Can an accepted motion be interrupted?
- Is one captured target used consistently from trigger to planner?
- Did any species membership change outside the target manifest?
- Did a direct JSON edit bypass Workshop validation or generator checks?
- Did profile, spawn, destination, generated data, or landing work stale the
  D1 pacing proof?
- Is the proof stored in a test, fixture, registered scenario manifest, or
  canonical system document where the next agent can find it?
