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
  boundary. They do not advance elapsed motion time. The wild Hop and Teleport
  adapter also takes spin, facing, and visibility from that sample; its former
  custom-jump counters are reserved compatibility storage, not live state.
- `Inspect` is read-only and typed. A query can enumerate actors or inspect one
  actor, the trace ring, population state, world-gate readiness, or system
  state. `OVERWORLD_ACTOR_INSPECT_POPULATION` returns the public population
  value. `OVERWORLD_ACTOR_INSPECT_WORLD_GATE` accepts only the Warp and Battle
  gate kinds.

Production uses a resident singleton. Host instance creation is private to the
test adapter. Public commands use actor handles, field epochs, and semantic
values. They never contain `FieldSystem *`, `LocalMapObject *`, overlay pointers,
or private runtime offsets. Invalid context fails closed and returns normal
player control.

Each resident actor slot owns one public snapshot, one Motion state, and one
movement-policy state. Wild refreshes the snapshot through a bounded value
view; it does not expose or retain Actor storage. An active motion keeps its
Actor-owned logical tile while the engine object supplies render position.
Wild retains only engine-adapter state such as prepared spawn work, refill work,
staged presentation handles, and prepared condition state.

The resident condition adapter builds bounded value-only observations for the
portable evaluator and records armed semantic trace events. It does not decide
condition truth, compose profiles, or own intent and motion. The movement-policy
service entry publishes this adapter because that fixed 16-byte entry had one
available data pointer; this is deployment placement, not movement-policy
ownership.

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
values, rules, pools, applications, operators, and conditions live in
`data/overworld_behavior_profiles.json`. Positional C profile records are
generated ROM compatibility output and are not an authoring source.

```text
catalog
  root profile: Default
  profiles
    normal
    conditional
      condition entries
  named pools
  ordered applications
    targeted normal application
    linked conditional or System application
  runtime bindings
```

Every non-root profile has one classification. Applications are grouped in
this precedence order: `routine`, `placement`, `capability`, `attitude`,
`modifier`, `system`, then `utility`. Manual order is preserved inside a group.
Later applications still win field by field, so group and manual order are
functional. Conditional is independent of classification. An archetype is
only design shorthand for a composition; it is never saved as a
classification.

A normal application owns a named or inline Pokémon target. A conditional
application owns only ordered identity and its profile; each condition entry
owns its own subject pool. A System application is linked from its runtime
owner and has no normal assignment. The generator lowers linked applications
to the existing compatibility representation.

Named pools are authoring-only reusable sets. A pool has a stable ID, display
name, one match record, and explicit members. Normal applications, condition
subjects, and actor-target filters can reference one. Pools cannot contain
other pools. The generator expands them before packaging, so they add no ROM
lookup or recursive runtime storage.

The target catalog has one complete `Default` root and this exact application
order. The machine-readable contract is
[`profile_building_blocks_target_v1.json`](../../tools/overworld/fixtures/profile_building_blocks_target_v1.json).

| Order | Classification | Profile | Application ID |
| ---: | --- | --- | --- |
| 1 | Routine | Scavenger | `apply-scavenger` |
| 2 | Routine | Sprint | `apply-sprint` |
| 3 | Routine | Floaty Bounce | `apply-floaty-bounce` |
| 4 | Routine | Small Bird Hop | `apply-small-bird-hop` |
| 5 | Routine | Erratic Flutter | `apply-erratic-flutter` |
| 6 | Routine | Meander | `apply-meander` |
| 7 | Routine | Hop Around | `apply-hop-around` |
| 8 | Routine | Idle | `apply-idle` |
| 9 | Routine | Drowsy Wander | `apply-drowsy-wander` |
| 10 | Routine | Perch | `apply-perch` |
| 11 | Routine | Rest | `apply-rest` |
| 12 | Placement | Fly In | `apply-fly-in` |
| 13 | Placement | Canopy Access | `apply-canopy-access` |
| 14 | Placement | Flower Bed | `apply-flower-bed` |
| 15 | Capability | Notice Player | `apply-notice-player` |
| 16 | Capability | Teleport | `apply-teleport` |
| 17 | Capability | Stalker | `apply-stalker` |
| 18 | Capability | Long Hop | `apply-long-hop` |
| 19 | Capability | Canopy Hop | `apply-canopy-hop` |
| 20 | Capability | Throw | `apply-throw` |
| 21 | Capability | Ram | `apply-ram` |
| 22 | Capability | Heavy Stomp | `apply-heavy-stomp` |
| 23 | Attitude | Startled | `apply-startled` |
| 24 | Attitude | Ambush | `apply-ambush` |
| 25 | Attitude | Playful | `apply-playful` |
| 26 | Attitude | Skittish | `apply-skittish` |
| 27 | Style | Waddle | `apply-waddle` |
| 28 | System | Follower | `apply-follower` |
| 29 | System | Mounted | `apply-mounted` |
| 30 | Utility | Asleep | `apply-asleep` |

Perch follows the ordinary Routines. Notice Player is the first Capability.
Startled precedes Skittish. Heavy Stomp follows Ram, adds ledge-hop landing
footfall feedback, and limits its shared Pokémon group to one active Wild spawn
for Golem, Rhydon, Snorlax, Tyranitar, Aggron, Groudon, Torterra, Hippowdon,
Rhyperior, Mamoswine, and Regigigas. The player condition
is last inside Playful. Follower, Mounted, and Asleep are runtime-linked and
cannot be normally assigned.

Snorlax also uses Drowsy Wander. It walks in uneven two-to-six-step bursts,
varies each step's travel time, often stops to look around, and avoids immediate
backtracking. Heavy Stomp remains independent of this Routine.

Ram keeps the strong stomp sound while its Walk direction is locked. Heavy
Stomp uses the stock ledge-hop landing sound when Walk direction is unlocked.

### 2. Behavior Condition Evaluator

Owns bounded condition truth, activation lifetime, cooldown, and target
selection. It consumes value-only subject and world observations plus the
current actor-system frame. It returns an active conditional-application mask,
one winning condition-entry ID per active application, and zero or one captured
target per active application. It also reduces those winners in shared
application order to one overall winning condition and one final target with
its source application and condition.

Condition entries are independent. The last listed active entry for one
conditional profile wins. Different conditional profiles can be active at the
same time. The evaluator does not compose profile fields and does not start,
cancel, or inspect motion.

Each condition owns its subject pool. The conditional application has no
normal Pokémon target. The first condition kinds include visible player,
visible compatible actor, target cannot see subject, and physical
terrain/speed. They use fixed records; there is no Boolean expression language.
While-true entries capture one target when they become true and keep it until
they become false. Timed entries capture one target when they trigger and keep
it through duration. Cooldown starts at that trigger. When cooldown ends while
the predicate remains true, the entry triggers again, selects a fresh target,
and restarts duration and cooldown.

Vision is one shared value-only service for Pokémon and the player. The initial
Vision is a 90-degree forward cone with three tiles of range, awareness of all
eight adjacent tiles, and solid-terrain occlusion. Actors do not block sight.
Observer and target tiles are not blockers. Invalid or unloaded terrain fails
closed.

Profiles own stable Current Vision fields. At bind or rebind, the controller
resolves and caches Current Vision from `Default`, matching normal
applications, and the forced-role profile. Conditional applications are
excluded, so a profile cannot change the Vision that activates itself. A
vision-based condition either uses Current Vision or owns one inline Custom
Vision. The player uses the same evaluator and initial defaults; player tuning
is not profile authoring.

Visibility is evaluated at intent boundaries. Geometry rejects candidates
outside the cone before the adapter traces the short line to a candidate. The
actor search remains bounded by the ten-actor world view. Conditions and
behavior planning consume the same visibility result.

Target-required activation fails when no valid target exists. If a captured
actor handle becomes stale, the complete activation ends before resolution.
The evaluator never keeps a slot number or engine pointer as target identity.

