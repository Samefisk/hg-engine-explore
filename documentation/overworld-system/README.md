# Overworld Pokémon System

This directory is the canonical entry point for wild Pokémon, followers, mounts, behavior profiles, Walk, Hop, Teleport, terrain, streaming, and their verification.

The current branch implements the listed paths, but its ownership and proof are
split across memory-placement overlays and focused runtime checks. The target
design treats those overlays as deployment details behind one deep actor system.

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

## Accepted target contracts

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

This map was audited at `34d7b9b83` on branch `feature/pokemon-mount`.

| Responsibility | Current source | Target owner |
| --- | --- | --- |
| Authored profiles and surfaces | `data/OverworldWildBehaviorData.c` | Behavior Schema |
| Behavior-data services, surface lookup, trajectory math, and cache dispatch | `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c` | Resolver and world adapters |
| Profile editor and compatibility parser | `scripts/overworld_behavior_profile_viewer.py` | Workshop adapter |
| V2 editor and resolver preview | `tools/overworld-viewer-v2/` | Workshop adapter using the canonical resolver |
| Profile composition and wild orchestration | `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` | Resolver, controllers, and actor facade |
| Walk momentum, profile transforms, surface queries | `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c` | Motion Module and Resolver |
| Timing and direction policy | `src/pokemon_move_history_overlay/overworld_walk_module.c` | Motion Module |
| Hop trajectory and vector helpers | `src/pokemon_move_history_task6_overlay/` | Motion planner helpers |
| Hop candidate planning and execution | spawns, helper, behavior-data, and mount overlays | Motion Module |
| Mount input, motion, streaming, and presentation | `src/overworld_mount_overlay/overworld_mount_overlay.c` | Mounted role and presentation adapters |
| Spawn, capture, battle, and reconciliation helpers | `src/overworld_wild_helper_overlay/` | Population and reaction modules |
| Resident lifecycle bridge | `src/overworld_wild_spawns.c`, `src/field/map_teleport.c` | Engine adapter |
| Package and source checks | `scripts/verify_overworld_*.py` | Affected verification router |
| Live checks | `scripts/headless-overworld-test.py` and focused harnesses | ROM scenario adapter |

Physical overlays can remain separate because Nintendo DS memory limits are real. They must stop being the conceptual module boundaries.

## Current capability status

The branch contains profile resolution, follower selection, mount lifecycle, exact-frame Walk, acceleration, skids, stomp and crash feedback, cardinal and diagonal movement, custom Hop, Teleport, mounted presentation, and map-transition handling. This is a capability inventory, not a claim that every runtime path is free of regressions.

The weak area is proof and diagnosis. Static verifiers protect ABI and package shape, but many live behaviors still depend on private memory offsets and one-off scenarios. The first roadmap phase adds semantic observation before further structural change.

## Change protocol

For every overworld-system change:

1. Name the affected contract and actor roles.
2. Find its owner in the source map and feature map in [`verification.md`](verification.md).
3. Add or update a scenario before changing ownership.
4. Before semantic tracing exists, use focused current instrumentation and ROM
   scenarios. After Phase 1, preserve old and new semantic traces during migration.
5. Remove the old path when the new interface-level scenario passes. Do not keep permanent dual ownership.
6. Update the canonical document if an invariant, owner, interface, or failure reason changed.

Every fixed runtime bug must leave behind a scenario or invariant check. This is how the system becomes easier for the next agent instead of accumulating private knowledge.
