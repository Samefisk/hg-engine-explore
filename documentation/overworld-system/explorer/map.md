# Overworld Pokémon system

A source map of how Pokémon act and move in the field. Start with the whole system. Open a block to see its parts. Follow a link to see what passes between them.

This map shows logical owners and data flow. It is not a list of every C call. Nintendo DS overlays store code; an overlay is not a system owner. The code still uses compatibility adapters. A source link does not prove game behavior. Use the current work table for proof gaps.

The map was read against local sources on 2026-10-04. Script control is marked as a contract because the portable role reducer currently accepts only Wild, Follower, and Mounted. The builder checks profile order and Waddle's classification against the saved schema and catalog.

## system: Overworld Pokémon system
Parent: `none`
Kind: `System`
Grid: `0,0`
Summary: One actor owns its identity, behavior state, and move.
Rule: One actor has at most one active motion.
Sources:
- `CONTEXT.md`
- `documentation/overworld-system/README.md`
- `documentation/overworld-system/architecture.md`
- `documentation/overworld-system/roadmap-progress.md`

Profiles supply behavior rules. Role control chooses intent: what the actor wants to do. Move policy sets speed and action rules. Motion checks, reserves, and runs one move. World checks supply legal places. Combat checks contact and changes HP; its adapters request shared knockback. Display code applies the shared pose. Field life adds actors and handles map changes. Tools read state and check claims.

## behavior: Behavior rules
Parent: `system`
Kind: `Module`
Grid: `0,0`
Summary: Build the rules for this Pokémon and this situation.
Rule: JSON is the authoring source. Generated C data is output.
Sources:
- `data/overworld_behavior_profiles.json`
- `documentation/overworld-system/authoring-debugging.md`

The subject holds Pokémon facts, such as species, form, level, and identity. A selector chooses a starting profile. The resolver combines that profile with matching applications and admitted conditions. It returns resolved Owner and Tired lanes, plus a record of which profiles supplied the values.

## schema: Profile fields
Parent: `behavior`
Kind: `Module`
Grid: `0,0`
Summary: Define field names, units, bounds, and the packed layout.
Rule: Generate ROM and host metadata from the same schema.
Sources:
- `tools/overworld/behavior_schema.json`
- `scripts/generate_overworld_behavior_schema.py`
- `include/generated/overworld_behavior_schema.h`

The schema defines what a profile can change. It supplies shared names and layout data to the ROM and the Workshop. It does not choose an actor's next move.

## catalog: Profiles and pools
Parent: `behavior`
Kind: `Module`
Grid: `1,0`
Summary: Store reusable behavior blocks and their ordered uses.
Rule: Later matching applications override earlier fields.
Sources:
- `data/overworld_behavior_profiles.json`
- `data/OverworldWildBehaviorData.c`
- `documentation/overworld-system/architecture.md`

Default is the complete root. Other profiles inherit from one parent. A profile application is one ordered use of a profile. Named pools are reusable Pokémon sets. The build expands pools before packaging. Conditional profiles have conditions with their own subject pools; they have no normal Pokémon assignment.

## classifications: Profile order
Parent: `catalog`
Kind: `Rule`
Grid: `0,0`
Summary: Routine → Placement → Follower → Capability → Attitude → Style → Follower/Mount → Modifier.
Rule: Preserve manual order inside each classification.
Sources:
- `CONTEXT.md`
- `tools/overworld/schemas/behavior-authoring-v5.schema.json`
- `data/overworld_behavior_profiles.json`

Routine sets ordinary movement and rhythm. Placement sets spawn placement. Follower supplies normal following before Capability, so an active Capability can replace it. Attitude sets a response to a target or world fact. Style changes how movement looks. Follower/Mount holds the later role overrides. Modifier supplies the final compatible changes. System and Conditional mark ownership and activation; they are separate from classification. Waddle uses the Style classification.

## bindings: Role profiles
Parent: `catalog`
Kind: `Rule`
Grid: `1,0`
Summary: Follower and Mounted are runtime-linked System profiles.
Rule: Mounted inherits normal Pokémon behavior, without Follower overrides.
Sources:
- `data/overworld_behavior_profiles.json`
- `lib/overworld/overworld_behavior_resolver.c`
- `src/overworld_mount_overlay/overworld_mount_overlay.c`

Follower supplies follow rules. Mounted is an empty override on the Pokémon's normal selected Owner behavior. It keeps that behavior's movement and capabilities. Dismount restores the same actor's Follower policy binding. A mount session is not itself a profile.

## conditions: Check conditions
Parent: `behavior`
Kind: `Module`
Grid: `0,1`
Summary: Check triggers, keep timers, and capture valid targets.
Rule: Evaluate during ordinary autonomous movement and at intent boundaries. Keep the accepted move unchanged.
Sources:
- `lib/overworld/overworld_behavior_conditions.c`
- `lib/overworld/overworld_behavior_condition_runtime.c`
- `lib/overworld/overworld_behavior_condition_adapter.c`

Each condition entry is independent. The last admitted entry in one profile wins. Several conditional profiles can apply together. While-true activation lasts while the condition is true. Timed activation lasts for its duration; cooldown starts at the trigger. A stale captured actor target ends that activation. The evaluator returns admitted applications and targets. It does not compose profile fields or start motion.

## vision: Sight checks
Parent: `behavior`
Kind: `Module`
Grid: `1,1`
Summary: Check range, facing, and terrain that blocks sight.
Rule: Conditional profiles cannot change the Vision that triggers themselves.
Sources:
- `lib/overworld/overworld_vision.c`
- `include/overworld_vision.h`
- `src/overworld_wild_helper_overlay/overworld_condition_visibility.c`

Current Vision is resolved at actor bind from Default, normal applications, and the forced role profile. A condition can use that stable Vision or its own Custom Vision. The shared service supports Pokémon and the player. Initial defaults are a 90-degree forward cone, three tiles of range, and awareness of all eight adjacent tiles. Solid terrain blocks sight. Actors do not.