All timer values use the public actor-system frame returned by Inspect. Expiry
comparison is unsigned and wrap-safe. The role adapter prepares applicable
entries at bind and supplies bounded observations only when it is ready to ask
for a new intent.

Wild lazily allocates one 2,044-byte condition workspace from `HEAPID_WORLD`.
It contains ten fixed 52-byte prepared actor records. Bind prepares only the
catalog indexes that can apply to that subject, then allocates exactly the
required entry-state array from the same heap. Despawn, slot reuse, actor
identity change, and field-context loss clear the owned state. Wild owns and
frees each nested state allocation even when the adapter overlay is
unavailable. One actor roster is cached for each public actor frame and is
invalidated immediately by a bind or clear. Full actor handles validate
captured targets before resolution.

Authoritative evaluation runs whenever the controller can request a new
intent: initial idle choice, completed motion, completed presentation, and the
next step of a movement chain. The resulting application mask and captured
target feed the resolver before the controller selects that intent. The
adapter resolves again only when the active application mask changes; an
unchanged mask reuses the cached resolution. A stale captured actor handle
clears the conditional result and that intent decision fails closed.
Trace-disabled calls do not walk condition trace records.

A timed retrigger always restarts its duration. It requests trigger presentation
only when the trigger also changes the resolved application mask. When one
timed profile ends, Tired starts only if no other timed conditional application
remains active. Adapter-private outcome bits are masked at the role boundary;
in particular, private `PROFILE_CHANGED` never escapes as Wild's public
`FAIL_CLOSED` bit.

### 3. Behavior Resolver

Owns deterministic composition:

```c
BehaviorResult BehaviorCatalog_Resolve(
    const BehaviorContext *context,
    ResolvedActorBehavior *result,
    BehaviorResolutionTrace *trace);
```

This is a private implementation interface. The resolver input contains
subject, encounter terrain, behavior class inputs, an explicit forced layer
set, active conditional applications, the overall winning condition, and one
already-resolved target with source provenance. It does
not contain actor role, world pointers, timers, or condition predicates.

Required order:

1. Validate subject and context.
2. Resolve the ordered profile selectors.
3. Materialize the selected profile from the complete root and its parent chain.
4. Resolve inherited policy.
5. Iterate the shared application list once.
6. Apply a matching normal application.
7. Apply a matching conditional application only when its active input bit is
   set.
8. Validate the final target's source application and condition. Target
   precedence was reduced by the evaluator using this same application order.
9. Resolve the Tired lane reference once.
10. Normalize both lanes.
11. Resolve mechanical primitives.
12. Produce a fingerprint and ordered provenance, including the winning
    condition entry and target source.

The resolver is one portable C source compiled for ARM and for the Workshop
host adapter. Both read the same generated compact behavior layout. The
Workshop uses Python only to collect context and project the C result into
editor labels; it contains no second profile-composition policy.

A behavior fingerprint identifies resolved values, not one Pokémon or one
resolver request. Different levels or subjects can legitimately produce the
same result. Observers retain each bounded request separately and bind the
selected request to the actual subject/context. Changed result bytes under one
fingerprint remain an error; changed request bytes alone are not one.

Current mount resolution resolves the same subject with the forced `Mounted`
System layer. Mount begin then snapshots the resolved Owner lane and binds its
fingerprint to the actor for the session. Mounted is an application, not a
resolver role. Follower is not forced in the mounted request. Mounted has no
field overrides, so the normal selected Owner movement fields remain composed.
Mounted Walk uses the shared chain counter. The mounted adapter
executes `PAUSE`, `HOP_FORWARD`, `HOP_IN_PLACE`, `LOOK_AROUND`, and the three
reposition modes. It consumes an action only after a successful start or a
final rejection; a temporary busy result keeps the exact action pending.
Mounted moving actions use the player engine anchor and dependent Pokémon
presentation, not a second engine mover.
At a preserved map transition, Wild may prepare the retained slot's Follower
profile for the destination map, but Mount keeps ownership of that slot's actor
policy until the mount session ends. Wild must not bind Follower policy over a
still-Mounted actor. Wild does not cache the destination Follower profile
while Mounted owns the slot. The old map-keyed cache then misses after
dismount, so the first normal Follower lookup resolves and binds the
destination profile.

The public actor view keeps lane and controller state separate. Native
controller enum values are compatibility details, not profile tabs or
classifications. Ordinary and emoting controller values project to Owner, and
the tired controller value projects to Tired. Conditional admission does not
change lane. Mounted control projects to Owner. An unknown native state has no resolved lane
(`BEHAVIOR_RESOLUTION_LANE_NONE`); it must not be labeled as valid behavior.
`controllerState` retains the raw native value for diagnosis.

Prepared Wild and Follower spawns bind their fresh actor before setup helpers
can resolve and cache its profile. A new bind must still clear the old subject's
policy. No cache hit may rely on a profile binding erased by a later bind.
Rejected binds leave the previous actor untouched; a failed startup Hop unbinds
only its newly accepted handle before the normal spawn rollback.

### 4. Role Controllers

Controllers decide what an actor wants. They never change coordinates or presentation.

- Wild controller: condition observation, chase, flee, wander, chain, Ram,
  rest, and battle intent. Internal held actor control suspends this planning
  during pickup, carry, throw, drop, cancel, and release; it is not a profile
  or behavior class.
- Follower controller: follow and release intent.
- Mounted controller: player input to intent. It uses the normal selected Owner
  behavior plus Mounted, not Follower's chase and spawn rules.
- Script controller: explicit scripted intent.

Ram is controller policy that emits Walk intents with direction lock, acceleration, stomp, and crash reactions. It is not a locomotion engine.

Wild and Follower adapters evaluate conditions only when the actor can request
a new intent. A condition change cannot interrupt an accepted motion. A chained
movement returns to the same boundary before requesting its next intent.
Mounted follower control does not evaluate autonomous conditions. Alert is a
presentation response to a qualifying trigger, not a controller state or a
condition predicate.

During migration, the fixed Wild runtime service entry exposes the value-only
`reduceRole` callback. It points at the same portable
`OverworldRoleController_Reduce` body used by host proof. The function is
packaged in audited boot-resident compatibility space; the service entry keeps
its 64-byte ABI. Wild and Mount call-site migration is a separate phase.

### 5. Motion Module: Policy

The stateful policy reducer owns momentum, acceleration counters, the resolved
per-event acceleration rule, skid selection, chain eligibility, and feedback
intent. Acceleration value `0` keeps the current travel time, values `1` through
`32` remove that many frames per event, and value `33` is the editor's `/2`
legacy rule. The default is `1`, so each acceleration event removes one frame.
Normal Walk variance keeps nominal momentum separate from the displayed tile
time. With acceleration enabled, the first maximum-speed tile retains full
variance. Each later eligible normal Walk commit reduces the range by the
acceleration amount (or halves it, rounding down, for `/2`), until zero.
This is per tile, independent of the below-cap acceleration cadence. The
existing momentum tile counter records capped-speed commits, saturating at255;
below the cap it retains its acceleration-cadence role. Stops and accepted
turns reset it; rejected starts and skid tiles cannot advance it.
The displayed-time entry remains fixed at `0x01FF9C8C`; its implementation
uses existing overlay159 code space after the presentation adapter and before
the gait-state reserve. No entry, state address, or memory reserve grows.
A turn or stop starts its braking and skid decision from the last
displayed Walk time, so the next motion does not jump to a faster hidden speed.
It consumes resolved
behavior plus prior terminal outcomes and produces an immutable policy snapshot
for planning. It mutates policy state only from explicit path-advance, commit,
cancel, and control-rebind events.

Candidate rejection must not become a synthetic stop. A direction outside the
resolved lane's cardinal/diagonal permission returns before changing momentum,
chain counters, deferred pause actions or presentation. A real `NONE` input
remains a stop request and follows the existing stop/skid rules. After the full
normal Wild direction search cannot start a step, the adapter can submit one
separate, profile-gated `NONE` directly to Walk policy. This does not reinterpret
an individual rejected direction and does not use the role or chain controller.
When a full random or untargeted Wild `WANDER`/`HOP` search is blocked, the
adapter reports that no movement started, preserves the committed facing, and
waits one normal movement pause before it searches again. An explicit
`TURN_AROUND` action and a directed blocked fallback can still change facing
without starting a step.

