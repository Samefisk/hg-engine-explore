# Overworld Pokémon System Architecture

## Target design and current migration boundary

This document defines the target ownership model. It is not a claim that every
adapter has migrated. The phase status and current owners are recorded in
[`roadmap.md`](roadmap.md). Until a roadmap exit gate passes, the named legacy
adapter remains the current engine owner even when this document uses the
present tense to define the target contract.

The system has one deep `OverworldActorSystem` module with a small external
interface and private internal modules. It is the stable home for overworld
Pokémon lifecycle, observation, resolution, motion state, movement policy, and
population timing. Fixed-address overlay tables are DS deployment adapters.

The public facade is:

```c
OverworldActorResult OverworldActorSystem_Apply(
    const OverworldActorCommand *command,
    OverworldActorReply *reply);

OverworldActorFrameResult OverworldActorSystem_Tick(
    const OverworldActorFrame *frame);

OverworldActorResult OverworldActorSystem_Inspect(
    const OverworldActorQuery *query,
    OverworldActorSnapshot *snapshot);
```

- `Apply` is the only external lifecycle request path. It accepts a bounded,
  value-only command and queues it for the next `Tick`. The reply acknowledges
  the sequence ID. Commands use one strictly increasing, wrap-safe sequence.
  A duplicate still in the acknowledgement ring returns its previous reply;
  an older replay outside that bounded ring is rejected as `STALE_SEQUENCE`.
- `Tick` runs once per usable field frame, applies queued commands, establishes
  the field boundary, advances every actor motion timeline exactly once, and
  reports whether more frame work is pending. Engine adapters read the shared
  sample, apply it to field objects, and acknowledge the real engine completion
  boundary. They do not advance elapsed motion time.
- `Inspect` is read-only and typed. A query can enumerate actors or inspect one
  actor, the trace ring, population state, or system state.

Production uses a resident singleton. Host instance creation is private to the
test adapter. Public commands use actor handles, field epochs, and semantic
values. They never contain `FieldSystem *`, `LocalMapObject *`, overlay pointers,
or private runtime offsets. Invalid context fails closed and returns normal
player control.

A retryable `Apply` result means the command was not queued or acknowledged.
A retryable motion decision leaves the intent pending and does not consume
input. Field adapters that require a same-frame lifecycle boundary queue the
command and invoke `Tick` before returning to stock field processing.

## Why this seam is deep

Callers should not need to know overlay addresses, movement flags, custom-jump arrays, mount `motionMode`, `MapObject` commands, terrain loader offsets, ARM/Thumb interworking, profile masks, or presentation offsets.

Compatibility adapters still contain some of those details. The facade hides
them from new callers and gives three stable calls for wild Pokémon, followers,
mounted control, scripted actors, transitions, and diagnosis. External callers
include only the facade header. New domain code must not call fixed-address
internal service tables directly.

The actor facade must not become a new monolith. Its implementation is a tower of private modules with explicit ownership.

## Tower of abstractions

### 1. Behavior Schema

Owns profile field names, units, bounds, lane use, override operators, enum values, feature IDs, and binary layout generation.

The field schema is named data and generates C and host metadata. Named profile
values, rules, targets, members, operators, and conditional states live in
`data/overworld_behavior_profiles.json`. Positional C profile records are
generated ROM compatibility output and are not an authoring source.

```text
profile
  spawn
  alert
  battle
  lanes
    owner
    active
    tired
      controller
      locomotion
      traversal
      momentum
      chain
      feedback
      presentation
```

### 2. Behavior Resolver

Owns deterministic composition:

```c
BehaviorResult BehaviorCatalog_Resolve(
    const BehaviorContext *context,
    ResolvedActorBehavior *result,
    BehaviorResolutionTrace *trace);
```

This is a private implementation interface. The resolver input contains subject,
encounter terrain, conditional physical-surface state, behavior class inputs,
and an explicit forced layer set. It does not contain actor role.

Required order:

1. Validate subject and context.
2. Resolve behavior class.
3. Load the base class profile.
4. Resolve inherited policy.
5. Match normal override layers.
6. Select conditional layers from the pre-condition Owner travel time and surface state.
7. Apply normal layers, then conditional layers, in source order.
8. Resolve Active and Tired lane references once.
9. Normalize all lanes.
10. Resolve mechanical primitives.
11. Produce a fingerprint and ordered provenance.

The resolver is one portable C source compiled for ARM and for the Workshop
host adapter. Both read the same generated compact behavior layout. The
Workshop uses Python only to collect context and project the C result into
editor labels; it contains no second profile-composition policy.

Current mount resolution first resolves the follower with the forced `Follower
Pokemon` override layer. Mount begin then snapshots the resolved Owner lane.
Mounted is not a resolver role. The mounted controller later chooses which
resolved values it consumes and ignores AI-only chain decisions.

### 3. Role Controllers

Controllers decide what an actor wants. They never change coordinates or presentation.

