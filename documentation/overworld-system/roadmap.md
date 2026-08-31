# Overworld Actor System Roadmap

## Objective

Make the overworld Pokémon system easy to extend and cheap to diagnose without changing current game feel during migration.

The migration wraps, observes, compares, switches, and deletes. It is not a full rewrite.

## Delivery state

This branch implements the shared code home, portable resolver and motion
models, resident actor facade, host control surface, and compatibility sampling
for current movement paths. The actor is now the sole motion clock and owns the
shared motion and policy state. Engine-boundary ownership, role-policy reducers,
transition coordination, legacy deletion, and live exit proof remain open where
named below. A roadmap exit gate is complete only after its required runtime
proof passes.

## Phase 0 - Canonical system map

Status: complete.

- Define one vocabulary.
- Define one architecture, frame order, ownership model, and invariant set.
- Define one proof ladder and feature map.
- Route agents and historical documents to the canonical entry point.

Exit gate: a new agent can find the current owner, target owner, required roles, and proof level without reading attempt logs.

## Phase 1 - Observe current behavior

Status: implemented; live diagnostic exit proof is pending. The public live
driver can now arm, close, and capture one descriptor-driven bounded window.

- Add a read-only, versioned compatibility snapshot with stable semantic fields.
  Its private storage adapter can change in later phases.
- Add the minimum generation-safe actor handle and field epoch required by
  that snapshot. These identifiers remain stable through later storage changes.
- Add a filtered fixed-size semantic trace ring.
- Generate `build/overworld-system.debug.json` with ABI versions, enum IDs, symbols, and snapshot offsets.
- Create the first declarative scenarios from explicit intended contracts.
  Known bugs start as failing scenarios and never become accepted baselines.
- Create the machine-readable feature/impact manifest at
  `tools/overworld/system_features.yaml` and generate the human table from it.
- Add `scripts/owctl trace`, `scenario`, `doctor`, and `verify affected` as one host facade.
- Add descriptor-driven `scripts/owctl actor inspect`, `actor trace`, and
  reusable semantic scenario evidence. Active legacy scenarios migrate only
  after their public event windows cover the old assertions.

Exit gate: a control lock, wrong target, wrong speed, presentation split, or stream wait can be explained from one bounded trace without private offset hunting.

## Phase 2 - One schema and one resolver

Status: implementation complete; packaged ROM parity proof remains pending.
The ROM, V1 data projection, V2 resolve endpoint, and profile membership tools
all call one portable C resolver. Named JSON is the authoring source and the
positional C blob is generated compatibility output. Golden vectors cover
class selection, ordered and forced layers, conditional replay, lane links,
operators, primitives, fingerprints, and provenance. The verifier also proves
that the ARM overlay and host adapter compile and publish the same C source.

- Define a named Behavior Schema with field path, type, unit, bounds, lane, operators, and feature ID.
- Generate the compact C layout, masks, editor metadata, validators, migration metadata, and trace labels.
- Extract profile composition into portable C.
- Compile the same resolver for ARM and host tools.
- Add golden resolution vectors and ROM/host parity.
- Make the Workshop use the canonical resolver.
- Keep the current binary blob as generated compatibility output.

Exit gate: deleting a profile rule from the portable resolver makes both ROM and Workshop resolution fail in the same tests. No second resolver remains. The source and host sides of this gate are implemented; the named packaged-ROM parity run is still required before runtime completion is claimed.

## Phase 3 - Actor facade and compatibility views

Status: implemented as a resident facade plus compatibility views; complete
storage consolidation remains gated by later phases.

- Put the existing lifecycle behind `Apply`, `Tick`, and `Inspect` without changing behavior.
- Add `ActorView` adapters over `OverworldWildSpawnState`, its runtime sidecar,
  and the separate player engine anchor. Do not move storage yet.
- Bind mount handles to the player anchor, follower actor, field epoch, map
  generation, and encounter generation.
- Make command and cancel paths idempotent with typed reasons. Commands use a
  strictly increasing wrap-safe sequence; in-window duplicates replay their
  acknowledgement and older out-of-window commands fail as `STALE_SEQUENCE`.
- Keep old state behind internal adapters only while a capability is migrating.

Exit gate: one actor snapshot can read all movement ownership and lifecycle
state without exposing the underlying parallel arrays.

## Phase 4 - Motion Plan and shared Walk

Status: shared clock and policy storage switched. Wild and mounted Walk sample
one actor-owned motion timeline, and actor path advances update the public
logical tile. Adapters still prepare targets, apply samples to engine objects,
run separate completion reducers, stream terrain, and publish effects. Mounted
Walk now acknowledges actor commit at the real vanilla movement-END boundary.
Planner, reducer, engine-boundary, parity, and deletion work remains pending.

- Introduce `Intent`, `Candidate`, `MotionPlan`, `Decision`, `PathAdvance`, and `Commit` around the working Walk path.
- Add the deterministic world fixture and host executor.
- Move wild Walk to the shared planner/executor.
- Compare old and new semantic traces before switching.
- Move mounted Walk to the same executor with actor authority, the player
  engine anchor, and mounted presentation.
- Centralize acceleration, skid, stomp, crash, facing, diagonal collision, streaming, and commit effects.
- Delete the duplicated mounted and wild Walk ownership paths.

Exit gate: exact Walk and all feedback pass wild/mounted parity. Only role intent and presentation differ.

## Phase 5 - Hop and Teleport

Status: shared timeline and presentation math implemented. Hop and Teleport use
the actor state for elapsed time, arc, spin, visibility, path advances, suspend,
rebind, resume, and terminal state. Wild and mounted adapters still choose
candidates, apply samples, control streaming and landing, and decide when the
engine boundary is ready to acknowledge. Live parity and adapter deletion remain
pending.