`planTurnSkidPath` is an Owner-lane Walk momentum option. An ordinary Walk,
including the first recovery step after a turn skid, validates its immediate
destination without reserving a future skid runway. On an actual turn skid,
Wild and Mounted validate the full skid corridor and the first step in the
requested turn direction before motion starts. A blocked skid path brakes
momentum without a crash; the next held direction can turn from rest. This
does not change the separate stop-skid option. A Sprint actor may walk into
the last clear tile before a wall or non-player actor even if a later obstacle
Hop has no safe landing. The actual Hop still validates the world when it
starts, and no skid may cross a blocked tile.

`stopSkid` is also an Owner-lane Walk momentum option. When it is enabled, a
normal Wild WANDER direction search that cannot start another step sends one
genuine Walk `NONE` request. Sprint's normal Tired-to-Routine transition can
send the same request before Owner planning resumes. The shared Walk policy
then applies the current speed-based stop skid. Movement Chain movement, pause,
and action selection do not start, plan, or gate this stop skid.

### 6. Motion Module: Planner

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

Planning does not mutate engine objects or actor state. It reads a bounded
world snapshot or compatibility read-only query context and emits a plan. It
does not retain engine pointers. Reservation acquisition and movement start
happen after acceptance.

Reservation acquisition is one actor-owned transaction. The Actor Motion
service compares target tile plus `targetSurfaceId` against all live actor
reservations. Only after that conflict check does it allocate a fresh non-zero
`reservationId`, overwrite any reservation value in the candidate plan, and
begin the motion. The request output is cleared on entry and receives that
identity only after `Begin` accepts the plan. The reservation is released on
commit, cancel, or detach. Wild has no private reservation scan. Hop occupancy
uses the same physical-surface identity, so actors at one X/Y tile but on
different valid surfaces do not block each other.

Hop uses the typed `PLAN_HOP` operation on the existing Actor Motion request
service. Wild and Mounted adapters submit the resolved profile plus one bounded
read-only world-query context. The Motion owner interprets direction mode,
distance range, travel time, elevation scaling, arc, and obstacle clearance.
Directed behavior catch-up plans only the next executable Hop and retains the
authored target for the staged continuation. After that Hop reaches its
terminal state, the same role plans the next segment after the resolved
profile's Hop pause. Follower ownership does not replace Hop time or Hop pause.
One planning update can perform at most 24 landing validations. It must not
search a complete multi-Hop route in one field update; terrain and object
queries in that search run on the field frame and can stall the whole game.
The Hop elevation arc scale affects only extra clearance from elevation
changes. Zero retains the base level-Hop arc (16 Q4 units); it does not make
Hop flat. Wild, Follower, and Mounted planners share this rule. Flat Walk and
flat chain repositioning request their own zero arc separately.
Flat repositioning uses `FLAT_TRAJECTORY` on the same 48-byte planning value;
its `trajectory` low half supplies and returns the authored duration. Clearance
uses linear tile-edge fractions, independently of Hop timing, and cannot add
an arc to clear a raised surface. The planned arc must equal the executed arc,
including when Hop time is zero or the flat action lasts one frame.
The private planner is
physically hosted at task-6 `0x023BD4F0` because the resident actor code block
has no free code budget; only Actor Motion can call it. The retired callback
table at `0x023BD4D8..0x023BD4EF` is zero.

The Wild staged-Hop engine task handle is the first word of the existing
144-byte per-slot movement-list allocation. This keeps allocation and state
sizes unchanged and makes task create, poll, cleanup, and free use one
Wild-owned object. The old cross-overlay pointer range at
`0x023C3F18..0x023C3F3F` is retired, unreferenced, and contains only the
linker's `0xABCD` sentinel fill in the linked source image.

Wild landing validation, helper-search configuration, and reposition engine
start remain local world-adapter work. Chain state starts and advances through
the public actor policy service, and the wild adapter uses public policy
inspection before it attempts the next reposition motion. Neither Wild nor
Mounted calls task-6 Hop code directly.

### 7. Motion Module: Executor

Walk, Hop, and Teleport share one execution lifecycle. Specialized planners can choose different paths, but interpolation, streaming, presentation synchronization, cancellation, and commit are shared.

```text
IDLE -> PLANNED -> MOVING -> COMMIT_PENDING -> SETTLING -> IDLE
                     |              |
                     +-> SUSPENDED -+
                     |
                     +-> CANCELED -> IDLE
```

A motion snapshots its resolved behavior fingerprint and field epoch. Mid-motion profile changes affect the next intent, not the current atomic motion.

The public 32-bit `commitSequence` belongs to the actor lifetime. It advances
once after a successful terminal acknowledgement, including across new motion
plans; rejected or duplicate acknowledgements do not advance it. It must not
copy the portable model's per-motion 16-bit counter, which resets at `Begin`.
Consumers compare the public counter with unsigned wrap handling.

The Wild/Follower custom-motion adapter starts its stationary engine command
and start sound only after the shared motion request succeeds. A rejected
request must not set `SINGLE_MOVEMENT` on a previously free engine object:
there would be no accepted controller to finish that command. Any synchronous
Hop preparation belongs to this attempt and is restored on rejection; flat
Walk must not run the Hop restore command. This also applies while an earlier
spawn Hop is still in its authored landing pause.
Walk presentation is transactional too. A proposed direction does not change
facing before terrain and actor admission accept the step. If shared admission
rejects after local preparation, the adapter restores the prior facing.
Before any preparation, the adapter reads the current actor policy and admits
only `IDLE` or `CANCELED`, matching Motion's admission rule. The local cooldown
can expire one tick before the actor finishes settling. Such a retry returns
`ALREADY_ACTIVE` without changing facing, local presentation, or the adapter's
current motion identity. It must not submit a replacement request that clears
the existing identity on rejection. The actor's authored pause is unchanged.

The normal and Teleport request paths share one pre-plan world guard. They
reject an active transition as `RETRY_WORLD_BUSY` and a mismatched request
epoch as `STALE_FIELD` before changing `lastIntent`, writing
`INTENT_CREATED`, selecting or building a plan, or calling `Begin`. Rejected
work therefore cannot escape the transition resume mask or leave observable
intent state behind.

The accepted request returns its reservation ID as the motion identity. Wild
and Mount capture that value and attach it to every engine-boundary call for
the motion. The Actor Motion boundary accepts the receipt only while its
non-zero identity equals the actor's current reservation ID; a delayed receipt
or work for a recycled slot returns `CONTEXT_LOST` before cancel, suspend,
resume, sampling, path acknowledgement, or engine-END acknowledgement can
mutate the new motion. Adapters do not auto-rebind an identity. Rebind belongs
only to the field transition owner.

Wild Teleport keeps its engine object's logical tile at the origin while the
shared motion is active. Flicker or hidden presentation can sample the planned
target, but only the terminal landing path calls `SetObjectLandingTile`.
The destination remains protected by the actor-owned reservation until that
terminal boundary or cancellation.

When the rendered target is reached, the production executor can enter
`COMMIT_PENDING` while it waits for the stock movement-END boundary. No new
intent is requested in this phase. The engine adapter revalidates the field
epoch after the callback because that boundary can transition or unload field
context. `LOGICAL_COMMIT` is published only after required engine
acknowledgement succeeds.

For mounted Walk, a paused stationary held command is not this boundary. The
adapter must also observe `PLAYER_MOVE_STATE_END` from the player controller.
It cannot infer END from `MapObject_IsMovementPaused`, because the temporary
delay command can pause before the authored actor motion reaches its target.
When a one-frame Walk reaches its terminal actor sample, the mounted adapter
marks only its active stationary command `0x3C` complete. The stock player
controller then emits END on the next field frame. This avoids an idle render
frame between one-frame tiles without creating an early END or skipping the
normal player-step handler.