- Wild controller: alert, chase, flee, wander, chain, Ram, rest, and battle intent.
- Follower controller: follow and release intent.
- Mounted controller: player input to intent. It uses the same resolved behavior as the follower and the Owner lane.
- Script controller: explicit scripted intent.

Ram is controller policy that emits Walk intents with direction lock, acceleration, stomp, and crash reactions. It is not a locomotion engine.

### 4. Motion Module: Policy

The stateful policy reducer owns momentum, acceleration counters, skid
selection, chain eligibility, and feedback intent. It consumes resolved
behavior plus prior terminal outcomes and produces an immutable policy snapshot
for planning. It mutates policy state only from explicit path-advance, commit,
cancel, and control-rebind events.

### 5. Motion Module: Planner

The planner converts one intent and one world revision into an accepted plan or a typed rejection.

```c
typedef struct OverworldMotionPlan {
    u8 kind;
    u8 facing;
    u8 traversalPolicy;
    u8 commitPolicy;
    s16 startX;
    s16 startY;
    s16 targetX;
    s16 targetY;
    u16 duration;
    u8 arcHeightQ4;
    u8 spinSpeed;
    u8 swayWidth;
    u8 visibilityPolicy;
    u8 pauseFrames;
    u8 pathAdvancePolicy;
} OverworldMotionPlan;
```

This is a private implementation value. External callers see its semantic
projection through `Inspect`.

The planner owns candidate order, direction rules, collision, encounter-terrain
and physical-surface queries, traversal permission, occupancy, reservation
requirements, exact timing, arc, facing, and immutable plan output.

Planning is pure with respect to engine objects and actor state. It queries a
world snapshot and emits a plan. Reservation acquisition and movement start
happen after acceptance.

### 6. Motion Module: Executor

Walk, Hop, and Teleport share one execution lifecycle. Specialized planners can choose different paths, but interpolation, streaming, presentation synchronization, cancellation, and commit are shared.

```text
IDLE -> PLANNED -> MOVING -> COMMIT_PENDING -> SETTLING -> IDLE
                     |              |
                     +-> SUSPENDED -+
                     |
                     +-> CANCELED -> IDLE
```

A motion snapshots its resolved behavior fingerprint and field epoch. Mid-motion profile changes affect the next intent, not the current atomic motion.

When the rendered target is reached, the production executor can enter
`COMMIT_PENDING` while it waits for the stock movement-END boundary. No new
intent is requested in this phase. The engine adapter revalidates the field
epoch after the callback because that boundary can transition or unload field
context. `LOGICAL_COMMIT` is published only after required engine
acknowledgement succeeds.

### 7. Path Advance, Commit, and Reactions

The executor emits a path advance when authority crosses a tile boundary. A
multi-tile Hop or Teleport can emit several advances but still has one terminal
commit. Each path advance updates, in documented order:

1. Authoritative logical tile and current traversal surface.
2. Terrain-stream progress.
3. Movement-distance and population-region signals.
4. Presentation position derived from the same motion timeline.

A path advance cannot increment a chain, accelerate, land, or trigger a warp.
The motion plan can opt specific engine step signals in or out, but those
signals remain distinct from terminal completion.

Commit runs once when the accepted movement decision completes. It updates, in
documented order:

1. Confirm final logical target and occupied surface.
2. Record movement history and previous-tile state.
3. Update chain and stamina counters for the accepted semantic action.
4. Update acceleration or momentum state.
5. Freeze one terminal outcome for publication.

Skid tiles, chain repositioning, render interpolation, and stream anchors state their commit policy explicitly. They cannot enter the normal chain count by accident.

After internal commit, publication is role-specific:

1. Release internal reservations and movement ownership.
2. Publish role-specific step, warp, battle, and interaction events.
3. Revalidate field epoch after any engine callback.
4. Suspend immediately if the callback changed context.
5. Emit safe post-commit presentation and feedback reactions.

### 8. Presentation Adapters

Presentation mirrors motion. It does not own it.

- Single-object adapter: one actor and one map object.
- Mounted adapter: actor authority, player engine anchor and rider graphics,
  plus the Pokémon dependent presentation.
- Effect adapter: shadow, flicker, particle, sound, or future elevated-surface sprite.
- Headless adapter: semantic poses and events with no renderer.

Mounted input changes the role and presentation adapter. It does not create a second profile or a second motion.

### 9. Population and Lifecycle

Population controls encounter preparation, spawn timing, despawn, identity,
capture, and battle handoff. It consumes path advances for player-centered
distance, commits for terminal movement decisions, and explicit world events.
It does not infer movement by counting render frames.

The transition coordinator owns field epoch changes, suspend, canonicalize, rebind, resume, and discard. Other modules receive typed commands instead of sharing an implicit transition sequence.

### 10. Observation

Observation is a first-class module, not temporary diagnostic code. `Inspect`,
the generated debug descriptor, and a bounded trace ring expose semantic state
without changing behavior.

