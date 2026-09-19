# Overworld Pokémon System

This directory is the canonical entry point for wild Pokémon, followers, mounts, behavior profiles, Walk, Hop, Teleport, terrain, streaming, and their verification.

The current roadmap branch adds a resident `OverworldActorSystem` facade,
portable behavior and motion modules, semantic observation, and one host
control command. Existing memory-placement overlays remain compatibility
adapters while live behavior moves behind that seam.

## Read order

Use only the row that fits the task. Read linked sections rather than whole
guides when a section answers the question; reuse material already loaded.

| Task | Entry point |
| --- | --- |
| Understand shared terms or find a code owner | [CONTEXT.md](../../CONTEXT.md), [system contracts](#system-contracts), and [source map](#current-source-map) |
| Change runtime ownership, profiles, motion, mounts, terrain or transitions | Matching contract in [architecture.md](architecture.md) |
| Create or edit a profile or its use | [author-overworld-profile](../../.agents/skills/author-overworld-profile/SKILL.md) |
| Understand profile sources or diagnose resolution | [authoring-debugging.md](authoring-debugging.md) |
| Implement the conditional-profile ownership shift | [conditional-profiles implementation plan](conditional-profiles-implementation-plan.md) |
| Diagnose live behavior or prepare a reproduction | [overworld-devtools](../../.agents/skills/overworld-devtools/SKILL.md) |
| Run an existing test or accept a runtime fix | [verify-overworld](../../.agents/skills/verify-overworld/SKILL.md) |
| Create or repair a permanent test | [author-overworld-scenario](../../.agents/skills/author-overworld-scenario/SKILL.md) |
| Refactor or add a system seam | [roadmap.md](roadmap.md#finite-delivery-slices) |
| Resume roadmap work | [current work table](roadmap-progress.md#current-work-table) and [handoff rules](verification.md#progress-and-handoffs) |

The four skills are task routes, not a required sequence. Existing tests do
not require test-authoring instructions. [verification.md](verification.md)
owns proof policy; [devtools.md](devtools.md) owns live control;
[devtools-tests.md](devtools-tests.md) owns checked-job operation and recipes.
Each skill links the sections needed for its actions.

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
- One typed Walk reducer owns input transitions, acceleration, turn and stop
  skids, stomp and crash intent, and chain eligibility for wild and mounted
  actors. Adapters only validate or start engine steps and publish effects.
- The reducer transaction is `INPUT -> START_RESULT -> COMMIT`. A rejected
  start does not change committed direction. `COMMIT` runs once at the actor
  terminal boundary. Mounted calls never enable chain handling.
- Walk time variance adds 0 through the configured frame limit once per
  accepted normal tile. It does not change nominal momentum, feedback checks,
  chain state, or other movement types. Mounted rider and Pokemon share the
  same selected duration.
- A direction forbidden by the resolved lane is a rejected candidate, not a
  stop command. It must leave momentum and chain progress unchanged. A genuine
  `NONE` input retains its separate stop/skid rules.
- Turn-skid path planning is an independent movement option. When enabled, an
  ordinary Walk, including the first recovery step after a turn skid, first
  keeps enough straight runway for the fastest possible skid. A normal turn is
  then accepted only when every skid tile and the first tile after the turn are
  open. A rejected planned step is another direction candidate; it does not
  crash, stop, or change momentum. Chain movement options are unchanged.
- Unlocked mounted diagonal side and destination failures submit a rejected
  candidate through Actor Motion before Walk policy input. Locked Ram input
  first retains the role-selected direction and its normal crash policy.
  Rejected raw directions do not synthesize
  `NONE`. The private rejection helper shares overlay153's audited code reserve;
  explicit linker bounds separate it from Field terrain code. This physical
  placement does not give terrain code ownership of movement decisions.
- Staged presentation cleanup cannot erase the active motion kind before that
  terminal boundary. Each tile in a staged Walk closes before the next tile
  starts, every later tile remains Walk, and the adapter preserves the actor's
  full settle pause. A chain action waits and retries until the previous shared
  motion has returned control.
- Chain counting, acceleration, and feedback count eligible movement decisions,
  not skid tiles, reposition moves, or interpolation frames.
- The default acceleration step removes one travel frame per acceleration
  event. The legacy `/2` rule remains an explicit profile option.
- A nonzero Movement Chain move count enables the chain. `NONE` ends the chain
  with no pause or presentation action. `PAUSE` waits for the configured
  passive pause without an action. Stop skid is a separate Walk-momentum option.
  A Runner uses it when the normal Wild planner cannot accept another movement
  direction, or when its normal TIRED lifecycle stops the current run. It is
  not caused by any Movement Chain movement, pause, or action. `HOP_FORWARD` jumps two tiles
  in the committed direction,
  uses the current Walk travel time per tile, preserves momentum, and starts
  the next chain without an idle pause. Pause-action chance applies only to visual
  actions.
- Multi-tile mounted motion must update logical location and terrain streaming
  across the traversed path. Warps cannot fire mid-motion.
- Hop landing validation must first prove that the target belongs to a real
  map-matrix cell, then read it from the current loaded terrain store. Matrix
  padding uses `MAP_EVERYWHERE` with a placeholder land model; it is not a
  playable destination even when it returns an ordinary terrain byte. The
  stock unavailable value `0xFF` also rejects the target. Only the candidate
  landing is tested: padding beside a valid Canopy, Rooftop, or Signpost does
  not reject that valid landing. Mounted and non-mounted Hop use this same
  gate, and a rejected candidate does not stop later candidates in the same
  heading.
- The actor owner holds one surface-aware target reservation from accepted
  motion through terminal commit or cancel. Occupancy conflicts only when the
  target tile and physical surface identity both match.
- Every accepted motion gets a fresh non-zero reservation identity after the
  target-conflict check. The request service clears the caller output first and
  never trusts a reservation value supplied by a candidate or caller.
- A normal or Teleport motion request rejects an active field transition or a
  stale field epoch before it records intent, writes an intent trace, plans, or
  begins motion. Every later engine-boundary receipt must carry the same live
  reservation identity. A zero, delayed, or recycled-slot receipt fails as
  `CONTEXT_LOST`; Wild and Mount adapters cannot silently bind it to new work.
- Native player-coordinate changes publish typed player-centered path advances
  even when no mounted adapter is active. Population does not count stock
  player steps, render frames, or adapter callbacks.
- Warp and battle readiness use the public actor world-gate inspection. An
  active transition, input-owned non-terminal motion, or live reservation
  closes both gates.
- The resident actor compatibility entry owns the current field context. ABI
  v3 returns one value with field epoch in the low half and map generation in
  the high half. If a required transition adapter is unavailable, field work
  retries without advancing its map marker or discarding retained actors.
- A retained Wild map-object pointer is never proof after field rebind. A Wild
  slot must first be present in `retainedActorMask`; the adapter then resolves
  the stable object ID in the current manager and validates actor, encounter,
  and subject identity before it stores or dereferences the pointer. Any
  failure makes the transition owner downgrade preserve work to discard.
- Wild Teleport keeps its logical object on the origin tile until terminal
  landing. The actor reservation protects the destination while presentation
  can use the planned target.
- The native-shadow position hook never reads Wild private state. It requests
  one versioned, sized value from the exact loaded Wild callback. The stock
  shadow task keeps its encounter generation beside its hidden flag. Wild
  accepts the request only when the object, manager, map generation, and
  encounter generation still identify the same actor. A rejected request
  keeps the stock position.
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
- Only the transition owner can rebind motion. Role and engine adapters must
  present the identity returned by the accepted request on every boundary call.
- Queued actor commands revalidate their expected field epoch when executed.
  Queued Wild battles revalidate map and encounter generations before start.
- No per-frame heap allocation is permitted.
- Runtime failures return stable reasons. An unexplained `FALSE` is not a sufficient system result.

## Current source map

This map describes `feature/overworld-actor-system-roadmap`.

| Responsibility | Current source | System owner |
| --- | --- | --- |
| Public actor lifecycle, handles, commands, snapshots, and trace | `include/overworld_actor_system.h`, `src/overworld_actor_system_overlay/` | Actor facade and Observation |
| Profile field schema and generated profile metadata | `tools/overworld/behavior_schema.json`, `include/generated/`, `tools/overworld/generated/` | Behavior Schema |
| Generated spawn identity, type, render, catch, and behavior-group metadata | `scripts/build_overworld_wild_spawn_metadata.py`, `include/overworld_wild_behavior_data.h`, `src/overworld_wild_behavior_data_overlay/` | Wild role adapter |
| Named authored profile values and rules | `data/overworld_behavior_profiles.json` | Behavior Schema |
| Generated compact profile blob and surfaces | `data/OverworldWildBehaviorData.c` | Behavior Schema compatibility data |
| Profile composition | `lib/overworld/overworld_behavior_resolver.c` | Behavior Resolver |
| Shared motion state and sampling | `lib/overworld/overworld_motion_model.c` | Motion Module |
| Look and wander policy entry plus actor policy state | `src/overworld_actor_system_overlay/` | Movement Policy |
| Workshop profile display and native resolution adapter | `scripts/overworld_behavior_profile_viewer.py`, `tools/overworld-viewer-v2/` | Workshop adapter |
| Wild compatibility orchestration | `src/overworld_wild_spawns_overlay/` | Wild role and engine adapters |
| Typed Walk reduction, surface queries, and feedback compatibility | `src/overworld_wild_runtime_overlay/` | Movement Policy plus world/effect adapters |
| Exact Walk timing and direction helpers | `src/pokemon_move_history_overlay/overworld_walk_module.c` | Motion helpers |
| Hop vector, range, duration, arc, and clearance planning | Actor Motion `PLAN_HOP` request; private code host in `src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c` | Motion Module |
| Hop landing, helper configuration, and chain-reposition execution | `src/overworld_wild_spawns_overlay/` | Wild world and engine adapters |
| Rider input, streaming, and dependent presentation | `src/overworld_mount_overlay/` | Mounted role and presentation adapters |
| Player path, commit, field-event, timer, and bounded population scheduling | `lib/overworld/overworld_population_model.c`, actor population entry, public `Inspect(POPULATION)` | Population module |
| Population despawn, spawn, and reveal work | wild spawn and helper overlays | Wild engine adapter |
| Warp and battle readiness | public `Inspect(WORLD_GATE)` with Warp and Battle query kinds | Actor facade |
| Transition order and retained actor generations | actor transition model and resident field driver | Actor lifecycle owner |
| Retained Wild map-object rebind | stable object-ID lookup and validation in `src/overworld_wild_spawns_overlay/` | Wild engine adapter |
| Host control, feature map, trace decode, and scenarios | `scripts/owctl`, `tools/overworld/`, `tests/overworld/` | Host adapter |

Physical overlays can remain separate because Nintendo DS memory limits are real. They must stop being the conceptual module boundaries.

## Capability status

The source map describes the implementation surface, not its proof status.
Use the [current work table](roadmap-progress.md#current-work-table) to resume
work and the feature manifest to select exact proof. Do not copy changing pass
counts or intermediate link results into this entry point. A source cutover is
not complete gameplay proof until its named accepted scenario has current
evidence.

## Change protocol

For runtime product changes:

1. Name the affected contract and actor roles. Find the owner in the source map
   and exact proof requirement in `tools/overworld/system_features.yaml`.
2. Follow [reproduction and acceptance](verification.md#reproduction-before-editing-acceptance-before-closure).
   A bug needs a measured pre-edit symptom; an ownership refactor needs a
   passing baseline and semantic parity. Use the live-tool skill only when
   observation is needed and the authoring skill only when coverage is missing.
3. Use `Inspect` and semantic traces to preserve old and new outcomes while a
   compatibility path is removed. Apply [scenario subject rules](verification.md#scenario-contract)
   for exact live actor proof.
4. Remove the old path when the new interface-level scenario passes. Keep one
   logical motion owner; do not retain permanent dual ownership.
5. Use the verification skill to accept the final result. Update the canonical
   document if an invariant, owner, interface or failure reason changed.

For instructions-only changes, check affected links and task paths. These
changes do not require a game run or supply gameplay proof.

For roadmap work, follow the [finite slices and work loop](roadmap.md#finite-delivery-slices).
The coordinator owns the current ledger. Each helper has one bounded question
and explicit file ownership. Keep normal-play, controlled fault, and observer
checks separate; see [test design](verification.md#design-the-test-before-the-run).

Every fixed runtime bug must leave behind a scenario or invariant check. This is how the system becomes easier for the next agent instead of accumulating private knowledge.