The field-input adapter latches the genuine terminal END before the world
gate masks input. It retries the matching actor commit and retains one stock
step until streaming completes. The canonical player-step bridge runs that
normal world step handler once; it does not manufacture another END.
If that handler starts an event, the receipt becomes `STOP` and
no next tile starts. Otherwise the later `PlayerMoveControl` call consumes one
`CONTINUATION_READY` receipt and starts the held-input successor in the same
field-control pass. This call precedes the next actor tick: it publishes the
successor origin without preloading elapsed time. The normal actor tick then
advances it once and the mount adapter synchronizes presentation. Preloading
elapsed1 here would produce elapsed2 at the first completed boundary.
The mount frame task only
samples physical direction input and services presentation or non-Walk work;
it cannot commit Walk or start a successor. A released D-pad therefore cannot
reuse a stale direction proposal.

Cardinal mounted Walk stays bound to the stock player terrain streamer. It
does not wait for a second custom terrain receipt after the stock player step.
Staged diagonal or long motion still owns and drains its explicit stream
anchor before terminal completion. Binding or restoring that watcher changes
only the land manager's watcher pointer. It must not overwrite the manager's
last sampled position: the stock loader advances that position only after it
has processed the ground, including when a natural chain Hop follows a Walk.

The adapter must preserve the completed motion kind through presentation and
staged-path cleanup. It clears that kind only after the actor receives the
matching terminal boundary. A flat Walk must therefore remain a Walk while it
is `COMMIT_PENDING`; clearing it early would route completion through the
legacy reducer and leave the actor without control return.

### 8. Path Advance, Commit, and Reactions

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

The resident population adapter also observes the native player anchor once
per usable field frame. A changed logical X/Y emits one
`OVERWORLD_POPULATION_INPUT_PATH_ADVANCE` with `PLAYER_CENTERED` and
`NATIVE_PLAYER`; an unchanged coordinate emits nothing. This applies to stock
unmounted movement and to custom movement that updates the same player anchor.
It replaces tile-step and adapter-call counting as the population distance
input.

Commit runs once when the accepted movement decision completes. It updates, in
documented order:

1. Confirm final logical target and occupied surface.
2. Record movement history and previous-tile state.
3. Update chain and stamina counters for the accepted semantic action.
4. Update acceleration or momentum state.
5. Freeze one terminal outcome for publication.

Skid tiles, chain repositioning, render interpolation, and stream anchors state their commit policy explicitly. They cannot enter the normal chain count by accident.

A nonzero chain move count enables Movement Chain. A resolved lane can name one
pause action or a tagged set of actions. The chain boundary applies the overall
action chance once, then uniformly samples one action from an admitted set.
`NONE` ends that chain with no pause or presentation effect. `PAUSE` waits for
the resolved passive pause time without starting an effect. A single `PAUSE`
uses the same overall action chance as any other single action or action set,
including while Mounted. A zero chance retains the legacy always-admit
meaning for existing profiles.
For ordinary Walk authoring, Movement Chain is either disabled or contains at
least two moves. A one-move Walk chain gives no readable grouping and is not
used. This restriction does not apply to Hop chains.
`HOP_FORWARD` is a two-tile Hop in the committed Walk direction. It uses the
current Walk travel time per tile, so the full Hop takes twice that time. It
has no settle pause, does not add a chain step, and preserves momentum for the
next chain.

Sprint does not use that chain action. Its normal motion is Walk. A blocked
cardinal terrain tile or a non-player actor on a cardinal midpoint can instead
trigger a two-tile forward Hop. The takeoff and landing must remain clear;
the shared Hop planner still accepts the landing and arc. A clear step stays Walk.
The Sprint lane opts in with a two-tile Hop
range and vertical-obstacle clearance; it has no chain move count or action.
Wild Wander, Flee, and Chase can approach a safe blocked-tile or actor Hop along their
chosen cardinal direction. Mounted Walk uses the same approach rule. Neither
role weakens the clearance check for an actual turn skid.

A chain action is a new motion. If the previous motion has reached its engine
end but the shared actor has not returned to `IDLE` or `CANCELED`, the action
stays pending and retries on a later frame. A rejected start never consumes the
authored chain action.

The Wild/Follower chain adapter distinguishes `RETRY`, `STARTED`, `COMPLETE`
and `ABORT`. Occupancy, reservation, busy ownership or missing preparation
data retain the selected continuation and its grid/count. Pure blocked-path
or terrain rejection can try another candidate before engine preparation.
Only a bounded search whose every enabled candidate is structurally invalid
may end as `ABORT` with `NO_CANDIDATE`; it preserves the ordinary authored
pause and returns control. An abort is not a completed action and cannot grant
missing segments. Unknown data never justifies this result.

The private landing classifier, Hop-plan wrapper and timed start return typed
motion decisions. Accepted is zero, not a Boolean true. Legacy Boolean callers
compare explicitly with `ACCEPTED`. The four-byte reposition result retains
the encoded count, grid delta, outcome and reason without new persistent state.
Rejected admission restores pending direction/distance; previous-tile history,
staged distance and reposition facing are committed only after admission.

Reposition identity must exist before the first motion request, not only after
its successful start. Jumps, steps, and skids retain their configured arc and
timing from the first segment. The pending action code and an active action's
grid/count state are distinct meanings even where the adapter packs them into
shared bytes. Dispatch an active reposition continuation before decoding a
pending action; waiting for the prior motion to settle must preserve that
continuation. Reposition segments never consume normal chain moves.

A face-player profile remains the final facing owner during ordinary Walk and
chain reposition. Motion owns facing only when the profile does not request
face-player.

An accepted engine acknowledgement publishes the model's new phase to the
public snapshot in the same call. For a zero-pause completion, the snapshot
also clears motion kind and stream state before the terminal trace. It does
not wait for the next actor tick. Policy inspection and chain readiness must
see the same terminal state as the commit counter; an authored nonzero pause
still publishes `SETTLING` and blocks a successor until that pause ends.

Walk policy uses one typed transaction for every role. `INPUT` returns a pure
step proposal. The engine adapter validates and starts that proposal, then
returns `START_RESULT`. Only an accepted result changes committed direction or
skid state. The adapter sends `COMMIT` only after the shared actor boundary is
terminal. This reducer owns acceleration, turn and stop skid reduction, stomp
and crash intent, and chain eligibility. Wild and mounted Walk enable chain
handling. Adapters publish returned effects and never run a second
Walk reducer.

For a turn skid, the reducer's step direction remains the committed travel
heading while its facing direction is the requested turn. Wild and mounted
adapters must keep both values through the motion plan and presentation. The
first recovery Walk moves in the new direction after the skid commits; a stop
skid keeps its current facing.

Walk time variance is an Owner-lane timing option from 0 through 32 frames.
The actor selects an extra duration for every normal Walk proposal, including
a braking turn, and caps the final travel time at 32 frames. A blocked proposal
keeps the same value. Each accepted tile gets its full independent variance;
the previous displayed duration does not clip it. The added time is
presentation timing only: acceleration, momentum,
skids, stomp thresholds, chain counters, repositioning and other locomotion
types continue to use their nominal values. Wild, follower and mounted roles
use this same policy; the mounted rider and Pokemon share the one motion time.
Walk variance uses a pseudorandom value keyed by actor identity and committed
step number. The same actor and step reproduce the same value, so a blocked
retry cannot reroll it. The keyed value is separate from the Movement Chain
phase and the game's general random stream.
For a continuing mounted Walk in the same heading, the Walk proposal carries
the previous displayed time in its reserved render field. The mount saves it
for presentation; the field service eases the player position before copying
that position to the Pokemon. A monotone within-tile curve removes the abrupt
linear-speed seam while preserving the new tile's selected frame count, exact
endpoint, logical path and step event.
The curve is slope-limited for extreme variance and cannot subdivide a
one-frame tile.

