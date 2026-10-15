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

Overworld combat is a resident feature owner. A Pokémon can lower trainer or
Pokémon HP only when its resolved profile has `attacking` on and its collision
meets `minImpactSpeed`. The profile supplies fixed `collisionDamage`.
Impact speed is the largest absolute X, Y or Z displacement in the current
contact update, converted to the shared speed unit and capped at 255. Vertical
drop speed uses the same gate for Player and Pokémon contacts.
Each hit is capped at half the target's max HP, with a one-HP minimum cap.
Ram, Throw, and Ambush are movement paths, not damage classes. Active Ambush gives
Weepinbell, Victreebel, and Carnivine a warned, 20-HP Hop contact and one-tile
Jump knockback. Knockback follows the hit direction. It can pass through
overworld Pokémon, even when the attacker lands in its path, but walls,
scripted tiles, and non-Pokémon objects still stop it. The shared knockback
controller checks each tile before and during motion. Pokémon actors report
validated ground or airborne contact; they do not store trainer HP. `PlayerHealth` keeps
the trainer's HP, protection, and damage-free healing clock in
resident overlay 161. A profile sets knockback type (None, Slide, or Jump)
and distance; Ram uses Jump for three tiles, Throw uses Slide for one, and
Ambush uses Jump for one.
One common knockback planner supplies Slide and Jump to the player, Pokémon,
and mounted movement adapters. All use the shared actor motion model. The field
service opens one eligible frame before wild actor work and closes it afterward,
including in areas with no wild actors. Player healing can start and continue
on foot or while mounted and moving. A hit resets the existing wait and
fractional healing; menus, dialogue, and battles still pause the eligible clock.
A small record in save misc stores HP
and the last completed healing point. Stock battle-blackout state remains a
separate game rule. The native health bar presentation reads HP and danger;
it cannot change damage. The [player HP plan](player-hp-implementation-plan.md)
owns the implementation contract; the [current work table](roadmap-progress.md#current-work-table)
owns resume and proof state. Source ownership does not by itself establish
current-ROM behavior.
Airborne Throw contact samples the trainer's field position plus the live
rider X/Y/Z face offset, so a mounted hit follows the rider rather than the
mount's ground point.

The combat entry at `0x01FFD580` owns generation-bound Pokémon HP metadata,
per-target one-second hit protection, and queued knockback. Wild current HP
uses the existing resident `savedHp` array. New encounter publication writes
`OW_WILD_HP_UNINITIALIZED` (`0xFFFF`); the first HP read sets normal full HP.
Numeric zero always means fainted. Reusing a slot starts a new HP owner, while
restoring the same encounter's presentation or combat cache retains its HP.
Max HP uses the native species,
form and level formula, zero EVs, and a stable HP IV from encounter personality.
The same encounter can reuse its nonzero max HP across a map-only rebind when
personality, encounter generation, species, form and level all match. Every
read still validates the current Field/save owner and reads resident current
HP. The rebind resets hit protection and queued combat work and publishes the
new map context. A new owner, changed stat input or empty cache reloads stats.
Battle creation and direct capture use that same IV and current HP. A follower
or mount reads and writes the actual selected party Pokémon after checking
its identity; a party pointer is never retained across frames. Pokémon do not
heal from standing still. At zero HP a wild encounter is removed; a party
Pokémon faints and cannot follow or mount. Faint removal consumes the encounter
without a shiny respawn reservation.

Ground blocked proposals and swept airborne contact can hit other Pokémon.
Contact uses `OverworldActorSystem_IsReady` to check the boot-resident Actor
entry's magic, version and size, then checks the current field and actor
identity. The SDK overlay load list does not own this resident image.
An actor cannot hit itself; thrown cargo cannot hit its thrower. An accepted
hit affects one target at most once during its protection interval. Rider and
mount have separate HP but share one queued movement. An accepted hit during
a due or active skid triggers the movement owner's normal crash immediately.
The order is skid, crash, then knockback. It must not silently clear or cancel
the skid, or wait for its remaining travel before starting the crash. Knockback
starts after the crash restores a valid movement boundary and origin. Other
accepted movement closes normally before knockback. A shared Walk at
COMMIT_PENDING must receive its terminal Walk policy commit even while combat
holds the next intent; engine END alone cannot return its control. That hit
completion does not start a new skid, chain step or ordinary AI move.
On foot, stock movement must reach the exact X/Z center of its current logical
tile before the knockback planner or terrain stream starts. A pending hit keeps
its direction and distance while normal input finishes that short step. The
hit takes control at the next centered boundary, before another stock step.
Knockback blocks a new
normal intent and uses a forced no-chain motion. Forced motion ignores Pokémon occupancy and destination
reservations but retains walls, scripted tiles and other objects. Map changes,
actor replacement, pause and faint cleanup remove stale queued work.
A living carrier keeps its exact current Cargo claim and binding during its
own knockback. Carried pose sync follows the same forced motion. Knockback
reuses the saved endpoint fields, so it clears the old windup and the next
held intent chooses a valid aim and starts the full authored windup again.
A hit held target still releases its carrier relation before knockback;
faint and stale-identity cleanup still drop Cargo.

The Actor owner emits one Crash and suspends the exact uncommitted skid.
The role adapter restores its saved start tile and base height, then reports
settlement with the same motion identity and field epoch. The mount adapter
invalidates the old Walk gait and refreshes its height caches before syncing
the grounded rider and mount. No old END, commit,
or cancel is published. A due skid in an already committed pause instead ends
that pause at the last completed tile. The HP latch holds normal movement
through the existing role Crash timer, including profiles with no knockback.
Queued Slide or Jump starts only after that timer ends. The read-only combat
receipt separates `crashPhase` from the queued-knockback bit. Internal urgent
probes check that latch without party reads; normal NULL-plan probes still
check fainted HP for follower eligibility.

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

All profile-controlled Pokémon have unlimited native movement range: both signed
X and Y limits are `-1` during spawn, role setup, restoration and presentation
recreation. The old Stats Range is not editable. Compact byte 8 now stores
`turnSkidOneTime`; it never controls native movement range. `turnSkidTwoTime`
and `stopSkidTime` occupy the high seven bits of bytes 56 and 62. Their existing
vertical-Hop and reposition-dust booleans remain in bit 0 and compose
independently. Compact storage remains 80 bytes, and later fields keep their
positions. This rule does not change terrain, walls, collision, height, movement
style Grid bounds, Hop distance, Vision, Throw range or distance despawn.

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
this precedence order: `routine`, `style`, `placement`, `follower`, `capability`,
`attitude`, `follower-mount`, then `modifier`. Follower remains a
runtime-linked System application; its `follower` classification puts normal
follow movement before capabilities. Mounted and Asleep keep their later
`follower-mount` position. Manual order is preserved inside a group.
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

The current catalog has one complete `Default` root and this exact application
order. The named source is
[`overworld_behavior_profiles.json`](../../data/overworld_behavior_profiles.json).

| Order | Classification | Profile | Application ID |
| ---: | --- | --- | --- |
| 1 | Moods | Angry (empty, unassigned) | `apply-angry` |
| 2 | Routine | Scavenger | `apply-scavenger` |
| 3 | Routine | Sprint | `apply-sprint` |
| 4 | Routine | Floaty Bounce | `apply-floaty-bounce` |
| 5 | Routine | Small Bird Hop | `apply-small-bird-hop` |
| 6 | Routine | Erratic Flutter | `apply-erratic-flutter` |
| 7 | Routine | Meander | `apply-meander` |
| 8 | Routine | Hop Around | `apply-hop-around` |
| 9 | Routine | Lurk | `apply-idle` |
| 10 | Routine | Drowsy Wander | `apply-drowsy-wander` |
| 11 | Routine | Perch | `apply-perch` |
| 12 | Routine | Rest | `apply-rest` |
| 13 | Style | Waddle | `apply-waddle` |
| 14 | Placement | Fly In | `apply-fly-in` |
| 15 | Placement | Canopy Access | `apply-canopy-access` |
| 16 | Placement | Flower Bed | `apply-flower-bed` |
| 17 | Placement | Swimmer | `apply-swim` |
| 18 | Follower | Follower | `apply-follower` |
| 19 | Capability | Teleport | `apply-teleport` |
| 20 | Capability | Stalker | `apply-stalker` |
| 21 | Capability | Long Hop | `apply-long-hop` |
| 22 | Capability | Canopy Hop | `apply-canopy-hop` |
| 23 | Capability | Find Throw Cargo | `apply-throw` |
| 24 | Capability | Find Throw Position | `apply-throw-find-position` |
| 25 | Capability | Heavy Stomp | `apply-heavy-stomp` |
| 26 | Capability | Water Runner | `apply-water-runner` |
| 27 | Attacks | Throw Held Actor | `apply-throw-release` |
| 28 | Attacks | Ram | `apply-ram` |
| 29 | Attacks | Basic attack (disabled) | `apply-basic-attack` |
| 30 | Attacks | Ambush | `apply-ambush` |
| 31 | Attacks | Stomp Slam | `apply-stomp-slam` |
| 32 | Attacks | Throw Away From Player | `apply-throw-away` |
| 33 | Attitude | Startled | `apply-startled` |
| 34 | Attitude | Find Playmate | `apply-find-playmate` |
| 35 | Attitude | Playful | `apply-playful` |
| 36 | Attitude | Skittish | `apply-skittish` |
| 37 | Attitude | Seek safety | `apply-seek-safety` |
| 38 | Follower/Mount | Mounted | `apply-mounted` |
| 39 | Modifier | Asleep | `apply-asleep` |

Skittish includes a self-damage condition for its existing Baby Pokémon pool. Seek safety
includes a separate self-damage condition for its existing Baby Follower pool.
Both use the shared accepted subject-damage event. Their existing notice
conditions remain independent triggers; damage to another subject does not
trigger either self-damage condition.

Lurk copies Idle with only Behavior changed to Chase. Idle remains available
without a normal application. The stable `apply-idle` ID now applies Lurk to
Weepinbell, Victreebel and Carnivine; its slot and members are unchanged.
Ambush runs for 90 frames and uses the shared passive Movement Chain pause
after each Hop. Its base value of 12 and variance of 8 give native pauses
of six to ten frames, with no extra Hop pause or new movement controller.
Canopy Hop uses no alert duration or emote. A terrain-only change can therefore
start its normal Hop on the same boundary without a cry or bubble asset load.

Moods compose before Routines. Angry is an empty unassigned Mood. Attacks
compose immediately after Capabilities; the tag alone does not grant damage.
The resolved attacking flag, impact-speed and contact rules remain authoritative.
Perch follows the ordinary Routines. Teleport is the first Capability.
Seek safety keeps the movement style supplied by the other matching profiles.
It does not override `chillAction`; a Hop follower still uses Hop while it
chases safety next to the player.
Its visible Alert emote is the crying face (the stock SAD bubble, ID3), with
10 alert frames. The emote uses the normal profile-change presentation; it
does not add a movement style or a second response controller.
Skittish and Seek safety explicitly replace Chain Pause Action with None.
Seek safety also has a `subject-damaged` condition for the same Baby Pokémon
Follower pool. It captures Player and uses the existing960-frame duration
and970-frame cooldown. Only accepted damage to that exact Pokémon publishes
its pending event; unrelated Pokémon damage and Player damage do not.
Skittish's self-damage condition uses the same Baby Pokémon pool as its notice conditions, with explicit Wild role scope. Other species, including Snorlax, do not receive this damage response.
It captures Player, moves Away from Player, and uses960/970-frame timing.
It inherits Movement Style and clears Chain Pause Action. Followers keep Seek
safety; mounted movement stays with the rider.

Find Playmate and Playful are separate conditional profiles. Find Playmate
captures one visible compatible Pokémon or Player for420 frames, with430-frame
cooldown, and approaches that same Object of interest. It inherits Movement
Style and clears Chain Pause Action. Playful applies only while Find Playmate
is already applied in the current resolution pass and its exact bound target
is at Chebyshev distance0..1. It has no entry emote or entry wait. Its existing
circle movement, one/two hops, and independent heart/cry choices remain.
Target loss, binding expiry or parent expiry ends the adjacency stage.

Startled precedes Skittish. Heavy Stomp follows Ram, adds ledge-hop landing
footfall feedback, and limits its shared Pokémon group to one active Wild spawn
for Golem, Rhydon, Snorlax, Tyranitar, Aggron, Groudon, Torterra, Hippowdon,
Rhyperior, Mamoswine, and Regigigas. The Player notice entry
is last inside Find Playmate. A valid first capture keeps its exact target and
source entry through that Find Playmate cycle. Follower is applied before the Capability group.
Follower, Mounted, and Asleep are runtime-linked and
cannot be normally assigned.

Swimmer is a Placement profile that grants Land plus Water. Water Runner is a
Capability that grants Land plus Water and also sets the presentation-only
Water surface terrain bit (`OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER_SURFACE`,
bit 10) for Suicune, Surskit and Masquerain. As a Capability it composes after
the Follower base, so a Follower Suicune also runs on top of water. Riding uses
the stock player step, whose collision (`sub_0205DA34`) reports deep water as
`0x21` (blocked plus surfable water). Its final return (`0x0205DAA2`) goes
through overlay 2 (`OVERWORLD_WATER_SINK_PLAYER_COLLISION_ADDR`): that exact
water block is lifted while riding a mount whose resolved terrain includes
Water, and while the player already stands on deep water without surfing, so
an explicit or forced dismount on water can walk back to land. Any other
collision reason keeps the block. Tile matching, destinations and `OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL`
ignore that bit; the resolver and Condition argument checks use
`OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_POLICY_ALL` so it survives composition. On a
deep-water tile (`OverworldWildSpawnGuard_IsSurfBehavior`) every other Wild or
Follower actor is cropped at the waterline: `OVERWORLD_WATER_SUBMERGE_DEPTH`
sprite rows (`include/config.h`, switch `OVERWORLD_WATER_SUBMERGE`) are cut off
the bottom of its body. Stock map water is never drawn over sprites, so the
crop is per draw: `OverworldWaterSink_Update` installs a private user SBC on
that object's RenderObj (`draw+0x60`) whose SHP is replaced by a CALLDL to a
copy of the stock billboard quad with the top edge lowered and the texture cut
by the same rows. Models and textures stay shared, and the tint and recall MAT
callbacks are untouched. `ReconcileNativeShadow` retargets the depth and hides
the shadow on deep water, placement and idle reconciles settle, and the motion
writer eases one row per frame. A hop arc in `unk88` lifts the body back out;
`unk94` drops the anchor by the lifted part so the cut stays on the waterline.
Stock `sub_020601A4` clears `unk94` on every move-start and tile-enter update,
and Wild motion sets `BIT_MOVE_START` each frame, so
`armips/asm/overworld_wild_shadow.s` keeps that clear for every object except
wild IDs `E0`–`E9`. The leaf lives in overlay 2's retired vanilla
follower-interaction graph at `0x0224F8FC` (extended
`overworld_follower_release_overlay2` module, loaded with the field); its
per-slot quads live in the Wild runtime. Mounted presentation keeps owning the
ridden Follower's offsets.

A new body (its encounter generation differs from the tag kept in the slot's
quad) and every hop settle the depth at once; only a walk across the bank
eases. The appearance capsule's RefreshAll entry points at the sink's
per-frame pass (`0x02250000`), which calls the hosted RefreshAll first and
then settles bodies that have not moved since they spawned, so a spawn is
drawn submerged from its first frame. A body that is in the water (cropped
rows above zero) keeps the stock shallow-water splash (`ov01_021FF4FC`, flag
`MAPOBJECTFLAG_UNK26`); an airborne one drops it. A Water Runner on deep water
is never cropped but keeps the same splash while it is not airborne; bit 7 of
`waterSinkTargetPx` records "on deep water" separately from the depth. A body
counts as airborne only above 3 pixels of lift, so a ridden mount's gait bob
keeps its splash. A ridden Follower gets no Wild terrain reconcile, so the
per-frame pass feeds the mount its own tile each frame while the Mount phase is
Riding (`WaterSink_MountFrame`). The stock terrain updates
`sub_0206039C` and the jump update's `sub_020603D0` call no longer clear that
flag for wild IDs, because Wild motion reaches them every frame; the sink
clears it when the body leaves water. A splash is only added while the shared
field-effect render pool (48 records) keeps 8 free. The body's stock
reflection (field effect 1, the "mirror" model, task init `ov01_021FDAC0` or
`ov01_021FDFD4`, render record at work+0x24) gets its own private quad too:
the near edge samples the last visible row and the far edge comes in by the
same fraction, so it mirrors only the part above the waterline. Both stock tall-grass
rustle calls (`sub_020601BC`, `sub_02060274`) go through the gate at
`0x022500B0`: a Wild body rustles once per tile entered and never while
airborne. Before that gate, a fly-in kept its logical tile on the take-off
grass and stacked one rustle per frame until the pool ran out and the game
crashed.

Rooftop Access is a normal Placement profile selected as the base for Mankey,
Primeape, and Annihilape. It inherits Default and enables Land plus Rooftop in
its terrain settings. Default's explicit terrain mask remains inherited.
Mankey and Annihilape keep their existing species selectors; Primeape has a
new direct selector. Their normal applications, including Canopy Access and
Long Hop, remain in the same order. The catalog now assigns global application
IDs and compiles a small candidate bank for each species; each actor's 32-bit
mask refers only to its own bank. The supported line
and render entries are defined in `armips/data/evodata.s` and
`armips/data/monoverworlds.s`; Primeape's evolution method is still marked TODO.

Snorlax also uses Drowsy Wander. It walks in uneven two-to-six-step bursts,
varies each step's travel time, often stops to look around, and avoids immediate
backtracking. Heavy Stomp remains independent of this Routine.

Ram keeps the strong stomp sound while its Walk direction is locked. Heavy
Stomp uses the stock ledge-hop landing sound when Walk direction is unlocked.
Ram has separate role-filtered notice conditions: Wild subjects capture Player;
Follower subjects capture the nearest visible Wild Pokémon. Both use the same
32-tile cardinal-line Vision, Until Crash activation and 100-frame cooldown.
The captured target supplies the first charge heading. The shared locked Walk
ignores ordinary previous-tile avoidance and keeps that heading and acceleration.
Follower damage recipients remain
Wild Pokémon, with the existing collision damage and Jump knockback.

### Shared Throw targets and pickup route

Follower resolves before Capability in both the ROM and Workshop. The same
Find Throw Cargo, Find Throw Position, and Throw Held Actor applications serve
Wild and Follower roles. Explicit subject-role filters keep player notice on
Wild actors and autonomous Throw off mounted actors.
Follower sight and accepted Player damage are separate visible conditions in
Find Throw Cargo. Sight captures the exact noticed Pokémon. Damage captures
the exact Pokémon whose physical contact lowered Player HP, including a thrown
Cargo rather than its carrier. Damage has no Vision requirement. Both conditions
can activate Find Throw Cargo during ordinary autonomous movement, before the
next legal pickup intent. The accepted move finishes with its original plan; a held or
recovering throw cannot be replaced by either trigger. Both Follower paths
select that same Object of Interest as Cargo and use the authored Throw Away
From Player Modifier. Wild Throw notices Player, selects a separate Cargo,
and aims that Cargo toward Player. All paths share pickup, carry and flight.

The initiating condition captures one full identity in Object of Interest
(the stored `Trigger` key). The selected actor goes into `Cargo`.
The explicit `object-of-interest-itself` selector restricts Cargo to that same
full current identity. The ordinary `trigger` prerequisite retains separate
Cargo selection for Wild Throw. Each binding is a value with
its source condition/application and authored lifetime. It does not own motion.
Later conditions cannot replace a bound identity. Each stage resolves the
identity's current position. A lost identity invokes the authored drop/clear
and retry response; it never falls back to the player.
An unrelated actor preparation can invalidate the shared condition cache during
windup. Binding reads therefore refresh current actor positions through the
existing frame builder and current player coordinates through the stock Player
owner. A position-only rebuild leaves the condition cache invalid so the next
normal evaluation still builds all candidate contexts. Removing a prepared actor
also invalidates this cache. A complete same-frame cache remains reusable, so
binding observations preserve the normal sight pass and its candidate contexts.
The subject must remain
current; exact target identity and authored expiry are still checked. The
private refresh uses the existing Field reserve at `0x02208600..0x02208700`
without changing the public condition or Throw service tables.
The release primitive preserves its explicit Trigger-line target even though
the carrier has no locomotion during release. Target and locomotion are separate
values; removing carrier locomotion must not erase the release target.
The native windup latch saves X/Z and base Y from the resolved aim. Wild Throw
uses the same current Object of Interest identity and its authenticated map
object position Y. Temporary face, bob and seat offsets do not become Cargo's
support height; a ground actor under a roof remains a ground aim. Throw Away
uses the legal endpoint's authenticated support height. Both full Object of
Interest and Cargo bindings must pass their lifetime checks before launch.
Target motion does not replace the saved aim. Away launch also rechecks that
same landing and its greater separation from the current Player. Only the
accepted held Cargo flight uses the saved Y through the shared trajectory and
terminal ACK. Ordinary Hop and post-flight ground settling retain their
existing landing-height owner.
Throw uses the shared accepted Hop plan with its normal flags. The Forced
motion bit does not mark a Throw. Flight proof follows the exact native
carrier/Cargo claim through release and accepted START, then requires that
same full Cargo owner and plan through landing and control return.

Cargo keeps its own profiles and accepted moves after selection and claim.
An uncarried pickup claim is a pursuit relation, not exclusive ownership.
Several current carriers can bind and pursue the same eligible Cargo. The
first carrier to pass the shared physical pickup check takes HELD control.
Another pursuit does not veto that check; a carried relation or HELD control
does. After the successful synchronous handoff, the same cleanup owner retires
every other uncarried claim and its target bindings immediately. A losing
carrier's accepted move still reaches its normal terminal boundary. Removing
one pursuit preserves other current claims and unrelated launched flights.
An incoming uncarried pursuit also does not prevent an actor from starting
its own pursuit. The first physical pickup retires Cargo's outgoing uncarried
pursuit before it writes HELD control, including reciprocal claims. Ordinary
Throw abort clears only that actor's outgoing relation and bindings. Identity
retirement clears incoming relations as well. A true carried relation remains
an ownership veto; a carrier cannot be picked up with nested held Cargo.
An incoming pickup claim does not change the target's profiles, condition
evaluation, movement, return move, overlap recovery, cry or encounter choices.
Only physical pickup transfers control to HELD. The catalog has no condition
that changes a target's behavior solely because it is marked for pickup.
Selection uses a single Field-owned resumable route
query over the active loaded map cells, with no Cargo-distance cutoff. It
uses the resolved Walk/Hop candidates, strict support heights, occupancy and
Actor reservations. Unknown data remains pending; storage exhaustion is a
resource limit, not proof that a route is blocked. The query returns one
legal next step to existing START. It has no second movement owner.

Cargo selection does not exclude a current Pokémon solely because it is the
Follower, captured, held, entering battle, doing spawn entry, or carrying another
Pokémon. Self and full current identity checks still apply. Selection does not
transfer physical ownership: the atomic pickup check still defers unavailable
targets and keeps one HELD owner.

Wild Throw ranks reachable Cargo by Chebyshev tile distance from its current
position to a native-proved legal pickup standing position. This is a geometric
distance, not a shortest-path length. Raw Cargo XY supplies only a lower bound
for skipping a candidate that cannot improve the winner. The sole route
workspace checks the incumbent first, then challengers, then re-proves the
selected full identity before granting eligibility. A changed origin keeps the
active search; saved standing positions refresh score estimates. A moved
incumbent outside its saved reach requires a new proof. Unknown data and storage
limits never count as an unreachable incumbent.

The visible profile controls are `cargoTargetCheckInterval` (1–15 frames,
initially12) and `cargoTargetSwitchAdvantage` (0–3 tiles, initially1).
A bound Wild checks again after the interval. A challenger must be strictly
closer and meet the advantage; an invalid or proved-unreachable incumbent needs
no advantage. Pending checks keep the existing claim and allow accepted
Walk/Hop/Skid movement to finish, but grant no new START. The Throw owner releases
only the old unheld Cargo claim and Cargo-dependent condition rows; Player
Object of Interest stays bound. Normal condition admission then captures the
proved replacement. HELD stops target switching, and Follower target choice
remains the exact Object of Interest.

The single route workspace gives competing current carriers turns after a
completed reachable search. A waiting request does not erase the current
frame's observation-to-START receipt or preempt an unfinished graph. On a later
frame, the owner yields to the next valid waiter in circular slot order. The
handoff preserves native work already spent that frame, full Cargo bindings,
claims and accepted motion. Invalid or unavailable requests leave the wait
queue. Waiting metadata uses the query's existing tail padding; it does not
create another path search, change the query heap size or expand its budgets.

The route proves the full path at the current dynamic revision. A bounded
ledger of complete native object, player-front and reservation changes can
reuse an edge only when its dynamic footprint did not change. One Tick may
run at most one native edge/goal query and sixteen internal search units.
A movement-policy key contains only the current locomotion's legal-route
inputs. An unlimited native range axis (`-1`) has no relative range anchor in
that key; a Hop render midpoint and its final rebase cannot erase the graph.
Bounded axes keep their real relative anchors. Hop timing, vertical clearance
and elevation scales remain Hop inputs and do not invalidate a Walk route.
An accepted move does not pause an already captured Trigger's Cargo search.
The frame driver services that same query while the carrier moves or settles, only when
its authored options require reachable Cargo. A successful current route can
admit Cargo through the shared prepared evaluator's private Cargo-only mode.
Native target access requires the accepted nonzero motion reservation while an
actor moves or waits for commit. After commit releases that reservation, a
settling actor stays accessible only at its accepted endpoint, with the same
plan epoch and valid current terrain and support. Full actor identity checks
still apply.
The evaluator validates the whole prepared batch, then evaluates only reachable
ActorFacts Cargo-capture entries. It keeps the normal role, target-pool, chance,
binding and full-identity checks. Evaluation uses a local copy of entry state:
saved rows, timers, published applications and the accepted move do not change.
A successful admission stores the full Cargo binding. Repeated binding reads
cannot replace or refresh it. Wild Throw may explicitly release unheld Cargo
under the ranking contract above. At the normal idle boundary, ordinary
evaluation activates its profile and emits the authored alert once.
Another target or Cargo publication cannot repeat that alert when the bound
full Object of Interest, active applications and both profile lanes are
unchanged. A new Interest or changed profile retains its authored alert.
The synchronous mode uses the existing WorldView.reservedBinding byte: zero
for ordinary evaluation and one for Cargo-only evaluation. The adapter builds
and validates the current Frame before observation; the Cargo callback borrows
that frame and checks its validity. The adapter sets the warm mode before
observation and prepared evaluation, then resets it before return. No service
table, persistent state or movement owner is added.
A duplicate intent observation in the same Actor frame cannot spend another
native query. Lost route bindings defer their abort until the existing idle
boundary. Invalid owner or prepared data still uses the existing fail-closed
cleanup. Held, windup, recovery, startup, Crash and battle gates remain.
A dirty goal cannot repeatedly take the native turn needed by a deferred edge.
Cached proof work can advance without another native query. Moving Cargo or
changed occupancy marks the goal dirty without restarting unfinished edge scoring. A retained goal can guide exploration, but it cannot grant
eligibility until its current native goal check and full directed path pass.
The same standing pose remains usable while it is inside current authored
reach and passes native checks. If Cargo occupies it, the query chooses a new goal.
When Subject or Cargo moves into authored pickup range, the current Subject
pose gets the first native goal check. A blocked result resumes the full normal
goal scan. XY proximity grants no pickup permission and adds no native work
quota; accepted pickup still needs the current native and identity checks.
A new Cargo search first tries the nearest standing pose inside authored
pickup reach. This is one native attempt; a blocked or stale priority pose
returns to the complete pickup square. Edge scoring stops at the first
unbeatable zero-distance candidate, then uses the same native edge and full
path proof. Neither shortcut grants eligibility from XY alone.
A partially proved path can resume only when the complete change ledger shows
that its checked suffix is unchanged. Each bounded witness block consumes
one of the same sixteen work units; a changed suffix restarts proof. Native
occupancy already ignores the current Subject object and its own reservation.
The ledger omits only those same full-identity dependencies, while current
origin and policy still change normally. It retains all other objects,
reservations and player-front dependencies. The standing goal still
needs a current native check before eligibility.
Custom Walk completion rebases the native range anchor to its landing tile.
The query keys that policy by the anchor's relative offset. During an ordinary
accepted Walk, the renderer advances the current tile at the midpoint while
the previous tile retains the accepted origin. Moving and commit-pending
Walks without skid use that previous tile for this policy offset. All other
states use the current tile. This keeps both the midpoint and completed step
from clearing the graph. The route root and real START still use the actual
native position and anchor; a future route pose uses its completed pose as
its anchor. A real offset, range, terrain rule, flag or grid policy change
still invalidates old work.
Actual pickup rechecks both full identities, the current pursuit, native
support and authored reach/height before held control changes. The carrier
keeps its existing idle dispatch boundary. Cargo can still be in an ordinary
accepted Walk or Hop, including its commit or landing pause. Its current fx32
X/Z distance and Y height, including a Hop arc, must be in the authored reach.
Out-of-reach Cargo keeps its own motion and profiles. No dwell or forced stop
is required before pickup.

At pickup, the current Cargo plan, full owner, Field, reservation and saved
motion receipt must agree. The existing Actor boundary cancels only that
Cargo motion and returns its control before the synchronous HELD commit.
The carrier's motion and policy are unchanged. Failed admission, missing
helper, queued combat or a rejected cancel cannot write HELD or a carried
claim. Successful cancellation clears only Cargo's motion presentation,
Return record and deferred condition presentation before its held pose is
synced. Forced combat, spawn/Fly In, teleport, skid, reposition and intermediate
staged moves remain outside moving pickup; normal full-leg staged Walk/Hop
uses the same rule. A held or stale actor cannot enter this handoff.

The unchanged private Wild cancel leaf is linked at `0x023B9048` and copied
as 200 authenticated bytes into boot-resident Actor158, after Field Rest tint
and before the anchored Motion model at `0x023B9220`. Wild still owns its
source and synchronous calls. It has no second motion owner or persistent
state. The Wild output excludes this distinct section; the package checks
require the exact hosted Thumb source, Actor copy and ROM bytes to agree.
Actor158 is loaded before gameplay and is retained when Wild149 unloads;
this cancel call cannot continue after its Wild caller returns.

The route workspace has one current owner. A current Follower search for its
exact Object of interest can replace an unfinished Wild search only while
that Wild actor is idle, has no bound Cargo, throw relation, reservation,
carrier/target/capture claim, or owned pickup. The same full Subject and target
identities still pass native validation. This handoff clears route work while
retaining the current frame's used query allowance; it cannot run a second
native search in that frame. Reserved or held Cargo keeps its owner. The
handoff changes no authored notice, windup, or recovery pause.

Before waiting for that workspace, every search checks its current eligible
Cargo mask against the current Frame. An unavailable bound Cargo or exact
Object of interest returns Invalid; an unbound search with no eligible Cargo
returns Unreachable. The existing idle abort then clears that search. This
uses eligibility, which admits ordinary moving targets, rather than requiring
a stopped target. It does not change the foreign owner's route, binding,
claim, frame allowance, or native work.

A storage-exhausted Cargo query is terminal Resource Limit, not Unreachable.
Both Resource Limit and a completed Unreachable search release their Throw
chain at the existing idle boundary, including a Wild search with Player
Interest and no bound Cargo. The
next current, idle, unclaimed search can reuse the same workspace. Owner
changes and same-owner retries keep the frame's used native-query allowance;
the same owner cannot restart in that frame. The new owner is published before
scope or position can defer. Bound Cargo, claims and accepted motion keep
their existing protection. An ordinary Pending search is not preempted by
another Wild search.

Query code is one authenticated relocatable code-addon member. Version 8 has a
192-byte typed entry with 38 callbacks, an image limit of `0xC154`, and a
complete-package limit of `0xC600`. The resident private Query service keeps its
version 2 and 24-byte table. The Condition service keeps its 24-byte table with
private version 13. Slot 152 dispatches typed native condition calls; callback
offsets stay fixed. The Cargo prefix limit is `0x8800`.

Catalog Blob version95 stores18-byte condition options. An optional parent
application is a global16-bit ID; active masks still use the current species'
local bank. Bound-target distance uses the full current captured handle and
includes its tile at distance0. The parent and distance checks form one
conjunction in the same resolution pass. Invalid options reject the batch
before state changes.

The portable Resolver now runs in this loaded image. Actor uses a small typed
forwarding wrapper. The existing current-Field service gate rejects unloaded or
stale context before dispatch. A 32-byte private packet names validation,
resolution or class inspection and borrows the immutable Blob, current request
and caller-owned outputs for one synchronous call. Resolution validates inside
Query once. It does not re-enter Acquire or retain a pointer. Public request 44
and result 216-byte layouts and resident Motion entry points stay fixed.

Appended return, condition, resolver and atomic pickup adapters are physical
code hosts for the sole shared Motion, Condition and Resolver implementations.
They add no second movement or condition engine. The packer checks named tail
entry references, fixed imports, relocations and body bytes. The Cargo observer
authenticates the complete image at discovery and the current Cargo prefix on
each Tick. Its per-Tick read cap remains 36 KiB at `0x9000`. The loader allocates
the exact package size and keeps the 32 KiB free-heap reserve.

Private Wild condition callers, cleared-Throw capture retirement, and the full
Throw cleanup wrapper occupy344 aligned bytes in a356-byte capsule within
existing388-byte Selector152 filler at `0x023C2C1C`. Its last32 bytes host the
exact stock-coordinate import check. A strict fully linked capsule copies the
Wild leaves without a link cycle. Throw observation and BindingPosition retain
their fixed entry addresses.
The moving condition helper uses fresh stock Player coordinates and traces only
the shared core's geometrically eligible targets through the existing solid-tile
trace. Moving checks share normal condition publication and profile resolution;
alerts and new intent headings wait for the next legal intent. Its four new
imports are exact named Thumb targets; the resident
import table uses nine words within its original36-byte reserve.

Normal and moving condition checks read current physical target support. The
native target-access pass reuses one immediately preceding support result only
when its original height input and physical height flags (bits23 and29) match
the subject query. The Field, tile, current surface hit and callback stay the
same within that call. Identity, accepted motion, terrain and failure checks
remain fresh. No result is kept across frames.
The full moving condition pass already reads Cargo. Only a completed successful
pass, including target publication, skips the extra Warm Cargo call in that actor
frame. An early skip or failed pass keeps the fallback. That fallback reads
support only when a prepared Actor Facts row can capture Cargo and requires
pickup reach, matching the shared Warm reducer. Other conditions keep their
normal per-frame checks. A newly captured Interest or changed Cargo-search
profile can start its route on the next actor frame. The full prepared batch
still validates before any timer or binding change.

The fixed Field loader publishes typed callbacks only for the current Field
epoch and map generation. Code, its temporary archive handle, and the sole lazy
route workspace use stock Field resource heap4. Code admission leaves 32 KiB
free; the 25 KB lazy route workspace leaves 16 KiB
(`OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE`). FIELD1 also holds the behavior
catalog and sits near 63 KB free on a populated route, so the 32 KiB rule
refused every pickup and entry route.
Stock script contexts and message banks retain World heap11. Before stock
parent Field exit destroys heap4, the existing Wild owner drains the query,
bindings and owned data while Field and Selector are still loaded. A private
completion receipt makes later overlay release safe; a fresh successful
Acquire clears that receipt. Acquire also requires a ready Field. Drain runs
before Selector shutdown and before a context rebind. Native engine callbacks
are borrowed only for a synchronous call.

A retained image can rebind within the same still-live Field. An epoch change
must be the exact next non-zero epoch and map generation together; a changed
Field, skipped epoch or one-sided epoch change is rejected. Old query work
drains before the new owner is published, and Acquire keeps its exact owner
check. Wild acquires that new owner before it prepares retained conditions.
Wild first checks Field overlay1 in the stock MAIN-region loaded table,
using the exact active flag and overlay ID across its eight slots. It then
passes the loaded Condition gate before entering the private Selector
current-context helper. That gate checks the same stock loaded table and
keeps the Selector direct-load and service-version guards. This fixed parent
lives in MAIN RAM in the supported ROM. Neither check reads archive metadata;
no retained loaded-state cache replaces the stock table. A borrowed transition call must name a ready map and
the exact nonzero Actor context before that helper can acquire or drain.
Failed admission uses the existing transition failure response: it does not
acknowledge preparation or claim that the retained actors were restored.

The native Cargo bridge maps slot bits to current compact observation bits
before the reducer. It publishes slot bits again using the proved full Cargo
identity. A same-frame cached route can survive observation order changes;
a stale identity or a missing native slot cannot gain pickup permission.
Wild's prerequisite-only option excludes its Trigger from separate Cargo.
The authored exact-Interest option3 admits that same current actor as Follower
Cargo; it still needs the shared current route, full identities and legal pickup.

The generic collision damage options include explicit recipients: Player,
Wild, Allied, their combinations, or All. This filter applies to ground and
flight damage. Follower supplies Wild-only recipients to the shared launch
profile. Carrying and landing restore the Cargo actor's own attack options.
Recipient overrides use their packed setter and are excluded from the generic
field-mask copy. Their mask bit must not copy an unrelated Walk-speed field;
changing a recipient filter preserves unauthored Owner and Tired speeds.
Mounted body and rider contacts use their separate collision checks. A hit to
one cannot forward damage to the other without that second contact.

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

Until Crash entries capture one target at admission and keep that activation
through loss of sight, without a duration. Only an adopted real
`WORLD_EFFECT_CRASH` ends this lifetime. Role adapters deliver that receipt to
the prepared entry state independently of trace capture; a reset, blocked
non-crashing Walk, timer, or cosmetic shake does not count as Crash. Cooldown
starts when the receipt is consumed at the next intent boundary. The trigger
must then become false and true again before a new activation can start.
The false-to-true event must follow cooldown. Current subject, map, field and
target identity guards still apply.

All authored conditions run through the same prepared reducer during ordinary
autonomous movement frames. While True, Timed, Until Crash, damage and Cargo
conditions keep their normal fact and lifetime rules. Activation, target capture,
profile metadata and contact damage settings take effect at the observed frame.
The accepted motion plan, reservation, duration and facing remain unchanged.
Bit5 records only pending entry presentation: the next legal intent applies the
alert and new target heading once, without another sight/chance roll or timer
restart. Bit6 retains an ended Timed episode only for its later authored Tired
reaction. An expired or invalid entry clears the pending entry marker. Field, actor and control
cleanup also clears it. Geometry selects eligible targets before native terrain
traces; inverse visibility checks also trace targets needed to prove that sight
is blocked. Fixed actor/entry limits bound this work. Cargo warm capture remains
a bounded fallback within the same condition owner when the full moving pass
does not complete.

Vision is one shared value-only service for Pokémon and the player. The initial
Vision is a 90-degree forward cone with three tiles of range, awareness of all
eight adjacent tiles, and solid-terrain occlusion. Actors do not block sight.
Observer and target tiles are not blockers. Invalid or unloaded terrain fails
closed.

Custom Vision also supports a strict forward cardinal line and all four
cardinal lines independent of facing, up to 32 tiles. Off-axis targets fail
before occlusion work. Adjacent awareness is an independent option. Ram
disables it and uses the full 32-tile cardinal lines. A fresh charge clears
ordinary Walk momentum and chooses its first heading toward the captured
target. Later intent boundaries keep the charge's committed heading and speed.
Custom Vision can also enable same-tile awareness. It uses option bit8 in the
existing two-byte Vision value and is off when omitted. The default/current
Vision still rejects same-tile targets. Self-targets remain excluded by full
actor identity; two distinct actors may share a tile.

Profiles own stable Current Vision fields. At bind or rebind, the controller
resolves and caches Current Vision from `Default`, matching normal
applications, and the forced-role profile. Conditional applications are
excluded, so a profile cannot change the Vision that activates itself. A
vision-based condition either uses Current Vision or owns one inline Custom
Vision. The player uses the same evaluator and initial defaults; player tuning
is not profile authoring.

Visibility is evaluated during ordinary autonomous motion and at intent boundaries. Geometry rejects candidates
outside the cone before the adapter traces the short line to a candidate. The
actor search remains bounded by the ten-actor world view. Conditions and
behavior planning consume the same visibility result.

Target-required activation fails when no valid target exists. If a captured
actor handle becomes stale, the complete activation ends before resolution.
The evaluator never keeps a slot number or engine pointer as target identity.

All timer values use the public actor-system frame returned by Inspect. Expiry
comparison is unsigned and wrap-safe. The role adapter prepares applicable
entries at bind and supplies bounded observations during ordinary autonomous
motion and when it is ready to ask for a new intent.

Wild lazily allocates one 3,100-byte condition workspace from `HEAPID_WORLD`.
It contains ten fixed 88-byte prepared actor records with 16-bit global condition
indexes. Each subject still has at most 32 prepared entries. Bind prepares only the
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
adapter resolves again when the active application mask, winning condition,
full captured target identity, or target source changes. Position changes alone
refresh target coordinates and reuse the cached resolution. The evaluator
compares this actor's prepared state before and after its update; shared scratch
from another actor cannot decide reuse. A transient bit in scratch entry0
reports a publication change and is cleared on each call. Private pure helpers
use boot-reserved Chain code and the loaded Selector tail; the Condition service
keeps evaluation ownership, and Query drains before Selector unloads.
A stale captured actor handle
clears the conditional result and that intent decision fails closed.
Trace-disabled calls do not walk condition trace records.

A timed retrigger always restarts its duration. It requests trigger presentation
only when the trigger also changes the resolved mask or publication. When one
timed profile ends, Tired starts only if no other timed conditional application
remains active. The role boundary masks the adapter's trigger, timed-end and
profile-change bits. Wild's private `FAIL_CLOSED` uses a separate bit, so a
profile change cannot be read as failure.

Throw uses the same three ordered conditional Capability applications for
Wild and Follower carriers. The initiating condition captures `Trigger`.
Wild Find Throw Cargo selects a distinct reachable actor into `Cargo`.
Follower sight and accepted player-damage conditions capture Object of interest
independently. Follower Cargo option3 selects that exact same current actor.
Both Follower trigger conditions contribute Find Throw Cargo before selection.
A valid-Interest condition keeps that profile active during bounded Pending work.
Sight and accepted damage retain separate condition identities and eligibility
rules; they are not one combined predicate. Both roles use Chase with pickup on
reach. Search covers the active map without a distance cutoff. Cargo keeps its own
profiles and accepted movement during pursuit. At the carrier's normal idle
boundary, pickup can take a current ordinary moving Walk/Hop Cargo when its
real body is within reach and height. It cancels only that Cargo's exact
accepted motion through Actor, then transfers control to HELD without an
idle dwell. After the shared motion ticks, idle dispatch checks existing Throw
carriers before other actors. It keeps one visit per actor and the normal
role, condition, profile, Trigger, route and atomic pickup checks. A legal
handoff also takes completed Cargo before its next own move starts. The atomic
pickup gate checks the current bound actors and their support and actual reach
before a pending route refresh can end the carrier pass. It can take adjacent
Cargo without waiting for a new route receipt. A deferred pickup leaves Cargo
free to continue its accepted move or start its normal next move. Claim priority is
fixed for that dispatch call, so release or capture cannot visit a slot twice.
When a fully validated moving Cargo is outside physical pickup reach, pickup
returns Deferred and keeps its current binding and claim. A logical route endpoint
alone cannot make the carrier abort while that Cargo is still moving into reach.
Idle Cargo outside reach and failed identity or ownership checks remain blocked.
Find Throw Position applies when an actor is held and uses Chase toward a
valid launch tile. An in-range Wild aim does not need row or column alignment;
its range remains the Manhattan tile distance. Follower's authored Throw Away attack overrides
only the held aim with target14: a safe endpoint at exact Throw range and
greater Chebyshev separation from Player. The current pickup tile can already
have a legal Away aim and then needs no Position movement. The native plan
saves its endpoint and support height for the same-endpoint recheck at launch.
Away selection projects the Player-to-carrier vector to that exact maximum-axis
range and rounds the shorter axis to the nearest tile. A noncardinal candidate
precedes the four existing cardinal fallbacks, with at most five landing queries;
cardinal-only selection keeps its previous four-query bound. Facing is only a
presentation value. The shared trajectory validates each crossed cell for an
unequal angle and preserves ordinary cardinal and 45-degree Hop probes.
Wild keeps its existing separate Trigger aim. Both search profiles divide the earlier Walk and
Hop travel times by 2 at the next intent boundary. An accepted move finishes
with its original timing. Release and normal return do not retain a search
profile's division. Throw Held Actor applies when that line is valid
and selects a windup and launch behavior. Its resolved `attacking`, minimum
impact speed, and damage are copied to the launched actor's flight. The normal
Tired behavior supplies recovery after the authored recovery duration.
Successful pickup ends the Cargo actor's prior recovery when it clears that
actor's tired state and timer. Failed pickup changes neither; other actors'
recovery remains intact. Landing therefore cannot retain a recovery flag
whose timer pickup already removed.
Trigger presentation, windup and recovery use the authored profile settings.
A pending route refresh can retain the already admitted Cargo condition only
for the same current Subject, Trigger and Cargo identities and eligible native
Cargo slot. Its typed receipt grants no route eligibility or next edge; START
and pickup still require a fresh proved route. New Cargo selection gets no
retention flag. Unknown flags, lost identities and invalid or unreachable
routes cannot retain that condition. This prevents a moving Cargo's pending
check from being mistaken for a stale target and clearing the Throw chain.

The condition observer publishes actor facts for reserved cargo, held cargo,
a valid throw line, and recovery. A condition may require and forbid sets of
those facts. Trigger perception and reachable Cargo selection use separate
bindings and filters. Later Throw
applications override the earlier behavior at intent boundaries; an accepted
motion completes before the new profile acts. The engine retains only the
generation-safe cargo reservation, held control, motion execution, collision,
and terminal cleanup. It does not choose the next Throw stage by a private
`PICKUP_THROW` controller.

A carrier hit before HELD can arrive while only the Sight Trigger is captured;
Cargo need not exist yet. A failed or interrupted Throw clears its bindings and
retires the capturing and binding-dependent condition rows, including their
ACTIVE state. It keeps unrelated conditions and cooldown history. The next
eligible Sight check can capture the same current actor again. A hit on a
fully held carrier keeps valid Cargo control and replans the windup afterward.
If a wall or another object blocks all knockback paths, the hit still retires
an unheld carrier's Throw capture before combat acknowledges the hit.

The Throw observation and reservation API remains an append-only service
in resident overlay 161, starting at `0x01FFC180`. The existing player-health
API and collision entry addresses stay fixed. Checked native wrappers borrow
typed Query callbacks for shared Throw observation and held-release intent.
The pure swept-contact geometry and accepted Player-damage publication also
use this authenticated image. Event storage remains Field-owned, and only an
accepted Player HP hit publishes its full physical-source identity. These leaves
read profile facts and use the existing actor, pickup and movement adapters;
they add no Throw stage controller or second movement path. Combat follows it
at `0x01FFD580`; their ITCM reservation ends at
`0x01FFFF80`, also the boot ITCM arena low bound. This leaves128 bytes below
the stock `0x02000000` high bound and retains the exception scratch at the top.
The existing `0x01FFF580..0x01FFFB80` capsules hold linked Wild and Mount role
adapters, including the Mount hit-ground helper at `0x01FFF700`. The Wild hit
adapter occupies `0x01FFFB80..0x01FFFF20`; the final HP tail ends by
`0x01FFFF80`. Private calls resolve in their owning overlay before packaging.
The combat service and movement model remain shared. Existing fixed entry
addresses stay unchanged.

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
resolver role. Follower is not forced in the mounted request. Mounted
explicitly sets Movement Chain to Off and applies its authored speed settings;
other normal selected Owner fields remain inherited. This is profile
composition, with no hidden mounted-role chain rule. Mounted Walk can use the
shared chain counter if its profile settings enable it. The mounted adapter
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

Wild and Follower adapters evaluate all conditions during ordinary autonomous
motion and at a legal intent boundary,
before an ordinary Routine pause can delay a new conditional profile. A changed
active profile clears that old pause; an unchanged profile or return to Routine
keeps it. Accepted native or shared motion, held control, staged work, emotes,
spawn movement, Crash and battle work still own their existing boundaries.
A private per-frame slot mask records completed condition checks, including
nested chain completion, so the later idle pass cannot check that actor twice.
The frame task clears the mask at entry. Normal Walk completion can still
request its next intent in that frame, so Ram does not gain a pause per tile.
Mounted follower control does not evaluate autonomous conditions. Alert is a
presentation response to a qualifying trigger, not a controller state or a
condition predicate.

Experimental `Basic attack` is currently disabled by a0% condition chance.
Its all-species pool and behavior remain saved for later use. When enabled, its while-true
Custom Vision condition selects the nearest Wild or Follower Pokémon in the
eight adjacent tiles or on the same tile. Its same-tile awareness option is on.
Held and recovering subjects are excluded. It composes
Chase/Hop toward that exact Object of interest, one-tile cardinal or diagonal
travel, Object of interest-only destination permission, inherited Hop time
without a speed operator, attacking enabled, minimum impact speed one and damage20.
Stationary contact cannot deal damage.
On-reach is None; knockback is inherited. With Default's Hop time four and no
knockback, the adjacent flat Hop takes four frames and removes20 real Pokémon
HP on accepted contact. Face movement is enabled. Return after move makes an
ordinary autonomous Walk or Hop return to its captured start tile using the
same shared Motion engine and admitted time/style. The return starts as soon
as the outward leg commits, with no movement or chain pause between legs.
One existing passive chain Pause follows the pair: one move, no movement
variance,100% Pause, authored base40 plus variance40 gives20–40 native frames.
Hop pause is zero, so it adds no second wait. The return is exact-origin only;
it rechecks support, side tiles, occupancy and reservations. A blocked origin
ends the return request, and a temporary reservation allows at most two distinct
Actor retry frames. Repeated native passes in the same frame do not spend extra
retries. Actor rebind, Field change, held control, capture, despawn and queued
combat clear the pair. Spawn entry, staged travel, forced hits and Mounted
control do not start autonomous return pairs.
The same condition owner ends it when no
eligible Pokémon remains on the same tile or an adjacent tile. Reaching the
target's tile alone no longer makes the condition false.

An alert with zero duration and no bubble uses the same intent boundary. It
does not run an alert-resume reset or add a movement cooldown. A newly triggered
profile that changes ordinary Walk to direction-locked Walk clears the prior
run's momentum at this legal boundary. Its first step aims at the admitted
target; later charge steps keep their accepted heading and acceleration. Ram
authors zero alert time and no bubble so it starts at that same boundary.

Direction lock uses an existing Walk heading only while its momentum speed is
nonzero. A stopped or newly zeroed Walk has no committed heading. Its first
proposal uses the admitted target direction, including in preview and the
shared role request. Later proposals retain the heading and acceleration.

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
Value `34` adds opt-in Linear speed. Movement Style exposes its time to full
speed in moving frames; the packed interval byte carries that duration in
this mode. It interpolates reciprocal speed over completed normal Walk time,
samples at tile boundaries, and carries fractional tile time only after an
accepted start. Existing modes and saved profiles remain unchanged.
Linear variance fades on that same elapsed clock, with width
`V - floor(min(elapsed, ramp) * V / ramp)`. Speed reaches its authored limit
and variance reaches zero at the first normal tile admission after the ramp.
The old cap-time byte remains reserved and zero; there is no second clock.

Momentum survives a same-lane profile change. If base time or acceleration
mode changes, the next input retunes the linear curve from the last displayed
tile time. This does not clear direction, turn or stop skid, reservation,
chain state, or a buffered direction. A real lane change, rest or Crash can
still reset momentum. With unchanged tuning, elapsed time and fractional carry
remain exact.

A condition can replace the lane before an accepted Walk ends. At its real
terminal boundary, a changed base time or lane may reset old momentum, but the
accepted Walk still commits and returns control exactly once. The policy
returns `CONSUMED` for that accepted completion. It must not clear its pending
step and then return `IGNORED`, which leaves Motion in `COMMIT_PENDING` with no
terminal policy value for a later retry. An unaccepted or duplicate completion
still earns no commit.

The exact contract and turn/stop rules are in the
[Walk timing specification](../overworld_walk_frame_timing_spec.md#acceleration-and-momentum).
The shared Walk Reset/Input implementation is physically hosted in the
boot-resident player-health overlay's free code reservation at `0x01FFF000`
and `0x01FFF040`. Its owner remains Motion Policy; it has no HP dependency.
The Wild runtime forwards those calls and retains Start Result and Commit.
The private Wild reset and Crash-publish wrappers use the empty tail of the
existing resident carrier capsule at `0x01FFF898..0x01FFF90A`. The carrier entry
stays at `0x01FFF800`; the package gates check each leaf, its calls, and its
exact loaded bytes. Their physical host adds no HP dependency or movement owner.
The unchanged previous-tile write leaf occupies `0x01FFF90A..0x01FFF930`.
The28-byte retained-spawn mask check occupies `0x01FFF930..0x01FFF94C`,
followed by the unchanged previous-tile read at `0x01FFF94C..0x01FFF980`.
This keeps the Wild file within its fixed slot while
retaining all existing published entries and the same Walk policy.
`PREVIEW_INPUT` runs Input on a policy copy. It reports the original pending
step and whether the same input selects a skid. Wild ledge checks and mounted
diagonal checks use it to defer raw input geometry until the real skid tile
is known. It changes no live policy, timing, RNG, trace, or reservation.
Mounted proposal transport preserves the fractional carry and turn rewind in
a four-byte adapter capsule at `0x01FFF57C`. The full mounted proposal save
entry is hosted at `0x01FFF400`; transport save/restore entries are hosted at
`0x01FFF480` and `0x01FFF4A0`. Every mounted proposal overwrites
it before Start Result; the actor policy owns the committed values. No mount
state offset or combat capsule address changes. Mounted Start Result is
hosted at `0x01FFF4C0`. The actor command acknowledgement cache occupies a
separate 48-byte Actor-owned loaded capsule at `0x01FFF380..0x01FFF3B0`;
Actor initialization clears it with the main state. Policy stays 36 bytes and
actor stride stays 176 bytes. The contiguous actor state is 2440 bytes inside
its unchanged 2448-byte reservation; the debug descriptor publishes the new
trace offsets. Shared Motion code remains at its prior fixed base and imports.
Normal Walk variance keeps nominal momentum separate from the displayed tile
time. With legacy acceleration enabled, the first maximum-speed tile retains full
variance. Each later eligible normal Walk commit reduces the range by the
acceleration amount (or halves it, rounding down, for `/2`), until zero.
This is per tile, independent of the below-cap acceleration cadence. The
existing momentum tile counter records capped-speed commits, saturating at255;
below the cap it retains its acceleration-cadence role. Stops and accepted
turns reset it; rejected starts and skid tiles cannot advance it. Linear speed
instead uses completed moving time for both its speed ramp and variance fade.
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
remains a stop request and follows the existing stop/skid rules. Mounted
player input has a short release grace first: while a fast Walk step runs
(nominal time at most `OVERWORLD_MOUNT_RELEASE_GRACE_MAX_TIME`, 4 frames per
tile), mounted chain control remembers the held D-pad keys in the mount
state's `directionReleaseGrace` byte. For the next
`OVERWORLD_MOUNT_RELEASE_GRACE_FRAMES` (4) blank control frames it keeps
those keys, so a rolled turn or brief release at a tile boundary while
sprinting continues or turns instead of stopping. The newest held key wins,
so a turn pressed during the step is kept. Held while stopped or slower, the
grace only counts down, so a press from a standstill, a slow single-tile Walk
or a push against a wall never carries an extra tile. After the grace, `NONE`
is the ordinary stop request. After the full
normal Wild direction search cannot start a step, the adapter can submit one
separate, profile-gated `NONE` directly to Walk policy. This does not reinterpret
an individual rejected direction and does not use the role or chain controller.
When a full random or untargeted Wild `WANDER`/`HOP` search is blocked, the
adapter reports that no movement started, preserves the committed facing, and
waits one normal movement pause before it searches again. An explicit
`TURN_AROUND` action and a directed blocked fallback can still change facing
without starting a step.

Once profile and momentum select a skid, the world cannot veto it. Turn and
stop skids use one-tile motion proposals. Each proposal validates its immediate
destination and diagonal side tiles; a blocker publishes Crash and clears
momentum at the last clear tile. If the first tile is blocked, Crash occurs in
place. A future skid tile or recovery destination is never a pre-start gate.
The recovery Walk checks its own tile when it starts. Reposition Skids retain
their selected direction, travel the clear prefix, and end in Crash at the
first blocker, including an in-place skid when the first tile is blocked.
No skid may cross a blocked tile. The legacy `planTurnSkidPath` data bit remains
packed for compatibility but has no clearance-veto meaning. Profile Deck shows
the fixed collision rule beside turn and stop skid controls.
An ordinary Walk still checks only its next tile. Sprint can therefore reach
the last clear tile before a wall or non-player actor even if a later obstacle
Hop has no safe landing. The actual Hop validates the world when it starts.

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

Shared Wild overlap recovery starts only after the actor is stable: no accepted
motion, native command, spawn entry, capture, held actor, or queued battle owns it.
Its caller excludes the current Mounted follower slot as a recovery mover.
That body still blocks a Wild actor's exit. Rider input and shared hit knockback
keep movement ownership of the mounted pair.
Equal X/Y tiles overlap only at the same current physical height, using the
native occupancy reader's exact base-Y rule. A roof actor above the player is
not displaced. Recovery tries the existing cardinal mover with the active
profile's terrain and surface permissions; it cannot cancel a motion or grant
an otherwise illegal exit. Ambush allows Land and Player while it still
chases Player, so a legal clear adjacent exit can use this shared recovery.

Hop uses the typed `PLAN_HOP` operation on the existing Actor Motion request
service. Wild and Mounted adapters submit the resolved profile plus one bounded
read-only world-query context. The Motion owner interprets direction mode,
distance range, travel time, elevation scaling, arc, and obstacle clearance.
Directed behavior catch-up plans only the next executable Hop and retains the
authored target for the staged continuation. After that Hop reaches its
terminal state, the same role plans the next segment after the resolved
profile's Hop pause. Follower ownership does not replace Hop time or Hop pause.
Ordinary random Hop draws geometric candidates without replacement and stops
at the first legal landing. This keeps each legal endpoint equally likely and
avoids a full native landing scan in an open area. Authored distance and
direction limits remain unchanged, and START checks the chosen landing again.
History-based flat Walk keeps its straight and reverse fallback priorities.
The changed random draw count can change a seeded path.
The directed helper's next-Hop search has a 64-validation budget. Random Hop
visits each geometric endpoint at most once: up to 96 for the authored maximum
of 12 tiles, or 24 for a three-tile profile. An open area needs one validation.
Neither helper searches a complete multi-Hop route in one field update;
terrain and object queries run on the field frame and can stall the whole game.
The Hop elevation arc scale affects only extra clearance from elevation
changes. Zero retains the base level-Hop arc (16 Q4 units); it does not make
Hop flat. Wild, Follower, and Mounted planners share this rule. Flat Walk and
flat chain repositioning request their own zero arc separately.
Slam Arc is a shape of this same Hop plan. It has rise, hang and drop frame
counts plus peak height. Horizontal motion ends during rise. Hang and drop
keep that accepted destination fixed. Height follows a curved fast rise that
slows at the peak, holds, then drops linearly over the authored drop frames.
For fixed-point rise progress `q` from 0 to 4096, the shared unit height is
`2*q - ((q*q) >> 12)`. Both rendered motion and clearance use that same helper.
Clearance checks
every crossed cell using this executed shape; it cannot stretch the phases
or raise the peak to make a blocked arc pass. Ordinary Hop keeps its existing
parabola. The private SLAM flag reuses spin/sway bytes for rise/hang without
changing the public intent, plan or planner-call sizes.
The shared native jump-start body lives at Actor `0x023B8800..0x023B8E50`.
Wild's ordinary and Slam wrappers call that same body through a typed Thumb
import. The build copies its single linked implementation and checks exact
source, copy and package bytes. This changes its code home only; Wild still
owns its movement state, task lifetime and landing checks. It does not create
a second jump engine.
SDK overlay metadata uses exactly one named `rom` region from that overlay's
linker script. Private regions can appear before it and remain excluded from
the owning overlay payload. Wild's load base stays `0x023CCFD8`, with a
`0xB000` file and `0x24` BSS; the copied jump body's Actor address cannot set
Wild's load address. Missing, duplicate or malformed `rom` declarations fail
packaging, and the existing package checks retain the exact y9 row.
Flat repositioning uses `FLAT_TRAJECTORY` on the same 48-byte planning value;
its `trajectory` low half supplies and returns the authored duration. Clearance
uses linear tile-edge fractions, independently of Hop timing, and cannot add
an arc to clear a raised surface. The planned arc must equal the executed arc,
including when Hop time is zero or the flat action lasts one frame.
The private planner is
physically hosted at task-6 `0x023BD4F0` because the resident actor code block
uses a separate fixed code home; only Actor Motion can call it. The retired Wild
callback table remains absent. Its 24-byte reserve at
`0x023BD4D8..0x023BD4EF` hosts the private Slam phase helper. One fixed Actor operation
dispatcher accepts Vector, Trajectory, Flat Trajectory, Clearance Begin and
Clearance Step, with exact checked branches and no mutable state. Its two
absolute Thumb imports must match the current named task-6 planner bodies.
Task-6 first leases the current Query owner, then lends a stack-local native
operations value to its shared clearance routine. Every function pointer in
that value must contain the odd Thumb address of its exact executable owner;
an even code address is not a valid indirect callback. Query cannot retain the
operations value or its world pointers after the call. Shared
height interpolation uses measured spare space in the existing boot-resident
Walk page at `0x023BF810`; this adds no new movement owner or load lifetime.
The same page hosts the pure crossed-cell step at
`0x023BFFA2..0x023BFFEA`. Its borrowed value contains the signed boundary
error and current cell; it holds no world pointers or persistent state.
The shared clearance routine checks each crossed cell through the leased
native height and obstruction callbacks. Interpolation imports the existing
typed Thumb division bridges.
The complete current planner call graph must match its linked executable,
while the independent history/save/diagnostic/role/shadow call seal stays fixed.

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
Its resident Thumb target must match the linked
`OverworldWildSpawns_OnPlayerStep` entry on each ROM build.
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

Mounted player control and the frame task share one physical key-order cache.
Its high nibble stores the raw held D-pad mask; its low nibble stores the
newest cardinal direction plus one. A single newly held direction takes
priority until released, including opposite-direction pairs. A simultaneous
new chord keeps the resolved lane's direction mode. Control applies this
selection before Hop, Walk preview, and Walk input; the frame task uses the
same selection for the pending turn buffer. This cache changes input only.
It cannot clear a pending proposal, active skid, or motion transaction.

Cardinal mounted Walk stays bound to the stock player terrain streamer. It
does not wait for a second custom terrain receipt after the stock player step.
Staged diagonal or long motion still owns and drains its explicit stream
anchor before terminal completion. Binding or restoring that watcher must not overwrite the manager's
last sampled position: the stock loader advances that position only after it
has processed the ground, including when a natural chain Hop follows a Walk.
Before BEGIN replaces the watcher, Field may retire an empty stock axis left
by an interrupted step. The loader must be idle, the player must match the
last sampled X/Z, and the active axis pointers must identify exactly that
sample component and the current player component. Field clears only the
old axis flag and pointers. It preserves the last sample and all load data;
the new watcher still needs a real stock sample before `STREAM_READY`.
The stateless empty-axis check is physically hosted at `0x01FFD510` in the
existing HP161 code gap. Field remains its owner. Stream state and all public
entries keep their current addresses; the private call is a direct Thumb BL.

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

Turn Around changes facing without moving tiles. Its profile parameter,
**Pause between turns**, belongs to **Movement Style → Turn Around** and sets
the interval in game frames. Zero permits a facing choice every frame.
The direction comes from the behavior's resolved target: Wander uses a random
direction, Chase faces toward its target, and Flee faces away. The current
packed lane reuses `ramMaxSpeed` for this interval when Turn Around is selected;
this does not enable a Movement Chain.

A nonzero chain move count enables Movement Chain. A resolved lane can name one
pause action or a tagged set of actions. The chain boundary applies the overall
action chance once, then samples one enabled rank with exactly one stock random
draw. Counting and choosing the rank each visit at most seven enabled bits;
random rejection must not extend a game update. Shared variance sampling keeps
the existing byte phase and update count at each chain boundary.
`NONE` ends that chain with no pause or presentation effect. `PAUSE` waits for
the resolved passive pause time without starting an effect. A single `PAUSE`
uses the same overall action chance as any other single action or action set,
including while Mounted. A zero chance retains the legacy always-admit
meaning for existing profiles.
`HOP_IN_PLACE` then makes a separate extra-Hop choice. The visible
`chainHopInPlaceExtraHops` (0..2) and `chainHopInPlaceExtraChance` (0..100)
fields default to zero; either zero skips the extra roll. Playful sets a
two-move chain and one extra Hop at 50 percent, while its action admission
stays 60 percent.
The shared reducer selects a total of one through three Hops once, and stores
that count in the deferred action's tick byte. A legacy zero count means one.
Adapters retain this choice through retries and complete each Hop before the
next. Wild uses its stock in-place emote sequence; Mounted uses its existing
shared Hop executor. These presentation Hops do not count as chain movement.
`chainHopInPlaceHeartChance` and `chainHopInPlaceCryChance` are independent
replace-only choices: Off, 25%, 50%, or 100%. Both default to Off; Playful
sets both to 50%. Each accepted sequence chooses its effects once and keeps
that choice through adapter retries. Selected hearts and the actor's own
species cry start with each Hop in that sequence. They do not run on a failed
action admission or replace the existing profile-entry alert. The heart
choice uses bits 6..7 of the packed chain-count byte; the cry choice uses
bits 6..7 of the packed on-reach byte. Their other fields still compose
independently, and the profile remains 80 bytes per lane.
The pure Walk variance and chain-chance helpers use the unused ends of the
existing Reset and Crash code reserves at `0x01FFF028` and `0x01FFF35C`.
Actor still owns their state and random draws. This physical code host has no
Player Health state or lifetime dependency; public entries and bounds stay fixed.
The pure Heart/Cry choice uses the existing Mount-finish padding at
`0x01FFF550`. The old Finish section keeps its two-byte end pad. Both adapters borrow it through typed Thumb callbacks. Off
skips its draw; the other values draw once, Heart before Cry.
The accepted emote initializer and mounted effect output use synchronous
private operations of the existing Query `conditionNative` callback. Its
56-byte packet borrows the current adapter state and a 16-byte callback table;
it keeps no pointers after the call. The entry remains 192 bytes. Before
admission, a private 80-byte leaf at `0x023DEDF0` checks the current Field,
epoch and map lease. It cannot load, rebind or drain Query work. Motion and
sequence state stay with their current owners.
The Wild callback table and unchanged pause-frame clamp use the existing
Field gap at `0x0220833C..0x02208360`. The mounted effect bridge uses the gap
after orphan cleanup at `0x022083B8..0x02208400`. Both require the loaded
parent Field and are copied into its linked capsule before packaging.
The mounted callback table uses HP padding at `0x01FFF7EC`; unchanged private
player, policy and terrain checks use existing padding at `0x01FFFB58`,
`0x01FFA4E0` and `0x01FF9770`. Each copy keeps its original owner and guards;
the neighboring public entries and section bounds stay fixed.
Reposition move formulas retain their authored text. Since the resolved count
is always 1..8, packed relative operands clamp to -8..7 and divisors clamp to 8;
these give the same final count as the original operands, including compound
bounds. The resolver sign-extends the four-bit count operand only for Relative.
For ordinary Walk authoring, Movement Chain is either disabled or contains at
least two moves. A one-move Walk chain gives no readable grouping and is not
used. This restriction does not apply to Hop chains.
`HOP_FORWARD` is a two-tile Hop in the committed Walk direction. It uses the
current Walk travel time per tile, so the full Hop takes twice that time. It
has no settle pause, does not add a chain step, and preserves momentum for the
next chain.

A mounted Movement Chain never moves the pair forward by itself: the chain
boundary consumes `HOP_FORWARD` like an unsupported action. Hop in place and
the reposition actions are unchanged.

### Jump

Jump is the profile ability stored in the packed `hopAllowVerticalObstacles`
bit (Workshop label "Jump"). It replaces the former automatic obstacle Hop.
Walking into a blocked tile or an actor never Hops by itself; stock Walk
reports the ordinary Crash.

- **Mounted B Jump.** A B press with the Jump ability starts a forward Jump
  at the next idle tile boundary. A press during a Walk step waits for that
  boundary; a press in the air, during a crash shake, skid or other custom
  motion is ignored. The mount tick also reads the frame's B press (stock
  `gSystem.newKeys`) unless a field task owns input, so a press during a
  stock wall bump, when the chain control does not run, is kept. The nominal Walk time per tile (no variance) picks the
  reach: 1-2 frames jump six tiles, 3 five, 4 four, 5-6 three, and 7 or more
  two. Standing still (speed 0), a held direction, such as one bumping an
  object, Jumps two tiles that way at the mounted Walk time per tile. With
  no held direction, standing still makes a short, fast cosmetic Hop in
  place (16 frames, arc 12 Q4) with no movement. The Jump uses the
  existing forward-Hop path: chain-hop end state, the current Walk time per
  tile, the exact distance in the lane's Hop range and the forward landing
  check, so a clean landing keeps Walk momentum. If the full reach cannot
  start, the longest shorter Jump that clears lands and then crashes. With
  none, the pair crashes in place. Only a crash after a Jump that landed four
  or more tiles (`OVERWORLD_MOUNT_JUMP_CRASH_MIN_DISTANCE`) hurts: a shorter
  landing, or a crash in place, just ends the Walk momentum with no damage or
  knockback. A hurting crash applies the fixed 20 damage to the
  rider only, through the ordinary contact hit, which also plays the mounted
  crash and queues a one-tile Slide knockback opposite the player's facing
  (the shared mounted knockback; a blocked tile behind cancels it). The
  mount's party HP never changes. It ends Walk momentum. A cardinal Jump or
  ledge Hop moves the player position one tile at a time and uses the live
  player terrain streamer, like cardinal Walk, so it neither waits for an
  idle loader nor stages a terrain anchor. Only a diagonal Jump still needs
  an idle stream; a busy stream drops that press without a crash.
- **No mounted Hop walking style.** Directional input on a mount always
  Walks. A Hop locomotion profile becomes Walk when the mount begins, and
  the mounted lane-Hop landing search is gone; only the ledge Hop and B Jump
  start a mounted Hop.
- **Jump into water.** A mounted Jump may land in water. A mount without
  the Water terrain bit (not a water runner) then costs the rider 10 HP
  through the ordinary contact hit, and on the landing tick
  (`OverworldMount_JumpLanded`, right after `UpdateCustomMotion`) the pair
  returns instantly to its takeoff tile (`motionStart*` rebase and commit)
  with its Walk momentum reset. A water runner lands and keeps running.
- **Automatic ledge Hop.** Unchanged: a downhill (or Both) ledge in the held
  cardinal direction starts a two-tile Hop at the current Walk time. An actor
  on the ledge blocks it.
- **Wild and Follower Jump.** A Walk step into a blocked tile or non-player
  actor, along the current heading, starts a Jump whose reach follows the
  same nominal Walk-time tiers (stopped counts as two tiles). Only a lane with the Jump ability and an exact
  two-tile Hop range qualifies. The shared clearance accepts only an arc
  that clears every crossed obstacle, so a Wild or Follower Jump never
  crashes; a rejected Jump leaves the step to the Walk planner.

**Jump clearance.** The shared Hop clearance applies the Jump model to a
`TRAJECTORY` Hop whose lane has the Jump bit and one exact Hop distance
(min equals max). Canopy Hop and other ranged lanes keep the ordinary
open-cell rule. Each crossed native cell has a height above the start
ground: a ledge tile is open downhill and 20 units against its downhill side
(or diagonally) unless the lane jumps Both; a ledge is classified before its
stock collision. A blocked tile with no native ground (a cliff face; stock
height lookup `sub_02061248` finds no plate) is open to a Jump that lands
lower than it starts, so a Jump falls off a cliff edge; on level ground or
uphill it stays a wall. Any other blocked tile is 20 units, an occupying
object 12, otherwise 0. Water is an open gap. A Wild or Follower landing classifier still rejects a water landing; the mounted forward-target check admits water for every mount (ledge Hop and B Jump). The arc is sampled once at the cell centre and must exceed
the obstacle by 1 unit. The base arc stays 16 units; it rises only as needed
and only up to the distance cap: 18 for two tiles, 22 for three and 24 for
four or more. A wall therefore clears only near the middle of a four-tile or
longer Jump; an object clears at every reach. The constants are in
`include/overworld_hop_clearance_native.h`.

**Code homes.** The Jump model lives in the Query add-on clearance reducer
and reads tiles through three Native Hop clearance ops callbacks (ops version
2, 72 bytes): stock collision, stock tile behavior and Wild occupancy. The
add-on image grew 488 bytes (cap `0x10C38`, package cap `0x11200`). The B
latch, crash receipts and crash damage are a fixed boot-resident leaf at
`0x023BE140` in overlay 155. The Hop in place follows the mounted front
admission at `0x023B86DA` in overlay 158. Both receipts carry the mount
session, so a dismount or remount cannot replay them. The forward-Hop slot
in overlay 159 owns only the input boundary.

Wild Wander, Flee, and Chase can approach a safe blocked-tile or actor Hop along their
chosen cardinal direction. Mounted Walk uses the same approach rule. Neither
role weakens the clearance check for an actual skid tile.
For a directed Wild Hop toward its captured target, Behavior > Allowed terrains >
Object of interest tile controls whether that exact tile is a landing candidate. When it is
off, the Hop stops short. Ambush turns this option on in the Profile Deck; the
usual terrain, reservation, and landing checks still apply.

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
The pure Hop-vector check rejects impossible ordinary targets before any
landing world query. Valid targets retain the full landing checks. A pending
chain still records the landing decision, including for an invalid vector,
because that decision controls abort versus retry. Flat Walk keeps its strict
diagonal landing checks and does not use the Hop-vector check.
The private Wild classifier can reject an unbound placement before Query
admission when its nonzero destination mask contains only authored surfaces.
It requires the current ready Field, a playable matrix tile and the private
immutable behavior blob returned by the successfully decoded loader. The
existing Runtime surface lookup proves a miss or a disallowed authored type;
native ground cannot supply a different surface type. Matching surfaces,
including FlowerBeds with native-ground support, keep full admission and
landing checks. Missing package data returns `PROFILE`. Bound actors, chains,
source reads and mixed masks keep their normal path. Every visited candidate
still enters the classifier and counts against the same scan budget.
The shared native terrain seam receives the wanted destination mask. A source
read uses the full `0xFFFF` mask; diagonal guards remove Object of interest tile permission.
It skips the native Land collision query when Land is not requested. A search
for authored surfaces alone can reject a catalog miss before native ground
reads, but only with the current immutable behavior package: its exact
84-byte compiled header and catalog pointer must match. Admission rejects an
unaligned blob before a header read, then compares all 21 four-byte words
with alias-safe loads. Build admission validates the catalog rows; callers
must not change those rows afterward.
A catalog hit keeps the loaded behavior, support, occupancy and reservation
checks. Mixed masks and raw worlds keep the full path. Missing data stays
unavailable, and malformed package identity is invalid; neither can prove a
structural terrain rejection. Bare Landing admits the package and callbacks
once before its source lookup, then passes those validated callbacks through
the existing Native Landing call. Native Landing retains its policy, binding,
terrain, support and occupancy checks; the destination terrain read still
checks the immutable package header. The callback pointer lives only for this
synchronous call, with no added state or cache.
Rejected admission restores pending direction/distance; previous-tile history,
staged distance and reposition facing are committed only after admission.

Destination bit 4 is `Object of interest tile` (the old Player tile symbol is a
source compatibility alias). With a bound Subject, the tile belongs to its
current published condition target. Admission validates its full live actor
identity and uses that actor's current tile. Cached Chase coordinates do not
make a moved target unavailable. Only that exact target can be
ignored by occupancy; other actors, map objects and reservations still block.
Ordinary directed Hop can land on the target when this bit is enabled. Source
reads, diagonal side guards and pickup standing goals do not gain a collision
exception. Unbound spawn placement retains the Player tile meaning because it
has no captured Object of interest.

Slam uses the same classifier with a private bound-target occupancy policy.
The policy ignores the authenticated full Object of interest handle. When
that target is Player, it also ignores the current attached Mounted Pokémon
presentation on the same tile. Full mount identity and rider input ownership
are required; a follower, detached mount, or another occupant still blocks.
The classifier removes this policy and the Object of interest bit before
checking the actual terrain and physical surface permissions. Target occupancy
can thus permit a normally legal landing but cannot grant Land, water or any
surface permission. Route queries reject this private landing policy. World
and Landing call sizes remain76 and44 bytes. Normal clearance, reservations
and unrelated occupants retain their existing checks. Damage still comes from
the shared attacking and impact-speed contact check.

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
add the Hop settle pause. A successful crossing preserves the owning Walk
heading and accumulated acceleration. This includes an Until Crash charge;
only a genuine Crash ends that charge, never the accepted ledge Hop. The owning Wander step applies its normal Walk pause
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
Before the role change, Wild checks the current follower's conditions again.
The Mounted profile keeps that follower's winning condition and target, even
when another actor was evaluated last. Begin also requires the current field,
player avatar, and follower object.
The Select edge uses the field's raw new-key snapshot, before button remapping.
The Select request stops new held-direction player steps for at most 20 field
frames while the current stock player step ends. It can retry for 120 eligible
field frames without keeping the player still for that whole time. At mount
begin, a still-active
Follower motion receives a terminal cancel and releases its reservation before
its engine command is cleared. Mounted input then owns the next actor motion;
it must not inherit an unfinished Follower motion.
If a follower selection is still replacing the old actor, the same Select
press waits for the new follower. A failed bind can retry for at most 120
eligible field frames. A Select press during a map-header transition is kept
until the new follower is ready, even while the field task is active. Ending a
mount session clears a pending press; a press made inside an unrelated field
task or the follower selector is not carried into normal play.
Select while mounted ends that mount and returns the same actor to Follower.
The end-session write clears the actual phase and keeps the motion identity
clear, so a later Select can mount a different selected follower.

Mount overlay cleanup retires the player's current stock renderer before
restoring its saved normal sprite key. It uses stock `sub_0205E420`, then
`MapObject_SetGfxID`; it must not create a new heap4-backed sprite-change VWait
task while Field teardown can destroy that heap. A retained avatar rebuilds
its renderer from the saved key on Field return. Normal dismount and other
cancellations keep the normal `ChangeMapObjSprite` path. Both paths clear
mount control and rider offsets through the same detach owner.

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

Stock grass, dry-ground dust and step dirt effects use a bounded renderer pool. The
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
Skid, stomp and mounted landing dust all go through the Wild runtime entry
`playLandingHopParticle`. Its stub tail-calls the boot-resident filter
`OverworldSkidDust_Play` (overlay 159, `0x01FF9A30`, 24 bytes). The filter
re-reads the object's tile behaviors with stock `sub_02061108`, because
custom motion does not refresh them. It then calls stock `sub_0206064C`,
which draws the dry-ground dust only off water, shallow water, ice and mud.
So a water-runner that skids on water raises no dust; land skids keep it.
Dry-ground dust and step dirt share one allocation guard. Their native init
tails at `0x021FF7EC` and `0x0220017C` have the same model offset and saved
frame. A failed model request returns FALSE before either effect can run its
update, draw or model destructor. A valid model keeps the stock lifetime.
The stock circle shadow keeps its existing lazy model owner. Its ready word
must be zero when native model admission returns NULL, and exactly one after
it returns a model on the main-RAM heap. The inline `0x021FDD8A` patch converts
the native pointer to that ready word without changing the model store,
callback frame or overlay size. With no model, the stock draw and destroy
callbacks skip model work, while the stock update retries admission. A later
successful admission uses the normal draw and once-only destruction paths.
This rule does not claim that a full pool is a leak or increase its capacity.
The alert-bubble entry checks the same native model pool before allocating
raw buffers or queuing VRAM transfers. A missing
pool or signed used count at or above capacity returns zero through the
original stock frame. The successful path keeps its context, arguments and
stack and resumes at `0x02203A59`. It does not change profile timers or motion.
Grass and dust guards each have an at-most 32-byte section. Bubble admission
has an at-most48-byte section after them in resident overlay129, before the
fixed Walk pause resolver. Existing export addresses must not move. The image
must fit its actual `0x023D8000..0x023E0000` reservation; historical Summary
feature headroom is not a separate reserved memory owner.

Alert bubbles share one Field-owned 148-byte owner with three 40-byte slots.
Each current object can own one bubble. A second request for that object or a
fourth concurrent bubble returns zero before allocation or sound. Each slot
owns a borrowed native model and separate 512-byte texture and 32-byte palette
keys, so different icons cannot overwrite each other. The normal stock script,
draw and animation owners stay in place. The quiet resident entry stays at
`0x01FFF3B0` and stops the admission sound for accepted and rejected requests.

Retirement destroys the model immediately, but keeps its source buffers and
VRAM keys until the native transfer queue drains. The existing VWait task then
frees each retired slot once. Field shutdown retires the stock effects before
it closes the owner. Failed model, key, source or task allocation rolls back
without a partial live slot. No overlay BSS is added. Final package checks
authenticate all named owners, imports and protected stock bodies after armips.

The three-emote proof follows each admitted object, effect, model, source buffer
and private key through retirement. A later effect may reuse its slot and keys.
That later object cannot count as an owned free or prevent the original three
from completing. Each owned model must clear before its once-only source and
key frees, after all its queued transfers drain. Whole-field model and VRAM
totals remain diagnostic values because other actors can change them during
normal play.

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
The untouched Pool path validates its exact loaded site with the shared LAND
predicate for land encounters and WATER predicate for Surf and Fishing.
Catalogued surfaces keep priority over the underlying tile. This gate reuses
the validated tile byte and does not reroll a site or consume RNG.

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

Natural spawn position search (Land and Surf) walks the 21x21 tiles around the
player in a fixed pseudo-random order and checks 32 eligible tiles per update.
While the player faces up, down, left or right, a search only checks tiles at
least four tiles ahead of that facing (out to ten), so a run keeps meeting
Pokémon in front of the player, partly beyond the screen, instead of behind.
Every fourth starting cursor checks the whole distance-4..10 ring, so a front
with no valid tile cannot stall spawning. A search with no facing uses the
whole ring. A profile with an explicit Pool destination mask (small birds,
flower beds) lands three of four spawns on the prepared tile when it already
satisfies the mask; only the rest run the slow destination scan that otherwise
holds the single spawn queue for dozens of updates.

Explicit destination searches preserve row-major candidate order, eligibility,
occupancy checks, and reservoir-sampling RNG calls. Avoid player-front queries
when the mask cannot use them. Catalogued surfaces, including Canopy, must
still veto underlying terrain.
The host spawn-search fixture checks selection parity and these work bounds.

Move From Off Screen keeps the selected spawn tile as its immutable target.
It may start at any loaded, safely off-screen origin A with a proved route to
selected spawn tile B. The shared route witness holds at most96 directed
movement steps; this is a step cap, not a cardinal distance limit. Each step
keeps its full height and surface endpoint plus its native forward
direction and movement kind. Each of the nine admitted Wild slots keeps its
own full path. Entry rejects follower slot7 before storage access; slots8/9
map to records7/8 without changing their full Actor handles. The sole Field
workspace is43516 bytes; no Cargo or96-step path capacity is reduced. The
next displacement is derived from the exact expected and next endpoints,
checked in 32 bits before narrowing, and checked again by the native planner.
Saved paths do not duplicate endpoint displacement in a second edge array.
The proof uses the spawn attempt's one prepared profile and the same Walk, Hop or
Teleport planner that will run each segment. A is prepared at least five tiles
beyond the player-relative inclusive8-by6 camera extent, which reserves one
update of player movement before its required four-tile creation margin.
Origin and route legality use the resolved movement and physical surface rules;
the spawn destination still keeps its authored terrain rule. If no such route
can be proved within the work and witness bounds, the spawn is rejected. It
never falls back to an on-screen appearance. Otherwise,
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

Retired (2026-10-11): the Move From Off Screen spawn state is no longer an
authorable choice (state number 1 stays unused). Its Query entry search was
rebuilt after every accepted step, so each tile waited about 13 updates for its
root read, edge proof and ready receipt. The Scavenger profile (Rattata/Pikachu
families) was the only user and spawns with the default Appear Hop. The Entry
route and Wild overlay code that executed that trip is unreachable from catalog
data and is kept only because the sealed Query image shares it (TKT-0065).

Spawn preparation, the owned queue, and entry travel use the existing Field
Query loader and workspace. The fixed Wild adapter borrows a typed native
callback table for one synchronous call. Entry reducers do not retain callback,
Field, control-packet, or caller-prepared pointers. The native owners still
perform the real movement START, creation, terrain read, and arrival effects.
A pending spawn owns the full prepared value and its serial before the caller
returns. READY is a route result, not a created actor. Construction consumes the
queued value before native guard or creation work. Only the current created
full handle can ADOPT that serial and start the proved trip. Ordinary spawn
modes and follower metadata use the same finalizer; follower metadata cannot
enter a Move trip. The existing airborne origin algorithm remains separate
from the directed Move route proof.

GUIDE resolves current standing support through the bounded native root
Landing check. Motion's last destination surface is not standing support.
The checked root token can identify the saved path only when current X, Y,
full base height, scope and movement policy match. Each saved edge still
checks current source support, target support and occupancy before START.
The real Walk controller chooses the authored heading before strict Landing.
That bare physical Walk check may omit both profile and lane; partial pairs
remain invalid. Ledge and Teleport keep their profile and lane requirements.
Strict Landing passes the selected vector through the shared stock height,
range, direction, diagonal-side and collision checks.
Removal clears the source and retires the Entry serial before the next Actor
sync detaches its handle. Proof keeps that removal pending until a later
completed Actor frame shows the same full identity inactive and idle.

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
epoch and immediately schedules complete reconciliation. A changed native
Player center (`PLAYER_CENTERED | NATIVE_PLAYER` path advance) also requests
maintenance and reports `RECONCILE_DUE`. An active pass keeps its phase and
marks one dirty replay. Same-center, duplicate, stale and non-native reports,
and terminal Commit, cannot request another pass.

The resident population entry owns the refill countdown and the bounded
maintenance schedule. Its control interface accepts a refill delay or an
explicit reconciliation request and returns at most one despawn, refill, or
reveal work item per frame. The wild engine adapter executes that item and
reports the next delay; it does not keep a second timer or phase machine.
Only a new ordinary terrain batch waits for that countdown to disarm. Player
movement can request distance maintenance during the wait, but cannot start
another batch or reset its timer. Follower reconciliation and already-started
search or finalization continue. A successful construction sets the Base
interval times the current active Land/Surf count, with a minimum count of one,
except that fewer than four active Land/Surf Pokémon (the Follower never counts)
cap every refill wait at 8 eligible frames. A route being run through, where
movement keeps despawning actors, must therefore refill quickly. The density
scaling starts at four active Pokémon.
A failed series retries after15 eligible frames for its first three failures.
The fourth failure uses the same density rule (8 below four, otherwise the
density delay) and resets the failure count.
Full slots use the normal delay. Field suspension pauses the timer; rebind
carries it into the next map. The private `HAS_REFILL_WAIT` control reads that
same owner.

Distance despawn needs two scheduled samples beyond 16 tiles. Normal movement
does not discard those samples. A confirmed actor finishes its current motion,
cannot start another AI decision, including later in the same frame, and
requests population maintenance once its Motion policy is idle. That
maintenance rechecks the live distance and exact encounter identity before
removal. Returning to16 tiles or less cancels the
pending removal. Followers, shiny encounters, throw participants, and every
Move or Hop From Off Screen startup phase remain hard protected and collect no
far samples. Slot reset clears both far samples and the pending removal bit,
so a removed encounter cannot leave distance state for that slot.

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
fallback. A field transition (walking into the next map) resets every slot's Walk
policy, but `OverworldActorWalkPolicy_ResetKeepingFollowerMomentum` (ITCM
tail, `0x01FFFF80`; the ITCM arena now starts at `0x02000000`) restores the
Follower's momentum. Restarting it at base speed made a Sprint Follower fall
behind after every border and cut diagonally at the next turn.
A READY admission ends the series except that alternate step: a
queued spawn's destination is only placed at commit, so a failed commit still
runs the alternate terrain for its slot, and a successful commit clears it.
Before this, a shore with no Land destination (for example Cherrygrove's beach)
retried slot 0 on Land after every backoff and never placed a water spawn.
Full slots need no attempt. A logical Land/Surf attempt keeps the
legacy16-candidate limit and cursor order. All16 checks fit in one bounded
terrain-attempt update; the attempt count remains one, so the change does not
expand the old search to256 candidates. Help-child position searches use the
same16-check bound. A profile destination scan initializes without a terrain
query, then checks at most4 eligible destinations per update and completes
its240 eligible positions in60 resumed batches. The prepared encounter,
profile, metadata, class and RNG state are reused across those batches.
For a Grass-only destination, the shared terrain reader rejects a known
non-Grass metatile before surface lookup. Unknown tiles still defer; actual
Grass retains the catalog surface veto. Mixed masks and source-pose reads
keep their complete checks. This changes no scan limit or RNG order.
Reverse Move entry checks a two-tile Ledge candidate's midpoint before
predecessor height work. It uses the same prepared-movement direction rule,
current binding and one token from the existing eight-token physical budget.
Invalid coordinates cannot reach that early read. Unknown behavior defers;
a positive result still needs full Landing, edge and Hop admission. The
240-update limit, 96 route endpoints and memo storage stay unchanged.
The Helper-to-Wild terrain callback uses a fixed `u32` output, including its
selector buffers. Helper and Wild use different enum-size compiler settings;
an enum pointer cannot cross this boundary. The getter writes the Land/Surf
value only on success and leaves the output unchanged on failure.
After the full scan, startup runs once. A refused queued startup clears the
pending marker, so the commit owner discards that attempt in the same update.
It must not resolve that profile or retry startup on the next update. A later
spawn uses a fresh attempt identity and still obeys the full scan and work
bounds; a refused startup does not count as a successful spawn.
The resident initial chance gates run once. Private Query SPAWN subtype1 owns
the ordered ordinary terrain loop beside its existing NativeSpawn and queue
code. It checks the current owner before and after preparation and returns a
delay through the existing Population timer; subtype0 remains direct spawn.
READY admits the queued value and ends that terrain series; it does not count
a successful creation. The synchronous Query
COMMIT owner publishes a delay only after a terminal result, using the exact
ordinary queue serial, Field, Runtime, actor owner, epoch and map generation
before and after native callbacks. It consumes the receipt before returning.
Manual, stale, rebound, empty and pending queues return no refill delay.
Private FINISH_REFILL closes an unqueued series once, using the same guards.
These receipts use five existing reserved Runtime bytes. Population remains
the only countdown owner. Pending attempts finish before the resident REVEAL item; they
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

### Population frame cost

Wild population work shares the 2-vblank game loop (2,240,760 ARM9 scheduler
ticks) with stock field, map-streaming and rendering work. Measured on Route 30
beside the pond (7 actors, the player walking), the loop used 75–95% of that
budget before the changes below. The remaining time is the headroom that the
mandatory VBlank wait reports; spawn, scan, creation and per-actor work must
never spend it.

- **Contact validity is O(1).** `CombatContact_Current` runs for every actor pair
  each update. It must not call the stock first-active-ID lookup, which scans
  the whole object array and thrashes the data cache (117 calls per loop with
  8 actors). After the Field generation gate it proves ownership from the
  stored object: its engine-owned ID (`0xE0 + slot`) and the active flag.
- **A failed free-roaming search rests.** An idle actor that is not under an
  active Condition application and is not on a Move From Off Screen trip
  searches for a move at its decision frame. If the search starts nothing, its
  cooldown becomes `OW_WILD_SPAWNER_IDLE_RETRY_REST_FRAMES` (8 updates). Before
  this, a land species beside water, or a grass species with no grass nearby,
  repeated a ~60,000-tick direction search on every update and never moved.
  A Condition that changes the profile still clears the rest, so reactions keep
  their timing.
- **One idle search per update.** At most `OW_WILD_SPAWNER_IDLE_INTENTS_PER_UPDATE`
  (1) actor searches for a move in one update. Each search costs 40,000–60,000
  ticks; actors whose pauses end together used to search together and overrun
  the frame. The others keep a zero cooldown and decide on the next update.
- **A new actor's first movement tick waits one update.** Constructing the
  actor (sprite archive read, model setup) already spends 250,000–300,000 ticks
  of its update; the first movement tick of that slot is left out of the same
  update's masks.

Standing costs that remain are listed in the TKT-0076 notes: a per-loop party
scan by two stock field callers (about 10% of the loop's instructions), one full
Condition evaluation per actor per update (about 36,000 ticks each, 130,000 for
the saved Mankey Follower), and stock per-object update work. They are design
costs, not defects, and are the next place to look if headroom becomes short.
The buffered value reserves its slot but does not contribute to active density
until construction succeeds. Creation rechecks field/map/manager identity, slot generation and vacancy,
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
  158 at `0x023B65C0`. Package checks verify these ranges and the loader.
- Overlay 158 loads at `0x023B65C0..0x023BAB00`; its core entry is at
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
  `0x023BFC60..0x023BFE50` in resident overlay 153. It receives the typed call
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
- Selector owns `0x023C22A0–0x023C3000` for the fixed condition service,
  Query loader and current-Field delegates. Pure Condition, Vision and route
  query bodies live in the authenticated Field-resource-heap4 code image from a028
  member21. The existing Selector callbacks stay below `0x023C22A0`.
  Field teardown drains query storage and unloads that image before releasing
  Selector. The behavior-data overlay begins at `0x023C3000`, so the fixed
  images do not overlap.
- Stock Field overlay 1 owns the bounded capsule at
  `0x022074A8–0x022089CC`. This replaces its retired graphics-tag table;
  both native table readers already use Field131's `gOWTagToFileNum`.
  The appearance entry and code start at `0x022074A8` and stay below
  `0x022081E0`. The unchanged 28-byte Wild route-height wrapper uses the
  private 32-byte slot `0x022081E0–0x02208200`. Its sole RouteOps callback
  is borrowed synchronously after loaded, ready Field admission; query work
  drains before Field unload. The packer retains its fully linked Thumb body
  and checks its callback pointer and exact packaged bytes. The unchanged
  private condition actor lookup occupies `0x02208200–0x02208400`. The unchanged
  private Wild Walk output is at `0x02208400`. The private Wild policy
  initializer stays at `0x022085D0`; its existing 48-byte reserve also holds
  the stateless chain-condition wrapper at `0x022085F4`. The shared Walk tuning
  helper has `0x02208500–0x02208700`; appearance Exit/update glue has
  `0x02208700–0x02208900`. The shared world-effect delivery entry is
  `0x02208900`. The condition service gate
  requires stock Field 1 to be loaded. Wild, Follower and Mounted roles adopt
  effects only for current field actors, before their field parent exits.
  Delivery retains the slot, map, encounter, runtime and service checks and
  adds no Actor state or movement owner. Appearance callbacks must be removed
  before the stock field destroys its objects or releases overlay 1.
  Link and package checks seal each body, Thumb calls, zero-initialized capsule
  state, the native data starting at `0x022089CC`, both table repoints and the
  unchanged stock overlay file, BSS and loader bounds. Heap 3 and existing
  public entries remain fixed.
  The private appearance release helper uses the existing HP extension gap at
  `0x01FFD250–0x01FFD2CC`, below the fixed HitCrash entry at `0x01FFD380`.
  Field links and seals this synchronous Thumb body; final packaging copies
  its exact bytes into the HP payload. HP does not link back to Field. The
  helper has no retained callback and only runs while Field is loaded.
  The following private filler `0x01FFD2CC–0x01FFD380` now contains the pure
  packed-profile merge helper (106 bytes), then the one shared profile skid
  picker at `0x01FFD336` (74 bytes). Resolver owns composition; Actor owns skid
  decisions. Their physical host has no Player HP state dependency. Field
  packaging stops at `0x01FFD2CC`, so it preserves both helper bodies. Link
  and package checks seal their exact Thumb starts, extents and callers.
  The pure rest-tint policy uses the existing boot Actor gap at
  `0x023B8E50..0x023B9048`, before Motion at `0x023B9220`. Field links its single
  implementation; the build copies its exact bytes (500 now) into Actor. Field
  retains policy ownership, its current-bank checks and the synchronous
  applicable-mask callback at `0x022088EA`. Calls require loaded, ready Field;
  the copy adds no state or service and does not extend Field lifetime. The
  build dependency is one-way from Field to the Actor copy. Exact source,
  typed Thumb calls and packaged bytes are checked without changing either
  owner's fixed bounds.
- One shared appearance module updates Wild, Follower and Mounted Pokémon
  after the Actor, Mount and player-ball frame work. It borrows each current
  resident Actor snapshot, the current HP service and the already loaded
  catalog/condition workspace. It does not resolve profiles or prepare spawns.
  Missing HP blends a private palette toward red. The same Actor frame clock
  supplies a triangle from fully off to a soft injury-based peak, with no
  new clock or state. Peak strength is `1 + ceil(5 * missingHP / maxHP)`
  sixteenths, at most six. Periods are 128 Actor frames for peaks two/three,
  64 for four/five, and 32 for six. Greater injury makes the pulse faster.
  Strength rounds down. Half of each cycle has zero strength and the material
  command retains the stock palette address, so the tint is completely off.
  A `damageActive` Boolean
  uses an existing padding byte in the 12-byte ARM appearance input. It keeps
  one private palette owned through the off phase, with its original colors,
  and blocks blue while injured. Strength changes reuse that palette. Full HP
  clears injury ownership through the existing release path.
  Tint uploads use the stock VRAM transfer queue and its Field VBlank callback,
  instead of changing texture-palette banks during Actor refresh. A private
  padding byte marks a pending transfer. The source buffer and private palette
  key cannot change or be freed until the native queue is empty. Pending or
  rejected transfers grant no material permission. Clear removes that
  permission at once; cleanup and Field exit can wait for the queued source.
  At full HP, an enabled rest option can apply slight blue only when no
  conditional entry is active and every applicable entry is still blocked by
  its existing cooldown. Empty or wholly disabled sets do not qualify. Red
  takes priority; neither view adds a timer or changes movement.
  The appearance entry is version 2, size 28. Its draw callback uses cached
  palette and identity data only. Slot reset, poisoned-object deletion and
  validated orphan cleanup release the old appearance before object deletion.
  The stock Field template Exit pointer at `0x02206380` enters the guard at
  `0x02208700`: exit state zero cancels recall and drains appearance callbacks
  before the original stock Exit can release graphics. A pending foreign
  callback defers that Exit; later states forward to the unchanged stock body.
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
- The private Cargo observation callback and the Wild bubble leaf
  use Field131's existing gap at `0x023CCDC8..0x023CCE98`. The 192-byte
  observer reserve holds an184-byte body; the 16-byte bubble leaf starts at
  `0x023CCE88`. The Field input entry and its reserve stay fixed. Wild links
  its normal callback and bubble calls to these synchronous leaves; packing
  places the exact 208 linked bytes in Field131 and excludes them from Wild.
  Current Field readiness and teardown remain the code lifetime boundary.
  Bubble callers stop before Field131 unload. The shared callback ABI, Query
  table, search storage and movement owner stay unchanged. Package checks
  bind each exact Thumb entry and full body, the observer's current moving
  and valid-Frame gates, its typed native target-access callback, and the bubble leaf's register call through the
  resident quiet helper at `0x01FFF3B0`, in the unused gap after Actor
  acknowledgements and before mounted Walk save. That helper keeps the stock
  bubble visual, then synchronously stops its menu-confirm sequence1501 before
  the sound update. It adds no state. Package checks compare the helper and
  the whole 208-byte Field slice through the final ROM. Native Throw proof
  pairs each bubble's sound call with its stop in the same guest loop.
- Item parameter reads for `ITEM_NONE` return a fresh, zeroed 36-byte
  `ITEMDATA` allocation on the caller's heap. This matches the authored and
  packaged no-item record and retains the caller's normal free operation,
  while avoiding an archive read. Other item, icon and palette requests pass
  the same archive, member and heap arguments to the existing archive loader.
  The single private `Item_LoadData` helper belongs to core129 and occupies
  bounded filler after generic core text, before fixed Thumb helpers at
  `0x023DEE44`. `GetItemArcData` retains its 48-byte extent; existing core
  exports, fixed helper bodies and tail sections stay in place. No item cache,
  persistent state or friendship rule is added.
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
- Vision runs during ordinary autonomous motion and at intent boundaries. It rejects candidates by cone before
  short-line occlusion work and examines at most the ten-actor world view.
- Profile resolution is cached by source revision, subject, forced layers,
  active conditional applications, and the captured target source.
- Spawn metadata uses one validated, reusable blob. The build generator and
  runtime loader share `OVERWORLD_WILD_SPAWN_METADATA_MAX_BLOB_SIZE`; generated
  data above that bound must fail the build, not silently force file reads for
  every normal spawn. Allocation uses the actual blob size. Failed loading
  retains explicit fallback behavior and teardown frees only owned memory.
  Unmounted cadence tests reject an observed base-form metadata cache miss.
- The persistent behavior catalog (53.3 KB) belongs to the field session and
  uses FIELD1 (heap 4). The Query add-on (69.6 KB) uses `HEAPID_WORLD`
  (FIELD2). The smaller persistent spawn-metadata cache uses
  `HEAPID_DEFAULT`. Each blob loads only while its heap keeps its size plus
  the 32 KB `OVERWORLD_FIELD_QUERY_HEAP_RESERVE` free. A map that cannot spare
  that runs without Wild; Goldenrod is one. Temporary archive handles use the
  blob's heap and close immediately after loading. Teardown frees each blob
  through its recorded allocation.
- FIELD2 also holds every stock script context. An item ball needs about
  19.3 KB there: its environment, script and message banks, the 9-string
  MessageFormat, two 1024-character string buffers, and a second context for
  the std fanfare. FIELD1 is destroyed and rebuilt by every battle and menu.
  The rebuilt heap is fragmented, with no 69.6 KB block on Route 30 (67.7 KB
  largest). FIELD2 survives intact. `field_heap_budget.s` therefore moves
  48 KB from FIELD1 (0xC4000 to 0xB8000 in every field mode except the
  0xA0000 one) to FIELD2 (0x28000). HEAP_ID_3's field-time total is
  unchanged. Measured on Route 30: FIELD2 has 44.5 KB free and FIELD1 62.8 KB.
  Goldenrod's FIELD1 has 71.9 KB free. A wild battle leaves 150 KB of
  HEAP_ID_3 free. A new FIELD2 allocation must keep at least 20 KB free for
  scripts on a spawning route.
- Wild cleanup for a battle or menu frees the condition workspace, but a
  same-map return keeps live actors without a REBIND transition.
  `EvaluateConditionsForSlot` prepares a live actor whose record is missing
  again, using the handle in the anchored Actor state slot. Without this, every
  retained actor fails closed at each intent boundary and stays frozen.
- Resolved behavior is copied or referenced as one coherent value, not rebuilt field by field during motion.
- Trace writes occur only when a filter is armed.
- The trace ring is fixed-size and overwrites old records.
- Normal `Tick` work is bounded by active actors and active motions.
- Map reconciliation is bounded by actor count.
- The stock Land model loader reads at most 4 KB per main-queue task call.
  It keeps the stock sequential cursor, completion flag, cancellation and
  cleanup path. Only its two read-limit instructions change; the package
  check authenticates the rest of the complete native task. The unchanged-save
  D1 checks must prove current-ROM pacing after a loader change.
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

Notice Player and its application were removed in TKT-0040. Each remaining
conditional profile keeps its own Vision, notice conditions, and alert fields.
The general Notice-only Routine-return and blocked-Hop scenarios are retired
because their required profile no longer exists. The actual-C blocked Hop
no-turn check remains. Damage tint and each profile's own cooldown tint remain
independent requirements.
