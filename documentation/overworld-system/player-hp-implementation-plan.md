# Player HP implementation plan

## Resume here

Read [the current work table](roadmap-progress.md#current-work-table) for the
active checkout, latest ROM, remaining proof and next action. Then use the
matching contract or [implementation owner](#implementation-owners) below.
This plan owns stable design and acceptance rules. Dated run reports and old
next actions live in the [history archive](roadmap-progress-archive-2026-10-04.md).
Do not use that archive as a resume instruction.

## Pokémon combat extension

The user approved extending the same profile attack, fixed damage, speed gate,
and collision rules to wild, follower and mounted Pokémon. Each hit is capped
at half the target's max HP (at least one HP).
Each target has one second of hit protection. Wild Pokémon use normal
max HP and retain current HP into battle and capture. Party Pokémon use real
party HP, including saves and healing. There is no level scaling for damage
and no rest healing for Pokémon. Zero HP removes wild encounters and faints
party Pokémon, which cannot follow or mount.

The common planner supplies None, Slide and Jump knockback for all targets.
Rider and mount both take damage but move once through the mounted adapter.
Forced motion ignores Pokémon while keeping wall, script and other-object
blocking. The older mounted proof in the history archive checked suppressed
knockback; the new mounted contract requires one shared movement and height
restoration.

On-foot knockback clears the held command and avatar movement at its terminal
frame. It then uses the same registered stock sprite callback to publish the
idle pose in that frame, since the normal field sprite pass has already run.
Mounted cleanup remains owned by the shared mounted adapter.

The dated delivery receipts and old branch handoffs are retained in the
[history archive](roadmap-progress-archive-2026-10-04.md#player-hp-delivery-records).
They do not establish proof for the current candidate.

## Outcome and scope

The trainer can take damage from wild Pokémon outside battle, escape, recover,
or black out. A Pokémon can deal damage only when its resolved behavior has
`attacking` on and it collides with the player. A profile can require a minimum
impact speed. The first version exercises this rule through Ram movement,
Pokémon thrown by other Pokémon, and Ambush Hops. It must work on foot and while riding, and
preserve existing saves.

Use the current checkout named in the work table. Preserve unrelated edits
and recheck source anchors before each targeted edit.

### Settled user decisions

| Area | Required result |
| --- | --- |
| Scope | Wild Pokémon attacks outside battle only; Ram and Throw are the first movement cases. No terrain hazards or player damage in battle. |
| Warning | Attacks give a warning before they can hit. The player can move out of the way. |
| Damage | Fixed maximum HP. The active Ram profile supplies 33 damage; the active Throw profile supplies 20. No level scaling in this version. Damage has a 50% per-hit cap. |
| Attack authority | Only a resolved profile with `attacking` on can damage the player on collision. `minImpactSpeed` can block slow contact. Damage amount belongs to that profile. Ram and Throw names do not grant damage. |
| Throw meaning | One Pokémon throws another Pokémon. It does not mean throwing the player. |
| Throw contact | Contact during flight can hurt the player even when the player was not the target. The same flight can hurt again after protection expires. No damage after landing. |
| Protection | An accepted hit starts 1 second of protection against damage and attack-driven forced player movement. |
| Riding | The trainer takes damage by the same rules while riding. The mount does not absorb HP loss. |
| Recovery | Start healing after 5 seconds without a hit, while moving or standing still. Taking damage resets the wait. Healing from near-zero to full takes about 10 further seconds. |
| Pauses | Menus, dialogue, and Pokémon battles pause attacks and healing. |
| Display | Use a compact health bar on the overworld screen for this MVP. Show current HP by fill, including at full HP; show an attack warning on the bar before damage. An accepted hit plays one stock player-shove sound, flashes the bar's own red border and white fill once at the start, and shows a soft red tint at the screen edge that fades over 16 frames. |
| Battle entry | Attack contact does not itself start a battle. Ram crash must not queue one. Keep the separate normal battle-entry path. |
| Zero HP | Return to the last healing point. Restore player and party HP. Keep money and items. |
| Healing places | Pokémon Centers and home rest restore player HP as well as party HP. |
| Save | Save current player HP; loading must not grant full HP. |

The later damage choices replace the early rough five-hit target: with 100 HP
and 33 damage, Ram takes four hits; Throw takes five. Level scaling and the
average of thrower/thrown Pokémon levels are deferred, not hidden requirements.
Do not add unused level fields or profile controls for them now.

### First-version choices and checks

These fill gaps in the discussion. They are current design choices, not
additional user decisions. Named constants let playtesting change them without
changing ownership or save layout. A listed rule still needs its proof below.

- Use 100 maximum HP. The active Ram profile starts at 33 damage and the
  active Throw profile at 20. Clamp subtraction at zero; apply the 50-point cap
  before subtraction. The HP owner accepts an amount, not an attack category.
- Use one completed, eligible field-update clock. Establish its actual rate
  before selecting frame constants; do not use native emulator cycles, the
  slower actor-policy cadence, or host wall time as seconds.
- Heal at 10 HP per second with an integer remainder accumulator. No healing
  on the frame that merely completes the five-second wait. Drop the fractional
  remainder on damage. Movement keeps the wait and remainder. Clamp at full HP.
- Freeze protection as well as healing during pauses. No elapsed-time catch-up
  after a menu, battle, load, or emulator pause.
- Healing uses the same eligible field clock on foot and while mounted.
  Actual travel, forced travel, turning, and blocked input do not reset the
  damage-free wait or stop healing. The existing `restFrames` field retains
  its layout and now records the damage-free wait.
- Treat the last healing point as the last completed Center/home healing event.
  Standing still does not change it. For an old save with no HP record, start
  at full HP and use the validated stock return point, or home if it is invalid.
- Preserve HP on ordinary map changes and battle return. Reset the rest wait
  on map change/load. Preserve remaining protection through same-session map
  changes; do not persist timers to disk. Loading zero HP enters recovery.
- Use an always-visible bar with exact proportional fill. Use green, yellow and
  red at healthy, low and critical HP; use an amber border for live danger.
  Hide it in menus, dialogue, battles and fades; restore it from current HP on
  field return. Do not flash the whole screen; keep the hit tint at the edge.
- A danger signal means a live attack warning/charge or hazardous thrown flight
  near the player. Derive it from bounded existing attack state; do not scan
  the entire map or treat every visible wild Pokémon as a threat.
- An accepted damaging contact can move the on-foot player when its resolved
  profile sets `knockbackType` and `knockbackDistance`. The options are None,
  Slide, and Jump, with distance 1–7 tiles. Ram uses a three-tile Jump;
  Throw Held Actor uses a one-tile Slide. Other profiles default to None.
  One player-health motion controller runs both types through the shared
  motion model and holds a stationary player command, so neither plays the
  normal walking animation. It follows the incoming motion or moves away
  from the adjacent attacker. It stops at walls, scripted tiles and non-Pokémon
  objects, and keeps the damage. Pokémon do not block it. Protection rejects
  later forced movement; field changes or zero HP cancel pending movement.
  Mounted hits reduce rider and mount HP and move their shared anchor once,
  with the seat height restored on landing.
- Player ball throws and carried Pokémon cannot damage the trainer. An
  ordinary wild Hop is harmless unless its resolved profile has `attacking`
  on and its moving body collides with the player at the required speed.

## Entry path and sources of truth

Start with the current work table, then the matching contract and source row
in this plan. Read a project skill only for its task. A small task does not
require the whole plan, roadmap or delivery history.

| Artifact | Operational job and consumer | Update trigger / proof |
| --- | --- | --- |
| This plan | User contract, chosen design, source routes and acceptance requirements | Change when scope, design or ownership changes; keep resume state in the work table |
| [System README](README.md#read-order) | Entry route for implementers | Keep one link to this plan; do not copy its rules |
| [Architecture](architecture.md) and [CONTEXT](../../CONTEXT.md) | Current ownership and shared terms | Update with the implemented HP boundary; label unimplemented design as proposed |
| [Feature map](../../tools/overworld/system_features.yaml) | Machine-readable source-to-proof mapping | Register HP capabilities and scenarios as they are implemented; no invented passing entries |
| [Current work table](roadmap-progress.md#current-work-table) | One short active state and next action | Keep one HP row current; preserve existing open D1–D7 work |
| [Verification](verification.md) and [checked jobs](devtools-tests.md) | Accepted proof and failure handling | Follow existing rules; change them only if an actual missing contract requires it |
| Run-owned manifests under `build/overworld-devtools/` | Immutable test inputs, raw memory data and accepted results | Link actual returned manifests after execution; a plan or a successful start is not a pass |

Do not add a second progress document, alternate emulator driver, or parallel
test registry. Keep the player-HP contract here during implementation. On
completion, move stable implemented ownership into the architecture and replace
duplicated explanations here with links. Keep user choices and rollout history
separate from claims of current game behavior.

## Implementation owners

For current contracts, read [combat ownership](architecture.md#target-design-and-current-migration-boundary) and
[the source map](README.md#current-source-map). These links locate source; they
do not grant game acceptance. The work table owns the remaining proof.

| Task | Source owner |
| --- | --- |
| Trainer HP, protection and healing clock | [Production model](../../lib/overworld/player_health_model.c), [public API](../../include/player_health.h), [field service](../../src/player_health.c) |
| Pokémon HP, party/encounter identity and battle transfer | [Pokémon HP adapter](../../src/player_health_pokemon.c), [combat API](../../include/overworld_combat.h) |
| Ground and airborne contact | [Contact adapter](../../src/player_health_contact.c), [pure swept-contact geometry](../../lib/overworld/overworld_contact_geometry.c), [Wild adapter](../../src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c) |
| Accepted Player-damage condition | [Contact publisher adapter](../../src/player_health_contact.c), [shared event publication and condition leaf](../../lib/overworld/overworld_player_damage_condition.c), [profile catalog](../../data/overworld_behavior_profiles.json) |
| Accepted subject-damage condition | The same contact publisher marks only the exact current Pokémon after its accepted `TryHit`. Prepared condition storage retains one pending event until a real admission; deferred entry presentation cannot consume a later hit. `subject-damaged` uses ordinary profile, role, target and timer rules. |
| Shared knockback and immediate skid Crash | `OverworldCombat_Plan` in [field service](../../src/player_health.c), [hit/Crash adapter](../../src/player_health_overlay/overworld_actor_hit_crash.c) |
| Save layout and zero/legacy records | [Save adapter](../../src/player_health_save.c), [save layout](../../include/save.h) |
| Blackout and completed healing point | [Recovery adapter](../../src/player_health_recovery.c), [Center script](../../armips/scr_seq/scr_seq_00003_commonscript.s), [home script](../../armips/scr_seq/scr_seq_00845_home_rest.s) |
| Native bar, warning, sound and edge tint | [Presentation adapter](../../src/player_health_presentation.c) |
| Accepted observations and packaged layout | [HP observer](../../tools/overworld/devtools_player_health_observer.py), [descriptor generator](../../scripts/generate_player_health_debug.py), [feature map](../../tools/overworld/system_features.yaml) |

Use the current checkout's read-only `.codex-reference/README.local.md` for the
validated vanilla revision and named blackout, healing and party sources.
Source facts narrow a live check; they do not replace it. Never copy reference
output into the product. The older implementation inventory and proof gaps
are in the [history archive](roadmap-progress-archive-2026-10-04.md#player-hp-implementation-inventory-recorded-before-rom3510).

## Module and interfaces

`PlayerHealth` owns trainer HP separately from Pokémon HP and actor lifecycle.
Resident overlay 161 holds the field state across actor and map teardown. The
portable reducer owns HP, protection, rest, healing remainder and recovery
state; thin adapters supply engine facts and apply effects. The actual files
are [the public overlay API](../../include/player_health.h),
[the reducer](../../lib/overworld/player_health_model.c),
[field owner](../../src/player_health.c),
[save adapter](../../src/player_health_save.c),
[recovery adapter](../../src/player_health_recovery.c),
[contact adapter](../../src/player_health_contact.c),
[presentation](../../src/player_health_presentation.c), and
[production-C verifier](../../scripts/verify_player_health.py).

| Interface | Input → result | Owner / invariant |
| --- | --- | --- |
| `Load` / `WriteSave` | Validated save record ↔ HP and healing destination | Save adapter; one serialized record, no per-frame flash writes |
| `Step` | Unique completed field frame, eligibility, player motion → timers/healing | Model; at most once per frame, independent of population |
| `TryHit` | Profile-approved collision damage, field epoch, frame → accepted/reason | Model + validated contact adapter; check protection before any damage/displacement |
| `HealAtPoint` | Completed Center/home event and validated destination → full HP/checkpoint | Healing adapter; update only on successful completion |
| `BeginRecovery` / `FinishRecovery` | Zero HP → one transition request → safe restored field | Recovery adapter; exactly one active recovery, no money/item mutation |
| `Inspect` | Versioned read request → coherent HP/timers/recovery/effect values | Observation adapter; read-only, correct frame and field identity |

Engine pointers remain within adapters. The throw adapter tracks its slot,
generation and map generation; it drops authority on cancellation or field
change. Do not retain a raw `MapObject *` across a transition.
Within a frame, repeated callbacks for one contact cannot charge twice. A later
frame of the same airborne contact can charge again after protection ends;
there is no once-per-throw damage latch.

### State and frame order

Persistent state: version/magic, current HP, and the validated healing destination
if the literal last-healed interpretation is used. Runtime-only state: last
processed frame, protection remaining, rest elapsed, heal remainder, pause reason,
recovery phase/sequence, hit sequence and presentation state.

Normal states are ready, resting and healing. Pause freezes their counters.
Zero HP enters recovery-pending, then recovery-active, then ready at full HP.
An ordinary actor or map reset must not initialize HP. Only new-game/legacy-save
initialization, an accepted hit, recovery, or a healing event changes its value.

Per eligible completed field update:

1. Validate field readiness and the frame identity. If paused, do not advance
   attacks, contact damage, protection or healing. Reject stale hit receipts.
2. Advance existing protection once. Protection lasts the configured full
   interval: a hit at frame F permits the next hit no earlier than F + interval.
3. Sample player/attack motion through authoritative poses and phase. Process
   bounded contacts in a stable order. The first accepted hit starts protection;
   other contacts in that frame return `PROTECTED`.
4. An accepted hit clears rest and healing remainder. At zero, latch recovery
   before a menu, battle or warp can claim the next transition.
5. If alive and no hit was accepted, update rest/healing from actual motion.
6. Publish one coherent observation and apply the health bar, warning and
   accepted-hit flash/edge tint. Protection-rejected contacts make no hit sound or
   visual effect.

Pause blocks new attack starts and their active damage/motion updates. Preventing
only HP subtraction while projectiles keep moving would violate the pause rule.
On resume, continue from a validated pose; no burst of queued contacts or timer
catch-up. A pause or transition must restore normal input ownership on exit.

### Attack adapters

**Ground contact:** inspect the current resolved lane on a blocked step into
the player's tile. Only `attacking = true` permits a hit; compare the last
completed Walk tile's speed with `minImpactSpeed`, then submit `collisionDamage`
to the HP owner. A proposed faster step into the blocked tile does not count.
If the player instead presses into a current wild actor and stays blocked,
check the attack fields that Wild last supplied to the HP owner for that
actor's current generation. Do not enter Wild's profile resolver from the
stock player-collision callback. Wild must publish a new attack lane when a
condition changes the resolved profile. Idle adjacency is not contact;
a still actor has zero impact speed and passes only a zero speed gate.
The blocked-step callback uses the Wild owner's current field and checks the
calling avatar before reading contact state. Stock `LocalMapObject + 0x128` is
a `u16`, not a field pointer; an object-owned field comes from its map-object
manager at `+0xB4`.
Ram supplies direction-locked acceleration and crash feedback, but it is not
an HP condition. Its crash path never queues a battle, including when a hit is
rejected by speed or protection. Normal talk and encounter input remain separate.

**Moving-body contact:** retain a motion record from accepted launch until
landing/cancel. A wild Pokémon's own resolved profile authorizes contact for
its normal motion. A Throw snapshots the throwing Pokémon's resolved profile
onto the thrown Pokémon's moving body. Only a body with `attacking = true`
and enough horizontal speed can submit its `collisionDamage`.
Bind both actors and the motion identity at launch. Use swept relative motion
between previous and current player/projectile poses, with a vertical body
interval, so fast throws cannot skip hits and high arcs do not hit the ground
player merely because X/Z match. Use the rider's body while mounted.
Proposed first-test collision volume: half-tile horizontal body extents and
one tile of body height, translated to native world units; verify this against
actual model poses before sealing the test threshold. This is a tunable proposal.

Check only the airborne portion of the final movement interval before landing;
mark the flight harmless at the exact landing boundary. A player under a high
arc, a landing-only overlap, a carried actor, and a stale/recycled slot must not
cause a hit. A cancelled or transitioned flight loses its contact authority.
Reuse the shared motion sample; do not invent a second projectile timeline.
The current render adapter is `OverworldWildSpawns_ApplyCustomJumpRenderOffset`;
it applies `OverworldMotionSample` X/Z, base height and height offset. Use that
authoritative sample or its producer, not the destination tile alone.
The native player anchor is `fieldSystem->playerAvatar->mapObject`; validate
mounted rider offsets before fixing body bounds. Inspect
`OverworldWildSpawns_CommitCustomJumpLanding` and
`OVERWORLD_MOTION_PHASE_COMMIT_PENDING` for exact final-flight/landing order.
Suppress an automatic CONTACT battle from an attacking body's landing or the
same real blocked ground step, including a speed-gated or protected hit.
Clear the ground suppression after separation. Preserve later independent
contact and A-button encounters.

### Follower response to accepted Player damage

`player-damaged` is a visible condition, separate from the Follower's sight
condition. Only a hit accepted by the Player HP owner publishes the physical
source's full actor identity. Mere contact, a blocked speed gate, protection,
paused damage and rejected HP writes publish nothing. A thrown hit names the
Pokémon whose body hit Player, not the thrower. The event is Field-owned and
checked against current source and recipient identities. It survives accepted
Follower movement until the next intent boundary; consuming the pending event
requires the matching source to be captured as Object of Interest.

Both sight and damage contribute Find Throw Cargo before reachable Cargo
selection. The Follower's visible `object-of-interest-itself` selector makes
that exact Pokémon its Cargo. It cannot substitute a nearer actor. Cargo keeps
its own behavior and accepted motion until legal pickup. A held throw or
recovery is not interrupted by another trigger. Lost, fainted or unreachable
actors retain the authored failure and cleanup rules.

The authored Throw Away From Player Attack uses the same pickup, carry,
position search and flight as wild Throw. It selects a legal cardinal landing
at exactly `throwMaxRange` tiles from the carrier and farther from the current
Player. Windup saves that endpoint and support height; launch rechecks the same
endpoint against current Player position and terrain without silently choosing
a new aim. Wild Throw remains a separate Cargo thrown toward Player. After
recovery and cleanup, the Follower resumes its normal following. Neither
trigger adds another movement engine or changes HP ownership.

### Save, healing and recovery

First prove a byte-range ownership map for `SAVE_MISC_DATA`, its initializers,
checksums and all current consumers. Prefer a compact versioned record within
proved unused space without moving existing fields. If space is insufficient,
use an explicit compatible extension/migration; do not append bytes and assume
older saves still load. Keep this storage choice open until the audit is done.

Test new game, current old-format saves, valid hurt saves, valid zero HP,
missing/invalid HP marker, out-of-range HP and interrupted save. Proposed policy:
absent/invalid feature data initializes only the HP record to full and a safe
destination; zero with a valid record is real and must recover. Never reset
unrelated saved data. Preserve stock whole-save checksum/fallback handling.

Hook completed Center/home healing, not dialogue start or a generic heal used
by battles/debug setup. Store the location needed for a safe return. A cancelled
healing interaction does not change HP or checkpoint. Nurse/home script paths
must be tested through their normal game flow.

At zero HP, reject more attacks and latch one recovery request. Release mount,
throw and actor control through their existing transition owner. Do not wait
forever for a battle gate that recovery itself holds closed. Defer to a safe
task boundary with a bounded retry and a visible failure reason if unavailable.
Restore player/party HP on successful recovery, clear timers/effects, and return
input only after a safe field is ready. Retrying cannot heal or queue scripts twice.

Use a cause-specific recovery adapter around proved stock warp/heal sequencing.
Do not route through battle money-loss code, rewrite the stock battle return
point globally, or refund money after loss. The current source calls stock
`Task_Blackout` through a child wrapper because that task has no destination
argument and reads the saved spawn twice. The wrapper substitutes the HP
checkpoint only during each synchronous stock task call and restores the stock
value before returning, including failure paths. This is a narrow exception to
the original no-temporary-save-write proposal; it still needs current-ROM proof
that the battle return point is unchanged. Validate destination and return
scripts. Invalid destination falls back to home. A zero-HP save resumes this
same safe flow.

### Presentation and observation

Use a compact, bounded main-screen sprite health bar after proving resource
ownership; do not reserve a background layer or blend register by guesswork.
Record OAM/tile/palette limits, owner, load/unload calls and effect priority.
Share through the existing field UI owner where needed. Allocate on field setup,
never per frame. The bar stays visible at full HP in normal field play.

Hide/release at menu, dialogue, battle, fade and field teardown. Rebind on return
using a fresh field identity. Preserve map-name labels, weather, follower
selector and stock fades. A resource failure reports an observation reason;
HP must remain correct, but missing warning keeps presentation acceptance open.
The accepted-hit cue uses `SEQ_SE_DP_WALL_HIT2`, which stock HeartGold uses
when an NPC shoves the player. The bar flashes once for the first four field
frames by changing only its own tile pixels. Independent translucent OBJ strips use the
same palette and field OAM manager to tint the outer 32 pixels of the main
screen red. Ordered coverage softens the inner edge, and alpha fades over the
16 frames. The tint uses main-screen blending only while no stock blend is
active. It clears alpha for one draw update before it restores the prior
blend state, so old edge sprites cannot make a last flash. The center stays clear and the
cue remains visible when a route-name banner hides the bar. It does not change
player or mount visibility. Zero-HP recovery
starts blackout at once, so that transition replaces the flash on a lethal hit.

Expose HP, last hit/cause/reason, protection, rest, heal remainder, pause reason,
recovery phase/sequence, checkpoint, current danger and requested/applied warning.
For attacks expose warning/start/contact/landing identities and native poses.
For the bar and warning record actual resource binding, proportional fill,
submitted draw state, DMA-readable palette source, and matching main OBJ palette
VRAM, not just the model's requested state. Keep reads bounded and use the shared
native bridge and descriptor validation.

The existing [descriptor generator](../../scripts/generate_overworld_actor_system_debug.py)
and [actor inspection probe](../../tools/overworld/devtools_actor_inspect_probe.py)
have fixed-layout consumers. Extend them through an explicit versioned HP
section/command, with matching package checks and stale-version rejection.
Do not stuff HP into a Pokémon actor slot. A valid recorder snapshot alone is
not registered acceptance.

## Delivery slices

The [current work table](roadmap-progress.md#current-work-table) owns status and
next action. This table defines the ordered product results and their checks.
A source path or built ROM alone does not close a slice.

| Slice / dependency | Product result | Completion criterion and proof home |
| --- | --- | --- |
| P0 — seam checks | Map save range, field clock, stock recovery, healing hooks and OBJ resource owner. | Host layout and packaged checks in [verification](verification.md); keep named source anchors current. |
| P1 — P0 save/clock | Model, save and field tick own HP and timers. | Current save/reload and battle/map/mount pause proof under `build/overworld-devtools/`. |
| P2 — P1 + recovery | Blackout and completed healing restore HP and the return point. | Accepted money/bag, Center/home, zero-save and retry cases. |
| P3 — P2 | Warned Ram contact follows the resolved attack settings. | Accepted contact, protection, mounted hit, miss/follower and normal encounter controls. |
| P4 — P2 | Swept Throw contact follows the same damage authority. | Accepted direct/incidental/miss/high-arc/landing/cancel/mounted cases; warning precedes damage. |
| P5 — P1 + graphics | Native health bar and effects reflect HP and danger. | Proportional fill, warning, hardware effect and menu/map-label/fade/battle suppression and restore. |
| P6 — P1–P5 | Freeze product, scenario and observer inputs after review. | Build through V2, then required current registered and regression proof; identities agree with the feature map. |

Parallel work is safe only across owned files: save/model and rendering can be
investigated separately, while Ram/Throw and the shared frame path need one
integration owner. Freeze all inputs after review and before final proof.

## Acceptance map

The [feature map](../../tools/overworld/system_features.yaml) and scenario
registry own registered IDs and claims. The table below defines requirements;
it is not a current pass list. Use
[author-overworld-scenario](../../.agents/skills/author-overworld-scenario/SKILL.md)
to create exact claims, recipes and feature mappings, then
[verify-overworld](../../.agents/skills/verify-overworld/SKILL.md) for acceptance.
One test can cover several compatible claims, but keep setup outside measurement.

For TKT0018, `player-hp.moving-heal-on-foot` and
`player-hp.moving-heal-mounted` are registered. Each takes one real Ambush hit,
then uses ordinary travel with no further setup writes. Current HP-owner reads
must show HP80 at eligible clock+300 and+305, HP81 at+306, and HP90 at+360;
dense native poses must prove ordinary movement during the wait and healing.
Their acceptance status belongs in the current work table and TICKETS.md. The old
`player-hp.ram-rest` movement-reset claim is retired because it conflicts with
the requested moving-heal rule. Its Ram, jump, stationary wait and healing
checks remain; its final movement check now requires continued healing.

| Scenario requirement / level | Required positive proof | Required rejection or boundary |
| --- | --- | --- |
| `player-hp.save-recovery` S1/S3 | Hurt HP survives save/restart; legacy save gains only new data; zero resumes recovery | Missing/invalid marker, bad HP/destination; unrelated save bytes intact |
| `player-hp.rest-clock` S1/S3 | No heal before the 5-second damage-free wait; 10 HP/sec afterward; full clamp; starts and continues while moving on foot/on mount | Hit resets wait and remainder; movement preserves both; duplicate tick, wrong timebase, no idle wake, no fractional carry after a hit |
| `player-hp.pause-resume` S1/S3 | Menu/dialogue/battle freeze attacks and timers, return resumes once | In-flight movement while paused, hidden healing, resume catch-up, stale contacts |
| `player-hp.ram-contact` S3 | Real warned Ram hits trainer, fixed damage, protection, fourth hit recovers | Miss/blocked path, ordinary touch, follower, protected hit starting battle |
| `player-hp.throw-contact` S3/S4 | Native airborne contact damages; incidental hit allowed; same flight can hit after protection | High arc, crossing between samples, landing boundary, carry, stale slot/epoch; ordinary Hop is a separate positive case when its profile attacks |
| `player-hp.mount-parity` S3 | Same damage/protection/rest while mounted; safe mount release at blackout | Rider/mount double count; mount party HP charged instead of trainer |
| `player-hp.healing-point` S3 | Completed nurse/home heal restores HP and records return point | Cancelled event or unrelated party heal changes checkpoint; merely entering another town changes HP return |
| `player-hp.blackout` S3 | Exactly one safe return; player/party restored; money and bag unchanged | Simultaneous lethal contacts, pending battle/warp, invalid destination, retry duplicate, leaked control |
| `player-hp.health-bar` S3/S4 | Full and injured HP submit the correct proportional bar; danger changes its border | Model-only receipt, wrong draw binding, menu/map-label/fade conflict, stale field resources |
| `player-hp.lifecycle` S3/bounded S5 | Hurt state survives transitions; controls/effects recover across repeated cycle | Old flight hits new map, old observation accepted, state/resource leak |

S1 checks call production C, including same-frame multi-hit and exact expiry
boundaries. For a natural throw shorter than protection, prove its real lifetime
and use the model to test the later-contact rule; do not fake a long live flight
and claim it is normal play. For contact proof, retain source/target generations,
poses, flight phase, contact, HP before/after, and absence of battle entry.

Give new readers real missing/wrong-identity/wrong-value controls through the
same native read path. Deliberately missing a required hit or effect receipt must
fail acceptance. Memory snapshots of proposed state do not alone prove rendering,
collision or control release. Screenshots/video are not agent test evidence.

### Build and regression gates

1. Run the small production-C/model and save-layout checks for the current slice.
   Verify ABI/linker/overlay packaging with the normal current build checks.
2. Use `hg-engine-delta-build` from the installed skill catalog for the ROM
   build. Preserve the saved open-after-build preference and user ROM/save
   files. Resolve the skill path on the executing host.
3. Register scenarios first. Then use `scripts/owctl doctor`,
   `scripts/owctl scenario validate`, and
   `scripts/owctl scenario run <registered-id> --json` through the shared worker.
   Follow session ownership and accepted-manifest checks in the linked runbook.
4. Use `scripts/owctl verify affected` to select relevant existing regressions.
   Explicit risks are normal battle entry, follower crash/throw lifecycle,
   mounted control, map transition, field UI and save compatibility. Do not
   repeat unrelated suites by default or remove a failing requirement.
5. If changes touch profiles, generated profile data, spawn search/refill,
   destination masks or Hop planning/landing, follow the existing
   [spawn-work gate](verification.md#spawn-work-budget-and-proof-freshness).
   Run extracted-C budget checks first, then `population.spawn-work-budget` and
   `world.unmounted.spawn-zero-stutter` on the same current ROM and unchanged
   required Continue fixture. Zero late loops is the only stutter pass. Preserve
   any existing missing-fixture blocker; do not prepare away the fixture rule.
6. Integrate reviews before final tests. No presentation, observer or product
   changes after acceptance without rechecking affected proof identities.

## Resume and completion rules

On interruption, update one HP row in the current work table with slice, owner,
source/ROM identity, exact manifest links, failure class, and next action.
Distinguish game, setup, test-tool, host and unknown failures. Do not replace a
failed manifest with a later summary. Reuse sufficient unchanged evidence.

Cold-start trace: README → current work table → matching contract/source row
→ bounded check. Failure trace: scenario manifest → named missing
observation or product failure → smallest correction → same trigger on current
inputs → accepted manifest → current work row. After two tools-only turns,
return to the product cause under the existing outcome-first rule.

Done means all settled rules have implemented paths and required current proof,
save compatibility holds, the warning is readable in user play, and no required
acceptance remains open. Source-ready, a built ROM, or a model pass alone does
not mean the feature is complete.