Ordinary Walk profiles resolve `walkPause` and `walkPauseVariance` to zero, so
the next decision can start without a synthetic stop after every tile. A
deliberately slow Routine may opt into a visibly long pause after playtesting;
short per-tile pauses are not used because they read as lag.

Walk horizontal sway is an Owner-lane presentation option from 0 through 7
pixels. Wild flat Walk passes that width to the shared Motion curve, which
offsets the rendered object perpendicular to its path and returns to zero at
the terminal frame. It does not change logical position, path advances,
collision, occupancy, reservations or chain repositioning.

Continue-straight chance applies to the one-tile direction of the last normal
movement, even when that movement was a longer chain reposition. A failed roll
excludes that direction from both random and directed flat-Walk selection.
Zero therefore selects a turn or backtrack whenever one is legal. If the
continue-straight and previous-tile preferences reject every otherwise valid
candidate, planning makes one final pass with those preferences lifted. This
fallback does not lift terrain, occupancy, surface, range, or direction-shape
rules. Random and directed flat-Walk planners use uniform reservoir selection
across the valid directions in the selected pass; candidate order does not
weight backtracking or any other direction. Chain-pause motion remains a
separate action.

A staged multi-tile Walk is a sequence of one-tile actor motions. Each tile
must reach its terminal Walk boundary and return control before the adapter
starts the next tile. The staged path carries its Walk type across that seam,
so later tiles cannot fall back to Hop. The scheduler resumes staged paths for
both normalized `WANDER` and `HOP` locomotion. It never shortens the actor's
authored settle pause. A lane change to another locomotion cancels and clears
the pending path instead of leaving it stuck.

A ledge crossing during Wander uses the shared Hop trajectory, but it does not
add the Hop settle pause. The owning Wander step applies its normal Walk pause
once after the crossing finishes. Ordinary Hop locomotion still uses the
profile's authored Hop pause. The root profile defaults that pause to zero;
a behavior must opt in when a visible landing pause is part of its design.

After internal commit, publication is role-specific:

1. Release internal reservations and movement ownership.
2. Publish role-specific step, warp, battle, and interaction events.
3. Revalidate field epoch after any engine callback.
4. Suspend immediately if the callback changed context.
5. Emit safe post-commit presentation and feedback reactions.

### 9. Presentation Adapters

Presentation mirrors motion. It does not own it.

- Single-object adapter: one actor and one map object.
- Mounted adapter: actor authority, player engine anchor and rider graphics,
  plus the Pokémon dependent presentation.
- Effect adapter: shadow, flicker, particle, sound, or future elevated-surface sprite.
- Headless adapter: semantic poses and events with no renderer.

Mounted input changes the role and presentation adapter and forces the Mounted
System profile. It does not create a second actor or a second motion.
The Select request stops new held-direction player steps and stays buffered
until the current stock player step has ended. At mount begin, a still-active
Follower motion receives a terminal cancel and releases its reservation before
its engine command is cleared. Mounted input then owns the next actor motion;
it must not inherit an unfinished Follower motion.

Initial mount attachment aligns both objects' current/next facing and backups
to the player's current facing before the first synchronized pose. This is an
attachment operation, not a per-frame override of motion-owned Hop spin.
The mounted presentation keeps the rider and Pokémon on the same logical base
position and puts the rider half a tile higher. Other headings keep the
half-tile offset behind each facing axis. South places the rider five-eighths
of a tile behind the Pokémon so the Pokémon is in front without a large gap.
This south-only depth offset does not change either actor's logical movement.
During mounted Walk, the field presentation adapter must publish the eased
player position to both MapObjects and refresh both stock graphics positions
in the same completed game update. The mount task republishes both positions
after its later crash-shake offset. The stock object graphics tasks run before
the mounted frame task, while the next draw moves the camera to the player's
new position. A MapObject-only update leaves both visible sprites one update
behind that camera target, so matching rider/Pokémon MapObject vectors alone
does not prove a fixed screen position.
The mount's native shadow is a separate field-effect slot. Its stock task also
runs before mounted presentation, so the same late refresh copies the mount's
current base position to the exact live shadow slot. The field-effect pool is
reached through the mount's MapObject manager and its FieldSystem; MapObject
offset `0x128` is not a FieldSystem pointer. The rider shadow stays
hidden; stock shadow visibility and lifetime still own both effects.

Mounted Walk adds a bounded sprite gait after the shared ground pose and seat
offsets are set, before both graphics positions are refreshed. The camera and
native shadow remain attached to the unchanged ground pose, not the bounce.
The rider follows the mount's vertical bounce with a small bounded lag, and
leans backward on acceleration and forward on braking. This presentation does
not change movement timing, speed variance, collision, Hop pauses or layering.

The four inheritable profile controls are `mountBounce` (0..3 pixels),
`mountStride` (16/32/48/64 pixels per cycle), `mountSettle` (0..3 strength), and
`mountLean` (0..3 pixels). Defaults are 2/48/1/1. Zero bounce and lean disable
those effects; zero settling makes the rider follow the bounce exactly.
The compact profile packs these four values into its former reserved byte16;
each field still resolves and overrides independently.

The gait phase follows distance, without restarting at a tile or speed change.
Its advance is capped at one eighth-cycle per game update at high speed to
avoid flicker. Body height changes by at most one quarter-pixel per update.
Settling limits rider/body separation to one eighth-pixel per strength level;
lean changes by at most one eighth-pixel per update. When movement stops, these
offsets settle to zero. Other motion modes reset gait so it cannot add a second
bounce to Hop or Teleport. A new mount session or player identity resets it too.
Repeated callbacks in one main update recompute from the same previous state;
they cannot advance the phase or damping twice.

The portable model is `lib/overworld/overworld_mount_gait_model.c`. Its adapter
and mounted presentation callback live in resident overlay159. The field
service table keeps its existing address and version. Gait code starts at
`0x01FF9D00`, presentation at `0x01FFA100`, and a zero-loaded 72-byte state
capsule at `0x01FFA500`. Boot reserves through `0x01FFA580` from the ITCM arena;
no field heap or implicit overlay BSS is used. Link and package checks enforce
these boundaries and preserve all older resident entry addresses.

Stock grass and dry-ground dust effects use a bounded renderer pool. The
model/field-effect slot count is 48 instead of the stock 32; the other stock
resource and memory budgets stay unchanged. Failed
creation must return FALSE from either initializer before storing or using a
missing handle.
The stock task creator then destroys the new task and resets its slot without
calling a destructor for an effect it never acquired. This presentation
failure cannot own or block player, Wild or Follower motion. The successful
initialization path is unchanged; a larger pool is not a substitute for safe
failure handling. Effect lifetime and recovery of pool capacity require their
own runtime evidence.
Each guard has its own at-most32-byte section appended to resident overlay129,
after existing code/data. Existing export addresses must not move. The image
must fit its actual `0x023D8000..0x023E0000` reservation; historical Summary
feature headroom is not a separate reserved memory owner.

The overlay-153 native-shadow position hook is a value client. It calls a Walk
helper that proves overlay 149 is loaded and requires the exact Thumb callback
at `0x023CD029`. The helper submits a 12-byte, versioned and sized value with
the object-derived slot and the shadow task's bound encounter generation. Wild
validates the object pointer against the current manager, Actor-owned map
generation, and encounter generation before it reads custom-jump state. It
returns only the encounter generation, `active`, and `baseY`. The stock task
stores the encounter token in the high half of its hidden-state word; patched
readers and writers use only the low half for the hidden flag. A missing,
stale, malformed, or inactive response means no position override. No Wild
private-state pointer crosses this service boundary.

### 10. Population and Lifecycle

Population controls encounter preparation, spawn timing, despawn, identity,
capture, and battle handoff. It consumes path advances for player-centered
distance, commits for terminal movement decisions, and explicit world events.
It does not infer movement by counting render frames.