## resolver: Combine profiles
Parent: `behavior`
Kind: `Module`
Grid: `0,2`
Summary: Produce final behavior values and their source record.
Rule: The ROM and Workshop use the same portable C resolver.
Sources:
- `lib/overworld/overworld_behavior_resolver.c`
- `include/overworld_behavior_resolver.h`
- `scripts/overworld_behavior_profile_viewer.py`

The resolver materializes the selected profile, then walks the shared application order once. Normal matches and admitted conditional applications supply field values. It validates target source data, resolves Tired, normalizes both lanes, and returns a fingerprint. That fingerprint identifies resolved values, not one Pokémon. Owner and Tired are behavior lanes, not roles or profile classifications.

## roles: Role control
Parent: `system`
Kind: `Module`
Grid: `2,0`
Summary: Choose what the actor wants to do.
Rule: Role control requests intent; it does not own coordinates.
Sources:
- `lib/overworld/overworld_role_controller.c`
- `include/overworld_role_controller.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Wild, Follower, and Mounted share role and action rules. Compatibility adapters still collect inputs and start engine work. A role is the source of control. It is not a profile classification or a locomotion type.

## wild: Wild control
Parent: `roles`
Kind: `Adapter`
Grid: `0,0`
Summary: Choose wander, chase, flee, rest, and battle intent.
Rule: Check conditions before choosing the next intent.
Sources:
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `lib/overworld/overworld_role_controller.c`

Wild uses the resolved behavior and a bounded world view. It asks for the next action only when control has returned. A Ram action emits a direction-locked Walk intent with speed and reaction rules. Ram is not a separate movement engine.

## follower: Follower control
Parent: `roles`
Kind: `Adapter`
Grid: `1,0`
Summary: Follow the player and handle release intent.
Rule: A follower keeps one actor identity when control changes.
Sources:
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_follower_release_overlay2/overworld_follower_release_overlay2.c`
- `src/overworld_follower_selector_overlay/follower_selector_input.c`

Follower behavior uses the runtime-linked Follower profile. Follow Hops still use shared planning and the authored Hop time and pause. Follower rules do not feed Mounted resolution.

## mounted: Rider input
Parent: `roles`
Kind: `Adapter`
Grid: `0,1`
Summary: Turn player direction input into actor intent.
Rule: The player and Pokémon execute one shared motion.
Sources:
- `src/overworld_mount_overlay/overworld_mount_overlay.c`
- `src/field/overworld_mount_field_input.c`
- `src/overworld_mount_action_overlay/overworld_mount_action_overlay.c`

The mount session binds the rider and current follower into one actor under player input. It uses normal Pokémon Owner behavior plus Mounted. Moving actions use the player engine anchor. Autonomous follower conditions do not run while Mounted owns control.

## held: Held actor control
Parent: `roles`
Kind: `Adapter`
Grid: `1,1`
Summary: Suspend free planning during pickup, carry, throw, and drop.
Rule: Held control is internal Wild control, not a behavior profile.
Sources:
- `src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `lib/overworld/overworld_throw_binding_native.c`
- `documentation/overworld-system/architecture.md`
- `CONTEXT.md`

Held control temporarily stops autonomous intent. Pickup, carry, release, and cleanup keep the same actor identity. Trigger and Cargo bindings belong to the shared Throw route. Flight contact belongs to the combat contact adapter; being held is not permission to deal damage.

## throw: Shared Throw route
Parent: `roles`
Kind: `Adapter`
Grid: `1,2`
Summary: Find Cargo, find a launch position, then release the held actor.
Rule: Wild and Follower use the same conditional Capability applications.
Sources:
- `data/overworld_behavior_profiles.json`
- `lib/overworld/overworld_throw_observation_native.c`
- `lib/overworld/overworld_throw_binding_native.c`
- `src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c`
- `src/player_health_contact.c`
- `documentation/overworld-system/architecture.md`

Find Throw Cargo, Find Throw Position, and Throw Held Actor compose in that order. Trigger keeps the initiating target; Cargo keeps the distinct actor to pick up. Binding reads refresh their current positions and validate identity. The helper supplies reservation, pickup, carry, launch, and cleanup. Conditions choose the next stage. The launched actor receives the resolved attack and contact settings; the combat adapter validates airborne contact.

## scripted: Script control
Parent: `roles`
Kind: `Contract`
Grid: `0,2`
Summary: A public role for explicit script intent.
Rule: Do not read this public role as proof of a complete script controller.
Sources:
- `include/overworld_actor_system.h`
- `lib/overworld/overworld_role_controller.c`
- `documentation/overworld-system/architecture.md`

The facade names Scripted as a role. The current portable role reducer admits only Wild through Mounted. Script control belongs to the target contract and is shown here so the gap stays visible.

## actor: Actor system
Parent: `system`
Kind: `Module`
Grid: `1,1`
Summary: Own actor identity, state, requests, and observation.
Rule: Engine pointers do not belong in public commands.
Sources:
- `include/overworld_actor_system.h`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`

The facade supplies Apply, Tick, and Inspect. Each resident actor slot owns its snapshot, motion state, and policy state. The public actor handle has generation and context data so a recycled slot cannot become the old actor. Fixed overlay tables are deployment adapters, not the public domain model.

## identity: Actor identity
Parent: `actor`
Kind: `Module`
Grid: `0,0`
Summary: Bind a subject to a live actor handle.
Rule: Recheck field, map, encounter, and actor identity before use.
Sources:
- `include/overworld_actor_system.h`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/pokemon_move_history_overlay/overworld_spawn_identity.c`

At most ten actor slots are present in the current interface. A handle includes generation data. Slot number or a retained engine pointer alone is not identity. A fresh bind clears the previous subject's policy state.

## commands: Apply commands
Parent: `actor`
Kind: `Module`
Grid: `1,0`
Summary: Validate and queue bounded value-only requests.
Rule: A retry means the command was not queued or acknowledged.
Sources:
- `include/overworld_actor_system.h`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`

