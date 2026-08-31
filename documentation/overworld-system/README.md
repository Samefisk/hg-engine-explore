# Overworld Pokémon System

This directory is the canonical entry point for wild Pokémon, followers, mounts, behavior profiles, Walk, Hop, Teleport, terrain, streaming, and their verification.

The current roadmap branch adds a resident `OverworldActorSystem` facade,
portable behavior and motion modules, semantic observation, and one host
control command. Existing memory-placement overlays remain compatibility
adapters while live behavior moves behind that seam.

## Read order

Read only what the task needs:

1. Read [`CONTEXT.md`](../../CONTEXT.md) for shared terms.
2. Read [`architecture.md`](architecture.md) before changing runtime ownership, profiles, movement, mounts, terrain, or transitions.
3. Read [`authoring-debugging.md`](authoring-debugging.md) for the Workshop, profile resolution, traces, and the intended agent control path.
4. Read [`verification.md`](verification.md) before claiming behavior is correct.
5. Read [`roadmap.md`](roadmap.md) before refactoring or adding a new system seam.

[`overworld_walk_frame_timing_spec.md`](../overworld_walk_frame_timing_spec.md) remains the active subordinate contract for exact Walk timing.

The documents named `*_attempts.md`, the old movement index, and the old movement architecture are historical evidence. Use them only to avoid repeating failed experiments. They do not define current behavior.

## System in one view

```text
Named profile source
        |
        v
Behavior schema -> Resolver -> Resolved behavior + provenance
                                  |
Wild AI / Follower AI / Rider input / Script
                  |               |
                  +---- Intent ---+
                           |
                           v
                  Planner -> Motion plan
                           |
                           v
                   Shared executor
                           |
             +-------------+-------------+
             |             |             |
       Advance/commit  Presentation   Semantic trace
             |             |             |
        Engine adapter  Actor adapter  Host decoder
```

## Current invariants to preserve

- Current mount begin resolves the current follower through the normal profile
  resolver with the forced `Follower Pokemon` override layer, then snapshots
  the resolved Owner lane. There is no separate mount-profile system.
- Current mounted movement uses the player `MapObject` as engine anchor and
  synchronizes the Pokémon presentation to it. The rider graphics are on the
  player anchor; they are not a second actor.
- Chain counting, acceleration, and feedback count eligible movement decisions,
  not skid tiles, reposition moves, or interpolation frames.
- Multi-tile mounted motion must update logical location and terrain streaming
  across the traversed path. Warps cannot fire mid-motion.
- Exact Walk travel time follows the active subordinate timing contract.

## System contracts

- One actor has at most one motion owner.
- A mounted player and Pokémon execute one motion. Actor state is authority;
  the player is the engine anchor and the Pokémon is a dependent presentation.
- Motion follows `Intent -> Policy -> Plan/Validate -> Reserve -> Begin -> Tick
  -> Path Advance -> Commit Pending -> Commit or Cancel`.
- One accepted movement produces zero or more path advances and at most one
  terminal commit. Multi-tile motion updates authoritative logical location as
  it crosses tiles, but it remains one movement decision.
- Skids, reposition moves, interpolation frames, and terrain-stream anchor changes are not extra movement decisions.
- Walk, Hop, and Teleport share lifecycle, streaming, presentation, cancellation, and commit rules.
- Terrain streaming and movement-distance consumers use path advances. Warps,
  chain counts, acceleration, and landing effects use the eligible terminal
  commit, not interpolation frames.
- A diagonal Walk needs a legal destination and two clear cardinal side tiles. A Hop can cross blocked tiles but must have a legal landing.
- A field transition must rebind a complete motion or cancel it completely. It must not leave partial control ownership.
- No per-frame heap allocation is permitted.
- Runtime failures return stable reasons. An unexplained `FALSE` is not a sufficient system result.

## Current source map

This map describes `feature/overworld-actor-system-roadmap`.

| Responsibility | Current source | System owner |
| --- | --- | --- |
| Public actor lifecycle, handles, commands, snapshots, and trace | `include/overworld_actor_system.h`, `src/overworld_actor_system_overlay/` | Actor facade and Observation |
| Profile field schema and generated metadata | `tools/overworld/behavior_schema.json`, `include/generated/`, `tools/overworld/generated/` | Behavior Schema |
| Named authored profile values and rules | `data/overworld_behavior_profiles.json` | Behavior Schema |
| Generated compact profile blob and surfaces | `data/OverworldWildBehaviorData.c` | Behavior Schema compatibility data |
| Profile composition | `lib/overworld/overworld_behavior_resolver.c` | Behavior Resolver |
| Shared motion state and sampling | `lib/overworld/overworld_motion_model.c` | Motion Module |
| Look, wander, and chain-pause policy primitives plus actor policy state | `src/overworld_actor_system_overlay/` | Movement Policy |
| Workshop profile display and native resolution adapter | `scripts/overworld_behavior_profile_viewer.py`, `tools/overworld-viewer-v2/` | Workshop adapter |
| Wild compatibility orchestration | `src/overworld_wild_spawns_overlay/` | Wild role and engine adapters |
| Surface queries and feedback compatibility | `src/overworld_wild_runtime_overlay/` | World and effect adapters |
| Exact Walk timing and direction helpers | `src/pokemon_move_history_overlay/overworld_walk_module.c` | Motion helpers |
| Hop trajectory and vector helpers | `src/pokemon_move_history_task6_overlay/` | Motion helpers |
| Rider input, streaming, and dependent presentation | `src/overworld_mount_overlay/` | Mounted role and presentation adapters |
| Population scheduling | actor population entry plus wild spawn and helper overlays | Population module and engine adapter |
| Host control, feature map, trace decode, and scenarios | `scripts/owctl`, `tools/overworld/`, `tests/overworld/` | Host adapter |

Physical overlays can remain separate because Nintendo DS memory limits are real. They must stop being the conceptual module boundaries.

## Current capability status

The branch contains the resident facade, generated debug descriptor, portable
resolver, portable motion state machine, native Workshop resolver adapter,
movement-policy entry, population entry, feature manifest, trace decoder, and
declarative scenario catalog. `OverworldActorSystem_Tick` is the only motion
clock. Walk, Hop, and Teleport compatibility adapters read that actor-owned
timeline and apply its samples to engine objects.

Package and compile proof exists. Seven scenario adapters are active and the
remaining baseline scenarios are marked `planned`. Do not claim a runtime exit
gate until its named ROM or visual scenario has run.

## Change protocol

For every overworld-system change:

1. Name the affected contract and actor roles.
2. Find its owner in the source map and feature map in [`verification.md`](verification.md).
3. Add or update a scenario before changing ownership.
4. Use `Inspect` and semantic traces first. Preserve old and new semantic
   outcomes while a compatibility path is being removed.
5. Remove the old path when the new interface-level scenario passes. Do not keep permanent dual ownership.
6. Update the canonical document if an invariant, owner, interface, or failure reason changed.

Every fixed runtime bug must leave behind a scenario or invariant check. This is how the system becomes easier for the next agent instead of accumulating private knowledge.