Legacy `POOL` is a position-preserving spawn rule, not a request to search all
terrain kinds. An explicit POOL layer resets earlier destination selection to
the encounter pool's already chosen site. A modern explicit destination mask
can instead request a new site. These rules are separate from movement terrain
permissions; a species authored in a Surf pool must not silently become a land
encounter. Native headbutt handling keeps its separate canopy-source rule.
Proof must bind the same encounter's input site, finalized site and completed
landing; equality between the finalized site and its copied startup target is
not enough. Loaded physical surface legality remains a separate requirement.

Canopy is a shared physical-surface type, like Rooftop and Signpost. The build
generator reads the flat `tree01_un` family of land-mesh materials. Each UV
repeat is one two-by-two tree footprint. Only its south/bottom row is a crown
support: that row aligns with the high edge of the paired `tree01` or
`tree01_re` billboard. The north row is the visible tree shoulder. The
generator removes overlap with authored surfaces and compresses the supports
into catalog rectangles. It scans all 287 real map matrices. The generic
one-block `single` matrix is excluded because its reused edge has no stable
neighboring model. Reused land blocks must produce the same local Canopy mask
or generation fails. The game does not scan land archives or models at runtime.

Canopy height is the checked native map height plus `0x31580` FX32. The common
tree crown is at `0x41580`, while its flat native ground plane is at `0x10000`;
the catalog stores only their difference. The native-height sample keeps the
result correct on raised or lowered map ground. The catalog entry returns the
reserved canopy surface ID `0xFFFE`, while ordinary native ground remains
`0xFFFF`. Landing applies the resolved height to the actor. Canopy is
catalog-only; behavior-6 collision edges are not a fallback surface. Whole
land model `0xD0` is a headbutt interaction model, not a traversable canopy
footprint.

The shared Hop landing gate rejects matrix padding before terrain or surface
matching. `MAP_EVERYWHERE` cells in the outdoor matrix hold placeholder land
models and are not playable. The gate classifies each candidate on its own:
padding beside a valid elevated landing does not invalidate that landing, and
one rejected candidate does not end the caller's remaining candidate search.
Mounted and Wild actors use the same rule.

Explicit destination searches preserve row-major candidate order, eligibility,
occupancy checks, and reservoir-sampling RNG calls. Avoid player-front queries
when the mask cannot use them. Catalogued surfaces, including Canopy, must
still veto underlying terrain.
The host spawn-search fixture checks selection parity and these work bounds.

Move From Off Screen keeps the selected spawn tile as its immutable target.
It starts with the same four cardinal origin rays as Hop and searches inward:
origin A is between1 and16 tiles from selected spawn tile B. A is prepared at
least five tiles beyond the player-relative inclusive8-by6 camera extent, which
reserves one update of player movement before its required four-tile creation
margin. Land actors can enter from
any walkable land tile; the spawn destination still keeps its authored terrain
rule. If no eligible off-screen origin exists, the spawn is rejected. It never
falls back to an on-screen appearance. Otherwise,
it starts an Owner-lane destination trip and replaces the player target with
the immutable spawn tile. The shared chase controller selects and
runs each Walk, Hop, or Teleport segment with the resolved Owner movement
parameters. Each segment must complete its normal Motion transaction before
the next segment starts. Move From Off Screen has no movement-policy
exceptions: Walk pause, Movement Chain actions, stamina, tired effects, turn
skid, battle rules, and the authored previous-tile rule work exactly as they
do for any other destination trip. A normal tired cycle can pause the trip and
the same Owner trip resumes afterward. On arrival, and only after the normal
movement completion pipeline is idle, the actor returns control to its resolved
Routine and never snaps to the target.

A resumed destination scan stops after its final candidate batch. Spawn-start
selection continues on the next update. This keeps both bounded operations out
of the same frame while reusing the prepared profile and spawn metadata.

Fly In is a distinct Placement spawn locomotion. It validates and stores the
destination and its physical surface height before choosing an offscreen origin
at flying height. Its motion uses independent start and target heights, no Hop
arc, and a monotonic descent. Intermediate ground, water, walls, and lower
surfaces do not become landing checks; only the destination must be a legal
placement.

The destination surface is the only landing-height source. The visual descent
is relative to that height, its terminal offset is exactly zero, and the actor
and sprite finish at that exact height. Fly In then hands control to the normal
Routine. Its universal descent lasts 144 frames. It exposes no per-profile
timing or arc controls.

Fly In uses the same ground-plus-lift presentation as Jump: the sprite descends
above the sampled ground, and its native shadow follows the rendered tile's
ground height. The landing tile remains the logical owner, but it does not
determine the shadow height for the whole path. On surfaces that normally
suppress native shadows, Fly In uses that same surface rule. Landing restores
the normal surface-based shadow state.

Off-screen Hop startup keeps that destination and selects a loaded origin
exactly eight cardinal tiles away. An explicit spawn-entry intent grants its
startup clearance; ordinary eight-tile Hops do not gain spawn-entry rules. The
origin must be at least four tiles beyond
the current player-relative inclusive8-by6 camera extent. Rank visible travel
among eligible origins. If the destination has moved just outside one camera
axis, an entirely out-of-view ray or a ray that reaches view only at its
destination remains an eligible zero-travel fallback. Prepared origins reserve
one extra tile beyond the required four-tile margin. A queued spawn commits on
the next update, so one tile of player movement cannot make its origin unsafe.
This does not repeat encounter, profile, metadata, or destination resolution.
Reject a spawn with no eligible origin without changing its target or falling
back to an on-screen appearance. This origin contract does not establish
landing height.

Stock saves restore dynamic native map objects without the live encounter
ownership that created them. Before allocating a new reserved Wild slot ID,
the presentation adapter must reject occupied, pending, retained or foreign
bindings, then delete only unowned script2074 remnants through the native
destructor. It validates every matching object before any deletion. This keeps
stock first-active-ID lookup aligned with the new logical slot and prevents a
saved object from hiding the current follower. Cleanup covers all ten reserved
slots and never edits the source save. `host.spawn-identity` checks the actual
caller/service bodies; `actor.follower-direct-load` checks the normal saved
follower in the game. Neither substitutes for natural spawning or motion proof.

`PATH_ADVANCE`, `COMMIT`, and `FIELD_EVENT` share one non-zero, wrap-safe
32-bit world-event sequence. The population model accepts only a strictly
newer sequence for the current field epoch. It reports a duplicate separately
and rejects stale input. Invalid field-event kinds are rejected before the
sequence is recorded. A Rebind event changes the population center and field
epoch and immediately schedules complete reconciliation.

The resident population entry owns the refill countdown and the bounded
maintenance schedule. Its control interface accepts a refill delay or an
explicit reconciliation request and returns at most one despawn, refill, or
reveal work item per frame. The wild engine adapter executes that item and
reports the next delay; it does not keep a second timer or phase machine.

Distance despawn needs two scheduled samples beyond 16 tiles. Normal movement
does not discard those samples. A confirmed actor finishes its current motion,
cannot start another AI decision, including later in the same frame, and
requests population maintenance once its Motion policy is idle. That
maintenance rechecks the live distance and exact encounter identity before
removal. Returning to16 tiles or less cancels the
pending removal. Followers, shiny encounters, throw participants, and every
Move or Hop From Off Screen startup phase remain hard protected and collect no
far samples.

Each usable Wild frame sends one typed, versioned value call to the population
entry. The call carries the Field and Wild adapter inputs and returns bounded
result flags. Actor does not read Wild private storage. Wild owns the queued
spawn, terrain work mask, selected slot, scan budget, and staged Hop handles in
its existing runtime allocation.