Apply uses a wrap-safe increasing sequence. A duplicate in the acknowledgement ring returns its old reply. An older replay outside that ring is rejected. Queued commands check the expected field epoch again when they run.

## tick: Tick the field
Parent: `actor`
Kind: `Module`
Grid: `0,1`
Summary: Apply queued work and advance each motion timeline once.
Rule: Display adapters read time; they do not advance it.
Sources:
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `lib/overworld/overworld_motion_model.c`

Tick establishes the field boundary, runs accepted commands, and advances actor motion on a usable field frame. Engine adapters still prepare some candidate work and apply game-object changes. The graph does not imply that all work is inside Tick.

## inspect: Read state and trace
Parent: `actor`
Kind: `Module`
Grid: `1,1`
Summary: Return actor, population, gate, system, and trace values.
Rule: Inspect is read-only and typed.
Sources:
- `include/overworld_actor_system.h`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`

Observation is part of the system. A bounded trace ring reports semantic events. The debug descriptor lets host tools decode state without treating private memory offsets as a domain interface.

## policy: Move policy
Parent: `system`
Kind: `Module`
Grid: `2,1`
Summary: Set speed, direction, chains, and action rules.
Rule: A rejected direction must not become a stop request.
Sources:
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`

Policy uses resolved behavior and past terminal outcomes. The shared Walk transaction is INPUT → START_RESULT → COMMIT. A rejected start does not change committed direction. The accepted move produces one terminal update to policy.

## walk-policy: Walk speed and skids
Parent: `policy`
Kind: `Module`
Grid: `0,0`
Summary: Keep speed and reduce turn or stop input.
Rule: A real NONE input has separate stop and skid rules.
Sources:
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`
- `src/pokemon_move_history_overlay/overworld_walk_module.c`

The shared reducer owns speed changes, committed direction, turn and stop skids, and reaction intent. An ordinary Walk needs a clear next tile. An actual turn skid needs its full corridor and first tile after the turn. A blocked turn path brakes without a crash.

## chains: Move chains
Parent: `policy`
Kind: `Module`
Grid: `1,0`
Summary: Count eligible moves and select the next chain action.
Rule: Count move decisions, not skid tiles or render frames.
Sources:
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c`
- `src/overworld_mount_action_overlay/overworld_mount_action_overlay.c`

A nonzero move count enables a chain. The chain can choose a pause, Hop, look, or reposition action. NONE ends with no action. PAUSE waits. A temporary engine-start failure keeps the exact selected action pending. Wild and Mounted use shared chain state.

## wander: Look and wander
Parent: `policy`
Kind: `Module`
Grid: `0,1`
Summary: Choose allowed directions and keep ordinary action rhythm.
Rule: A blocked search keeps committed facing and waits before a new search.
Sources:
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

The policy entry owns look and wander decisions. Wild supplies context and executes accepted work. A separate explicit turn-around action can change facing without starting a step.

## reactions: Crash and stomp
Parent: `policy`
Kind: `Module`
Grid: `1,1`
Summary: Select feedback for accepted actions and blocked Ram movement.
Rule: Feedback does not own motion.
Sources:
- `lib/overworld/overworld_role_controller.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`
- `src/overworld_mount_chain_overlay/overworld_mount_gait.c`

Ram can lock direction and request stomp or crash feedback. Heavy Stomp is a separate capability. Adapters publish sound and effects from policy and terminal outcomes. Feedback frames do not add extra moves.

## motion: Shared motion
Parent: `system`
Kind: `Module`
Grid: `2,2`
Summary: Plan, reserve, run, and end one move.
Rule: Walk, Hop, and Teleport share ownership and completion rules.
Sources:
- `lib/overworld/overworld_motion_model.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `documentation/overworld-system/architecture.md`

The lifecycle is Intent → Policy → Plan and validate → Reserve → Begin → Tick → Path advance → Commit pending → Commit or cancel. A move snapshots its behavior fingerprint and field epoch. New behavior changes the next intent, not an accepted move.

## planner: Plan a move
Parent: `motion`
Kind: `Module`
Grid: `0,0`
Summary: Turn intent and world facts into a plan or a clear rejection.
Rule: Planning does not move game objects.
Sources:
- `lib/overworld/overworld_motion_model.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `include/overworld_motion_model.h`

The plan records origin, target, duration, facing, surface, arc, and completion policy. Private planner strategies choose different routes. World adapters answer bounded queries; they do not own motion rules.

## walk-plan: Plan a Walk
Parent: `planner`
Kind: `Module`
Grid: `0,0`
Summary: Check a tile step and choose exact travel time.
Rule: Diagonal Walk needs its destination and both cardinal side tiles clear.
Sources:
- `src/pokemon_move_history_overlay/overworld_walk_module.c`
- `lib/overworld/overworld_motion_model.c`
- `documentation/overworld_walk_frame_timing_spec.md`

Walk uses the resolved direction permissions, nominal speed, time variance, and turn or stop rules. Timing helpers do not create a second motion owner.

## hop-plan: Plan a Hop
Parent: `planner`
Kind: `Module`
Grid: `1,0`
Summary: Select a legal landing, duration, and clear arc.
Rule: Actor Motion is the entry to Hop planning; roles do not call task-6 directly.
Sources:
- `src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Hop can cross blocked tiles if its landing and arc are legal. Planning checks at most 24 candidate landings in one update. Follow catch-up plans one executable Hop, then plans the next segment after completion and pause. Task-6 is the physical code host, not the owner.

## teleport-plan: Plan a Teleport
Parent: `planner`
Kind: `Module`
Grid: `0,1`
Summary: Choose and protect a legal target with teleport display rules.
Rule: Wild logical position stays at the origin until terminal landing.
Sources:
- `src/pokemon_move_history_task6_overlay/overworld_actor_teleport_planner.c`
- `lib/overworld/overworld_motion_model.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Teleport can show the planned target while the origin remains the logical position. Its reservation protects the destination. It still uses shared start, cancellation, and terminal completion rules.