Successful wild Hop and Teleport cleanup no longer cancels the acknowledged
shared motion. Cancel is idempotent for direct and queued callers, stale
suspended replacement publishes its terminal cancel, and actor detach is an
explicit terminal release.

- Move Hop planning into the Motion Module.
- Reuse the shared executor for duration, arc, streaming, commit, cancel, pause, and presentation.
- Move Teleport through the same lifecycle with visibility policy as data.
- Preserve specialized candidate rules for ledges, canopy, diagonal fallback, and fixed/per-tile timing.
- Remove separate custom-jump and mount-motion ownership once scenario parity passes.

Exit gate: Walk, Hop, and Teleport share one motion state machine and terminal event contract.

## Phase 6 - Roles, chains, and Ram

Status: policy storage and pure look, wander, and chain-pause helpers are
implemented in the actor system. Wild and mounted Walk use the same actor policy
slot, but their commit reducers still differ. Wild role sequencing still owns
chain action publication and Ram crash/battle reactions. Ram is not yet an
actor-owned controller.

- Move wild, follower, chain, and player input decisions behind role controllers.
- Keep mounted control as a rebind of the current follower actor to rider input.
- Make chain movement consume semantic commits only.
- Express Ram as a Walk-intent controller policy with locked direction, acceleration, stomp, crash, and battle reactions.
- Remove AI-only fields from mounted runtime state. Do not remove them from the resolved profile.

Exit gate: a new role adds one controller or presentation adapter without copying motion code.

## Phase 7 - World lifecycle and population

Status: field epochs, motion suspend/rebind, authoritative path-advance signals,
public logical-tile updates, and the population timer tick have actor-owned
entries. Terrain streaming, reservation checks, transition order, warp/battle
gates, and bounded population maintenance still live in role or engine adapters.
Full transition and streaming soak proof is pending.

- Centralize path advances, target reservation, surface occupancy, warp gates,
  and battle gates. Streaming and distance consume path advances; terminal
  reactions consume commit.
- Centralize field transition suspend, canonicalize, rebind, resume, and discard.
- Make population consume time, actor commits, and field events explicitly.
- Prove fast Walk, long Hop, Teleport, cardinal and diagonal streaming, and mid-motion transitions with soak scenarios.
- Replace direct retained pointers with handle and epoch validation where practical.

Exit gate: no movement type has a private map-transition or terrain-streaming protocol.

## Phase 8 - Delete legacy surfaces

Status: started. The duplicate runtime profile resolver was removed and its
old ABI slots were retired. Remaining compatibility arrays and callbacks stay
until their active ROM scenarios pass.

- Consolidate migrated parallel arrays into one coherent actor slot only after
  Walk, Hop, Teleport, roles, and lifecycle ownership have moved.
- Remove redundant Walk entry structs and oversized helper callbacks that expose private mechanics.
- Remove duplicate host resolver code and positional authoring logic.
- Remove legacy state arrays and compatibility paths after each capability moves.
- Replace implementation-string tests with facade-level scenarios where their old target no longer exists.
- Move superseded attempt documents to the archive after every live feature has an owner and scenario.
- Keep fixed-address thunks only where ROM layout still requires them.

Exit gate: deleting the actor system facade would reveal substantial hidden complexity; deleting an adapter removes only engine-specific detail.

## Change order and risk controls

- Observe before moving ownership.
- Move one locomotion and one role at a time.
- Require semantic equivalence by default until a behavior change is explicitly
  intended. Require byte equality only when binary layout is explicitly unchanged.
- Never keep two live motion owners as a fallback.
- Do not mix a schema migration with a motion migration in the same change.
- Do not claim parity from static source checks.
- Preserve the user's current game feel unless a separate behavior change is requested.

## Remaining completion sequence

Overlay 158, the mount overlay, and the wild overlay have only a few bytes of
free code. Completion must replace and delete existing paths; it cannot add a
second orchestration layer.

1. Replace the broad motion dispatcher with one request call and one engine-
   boundary call in the same fixed service slot. The boundary owns unapplied
   path advances, stream wait/ready, presentation acknowledgement, engine-END
   acknowledgement, suspend/rebind/resume, and cancel. Proof: model ordering,
   package ABI, then one focused Walk ROM scenario.
2. Move Walk commit reduction into the actor policy service. Wild and mounted
   adapters consume one reducer result and only publish engine effects. Delete
   their duplicate acceleration/skid completion paths. Proof: exact timing,
   acceleration, turn/stop skid, stomp, and crash parity scenarios.
3. Route Hop and Teleport through the same boundary. Keep collision and terrain
   queries in the world adapter, but pass ordered candidates and typed rejection
   reasons to the planner. Delete adapter-local elapsed and terminal gates.
   Proof: cardinal/diagonal, ledge, mounted-single-motion, fixed/per-tile,
   transition, and presentation scenarios.
4. Replace the implicit map-change sequence with one transition command:
   suspend, canonicalize, advance epoch, rebind, then resume or discard. Feed
   player path advances and transition events into the bounded population work
   queue. Proof: transition, streaming, population, and long-soak scenarios.
5. Migrate active scenarios to public actor evidence. After each public scenario
   passes, delete the covered private arrays, fixed callbacks, source-string
   assertions, and positional writer transforms. Keep only fixed thunks required
   by ROM layout.

## Deferred ideas

These are compatible with the architecture but are not migration prerequisites:

- Expanded surface graph for roofs, bridges, cliffs, and flight.
- Effect-owned Pokémon presentation above occluding geometry.
- More scripted actor roles.
- A graphical trace timeline inside the Workshop.

They must use the same schema, actor, motion, world, presentation, and verification interfaces. They must not create a parallel system.