## Real seams and adapters

The following seams have at least two real adapters and are justified:

| Seam | Production adapter | Second adapter |
| --- | --- | --- |
| Role | Wild or Follower AI | Mounted input or Script |
| World | Nintendo DS field engine | Deterministic host fixture |
| Presentation | Map objects and effects | Headless semantic poses |
| Execution | Nintendo DS executor | Host event executor |

Planner families are private strategies, not public plugin APIs. Fixed overlay entry tables are deployment adapters, not domain interfaces.

## Nintendo DS deployment topology

The conceptual module uses one small resident code home and several unloadable
engine adapters.

- Overlay 158 is resident at `0x023B6B00-0x023BAB00`. Its first `0x3100` bytes
  hold code and fixed entries; its last `0x0F00` bytes hold bounded state.
- The public facade, compatibility entry, debug layout, resolver, motion,
  population, and movement-policy entries have fixed addresses and
  magic/version/size checks.
- Unloadable overlays receive bounded value inputs and return bounded values.
  No facade state retains pointers into an unloadable overlay.
- ARM/Thumb interworking and `LONG_CALL` requirements remain explicit adapter
  contracts.
- Every overlay has a byte budget checked from the linker map and packaged ROM.
- Portable resolver and motion code are separated from ROM context adapters
  that read behavior blobs, `FieldSystem`, and map objects.
- Host adapters compile the portable parts without Nintendo DS pointers or
  overlay assumptions.

## Target frame order

Every usable field frame targets one order. The current facade owns the
field-boundary, command, and motion-clock phases. Compatibility adapters still
own some candidate preparation, engine application, transition, and reaction
steps named below:

1. Validate field epoch and actor handles.
2. Apply pending lifecycle commands.
3. Advance active motions.
4. Emit bounded path advances in traversal order.
5. Enter `COMMIT_PENDING` when engine acknowledgement is required.
6. Produce at most one acknowledged terminal commit per actor.
7. Run role-specific commit publication and reactions.
8. Ask idle controllers for at most one intent.
9. Run policy and plan against one world revision.
10. Acquire reservations and start accepted motions, or record typed decisions.
11. Synchronize engine anchors and dependent presentations.
12. Run bounded population maintenance.
13. Publish observation state.

Input is consumed only after the actor system accepts ownership. World-busy is retryable and distinct from blocked.

## Typed decisions

The minimum stable reasons are:

- `OK`
- `RETRY_WORLD_BUSY`
- `REJECTED_BLOCKED`
- `REJECTED_SIDE_TILE`
- `REJECTED_TERRAIN`
- `REJECTED_OCCUPIED`
- `REJECTED_RESERVED`
- `REJECTED_DIRECTION`
- `REJECTED_PROFILE`
- `UNSUPPORTED_LOCOMOTION`
- `MOTION_ALREADY_ACTIVE`
- `STALE_ACTOR`
- `STALE_FIELD`
- `PRESENTATION_MISSING`
- `DATA_UNAVAILABLE`
- `NO_MEMORY`
- `CONTEXT_LOST`
- `STALE_SEQUENCE`

Cancel is idempotent. It leaves authority on a complete tile, releases reservations, clears engine movement ownership, restores engine anchors and presentation, and records one reason.

## Performance contract

- No per-frame heap allocation.
- Fixed candidate arrays and bounded actor loops.
- Profile resolution cached by source revision, subject, forced layers, and relevant resolver context such as conditional physical-surface state.
- Resolved behavior is copied or referenced as one coherent value, not rebuilt field by field during motion.
- Trace writes occur only when a filter is armed.
- The trace ring is fixed-size and overwrites old records.
- Normal `Tick` work is bounded by active actors and active motions.
- Map reconciliation is bounded by actor count.

## Locality and deletion tests

A successful migration passes these tests:

- Adding a locomotion changes one planner, the shared executor only when its lifecycle is genuinely new, profile schema, and scenarios. It does not add a mounted copy.
- Adding a role changes one controller or presentation adapter. It does not copy movement mechanics.
- Changing profile composition changes the portable resolver once. It does not change ROM C, legacy Python, V2 Python, and JavaScript separately.
- Changing streaming changes the world/executor adapter once. It does not patch Walk, Hop, and Teleport independently.
- Removing the actor facade would expose significant lifecycle, motion, and transition complexity. Removing a private adapter would remove only its engine-specific details.

## Anti-patterns

- Do not add another movement owner or parallel runtime array.
- Do not add a mount-only copy of a profile field or motion rule.
- Do not model flat Walk as a behavior-level zero-height Hop.
- Do not infer semantic commits from coordinate changes. Emit explicit path
  advances and one explicit terminal commit.
- Do not let presentation write logical position.
- Do not use private raw memory offsets as the long-term verification interface.
- Do not layer a new path permanently over an old path. Compare, switch, then delete.
- Do not treat a source-string verifier as proof of runtime behavior.