## reserve: Reserve the target
Parent: `motion`
Kind: `Module`
Grid: `1,0`
Summary: Protect a target tile and physical surface for one accepted move.
Rule: Allocate a fresh nonzero motion identity after the conflict check.
Sources:
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `include/overworld_actor_system_internal.h`

Reservations conflict only when tile and surface identity both match. The accepted request returns the reservation identity. Every later engine-boundary receipt must carry that same live identity. Commit, cancel, or detach releases the reservation. A delayed receipt cannot finish new work in a reused slot.

## executor: Run the motion
Parent: `motion`
Kind: `Module`
Grid: `0,1`
Summary: Advance shared time and publish one pose sample.
Rule: The real engine END boundary is required for terminal commit.
Sources:
- `lib/overworld/overworld_motion_model.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_motion_receipt.c`

Motion uses Idle, Planned, Moving, Commit pending, Settling, Suspended, and Canceled phases. Tick advances time once. Reaching the rendered target can leave the motion waiting for engine END. A paused engine command alone does not prove END. The adapter validates context after the engine callback.

## path: Cross a tile
Parent: `motion`
Kind: `Event`
Grid: `1,1`
Summary: Publish logical position and terrain-loading progress.
Rule: A tile crossing is not an extra move decision.
Sources:
- `lib/overworld/overworld_motion_model.c`
- `src/pokemon_move_history_overlay/overworld_field_terrain_stream.c`
- `lib/overworld/overworld_population_model.c`

A long move can cross several tiles. Path advances update logical location, surface, terrain-loading progress, and movement-distance consumers. They do not increment chains, accelerate, land, or fire warps.

## commit: End a move
Parent: `motion`
Kind: `Event`
Grid: `0,2`
Summary: Commit once, or cancel the complete move.
Rule: The public commit sequence advances once per accepted terminal acknowledgement.
Sources:
- `lib/overworld/overworld_motion_model.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`

Commit confirms the target and surface, records history, updates eligible chain and speed state, and publishes one terminal outcome. Duplicate or rejected acknowledgements do not advance the public sequence. Cancel releases the complete owned motion.

## world: World checks
Parent: `system`
Kind: `Module`
Grid: `0,1`
Summary: Supply legal terrain, surfaces, and occupied places.
Rule: Encounter terrain, movement permission, and physical surface are separate facts.
Sources:
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/overworld_field_terrain_internal.h`

World adapters connect shared policy and motion to the Nintendo DS field engine. They read ground, water, loaded map cells, physical surfaces, and actor occupancy. Host fixtures supply a second world adapter for bounded checks.

## terrain: Ground and water
Parent: `world`
Kind: `Adapter`
Grid: `0,0`
Summary: Read loaded terrain and traversal permission.
Rule: Map-matrix padding is not a playable landing.
Sources:
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

The landing gate first proves the candidate belongs to a real map cell. It then reads current loaded terrain. Placeholder MAP_EVERYWHERE cells and unavailable terrain reject a landing. A rejected candidate does not stop the remaining candidate search.

## surfaces: Raised surfaces
Parent: `world`
Kind: `Adapter`
Grid: `1,0`
Summary: Supply Canopy, Rooftop, and Signpost support and height.
Rule: Surface identity is part of occupancy and reservation checks.
Sources:
- `data/OverworldWildBehaviorData.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`
- `documentation/overworld-system/architecture.md`

Surface support data is generated at build time. The game does not scan tree models at runtime. A valid raised surface can share X/Y with ground below it. Its physical identity keeps those positions distinct.

## occupancy: Actor occupancy
Parent: `world`
Kind: `Adapter`
Grid: `0,1`
Summary: Check player and actor blockers on the candidate surface.
Rule: An engine object pointer alone does not prove actor identity.
Sources:
- `src/pokemon_move_history_overlay/overworld_wild_occupancy.c`
- `include/overworld_wild_occupancy.h`
- `src/pokemon_move_history_overlay/overworld_spawn_guard.c`

Occupancy reads live object and actor facts. Accepted motion uses a separate Actor-owned reservation. Both checks preserve the relevant tile, height, and surface rules.

## streaming: Load terrain
Parent: `world`
Kind: `Adapter`
Grid: `1,1`
Summary: Load terrain along authoritative path progress.
Rule: Loading progress cannot create another logical move.
Sources:
- `src/pokemon_move_history_overlay/overworld_field_terrain_stream.c`
- `include/overworld_field_terrain_internal.h`
- `src/field/overworld_mount_field_input.c`

Cardinal mounted Walk uses the stock player terrain streamer. Staged diagonal or long motion drains its explicit stream anchor before completion. The adapter tracks field context and motion identity. Warps cannot fire mid-motion.

## life: Field life
Parent: `system`
Kind: `Module`
Grid: `0,2`
Summary: Schedule population and handle safe field changes.
Rule: A map change must rebind or cancel a complete motion.
Sources:
- `lib/overworld/overworld_population_model.c`
- `lib/overworld/overworld_actor_transition_model.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Population consumes typed path advances, commits, and field events. The resident owner schedules bounded work. Wild adapters prepare encounters, execute spawn or removal work, and preserve encounter identity. The field transition owner controls safe rebind and resume.

## population: Population schedule
Parent: `life`
Kind: `Module`
Grid: `0,0`
Summary: Schedule despawn, refill, and reveal work across frames.
Rule: Return at most one maintenance work item per frame.
Sources:
- `lib/overworld/overworld_population_model.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`

One owner keeps the refill timer and maintenance phase. Inputs carry a field epoch and increasing world-event sequence. Duplicate and stale events are separate results. Stock unmounted player coordinate changes also publish player-centered path advances.