An ordinary refill prepares one encounter and its own destination in a runtime
buffer. The next usable movement update spends its entire maintenance budget
on committing or cancelling that value; reveal waits for a later update.
The refill also admits at most one terrain attempt per update. A pending mask
retains the ordered Headbutt, Fishing, preferred Land/Surf and alternate work;
the original Land/Surf slot is kept and a newly occupied slot cancels that
fallback. Full slots need no attempt. A logical Land/Surf attempt keeps the
legacy16-candidate limit and cursor order. All16 checks fit in one bounded
terrain-attempt update; the attempt count remains one, so the change does not
expand the old search to256 candidates. Help-child position searches use the
same16-check bound. A profile destination scan initializes without a terrain
query, then checks at most12 eligible destinations per update and completes
its240 eligible positions in20 resumed batches. The prepared encounter,
profile, metadata, class and RNG state are reused across those batches.
The initial chance gates run once, and the existing density delay is set when
the series ends. Pending attempts finish before the resident REVEAL item; they
add no timer or movement owner. Field busy/context loss clears both the pending
terrain mask and position count with the queued candidate. A resumed search
draws no new start RNG; later encounter and profile RNG runs only after a
position becomes ready or the final Land/Surf fallback is reached.
Cold refill work first loads spawn metadata, then behavior data on separate
updates, before it creates an automatic follower or wild object. These two
attempts retain pending maintenance and draw no RNG or refill timer; loader
failure remains latched by the normal loader. Teardown resets warmup with the
owned caches. Direct user release retains its separate path. This adds two
updates to a cold automatic spawn, not to each refill or movement step.
Ordinary refill checks the current follower identity under one synchronous
native party read lock. The selector's species/egg/level/HP checks must first
validate that same Pokémon, including the stock checksum check. Matching keeps
the original field order and releases only the lock it acquired, even on a
mismatch. No party value or lock is cached across updates; this avoids repeated
decryption without changing selection, refill timing or encounter RNG.
The native party move query used by the field input loop also groups the four
move reads under one native lock. Its first egg read still validates checksum;
eggs and Bad Eggs skip the move reads. First-match order, current party data,
and the no-match value remain stock. Both exits release only the acquired lock.
This is bounded synchronous work, not a party cache or a change to spawn timing.
The buffered value reserves its slot and contributes to the existing refill
count. Creation rechecks field/map/manager identity, slot generation and vacancy,
target/origin terrain, surface, player-relative destination, occupancy, spacing,
behavior limit and any saved-shiny record. A failed check discards the value:
no reroll, retarget, or saved-shiny removal. Field-busy/context loss cancels it.
This adds no per-frame allocation, second countdown, or second motion owner.
The native observer authenticates successful enqueue and carries its exact
finalizer receipt across only one completed queue; stale receipts cannot pair.

`Inspect(POPULATION)` returns a value-only
`OverworldActorPopulationSnapshot`. Its `workPending` field is the normalized
boolean form of private maintenance state; phase and dirty bits never leak
through the public ABI.

Overlay 158 loads at `0x023B6B00-0x023BAB00`. The public actor facade and
service directory keep their fixed addresses. Actor and population code is
bounded below `0x023BA170`. Actor state starts at
`0x023BA170`, uses no more than `0x0990` bytes, and must end at or before overlay 157
at `0x023BAB00`. The fixed capacities are 10 actors, 2 queued commands, 2
acknowledgements, and 16 trace events. This layout preserves the full field
heap; actor growth must not borrow field-startup memory.

The two lane selector callbacks have fixed private ABI slots at `0x023B6BB8`
and `0x023B6BCC`. Overlay 149 calls their Thumb addresses. The actor linker and
debug generator verify both slots so a code-size change cannot redirect wild
movement into resident data.

The transition coordinator owns field epoch and map-generation changes. The
resident field adapter starts one sequence and keeps its inputs and cumulative
acknowledgements across retries. It runs the returned work in this order:
canonicalize engine state, rebind retained presentations, then resume or
discard. It acknowledges work only after the wild adapter succeeds.
After DISCARD, the wild adapter can clear its local map marker and rearm its
map/object-manager view. That rearm preserves the generation supplied by the
Actor owner; it must not increment a second map counter. The permanent
`actor.binding.current-context` scenario checks a naturally bound actor against
the current public owner context before accepting its motion evidence.

Compatibility ABI v3 exposes that current context as one pointer-free value:
the low 16 bits are the Actor-owned field epoch and the high 16 bits are the
Actor-owned map generation. The compatibility entry keeps its retired update
slot at byte offset 12 zero and places `getContext` at byte offset 28. The field
driver reads this value before it starts a transition and uses the full packed
context as its sequence identity. A counter in the unloadable field overlay
would reset while the Actor retains its completed receipt, causing the next
map change to be rejected as a conflicting retry. Both context halves advance
together and skip zero; the full packed sequence retains wrap ordering. Active
retries keep the captured value. The actual-C field reload regression checks
reload, work retries, completed receipts and generation wrap in the host gate.
If a required unloadable
adapter cannot be loaded, the driver returns `UNAVAILABLE`, keeps the prior map
marker, and retries later; it does not run a second transition owner or discard
retained actors as a fallback.

Queued actor commands keep their expected field epoch and revalidate it when
the queue executes, not only when the command is accepted. A queued Wild
battle stores both map generation and encounter generation and discards the
request if either identity changes before battle start.

During Wild Rebind, an old `LocalMapObject *` is never dereferenced as proof.
Every active slot considered for preserve must first have its bit in
`retainedActorMask`. The adapter then inspects the public Actor value, requires
a non-zero actor generation, and matches slot, next field epoch, next map
generation, encounter generation, and subject identity. Only after those
checks does it resolve the stable object ID through the current `MapObjectMan`
and prove current-manager membership, active state, expected ID, and battle
script before replacing the pointer. A missing mask bit or any identity failure
rejects rebind. The field transition owner then downgrades the preserve
disposition to discard; the Wild or Mount adapter does not bind new context by
itself.

Successful presentation normalization must be followed by the existing role
pass-through policy before rebind completes. Normalization clears transient
object flags; it does not own collision policy. The follower remains
pass-through, ordinary Wild actors remain solid, and Wild Teleport retains
its existing active/flicker/player-tile conditions. Check this flag on the
same retained live actor across the boundary, not only at initial spawn.

Warp and battle readiness use one actor-owned gate rule. A transition closes
the gate. Otherwise, any active input-owning actor with a reservation or a
motion phase other than `IDLE` or `CANCELED` closes it. The mounted field-input
adapter consumes the Warp query and suppresses only transition signals while
closed. The Wild battle adapter consumes the Battle query before it starts or
services a queued encounter.

The wild overlay receives `OverworldActorTransitionCall` through its existing
fixed callback slot. The field driver sends the same typed call directly to the
resident mount adapter before it invokes wild transition work. The throw helper
receives a separate typed presentation command through its existing fixed
callback slot. Negative slot numbers are not lifecycle commands.

### 11. Observation

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

- Mount action overlay 160 occupies ITCM `0x01FF8620..0x01FF9800`, including
  the Walk easing and graphics entries before its action entry at `0x01FF8800`.
  Mount chain overlay 159 occupies `0x01FF9800..0x01FFA580`, including the
  mounted gait code and explicit state capsule. The stock ITCM autoload ends
  at `0x01FF8620`. Boot reserves both adapters by setting the ITCM arena low
  to `0x01FFA580`, then loads
  them through `HandleLoadOverlay` so file reads do not use DMA into ITCM.
  Heap 3 stays at `0x106730`; it must not be cut to make a code home.
  The SDK FNT/FAT archive and its `0xC00` guard stay below actor overlay
  158 at `0x023B65A0`. Package checks verify these ranges and the loader.
- Overlay 158 loads at `0x023B65A0..0x023BAB00`; its core entry is at
  `0x023B6B00`. The fixed facade and resident
  actor/population code occupy the range through `0x023BA170`. Bounded state
  starts there and ends before `0x023BAB00`.
  The resolver's five-byte legacy spawn lookup uses target-selector slot
  padding at `0x023B6BD8`; its entry and the following slot stay fixed.
- The public facade, compatibility entry, debug layout, resolver, motion,
  population, and movement-policy entries have fixed addresses and
  magic/version/size checks.
- The version-5 movement-policy entry publishes the private Walk policy table
  and the version-1 condition adapter. Actor validation checks the adapter's
  magic, version, and 16-byte size. The adapter builds condition frames and
  records condition trace facts; the portable evaluator remains the only
  condition-truth owner.
