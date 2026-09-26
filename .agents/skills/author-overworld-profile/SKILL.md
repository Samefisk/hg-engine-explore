---
name: author-overworld-profile
description: Create, edit, reorder, or remove hg-engine overworld profiles, selectors, and applications, then prove their resolved behavior.
---

# Author an overworld profile

Use the named behavior catalog as the only authoring source. Every non-root
profile has a stable ID, display name, parent, classification, and local field
operators. The one root profile is complete and has no classification.

## Model the result

Read **Profile**, **Root profile**, **Profile selector**, **Profile
application**, **Layer**, **Lane**, and **Resolved behavior** in
[CONTEXT.md](../../../CONTEXT.md). Read
[one source model](../../../documentation/overworld-system/authoring-debugging.md#one-source-model)
before editing. Read the field entry in
[`behavior_schema.json`](../../../tools/overworld/behavior_schema.json) when its
meaning, unit, bounds, lane, or operators matter.

Identify:

- the subjects and resolver context that must match;
- the selected profile and every matching, forced, linked, or conditional
  application;
- the smallest profile, selector, application, or operator change that gives
  the requested result;
- one nearby subject that must not change.

Selectors choose the initial materialized profile. Applications contribute
only their profile's local operators. Later matching applications consume the
earlier result. A parent supplies inherited authoring values; it does not turn
one profile into a second profile type. Classifications set composition order:
Routine, Placement, Capability, Attitude, Modifier, System, then Utility.

A profile can be normal or conditional. Conditional is independent of its
classification. A conditional profile owns one or more independent condition
entries. Each entry owns its subject pool and can use Current Vision or its own
Custom Vision. If several entries in one profile are admitted, the last listed
entry wins. Different conditional applications still compose in application
order, field by field. Conditions choose when a profile applies; they do not
create another behavior lane.

A normal application owns its Pokémon target. A conditional application omits
that target: all conditional membership lives in each condition's subject
pool. A profile can set stable Current Vision; conditional applications are
excluded when that value is resolved, so they cannot change the Vision that
admits them.

## Make the edit

The canonical file is
[`data/overworld_behavior_profiles.json`](../../../data/overworld_behavior_profiles.json).
Do not hand-edit generated profile arrays, indexes, counts, or
`data/OverworldWildBehaviorData.c`.

Prefer the Workshop for structural changes. Start it from the repository root:

```bash
OPEN_PAGE=0 scripts/keyboard-maestro-start-overworld-viewer.sh
```

Open <http://127.0.0.1:8766/>, use Profiles, and save. For a small direct JSON
edit, regenerate the compatibility output:

```bash
python3 scripts/generate_overworld_behavior_catalog.py
```

Preserve these rules:

- Keep the root complete, parentless, and undeletable.
- Keep profile and application IDs stable. Names are display text.
- Keep parent links acyclic and all references valid.
- Keep only local field operators in a non-root profile.
- Use `replace` for exact values. Use relative or bounded operators only when
  composition is intended.
- Put normal matches and members in selectors or normal applications. Put
  conditional membership only in each condition's subject pool.
- Keep applications in classification order: Routine, Placement, Capability,
  Attitude, Modifier, System, then Utility. Preserve manual order inside each
  classification. The resolver uses application order, not profile definition
  order. At most 32 applications can reach the current runtime mask.
- Keep runtime-owned Follower, Mounted, Asleep, and Default Tired bindings
  valid. Mounted is an empty override and inherits all fields from the selected
  Pokémon profiles. Pickup, carry, throw, drop, cancel, and release use internal
  held actor control; do not create or restore a Picked Up profile.
- Give each conditional profile at least one valid condition. Keep its target,
  activation mode, duration, cooldown, and subject pool explicit. Timed
  conditions restart duration only when they retrigger after cooldown.
- For a vision condition, choose Current Vision or define Custom Vision on the
  condition. Keep stable Current Vision fields on the profile.
- Use the Conditions, Spawn, Behavior, Movement Style, Vision, and Tired main
  tabs. Behavior and Movement Style are separate main tabs. Do not model
  controller states as authoring tabs or profile concepts. Do not create Chill,
  Active, or Attentive profile concepts.
- Use Fly In for descending spawn entry. It descends from offscreen flying
  height to the prevalidated destination surface, then returns control to the
  normal Routine.
- For Walk, keep `walkPause` and `walkPauseVariance` at zero. Do not use a
  one-move Movement Chain: use zero to disable the chain, or at least two
  moves. A deliberate slow-pause exception must belong to a clearly named
  Routine, use a visibly intentional pause, and receive a playtest.
- Treat Movement Chain pause actions as a set. In the Workshop, use the action
  checkboxes. No checked action continues into the next chain. One checked
  action keeps the existing single-action behavior. With several checked
  actions, `chainPauseActionChance` is one admission roll for the whole set;
  after a pass, the runtime picks one checked action with equal probability.
  Do not give every checked action the full overall chance.
- A lone `Pause` uses `chainPauseActionChance` like every other action, including
  while Mounted. In a multi-action set, `Pause` shares the set's chance. A zero
  chance retains the legacy always-admit meaning. For example,
  Meander checks `Look Around` and `Pause` at 50% overall: each runs about 25%
  of chain endings and the other 50% starts the next chain. Keep `walkPause`
  and `walkPauseVariance` at zero; do not restore a per-step Walk pause to
  create this rhythm.

The generator lowers this one authoring model into the existing ROM tables.
Those tables are compatibility data, not authoring profile types.

## Prove the result

Inspect the catalog and generated-output diff. Reject unrelated ID, parent,
selector, application-order, membership, field, or reference changes. Run:

```bash
python3 scripts/generate_overworld_behavior_catalog.py --check
python3 scripts/verify_overworld_workshop_authoring.py
python3 scripts/verify_overworld_behavior_resolver.py --rule-removal-control
```

When the pause-action set or its overall chance changes, also run:

```bash
python3 tools/overworld/test_passive_chain_pause.py
python3 tools/overworld/test_workshop_profile_building_blocks.py
```

Resolve each affected subject again. Confirm selection, application order,
condition winners and target source, changed fields, Tired links,
normalization, primitives, and fingerprint.
Confirm the chosen non-target subject is unchanged.

Behavior-profile changes stale spawn-work pacing proof. Run the extracted-C
budget checks before live proof:

```bash
python3 tools/overworld/test_spawn_refill_budget.py
python3 tools/overworld/test_spawn_destination_scan.py
```

Use [verify-overworld](../verify-overworld/SKILL.md) for the current-ROM
`population.spawn-work-budget` and `world.unmounted.spawn-zero-stutter` gates,
and for affected registered scenarios. Use
[author-overworld-scenario](../author-overworld-scenario/SKILL.md) if required
runtime behavior has no permanent test.

## Report

Name the changed profiles, parents, selectors, applications, operators, and
affected lanes. State the checks that ran and the exact remaining live-proof
gap, if any.