## spawn: Prepare a spawn
Parent: `life`
Kind: `Adapter`
Grid: `1,0`
Summary: Prepare an encounter, find a site, then bind a fresh actor.
Rule: Prepare profile and spawn metadata once per automatic attempt; reuse them on resume.
Sources:
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_helper_overlay/overworld_spawn_spatial.c`
- `scripts/build_overworld_wild_spawn_metadata.py`
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`

Destination search uses bounded candidate batches. Its final scan batch and spawn-start selection run on separate updates. Encounter terrain and resolved placement both matter. Startup Hop, Fly In, or an off-screen trip must keep the selected destination and complete normal motion handoff. Code work limits do not by themselves prove that current gameplay has no stutter.

## transition: Map change
Parent: `life`
Kind: `Module`
Grid: `0,1`
Summary: Suspend, normalize, rebind, resume, or discard owned work.
Rule: Only the field transition owner can rebind active motion.
Sources:
- `lib/overworld/overworld_actor_transition_model.c`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

A retained Wild actor must be in the retained actor mask. The adapter resolves its stable object ID in the current manager, then validates map, encounter, actor, and subject identity. A stale pointer is not proof. Missing required adapters cause retry, rather than partial rebind.

## gates: Warp and battle gates
Parent: `life`
Kind: `Module`
Grid: `1,1`
Summary: Tell callers when a warp or battle may start.
Rule: A transition closes the gate. An actor that owns input also closes it while motion is unfinished or a reservation is live.
Sources:
- `include/overworld_actor_system.h`
- `src/overworld_actor_system_overlay/overworld_actor_system_overlay.c`
- `src/field/overworld_mount_field_input.c`

Callers use public Inspect WORLD_GATE with Warp or Battle queries. Queued Wild battles also check map and encounter generations before start. Gate readiness is a typed value, not a private movement flag.

## display: Game display
Parent: `system`
Kind: `Module`
Grid: `2,3`
Summary: Show the shared pose with objects, shadows, sound, and effects.
Rule: Display mirrors authority. It never becomes a second mover.
Sources:
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_mount_chain_overlay/overworld_mount_presentation.c`
- `documentation/overworld-system/architecture.md`

Authority owns logical position and motion phase. Display adapters apply the shared sample to game objects. The player object is the mounted engine anchor and also renders the rider. The Pokémon object is dependent presentation.

## wild-display: Wild game object
Parent: `display`
Kind: `Adapter`
Grid: `0,0`
Summary: Apply shared pose, facing, spin, and visibility to Wild and Follower objects.
Rule: Start an engine command only after the shared request accepts.
Sources:
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_motion_receipt.c`

A rejected request rolls back this attempt's preparation. Engine movement completion returns a typed receipt with the accepted motion identity. Wild presentation cleanup must preserve the active motion kind through its terminal boundary.

## mount-display: Mounted display
Parent: `display`
Kind: `Adapter`
Grid: `1,0`
Summary: Keep the rider and Pokémon on one sampled path.
Rule: The player is the engine anchor. The Pokémon mirrors it.
Sources:
- `src/overworld_mount_chain_overlay/overworld_mount_presentation.c`
- `src/overworld_mount_action_overlay/overworld_mount_walk_ease.c`
- `src/overworld_mount_overlay/overworld_mount_overlay.c`

The mounted pair shares one duration and one render path. Easing changes display sampling when Walk speed changes; it does not add motion or alter committed ownership.

## effects: Shadows, sound, and effects
Parent: `display`
Kind: `Adapter`
Grid: `0,1`
Summary: Publish surface-aware shadows and action feedback.
Rule: Effects consume motion and policy results; they do not decide movement.
Sources:
- `src/overworld_mount_chain_overlay/overworld_mount_gait.c`
- `src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Shadow queries validate the live object and encounter. Fly In samples ground height along its display path, then restores normal surface-based shadow rules on landing. Sound and landing effects use eligible action outcomes.

## combat: Combat and HP
Parent: `system`
Kind: `Module`
Grid: `0,3`
Summary: Validate contact, change HP, and request the hit response.
Rule: Ram, Throw, and Ambush are movement paths; profiles supply attack rules.
Sources:
- `include/overworld_combat.h`
- `include/player_health.h`
- `src/player_health_contact.c`
- `src/player_health_pokemon.c`
- `documentation/overworld-system/architecture.md`

The resident combat service connects contact to trainer and Pokémon HP owners. Resolved attacking, impact-speed, damage, recipient, and knockback fields control the hit. Identity and per-target protection are checked before damage. Rider and mount have separate HP but share one knockback move. Source ownership here does not grant current game proof.

## contact: Ground and flight contact
Parent: `combat`
Kind: `Adapter`
Grid: `0,0`
Summary: Report valid ground or swept airborne contact to the HP owner.
Rule: Recheck actor, field, map, and encounter identity before a hit.
Sources:
- `src/player_health_contact.c`
- `include/player_health.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Blocked steps and field-frame pose samples supply contact facts. Flight checks use the segment between the old and new poses, including the mounted rider's live offset. Throw cargo cannot hit its thrower. Landing and cancellation end flight authority. This adapter checks the profile attack gate and sends valid hits to the target's HP owner.

## trainer-hp: Trainer HP and field clock
Parent: `combat`
Kind: `Module`
Grid: `1,0`
Summary: Own trainer HP, hit protection, healing time, and recovery state.
Rule: One eligible field frame advances the HP model once.
Sources:
- `lib/overworld/player_health_model.c`
- `include/player_health_model.h`
- `src/player_health.c`
- `src/field/map_teleport.c`

The portable reducer owns trainer HP and timers. The resident field adapter opens the eligible frame before actor work and closes it afterward, including when no wild actor is active. A hit resets the healing wait and partial point. Ordinary movement does not stop healing; ineligible field states pause the clock. Zero HP requests recovery.