- Walk client overlays link to individual fixed helper functions from
  `0x023BF400` through `0x023BF9A0`. The old Walk service-table range at
  `0x023BF400..0x023BF487` now hosts the direct `DecelerateTime` and
  `ProposeStep` helpers. It is not restored as a service table or a second
  state owner.
- The Field terrain-stream engine helper is physically hosted at
  `0x023BFC60..0x023BFFEA` in resident overlay 153. It receives the typed call
  and a private pointer to Field's 24-byte stream state. The Field
  service remains the sole caller and state owner; its state still starts
  zeroed on every load. The state owns the watcher, motion identity, and one
  packed Actor field context. Mount is a value client. A transition `REBIND`
  replaces that context before motion resumes. This is code placement, not a
  Walk or Mount streaming owner.
  Link and package checks protect the prior Walk helpers, the exact Thumb
  entry, and the fixed mount-abort helper above it.
- Unloadable overlays receive bounded value inputs and return bounded values.
  The Wild presentation cleanup code has an explicit host in overlay153 at
  `0x023C0000..0x023C0400`, within its existing resident reservation. Wild
  remains the caller and state owner; the helper adds no persistent state.
  The exact Thumb entry and upper bound are checked without moving existing
  move-history, Field, Walk or mount entries.
  No facade state retains pointers into an unloadable overlay.
- The same Wild-owned resident tail hosts the native occupancy reader at
  `0x023C0184`, after spawn-identity cleanup and before `0x023C0400`.
  Its call borrows the field and ignored-object pointers; it stores nothing.
  Wild retains the three original query wrappers and their argument contracts
  for the native observer. Query modes preserve the original logical-player,
  non-player and exact-height rules, including their early returns. This is
  code placement, not a new collision policy or motion owner. Actual-C parity,
  typed Thumb callers, exact packaged bytes and the unchanged resident bound
  are required checks; the new source and object are sealed build inputs.
- The 40-byte Wild overlay entry keeps its fixed layout. Byte offset 32 is the
  native-shadow value-copy service; its request and response contain no
  pointers, and its invalid-entry result is a safe no-override.
- Spawn guard/proximity/surf code uses the existing History tail
  `0x023C025C–0x023C0400`. Unchanged spatial queries use Helper's
  `0x023C7F60–0x023C8000` and Selector's `0x023C2200–0x023C22A0` tails.
  These are Wild-owned read-only functions, not new Helper/Selector policy.
  Selector is linked to Wild; all calls into Helper follow helper preparation
  or a live actor/profile, and teardown stops those calls before unloading.
  Slot limits, typed Thumb imports, and exact packaged bodies are checked.
- Selector owns `0x023C22A0–0x023C3000` for the condition evaluator service.
  Its existing callbacks stay below
  `0x023C22A0`. Field teardown unloads Selector before another cold overlay
  can use this shared tail. The behavior-data overlay begins at
  `0x023C3000`, so the two images do not overlap.
- ARM/Thumb interworking and `LONG_CALL` requirements remain explicit adapter
  contracts.
- Normal field walking friendship uses a 34-byte wrapper at `0x023CCF90`.
  It takes one native party-data lock, calls the unchanged stock friendship
  routine, and releases the original lock token. RNG order, update frequency
  and friendship rules remain stock; no work is deferred. This entry relies
  on the normal field input path's prior `CountAlivePokemon` validation of
  every party member, not on daycare (which does not validate every step).
  Only the walking call at `0x021E793E` redirects here. Field131 is already
  required by the field-input host before this call.
  Existing Field BSS addresses stay fixed. Objcopy now includes their zero
  bytes before the executable tail, so overlay131's loader BSS size is zero:
  clearing the old BSS length after the larger file would erase adjacent Wild
  data. Shared package metadata checks the zero gap, fixed bounds, three native
  Thumb calls and packaged walking caller. No new persistent state is added.
- Field imports its five memory/division helper exports as typed Thumb
  functions from the resident core bridges. A raw stock ARM address is not a
  valid Thumb `BL` target. Package proof checks all Field callers and the exact
  bridge bodies, including their instruction-mode switch and return ABI.
- Actor, Selector, Wild, and the Field terrain helper also retain Thumb
  function metadata for their resident core imports. An odd linker address
  alone is insufficient: a generated `BX pc` / ARM-branch veneer can enter
  Thumb code in ARM mode. Package proof rejects that path and checks the real
  core targets and typed caller bindings; removing a local helper bundle must
  preserve this call contract.
- A cross-overlay tail bridge preserves every argument register used by its
  declared C signature, plus `sp` and `lr`. In particular, a five-argument
  motion-boundary bridge cannot use `r3` as an unpreserved target scratch
  register because `r3` carries the fourth argument.
- Every overlay has a byte budget checked from the linker map and packaged ROM.
- The structural ownership scan must include every linked client, including
  Walk overlay 153. Omitting a client is a gate failure, not proof that the
  client has no private-state or retired-entry reference.
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
- Vision runs only at intent boundaries. It rejects candidates by cone before
  short-line occlusion work and examines at most the ten-actor world view.
- Profile resolution is cached by source revision, subject, forced layers,
  active conditional applications, and the captured target source.
- Spawn metadata uses one validated, reusable blob. The build generator and
  runtime loader share `OVERWORLD_WILD_SPAWN_METADATA_MAX_BLOB_SIZE`; generated
  data above that bound must fail the build, not silently force file reads for
  every normal spawn. Allocation uses the actual blob size. Failed loading
  retains explicit fallback behavior and teardown frees only owned memory.
  Unmounted cadence tests reject an observed base-form metadata cache miss.
- The persistent behavior catalog belongs to the field session and uses
  `HEAPID_WORLD`. The smaller persistent spawn-metadata cache uses
  `HEAPID_DEFAULT`. This leaves stock field scripts and message banks with
  `17,988` more bytes than storing both catalogs on the field heap, while the
  metadata cache remains below the default heap's capacity. Temporary archive
  handles use `HEAPID_WORLD` and close immediately after loading. Teardown
  frees each catalog through its recorded allocation.
- Resolved behavior is copied or referenced as one coherent value, not rebuilt field by field during motion.
- Trace writes occur only when a filter is armed.
- The trace ring is fixed-size and overwrites old records.
- Normal `Tick` work is bounded by active actors and active motions.
- Map reconciliation is bounded by actor count.
- Canopy discovery across all real map matrices is build-time work. Runtime
  canopy queries use the cached land-block surface directory and its bounded
  local rectangle list. The packed 8-byte surface entry stores type, native
  height mode, and signed anchor offsets. Generated rows, blob size, per-block
  row count, and reused-land parity must pass before packaging.

## Locality and deletion tests

A successful migration passes these tests:

- Adding a locomotion changes one planner, the shared executor only when its lifecycle is genuinely new, profile schema, and scenarios. It does not add a mounted copy.
- Adding a role changes one controller or presentation adapter. It does not copy movement mechanics.
- Changing profile composition changes the portable resolver once. It does not change ROM C, legacy Python, V2 Python, and JavaScript separately.
- Changing streaming changes the world/executor adapter once. It does not patch Walk, Hop, and Teleport independently.
- Removing the actor facade would expose significant lifecycle, motion, and transition complexity. Removing a private adapter would remove only its engine-specific details.

## Anti-patterns

- Do not add another movement owner or parallel runtime array.
- Keep mount tuning in the Mounted System profile. Do not copy profile fields
  or motion rules into the mount controller.
- Do not model flat Walk as a behavior-level zero-height Hop.
- Do not infer semantic commits from coordinate changes. Emit explicit path
  advances and one explicit terminal commit.
- Do not let presentation write logical position.
- Do not use private raw memory offsets as the long-term verification interface.
- Do not layer a new path permanently over an old path. Compare, switch, then delete.
- Do not treat a source-string verifier as proof of runtime behavior.
- Do not represent pickup or carry ownership as a profile or behavior class.
