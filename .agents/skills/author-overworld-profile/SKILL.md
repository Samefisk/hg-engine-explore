---
name: author-overworld-profile
description: Create, edit, reorder, or remove hg-engine overworld profiles, selectors, and applications, then prove their resolved behavior.
---

# Author an overworld profile

Use the named behavior catalog as the only authoring source. Every profile has
the same shape: a stable ID, display name, parent, and local field operators.
The one root profile is complete.

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
one profile into a second profile type.

A profile can be normal or conditional. A conditional profile owns one or
more independent condition entries. Each entry can use a different subject
pool. If several entries in one profile are active, the last listed entry wins.
Different conditional applications still compose in application order, field
by field. Conditions choose when a profile applies; they do not create another
behavior lane.

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
- Put matches and members in selectors or applications, not profile records.
- Keep applications in layer order: archetype, capabilities, attitude, style
  traits, Follower/Mount, then modifiers. Archetypes are first and modifiers
  are last. The resolver uses application order, not profile definition order.
  Keep a conditional helper beside the layer that owns it. At
  most 32 applications can reach the current runtime mask.
- Keep runtime-owned Picked Up, Follower, and Default Tired bindings valid.
- Give each conditional profile at least one valid condition. Keep its target,
  activation mode, duration, cooldown, and subject pool explicit. Timed
  conditions restart duration only when they retrigger after cooldown.

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