## pokemon-hp: Pokémon HP and battle transfer
Parent: `combat`
Kind: `Module`
Grid: `2,0`
Summary: Own encounter HP and update the real selected party Pokémon.
Rule: A reused actor slot starts a new HP owner; numeric zero means fainted.
Sources:
- `src/player_health_pokemon.c`
- `include/overworld_combat.h`
- `include/overworld_wild_spawns_internal.h`

Wild HP lives in the resident encounter array and uses species, form, level, and a stable personality-derived HP IV. Follower and Mounted read and write the selected party Pokémon after identity checks. Each target has hit protection and a half-max-HP damage cap. Battle and capture adapters carry the encounter's current HP into the matching Pokémon. Fainted actors cannot continue normal field control.

## knockback: Shared hit motion
Parent: `combat`
Kind: `Adapter`
Grid: `0,1`
Summary: Plan Slide or Jump once and hand it to the target's motion adapter.
Rule: A skid hit completes Crash before the queued knockback starts.
Sources:
- `src/player_health.c`
- `src/player_health_pokemon.c`
- `src/player_health_overlay/overworld_actor_hit_crash.c`
- `lib/overworld/overworld_motion_model.c`
- `src/overworld_mount_overlay/overworld_mount_overlay.c`

OverworldCombat_Plan creates one forced motion plan for trainer, Pokémon, and mounted adapters. It keeps wall, script, and non-Pokémon object checks while allowing the forced path through Pokémon. The movement owner supplies immediate Crash for a due or active skid. The shared executor supplies the timeline, terminal result, and returned control; the mounted pair moves once.

## hp-save: HP save record
Parent: `combat`
Kind: `Adapter`
Grid: `1,1`
Summary: Store trainer HP and the completed healing destination in save misc.
Rule: Validate the versioned record without changing the save block size.
Sources:
- `src/player_health_save.c`
- `include/save.h`
- `src/player_health.c`

The save adapter reads and updates the in-memory save record. Old records initialize to full HP and a safe healing destination; a valid zero remains zero. The field owner updates it when HP changes. The normal game Save operation owns writing the save file.

## recovery: Healing and blackout
Parent: `combat`
Kind: `Adapter`
Grid: `2,1`
Summary: Restore HP after completed healing or one stock blackout task.
Rule: Change the HP checkpoint only after a completed Center or home event.
Sources:
- `src/player_health_recovery.c`
- `src/player_health.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `armips/scr_seq/scr_seq_00845_home_rest.s`
- `src/player_health_save.c`

Completed healing scripts publish markers. The adapter consumes them, records the healing destination, and restores trainer HP. Zero HP creates one recovery task that leaves the field and invokes stock blackout. It supplies the HP destination only around stock destination reads, then restores the stock checkpoint. Completion restores HP and releases recovery ownership.

## hp-display: Health bar and hit feedback
Parent: `combat`
Kind: `Adapter`
Grid: `0,2`
Summary: Show HP, danger, and accepted-hit feedback through owned display resources.
Rule: Presentation reads HP and contact facts; it cannot apply damage.
Sources:
- `src/player_health_presentation.c`
- `include/player_health_presentation.h`
- `src/player_health.c`

The field owner supplies HP, danger, and the accepted-hit flag. The renderer owns health-bar sprites, palette state, and hit feedback, with release and rebind paths for field and UI changes. Its native receipt reports requested and submitted display state. That receipt does not prove final screen appearance.

## tools: Tools and proof
Parent: `system`
Kind: `Support`
Grid: `1,3`
Summary: Edit profiles, read state, and check exact claims.
Rule: A diagram or source check is not accepted gameplay proof.
Sources:
- `scripts/owctl`
- `tools/overworld/system_features.yaml`
- `documentation/overworld-system/verification.md`
- `documentation/overworld-system/roadmap-progress.md`

The Workshop edits behavior. Shared melonDS tools control disposable test sessions and read memory-backed observations. Registered scenarios and proof manifests define accepted claims. Changed inputs can make older evidence stale. This map does not copy changing test results into block badges.

## workshop: Workshop
Parent: `tools`
Kind: `Tool`
Grid: `0,0`
Summary: Edit profiles and inspect native resolver output.
Rule: The editor does not contain a second composition policy.
Sources:
- `tools/overworld-viewer-v2`
- `scripts/overworld_behavior_profile_viewer.py`
- `lib/overworld/overworld_behavior_resolver.c`

The host adapter collects context and projects the same C result into editor labels. Changes to profiles generate compact ROM data before a build.

## host: Shared live tools
Parent: `tools`
Kind: `Tool`
Grid: `1,0`
Summary: Control owned sessions and decode public state and traces.
Rule: Use melonDS and shared tools; preserve user ROMs, saves, and sessions.
Sources:
- `scripts/owctl`
- `tools/overworld`
- `documentation/overworld-system/devtools.md`

Host tools use typed requests and semantic values. Diagnosis relies on memory-backed state. Source checks, packaged ROM checks, and live game observations supply different levels of evidence.

## proof: Registered proof
Parent: `tools`
Kind: `Tool`
Grid: `0,1`
Summary: Check a claim against its current inputs and acceptance rules.
Rule: An old ROM pass cannot close a changed current-ROM requirement.
Sources:
- `tools/overworld/system_features.yaml`
- `tests/overworld/scenarios`
- `documentation/overworld-system/verification.md`
- `documentation/overworld-system/roadmap-progress.md`

Manifests bind evidence to the tested inputs. Required gameplay checks must pass on the current candidate before a runtime fix closes. The work table records remaining gaps. No game run was made to create this documentation map.

## Connections

Arrows point from the source to the receiver. A reads link points from the reader to the thing read. Link types are shown with color and text. At a higher level, links with the same endpoints and type form one bundle. The bundle count is the number of documented relations, not a runtime call count. Open a link to read each relation and its source.

| From | To | Type | Meaning | Source |
| --- | --- | --- | --- | --- |
| schema | catalog | builds | The field schema defines the generated profile layout. | scripts/generate_overworld_behavior_schema.py |
| catalog | resolver | supplies | Named profiles and ordered applications supply composition input. | lib/overworld/overworld_behavior_resolver.c |
| classifications | resolver | supplies | Classification and manual order set field override order. | CONTEXT.md |
| bindings | mounted | supplies | Mounted forces the empty System override on normal Pokémon behavior. | src/overworld_mount_overlay/overworld_mount_overlay.c |
| bindings | follower | supplies | Follower uses its runtime-linked System profile. | documentation/overworld-system/architecture.md |
| vision | conditions | supplies | Sight results are bounded input to condition truth. | lib/overworld/overworld_behavior_conditions.c |
| conditions | vision | reads | A sight condition uses Current Vision or Custom Vision. | lib/overworld/overworld_behavior_conditions.c |
| conditions | resolver | supplies | Admitted applications and target source data enter profile composition. | lib/overworld/overworld_behavior_resolver.c |
| conditions | identity | reads | Captured targets must retain the same valid actor identity. | lib/overworld/overworld_behavior_condition_adapter.c |
| conditions | terrain | reads | Terrain and visibility observations enter condition evaluation. | lib/overworld/overworld_behavior_condition_adapter.c |
| resolver | wild | supplies | Resolved lanes and target guide the next Wild intent. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| resolver | follower | supplies | Resolved Follower fields guide follow intent. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| resolver | mounted | supplies | The mount session snapshots normal Owner behavior plus Mounted. | src/overworld_mount_overlay/overworld_mount_overlay.c |
| resolver | walk-policy | supplies | Resolved fields set direction, speed, skid, and variance rules. | documentation/overworld-system/architecture.md |
| resolver | planner | supplies | A plan uses resolved movement timing and permissions. | documentation/overworld-system/architecture.md |
| wild | conditions | requests | Wild checks conditions at a new intent boundary. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| follower | conditions | requests | Autonomous Follower intent uses prepared condition observations. | documentation/overworld-system/architecture.md |
| wild | wander | requests | Ordinary Wild intent asks for look or wander policy. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| wild | walk-policy | requests | Wild Walk and Ram feed the shared policy transaction. | src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c |
| mounted | walk-policy | requests | Rider direction feeds shared Walk policy. | src/overworld_mount_overlay/overworld_mount_overlay.c |
| mounted | chains | requests | Mounted actions use the shared chain state and handoff. | src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c |
| follower | planner | requests | Follow intent requests the next executable shared move. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| held | wild | updates | Held control suspends autonomous Wild planning. | CONTEXT.md |
| commands | identity | updates | Lifecycle commands cancel, detach, or change the role of validated actors. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| commands | tick | supplies | Accepted queued commands run at a Tick boundary. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| identity | inspect | supplies | Snapshots expose the actor handle and semantic state. | include/overworld_actor_system.h |
| tick | executor | updates | Actor Tick advances the shared motion timeline once. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| walk-policy | walk-plan | supplies | Policy selects the accepted step's movement rules. | documentation/overworld-system/architecture.md |
| chains | planner | requests | An admitted chain action requests its next motion plan. | documentation/overworld-system/architecture.md |
| wander | planner | requests | An allowed direction becomes a movement candidate. | documentation/overworld-system/architecture.md |
| reactions | effects | supplies | Reaction intent supplies sound and effect work. | src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c |
| planner | reserve | supplies | An accepted plan reaches the Actor-owned target-conflict check. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| walk-plan | terrain | reads | Walk checks destination and diagonal side tiles. | lib/overworld/overworld_motion_model.c |
| hop-plan | terrain | reads | Each candidate landing must be a real loaded map cell. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| hop-plan | surfaces | reads | Hop checks landing surface height and arc clearance. | src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c |
| hop-plan | occupancy | reads | Landing checks reject relevant occupied destinations. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| teleport-plan | terrain | reads | Teleport needs a legal target. | src/pokemon_move_history_task6_overlay/overworld_actor_teleport_planner.c |
| planner | occupancy | reads | Candidate admission checks relevant blockers. | documentation/overworld-system/architecture.md |
| reserve | executor | supplies | Successful Begin owns a fresh reservation and motion identity. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| executor | path | supplies | Shared execution reports crossed tiles. | lib/overworld/overworld_motion_model.c |
| executor | commit | supplies | Terminal motion waits for the matching engine acknowledgement. | lib/overworld/overworld_motion_model.c |
| path | streaming | updates | Path advances drive long-motion terrain loading. | src/pokemon_move_history_overlay/overworld_field_terrain_stream.c |
| path | population | supplies | Player-centered distance uses typed logical path advances. | lib/overworld/overworld_population_model.c |
| commit | walk-policy | updates | Terminal commit updates eligible speed and direction state. | documentation/overworld-system/architecture.md |
| commit | chains | updates | One eligible terminal decision advances chain state. | documentation/overworld-system/architecture.md |
| commit | population | supplies | Population consumes terminal commits separately from path advances. | lib/overworld/overworld_population_model.c |
| commit | reserve | updates | Commit or cancel releases the owned destination. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| executor | wild-display | supplies | Wild display reads shared pose, facing, spin, and visibility. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| executor | mount-display | supplies | Rider and Pokémon read the same motion sample. | src/overworld_mount_chain_overlay/overworld_mount_presentation.c |
| wild-display | commit | supplies | Wild returns the accepted motion identity at engine END. | src/overworld_wild_runtime_overlay/overworld_wild_motion_receipt.c |
| mount-display | commit | supplies | Mounted commit waits for the genuine player movement END. | src/field/overworld_mount_field_input.c |
| surfaces | effects | supplies | Physical surfaces set height and shadow rules. | documentation/overworld-system/architecture.md |
| population | spawn | requests | The bounded schedule emits refill work for Wild to execute. | lib/overworld/overworld_population_model.c |
| spawn | resolver | requests | A prepared spawn resolves its profile once for that attempt. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| spawn | terrain | reads | Placement checks encounter terrain and legal destination terrain. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| spawn | identity | requests | Prepared spawns bind a fresh actor before profile caching. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| spawn | planner | requests | Spawn-entry movement keeps its selected destination. | documentation/overworld-system/architecture.md |
| transition | executor | updates | The transition owner suspends, rebinds, resumes, or cancels motion. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| transition | identity | updates | Field and map generations invalidate stale bindings. | lib/overworld/overworld_actor_transition_model.c |
| transition | population | supplies | A rebind field event schedules complete reconciliation. | lib/overworld/overworld_population_model.c |
| gates | executor | reads | A live input-owned unfinished motion closes world readiness. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| gates | transition | reads | An active transition closes Warp and Battle gates. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| mounted | gates | reads | Mounted field input inspects Warp readiness. | src/field/overworld_mount_field_input.c |
| wild | gates | reads | Wild battle handoff inspects Battle readiness. | documentation/overworld-system/architecture.md |
| inspect | executor | reads | Inspect projects semantic motion state without changing it. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| inspect | population | reads | Inspect returns the public population value. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| inspect | gates | reads | Inspect returns typed Warp or Battle readiness. | src/overworld_actor_system_overlay/overworld_actor_system_overlay.c |
| workshop | catalog | updates | The editor changes named profiles and applications. | scripts/overworld_behavior_profile_viewer.py |
| workshop | resolver | reads | The Workshop inspects native C resolution output. | scripts/overworld_behavior_profile_viewer.py |
| host | commands | requests | Shared host tools submit typed lifecycle control. | tools/overworld |
| host | inspect | reads | Host tools decode public state and semantic trace. | tools/overworld |
| proof | host | requests | Registered scenarios run through shared owned sessions. | documentation/overworld-system/verification.md |
| proof | motion | checks | Feature manifests name exact motion proof requirements. | tools/overworld/system_features.yaml |
| proof | life | checks | Current spawn pacing and transition inputs need current proof. | documentation/overworld-system/verification.md |
| conditions | throw | supplies | Ordered Capability applications select pursuit, pickup, launch position, and release. | documentation/overworld-system/architecture.md |
| throw | conditions | supplies | Current Trigger, Cargo, reservation, held, launch-line, and recovery facts enter condition evaluation. | lib/overworld/overworld_throw_observation_native.c |
| throw | identity | reads | Binding refresh checks the current actor identity and position. | lib/overworld/overworld_throw_binding_native.c |
| throw | held | updates | Pickup, carry, launch, and cleanup change held control while keeping the actor identity. | src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c |
| throw | contact | supplies | Launched actors carry resolved attack settings into validated flight contact. | documentation/overworld-system/architecture.md |
| resolver | contact | supplies | Resolved attack, impact speed, damage, recipient, and knockback fields gate a hit. | src/player_health_contact.c |
| contact | identity | reads | Every hit checks current subject and target generations. | src/player_health_contact.c |
| contact | trainer-hp | requests | Valid trainer contact asks the trainer HP model to accept a hit. | src/player_health_contact.c |
| contact | pokemon-hp | requests | Valid Pokémon contact asks the selected HP owner to accept a hit. | src/player_health_contact.c |
| contact | knockback | requests | A hit on the mounted Pokémon queues shared rider and mount movement. | src/player_health_contact.c |
| trainer-hp | contact | updates | Field begin and end calls bound the contact sampling window. | src/player_health.c |
| trainer-hp | hp-save | updates | Changed trainer HP updates the in-memory save record. | src/player_health.c |
| hp-save | trainer-hp | supplies | Validated saved HP initializes the trainer model at field entry. | src/player_health.c |
| trainer-hp | recovery | requests | Zero HP asks for one recovery task. | src/player_health.c |
| trainer-hp | knockback | requests | Accepted trainer damage queues the configured forced move. | src/player_health.c |
| pokemon-hp | knockback | requests | A living Pokémon with pending hit motion requests the common plan. | src/player_health_pokemon.c |
| pokemon-hp | wild | supplies | The combat receipt supplies faint removal, Crash, or pending knockback work. | src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c |
| pokemon-hp | identity | reads | Encounter and party HP access rechecks the selected Pokémon identity. | src/player_health_pokemon.c |
| knockback | terrain | reads | Forced motion checks each tile for wall, script, and fixed-object blocks. | src/player_health.c |
| knockback | reactions | requests | A hit during a skid requests immediate Crash from the movement owner. | src/player_health_pokemon.c |
| knockback | executor | supplies | The common planner supplies a forced plan to shared motion execution. | src/player_health.c |
| knockback | mounted | supplies | Rider and mount use one movement anchor for the hit response. | src/player_health.c |
| recovery | hp-save | updates | Completed Center or home healing records the HP checkpoint. | src/player_health_recovery.c |
| recovery | hp-save | reads | Stock blackout uses the validated HP destination for its synchronous reads. | src/player_health_recovery.c |
| recovery | trainer-hp | updates | Completed healing or blackout restores trainer HP. | src/player_health_recovery.c |
| trainer-hp | hp-display | supplies | The field owner supplies HP, danger, and accepted-hit state to presentation. | src/player_health.c |
| host | trainer-hp | reads | Native HP observation reads the resident owner and field-clock state. | tools/overworld/devtools_player_health_observer.py |

## Build and use

Open `index.html` in a browser. It works without a server or network access. Click a block to open its parts. A block with no parts stays selected in the detail panel. Click an arrow or its count to read the exact links. Use the trail at the top or Escape to go up. On a small screen, the blocks use one column and the detail panel follows the graph.

Edit this Markdown file, then run `python3 documentation/overworld-system/explorer/build.py`. Run the same command with `--check` to validate source paths, graph structure, profile order and Waddle's saved classification, and whether the HTML matches the Markdown. The builder reads this map, its template, the V5 authoring schema, and the profile catalog. It writes only this folder's `index.html`. It does not build a ROM or control a game session.
