# Stackable overworld behavior transition and side-effect migration matrix

## Status and purpose

This is the phase-0, source-backed contract for replacing the flattened
`chill`/`attentive`/`tired` profile with one-state profiles and stackable
runtime overrides. It is an audit, not an implementation description. The
new transition orchestrator must preserve every side effect listed here or
deliberately record a behavior change.

The central rule is:

```text
immutable context-resolved base state profile
    + ordered, owner-addressable runtime override layers
    = effective behavior profile and effective state
```

Removing any layer must recompute the effective result from the base and all
remaining layers. A layer must never be undone by applying an inverse patch.
State/profile composition and transition side effects are related but separate:
the composer is pure; a transition orchestrator compares the old and new
effective result and performs lifecycle work.

Primary sources audited:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c`
- `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
- `src/overworld_wild_spawns.c`
- `src/script_new_cmds.c`
- `src/overworld_follower_release_overlay2/overworld_follower_release_overlay2.c`
- `src/overworld_follower_selector_icons_overlay2/overworld_follower_selector_icons_overlay2.c`
- `src/field/map_teleport.c`
- `src/overlay.c`
- `include/overworld_wild_spawns_internal.h`
- `include/overworld_wild_helper.h`
- `include/overworld_wild_behavior_data.h`
- `include/overlay.h`
- `src/overworld_wild_spawns_overlay/linker.ld`
- `src/overworld_follower_release_overlay2/linker.ld`
- `src/overworld_follower_selector_icons_overlay2/linker.ld`
- `data/OverworldWildBehaviorData.c`
- `Makefile`
- `documentation/overworld_wild_sing_alert_logic.md` for the retired Sing
  runtime path

## Current state and proposed ownership vocabulary

The live implementation stores one `movementSpotStates[slot]` byte:

| Value | Current meaning | Migration meaning |
| --- | --- | --- |
| `CHILL` (`0`) | Reads chill fields and can detect the player | The controller's base/calm state when no state-declaring runtime layer wins |
| `EMOTING` (`1`) | Temporarily suspends ordinary AI while an alert, hop-in-place, or look-around presentation runs | **Presentation phase, not a behavior-profile layer.** It gates movement while the effective stack remains independently inspectable |
| `ACTIVE` (`2`) | Reads attentive fields and runs chase/flee/RAM/special active behavior | A state-declaring layer, normally owned by `awareness`, `aggro`, or `help-call` |
| `TIRED` (`3`) | Reads tired fields and runs a rest timer, asleep/idle visual, or tired locomotion | A state-declaring layer, normally owned by `stamina`, `battle-fled`, `ram-crash`, `throw-recovery`, or `forced-sleep` |

Recommended runtime owner keys are semantic and slot-scoped. They are not
display names:

| Owner | Responsibility | Expected removal |
| --- | --- | --- |
| `controller.base` | Immutable context/controller-selected starting state | Replaced only when the spawn/controller identity changes |
| `awareness` | Normal player detection and active behavior | Controller recovery/de-escalation, reset, or despawn |
| `aggro` | Forced active behavior from follower-ball collision/release | Generated ordinary-tired calm-reset action when it may underlie tired; all-slot battle `CLEAR`; reset/despawn |
| `help-call` | Active behavior assigned to summoned children | Generated ordinary-tired calm-reset action when it may underlie tired; all-slot battle `CLEAR`; child reset/despawn |
| `stamina` | Exhaustion after completed active movement | Rest completion, reset, or despawn |
| `ram-crash` | Crash-to-tired transition | Rest completion, reset, or despawn; may share a tired profile with `stamina` but needs a distinct owner/handle |
| `battle-fled` | Fled-battle tired behavior | Rest completion, reset, or despawn |
| `throw-recovery` | Carrier exhaustion after completing a throw | Rest completion, reset, or despawn |
| `pickup.carrier:<slot>` | Picked-up target behavior/presentation | Drop/throw completion, reservation cancellation, map transition, reset, or despawn |
| `forced-sleep:<source>` | Forced asleep behavior, formerly Sing | Wake timer, source cancellation where applicable, reset, or despawn |
| `follower` | Follower-specific behavior layer | Follower recall/reselection/despawn |

Different owners may apply the same override-definition ID. A state-candidate
definition references one complete state profile; a modifier definition carries
a typed partial patch. Runtime APIs apply definitions, never raw state-profile
IDs. Removal must use an application handle or owner key, never only the
definition or referenced state-profile ID. Temporary
presentation ownership (emote step, native held command, staged hop, phantom
flicker, canopy proxy, RAM shake, throw reservation) must remain separately
tracked even when it is initiated by a behavior-layer transition.

Every override definition declares two lifetime policies:

| Policy field | Frozen values | Phase-0 meaning |
| --- | --- | --- |
| `mapHeaderPolicy` | `CLEAR`, `PRESERVE_LOGICAL`, `SYSTEM` | `CLEAR` is removed before a retained-primary map change; `PRESERVE_LOGICAL` may survive only if compatible after immutable context/controller re-resolution; `SYSTEM` discards the old entry and asks its registered owning system to re-evaluate/re-emit fresh state after reconciliation |
| `battlePolicy` | `CLEAR`, `PRESERVE_LOGICAL`, `SYSTEM` | `CLEAR` is removed by the all-slot battle reset; `PRESERVE_LOGICAL` remains stored but suspended from competition until explicit resume; `SYSTEM` discards the old entry and asks its registered owning system to re-evaluate after field return |

`SYSTEM` is an engine-owned lifetime policy, independent of precedence channel.
`SYSTEM_SAFETY` is the internal highest-precedence channel and does not imply
`SYSTEM` lifetime; follower possession demonstrates the inverse combination of
`POSSESSION` channel with `SYSTEM` map lifetime. Ordinary authored content may
use neither mechanism unless its separately validated contract permits it.

Phase-0 maps current owners explicitly:

| Migrated owner/definition family | `mapHeaderPolicy` | `battlePolicy` |
| --- | --- | --- |
| Awareness active | `PRESERVE_LOGICAL` | `CLEAR` |
| Aggro active | `PRESERVE_LOGICAL` | `CLEAR` |
| Help-call active | `PRESERVE_LOGICAL` | `CLEAR` |
| Stamina, RAM-crash, battle-fled, and throw-recovery tired | `PRESERVE_LOGICAL` | `CLEAR` |
| Forced sleep (dormant runtime source) | `PRESERVE_LOGICAL` | `CLEAR` |
| Pickup/carried possession | `CLEAR` | `CLEAR` |
| Follower assignment/possession | `SYSTEM` (re-evaluate from follower identity/controller) | `CLEAR` |
| Other authored/scripted runtime state or modifier | `CLEAR` unless explicitly declared and validated | `CLEAR` |

Phase-0 never infers persistence from channel, owner, role tag, or priority.

Timed behavior is stored per candidate layer instance or generation-safe
action token, not in one slot-global state timer. Each candidate timer stores
`(runtimeEpoch, slotGeneration, ownerId, instanceKey, entryGeneration)`,
`remainingTicks`, an explicit whitelisted clock such as `FRAME` or
`COMPLETED_MOVEMENT`, a hidden policy, and `timerGeneration`. Presentation,
reservation, cooldown, and RAM-shake timers instead belong to exact
`(slotGeneration, actionKind, actionInstanceKey, actionGeneration)` records;
they cannot select or remove a behavior state. Candidate hidden policies are:

- `PAUSE_WHILE_HIDDEN`: decrement only while this entry is the winning state
  candidate. Migrated stamina, RAM-crash, throw-recovery, and battle-fled tired
  candidates use this policy.
- `CONTINUE_WHILE_HIDDEN`: decrement whenever the entry is present. Migrated
  forced sleep uses this policy, including beneath `POSSESSION`.
- `EXPIRE_ON_HIDE`: queue the exact authored expiry delta the first time a
  recomposition hides the entry. No migrated phase-0 definition uses it unless
  its generated controller explicitly proves the legacy behavior.

An untimed definition has no timer instance. Ordinary decrement changes only
`remainingTicks`; it does not recompose or bump layer/effective generations.

An `EMOTING`-equivalent presentation token is a separate clock gate. While it
owns the slot, every gameplay candidate timer and every non-presentation action
timer for that slot is suspended, including migrated legacy tired/asleep timers
even when their candidate remains the effective logical node. Hidden-policy
evaluation resumes after the token releases; only the owning presentation's
action timer advances. A `POSSESSION` candidate is not by itself a presentation
gate: after pickup/throw entry presentation stabilizes, forced sleep with
`CONTINUE_WHILE_HIDDEN` continues beneath `CARRIED`.

The imported manual hop/look-around routes have the narrow D10/D11 source timer
exception: when started from tired, their legacy shared timer overwrites the
exact tired candidate's remaining time and completes at zero. Null/mismatched-
object terminalization for both routes is an intentional phase-0 safety
correction. Hop keeps the source-observable timer/end-state result but adds
generation authentication, no-dereference cleanup, and quarantine; look adds
those protections and fixes an internal early-return defect that can bypass its
later terminal block. All other presentation gates use the separate-timer
suspension rule above.

Expiry submits one atomic, handle-targeted transition action. `REMOVE_REQUIRED`
must validate the full handle or abort the complete batch with no mutation;
only explicit `REMOVE_IF_PRESENT`/`REMOVE_OWNER_IF_PRESENT` operations may
diagnostically no-op. Migrated ordinary tired uses `LEGACY_RETURN_CALM`:
required removal deletes its exact tired handle, and generated if-present
operations remove `awareness` plus `aggro`/`help-call` whenever either can be
active beneath that controller's tired node. `battle-fled` has its own required
exact `REMOVE_SELF` recovery plus tired-exit counter/cooldown actions, with no
calm-reset owner operations because battle entry already cleared those layers.
Forced sleep also uses required exact `REMOVE_SELF`.

## Deterministic legacy import and static fold

Legacy rows expand only into the ADR's closed static-action union:
`ASSIGN_CONTROLLER`, `BIND_NODE`/`UNBIND_NODE`, `APPLY_STATE_MODIFIER`,
`APPLY_CONTROLLER_MODIFIER`, `APPLY_CANDIDATE_TIMER_OPERATOR`,
`BIND_HOOK_SET`, spawn-policy bind/patch, and population-policy bind/patch.
Controller assignment chooses the greatest
`(assignmentPriority, ruleStableId, actionStableId)`; `controllerStableId` is
the winning action's payload and is not a tie-break. Every other
namespace folds ascending by `(staticPriority, ruleStableId, actionStableId)`;
complete bindings replace only within their namespace, while numeric
operations fold one by one. Equal complete keys are invalid. Serialized order,
display name, and target array index are not tie-breakers.

The special imports are exact:

- `OW_WILD_BEHAVIOR_CLASS_PICKED_UP` is a runtime pseudo-class and is excluded
  from ordinary controller-assignment/static-rule import. Resolve its class
  profile with the source exemption that skips the entire override sweep,
  normalize it, and generate the non-AI complete `CARRIED` profile plus
  controller-local nodes and `POSSESSION` wrappers. It creates no spawn or
  population assignment.
- Follower import performs the normal species/class and matching-override fold,
  but force-applies the semantically identified legacy `Follower Pokemon`
  record exactly once at its legacy ordinal even though `TARGET_DISABLED`.
  Zero or multiple records with that semantic identity are a migration error.
  It generates controller-local `FOLLOWER` state and follower spawn policy;
  runtime code never depends on override index `10`.
- Forced asleep runs one legacy override loop in ordinal/static order. A row
  applies exactly once when its normal context matches, except that the unique
  semantic `OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP` row is forced true when
  the loop reaches its source-discovered `forcedRowOrdinal`; the loop then continues through every
  later matching row and normalizes once at the end. Zero or multiple semantic
  forced rows are a migration error. Version-39 evidence is one-based ordinal
  `10`, zero-based source index `9`, but neither number is identity or a stable-
  ID input. The importer may not normal-fold first and
  append the forced row afterward. It generates exactly one controller-local
  `ASLEEP` node and one semantic candidate/timer wrapper per controller, but no
  live caller. Context variants use exactly one non-double-applying strategy per
  field namespace: complete post-loop `BIND_NODE` profiles, or one pre-loop
  binding with replicated ASLEEP-scoped actions preserving original matchers,
  ordinals, ordering, and priorities. Multiple nodes, mixed strategies, or loss
  of a later overlapping writer is invalid.
- A controller whose authored tired binding can be absent receives the
  reserved `CUSTOM/FALLBACK_TIRED` node/profile described in D04. Migration
  partitions immutable contexts by complete legacy matcher truth vector and
  emits one complete post-fold fallback profile/exact binding per cell.
  Semantic `TIRED` never resolves this node; only each imperative route's
  generated ordinary exact wrapper may choose it when authored tired is unbound.

Legacy `restTime` becomes candidate-timer-source operations, not a last-writer
binding. The completed candidate-timer fold is authoritative for a newly armed
timer; no later flat-profile value may replace it. It permits exact `SET` and
plain relative `ADD`; bounded and compound
forms are invalid. Each matching `ADD` clamps its intermediate result to
`0..64` before the next action. Exact bytes remain literal until the full fold.
After that ordered fold and before sentinel conversion, a bound non-`ASLEEP`
tired result of zero is repaired to finite `1`, including a late `SET(0)`.
Only then does asleep+zero map to indefinite `255` and do other values at least
255 map to finite `254`. Legacy `alertTime` is instead the controller-owned alert
presentation duration (`0` means automatic/default); its operators fold in the
controller namespace and the result is captured by the presentation action
token only when alert presentation starts.

## Direct `movementSpotStates` write inventory

The following inventory covers every direct assignment found in live source.
Reads and derived selections are covered in later sections.

### D01a — Movement and presentation reset

- **Source:** `OverworldWildSpawns_ResetSlotSpotState` in
  `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- **Trigger:** New-spawn initialization, ordinary movement reset, all-slot
  battle preparation, capture preparation, map/context reconciliation, or the
  movement portion of destructive slot reset.
- **Old → new:** Any state → `CHILL`.
- **Current side effects:** Clears throw state first; clears movement and spot
  cooldowns; emote timer/step/direction/jump count/end state/bubble flags and
  partner-prep pointer; active-step stamina counter; queued battle for the
  slot; previous/pending/last movement history; spawn-run state; staged-hop
  target; RAM direction/step/speed and movement chain; RAM shake data; phantom
  hidden/flicker/visible-pause/teleport state and object pointers; canopy proxy
  pointer; custom hop sound suppression state.
- **Resource ordering:** The raw spot-state reset only zeros RAM-shake and
  phantom fields/pointers; that is not authenticated restoration. Its caller
  must first restore an authenticated shake object's exact saved base
  coordinates, reveal/normalize the authenticated phantom primary, and
  delete/clear owned auxiliary phantom objects. If authentication fails, clear
  the generation-safe resource token without writing through the stale
  pointer. If the owning overlay is unavailable, resident code quarantines the
  slot and records a generation-scoped cleanup obligation; the first later
  callable overlay pass must authenticate and finish reveal/delete cleanup
  before AI, interaction, or reuse. Only then may the contract claim physical
  normalization; raw field zeroing alone is logical cleanup.
- **Stack migration:** This function's movement/presentation cleanup does not by
  itself invalidate encounter handles. The caller supplies an atomic layer
  delta according to D01b, D01c, or D01d. Presentation/task handles are always
  discarded; logical behavior layers are removed, suspended, or retained only
  by their explicit lifetime policy.

### D01b — Logical layer reset or suspension without identity destruction

- **Source:** The current behavior is implicit in calls from
  `OverworldWildSpawns_ResetAllMovementCommands`, battle preparation, and
  `OverworldWildSpawns_PrepareMapHeaderChange`; the new orchestrator makes it an
  explicit layer transaction.
- **Trigger:** Battle start, retained-primary map-header reconciliation, or
  another context operation that keeps the same encounter identity.
- **Old → new:** Current code resets the spot state to calm. In the new model,
  `CLEAR` layers are removed and allowed `PRESERVE_LOGICAL` layers are suspended
  or retained as defined below; base/controller identity remains valid.
- **Stack migration:** Do not increment `slotGeneration`. Handles for removed
  entries become stale through `entryGeneration`; suspended entries retain their
  handles and timers. Battle suspension excludes an entry from both state
  selection and modifier folding. Map preservation does not use hidden
  suspension: compatible `PRESERVE_LOGICAL` entries participate after
  re-resolution and incompatible ones are removed atomically.
- **Persistence:** Encounter identity and base assignment survive until a map
  re-resolution replaces the assignment. All object/task presentation handles
  are invalid.

### D01c — Destructive identity reset

- **Source:** `OverworldWildSpawns_ResetSlotState`, its capture/defeat/distance
  despawn callers, follower removal, and destructive context-clear paths in the
  spawns overlay.
- **Trigger:** Capture, defeat, distance despawn, follower recall, destructive
  map/context loss, or explicit slot destruction.
- **Old → new:** Live encounter → empty slot.
- **Current side effects:** Performs D01a, restores canopy render state, clears
  throw and auxiliary objects/cache, saved HP, logical spawn identity, follower
  party selection, capture/presentation masks, behavior class/limit key,
  profile cache, pending/queued battle identity, and spawn-run state.
- **Stack migration:** Clear all layers and effective caches, then increment
  `slotGeneration` exactly once for the successful `live -> empty`
  invalidation. Repeated cleanup of the already-empty slot is idempotent. This
  is the operation that invalidates every encounter layer handle. Object
  cleanup must still be pointer/authentication safe.
- **Persistence:** Nothing from the destroyed encounter survives.

### D01d — New encounter initialization

- **Source:** `OverworldWildSpawns_InitSpawnSlotState` in the spawns overlay.
- **Trigger:** A prepared encounter is assigned to an empty/reusable slot.
- **Old → new:** Empty slot → controller base/calm state.
- **Current side effects:** Increments `encounterGeneration`; stores spawn
  identity, behavior class/limit key, catch value and presentation coordinates;
  calls D01a; clears profile cache; initializes pass-through and canopy state.
- **Stack migration:** Require an empty layer array and a nonzero generation.
  Virgin runtime initialization sets `slotGeneration=1`; D01c has already
  advanced a reused slot. D01d never advances `slotGeneration`. Install the
  newly resolved controller base and static modifiers, and expose no stale
  handle from the prior encounter.
- **Persistence:** Only immutable data resolved for the new encounter exists.

### D02 — Retained-primary real map-header change

- **Source:** `OverworldWildSpawns_ResetSlotMovementCommandForMapHeaderChange`
  in the spawns overlay.
- **Trigger:** The authenticated retained-primary path for a real
  `previousMapId != currentMapId` change uses preserve/canonicalize in
  `OverworldWildSpawns_PrepareMapHeaderChange`, called by
  `OverworldFieldService_OnMapHeaderChangedImpl` in `src/field/map_teleport.c`.
  It is available only when the destination remains enabled and the manager,
  logical slots, and retained primary objects all authenticate. Failure takes
  the discard/context-loss path instead.
- **Old → new:** Saves the old state; maps `EMOTING` to its
  `movementEmoteEndStates[slot]`; performs the D01a reset; restores the saved
  `CHILL`, `ACTIVE`, or `TIRED` state.
- **Current side effects:** Preserves `movementActiveSteps`, spot cooldown,
  movement cooldown, and the tired timer only when the state was already
  `TIRED` at the first capture. Capture order matters: an `EMOTING` state is
  converted to its end state only **after** `tiredTimer` is sampled, so
  `EMOTING` with end state `TIRED` canonicalizes to tired with timer `0`. It
  cancels/finishes object commands, staged/custom hops, RAM and
  chain state, throw relations, phantom effects, and canopy proxy state through
  the reset path. A `PICKED_UP` behavior class is resolved back to the spawn's
  normal class. Canonicalization clears held/single movement, restores the
  paired alert/canopy presentation, restores tree-top render state, updates
  last-known coordinates, clears far samples, and requests native-shadow
  reconciliation.
- **Stack migration:** Discard all object/task-owned presentation handles.
  The frozen `void prepareMapHeaderChange(state,mode)` callback is a
  generation-keyed two-phase state machine. The resident caller owns a separate
  fixed claim carrier `(status,retentionPlanEpoch,retentionPlanGeneration,mode,
  claimSequence,runtimeEpoch,state/source identity,installed-destination
  identity,resultMarker)`. Before each `PRESERVE` or `CANONICALIZE` invocation,
  it publishes a fresh nonzero sequence and exact expected tuple/mode last. The
  callback can act only by atomically claiming that complete
  `PUBLISHED→CLAIMED` identity, records `COMPLETED` before return, and accepts
  one exact caller ACK. Its C return type is `void`, so it communicates no
  result status; any surrounding `BOOL` denotes only callback/overlay
  availability. The caller must re-read and authenticate the exact resident
  `COMPLETED` claim/result marker after return before any middle write. An ACKed
  `PRESERVE` claim returns to `EMPTY` only for a
  fresh `CANONICALIZE` claim on the same plan; the plan retains its last mode/
  sequence tombstone. Duplicate, stale, wrong-mode, or wrong-plan claims are
  no-ops. `PRESERVE` captures source map/manager/object and slot generations,
  precomputes/reserves the complete retained plan, and publishes both
  `PREPARED` and the matching claim result for the coordinator's nonzero
  `(retentionPlanEpoch,retentionPlanGeneration)`. The coordinator initializes
  both counters to `1`; the virgin plan uses generation `1`, every later plan
  advances once after its predecessor is consumed, and neither plan nor claim
  can overwrite an unconsumed predecessor.
  Its reservation ledger has four closed one-per-slot kinds (object command,
  movement stabilization, presentation restore, stack rebind) and seven global
  cells (map manager 1, overlay pins 149–152 = 4, behavior snapshot 1, cleanup
  publication 1). Static assertions freeze max spawns `10`, slot cells `4`,
  global cells `7`, and evaluated capacity `47`. Before the first acquire,
  `PRESERVE` enumerates and exactly deduplicates every typed reservation key into
  47-cell scratch.
  Overflow publishes `FALLBACK/RETENTION_LEDGER_CAPACITY_EXCEEDED` with zero
  acquired leases; there is no spill, truncation, eviction, or replacement.
  Ordinary infallible middle writes remain legal only after the caller observes
  that exact completed fallback claim. Each ledger cell is claimed before its acquire.
  Any later planning/reservation/authentication/storage failure transfers all
  held cells into `FALLBACK` for that tuple before returning.
  Resident map-generation, map-ID, manager, and object writes occur only after
  the caller observes its exact completed first-half claim with either legal
  marker; they are unconditional, non-allocating, and infallible and neither
  mutate layers nor consume the marker. `CANONICALIZE` first atomically claims
  its fresh carrier for the same plan, then authenticates the exact tuple,
  captured source identities, and installed destination identities. `PREPARED`
  executes its reserved infallible plan; `FALLBACK` executes D01c. A failed
  claim CAS from missing/stale/wrong/replayed mode, sequence, or tuple is a
  complete diagnostic no-op: no quarantine/D01c, ledger release, or current-
  plan mutation. Once the exact current invocation has successfully claimed,
  returning while still `CLAIMED`, malformed/wrong completion, or failure to
  publish exact `COMPLETED` quarantines and executes D01c/release only for that
  claimed plan. An unrelated stale completion tombstone is a no-op. Only after
  exact claim may captured/installed authentication mismatch likewise
  quarantine and execute D01c for that plan. Every terminal path
  uses one tuple-authenticated release operation: atomically claim each `HELD`
  ledger cell, release it once, set `reservationsReleased`, mark `CONSUMED`, and
  complete the exact callback claim. Missing-callback maintenance creates a
  system claim for that exact tuple; it cannot consume whichever plan is merely
  current. Replay releases nothing. Claim-sequence or plan-generation wrap
  drains the exact claim/plan, advances retention epoch, then restarts at `1`.
  After this protocol validation, discard all object/task-owned presentation handles.
  Apply each definition's `mapHeaderPolicy`: remove `CLEAR` (including pickup/
  throw possession), retain only `PRESERVE_LOGICAL` entries compatible with the
  newly resolved controller/context, and use `SYSTEM` to re-evaluate follower
  assignment/possession from canonical follower identity rather than copying a
  runtime entry. Re-resolve immutable map/static context, controller, base
  state, node bindings, and static modifiers after the new map ID is installed.
  Do **not** replace this retained encounter's captured spawn-policy ID,
  population-policy ID/group, or limit. The destination resolver may record
  `wouldSelectSpawnPolicyId` and `wouldSelectPopulationPolicyId/group` for
  diagnostics only; those values cannot relocate/recount the encounter or
  enter its effective hash. A preserved controller-semantic candidate such as awareness or
  tired rebinds to the destination controller's unique corresponding role node;
  it retains its owner/key and remaining timer. Zero bound semantic matches
  remove the preserved entry with `CONTEXT_NO_LONGER_APPLICABLE`; more than one
  match is `AMBIGUOUS_SELECTOR` and aborts before the point of no return. An
  ordinary exact selector is always `(controllerStableId,nodeStableId)` and
  becomes inapplicable when either component differs. The three imperative
  tired origins use only the ordinary semantic/exact wrappers plus D04's
  internal destination translation table; there is no third serialized selector
  kind. Then recompose retained layers. An alert
  presentation commits its intended end transition before reconciliation,
  matching current `EMOTING → endState` canonicalization.
- **Persistence:** State intent, active-step count, cooldowns, and tired timer
  survive the current valid preserve path, except the `EMOTING → TIRED` timer
  quirk above. Pending/queued battle identity and throw state do not. Phase-0
  reproduces that zero-timer quirk through one atomic handle-safe action:
  preflight authenticates the presentation token plus the exact candidate
  handle and `timerGeneration`, commits the pending end delta, sets only that
  timer to zero, and records its mandatory expiry. It never writes a slot-global
  “current tired” timer. The first resumed eligible tired tick recovers to calm.
  Invalid/disabled destinations, failed primary authentication, discard,
  and destructive context loss run D01c and preserve no layers.

Same-map object-manager/objects-array replacement is a separate parity path.
It keeps encounter identity and `slotGeneration` but performs the current
all-slot logical movement reset: clear every ordinary runtime layer and timer,
discard every object/task/presentation handle, return retained slots to
base/calm, authenticate/rebind the new manager, then re-emit only authenticated
`SYSTEM` state such as follower assignment. It does not use D02's
`PRESERVE_LOGICAL` behavior merely because the map ID is unchanged. Both this
reset and D02's zero-timer capture-order behavior are explicit phase-0 parity
exceptions.

### D03 — Tired/rest completion

- **Source:** `OverworldWildSpawns_StartTiredCooldown` in the spawns overlay.
- **Trigger:** `OverworldWildSpawns_TickTiredEmote` reaches zero, has no object,
  or enters with no usable rest duration/visual.
- **Old → new:** `TIRED` → `CHILL`.
- **Current side effects:** Clears RAM/crash movement state, emote timer/step/
  direction/jump count, active-step counter, and spot cooldown; sets movement
  cooldown to `OW_WILD_SPAWNER_TIRED_WANDER_PAUSE_FRAMES` (`24`); optional
  cooldown sound is compiled out by default. `ClearRamCrashMovementState`
  clears direction, step counter, chain, and speed; it does **not** clear the
  active crash-shake timer or its saved base coordinates. The shake continues
  to its own completion/restoration path.
- **Stack migration:** On migrated ordinary-tired expiry, atomically remove the
  exact tired handle with `REMOVE_REQUIRED` and use explicit
  `REMOVE_OWNER_IF_PRESENT` actions for the controller's generated calm-reset
  owner set, then run tired exit cleanup. The set always includes awareness and
  includes aggro/help-call whenever those can underlie the tired node. This freezes legacy
  recovery to calm. `battle-fled` instead owns an authored `REMOVE_SELF` action
  with the same tired exit counters/cooldown and no calm-reset owner removals.
  Weather, forced sleep, and dormant aggro metadata are not in the ordinary
  calm-reset set.
- **Persistence:** No tired owner survives completion. Unrelated layers remain.

### D04 — Enter tired/asleep behavior

- **Source:** `OverworldWildSpawns_StartTiredEmoteWithProfile` and wrapper
  `OverworldWildSpawns_StartTiredEmote` in the spawns overlay.
- **Trigger:** Stamina exhaustion, attentive RAM crash, successful pickup throw,
  fled battle, or a caller-supplied forced profile.
- **Old → new:** Normally `ACTIVE` → `TIRED`; the helper is permissive and may
  be called from other states.
- **Current side effects:** Resolves/copies the profile and primitives; reveals
  an active/chill phantom before resting; supplies a fallback tired-emote
  profile when tired is absent; clears active single movement for asleep;
  derives `restFrames`; writes tired state; clears RAM direction, **RAM step
  counter**, speed, and chain;
  initializes tired timer; resets emote metadata and active-step counter; sets
  the initial tired pause. Moving tired behavior clears an active single
  movement, sets decision cooldown, and schedules frame AI. Idle/no-visual
  tired behavior only schedules timer handling. Visual tired/asleep behavior
  starts the configured emote/bubble path when enabled. Invalid/zero-duration
  cases immediately pass through D03.
- **Stack migration:** Apply the caller-specific state-candidate definition ID
  with a distinct owner and initialize that entry's own timer. Composition is
  atomic. Entry actions use the newly composed effective locomotion/visual, not
  a stale profile captured before the apply. Preserve unrelated layers. When
  the authored `TIRED` node is absent, imperative `FLED`, active-RAM wall-crash,
  and successful throw-recovery routes use no new selector type. Each route owns
  two generated ordinary wrappers: semantic `TIRED`, plus a controller-local
  exact `(controllerStableId,fallbackNodeStableId)` wrapper. Preflight selects
  semantic on one bound authored match, exact fallback on zero, and rejects
  ambiguity. Migration partitions the finite immutable v39 context domain by
  complete legacy matcher truth vector and lowers every class into finite,
  disjoint atomic cells expressible by the existing conjunctive matcher schema;
  non-expressible/overlapping/incomplete lowering rejects migration. Each cell gets one
  complete post-fold fallback profile produced by the ordered tired projection,
  including tired-only and shared-movement actions, followed by profile repair
  `TIRED_EMOTE`. An existing exact post-legacy
  `BIND_NODE(controller,fallbackNode,profileVariant)` selects it; the generated
  exact fallback wrapper carries timer enablement and finite rest source `4`
  (`stamina=1` is not a controller scalar). No semantic
  modifier is retargeted to `CUSTOM`. Ordinary exhaustion uses only semantic `TIRED`, is disabled without
  authored tired, and never falls back. On retained controller rebinding, the
  stored origin/owner authorization is preserved. Definition/runtime schemas
  use canonical tagged origin and required-owner pairs. Generated mappings are
  exactly `FLED→battle-fled`, `RAM_CRASH→ram-crash`, and
  `THROW_RECOVERY→throw-recovery`; the generated stamina wrapper has absent
  origin plus required owner `stamina`. Ordinary authored/shared definitions
  have absent authorization and remain owner-unconstrained. All four generated
  tired families freeze both multiplicity flags `FALSE` and require
  `instanceKey=0`; ordinary definitions retain their authored multiplicity.
  Before any
  idempotency/collision/multiplicity shortcut, `Apply`/`Replace` validates the
  definition/runtime pairs, requires the operation owner to match a present
  required owner, and copies both pairs; callers cannot supply or override
  them. Public Replace rejects generated↔ordinary and different origin/owner
  families, while authorized same-definition Replace recopies metadata and
  restarts entry/timer generations. Stamina
  bypasses the translation table, re-resolving destination semantic `TIRED`
  directly. The three imperative origins use an internal generated translation
  table keyed by `(tiredOriginKind,destinationController,authoredTiredBound)` to
  remap only to the same-origin/same-required-owner destination semantic/exact wrapper without
  changing owner, handle/timer generation, remaining time, recovery policy, or
  generated metadata. This is retained-context revalidation, not a serialized selector
  or public replace. Generated exact wrappers use existing schema, are
  read-only in the editor; duplication copies origin and fixed required system
  owner unchanged and clone/remaps controller-local wrappers/translation targets
  under the ordinary exact-reference rule. Missing/noncanonical metadata,
  unauthorized runtime owner, route/wrapper/entry/recovery mismatch, stamina
  origin/table rows, ordinary definitions with generated authorization, and
  incomplete/duplicate translation keys are invalid data.
- **Persistence:** Survives a valid map-header preserve with its remaining timer;
  cleared by battle-wide movement reset, capture, destructive context loss,
  despawn, or slot reuse.

RAM locomotion ownership and crash-shake ownership are independent. The tired
entry/exit actions clear direction, step counter, speed, and chain, but do not
cancel or restore an active crash shake. The shake token owns its authenticated
object identity, timer, and saved base X/Z until normal completion. An early
cleanup restores the exact base coordinates before another action takes
positional ownership, before object delete/recreate/rebind, before battle/map/
destructive cleanup, or before starting a replacement shake; if the object no
longer authenticates, it clears the token without writing the pointer.

### D05 — Phantom alert enters active directly

- **Source:** `OverworldWildSpawns_EnterPhantomTeleportActiveState` in the
  spawns overlay.
- **Trigger:** Alert presentation completes or a no-visual alert immediately
  enters active and attentive locomotion resolves to `PHANTOM_TELEPORT`.
- **Old → new:** `EMOTING` or `CHILL` → `ACTIVE`.
- **Current side effects:** Clears RAM step/chain and alert timer/step/end-state/
  bubble flags; resets active steps; calls the legacy-named
  `OverworldWildSpawns_RecreatePhantomObjectForActiveState`, which does not
  create a new primary object. It authenticates and normalizes the existing
  primary object: cancels the alert presentation, finishes its command, reveals
  it, clears movement ownership, deletes/clears auxiliary flicker objects,
  commits the current tile as landing, and reapplies pass-through. It then
  starts real-flicker behavior when compiled and the visible cooldown.
- **Stack migration:** Apply/activate the `awareness` layer before active entry;
  the active-entry hook owns primary-object normalization, visibility,
  pass-through, auxiliary flicker cleanup, and cooldown reconciliation. It
  cannot be reduced to a profile pointer swap.
- **Persistence:** Awareness is retained across an authenticated retained-primary
  map-header change when compatible with the destination controller; all
  phantom presentation objects/timers are canonicalized and rebuilt safely.

### D06 — Generic alert presentation completes

- **Source:** `OverworldWildSpawns_TickSpotEmote` in the spawns overlay.
- **Trigger:** Alert/manual presentation timer reaches zero or its object is
  unavailable. In current source, look steps can return before this terminal
  handling; D11 deliberately corrects that additional internal defect.
- **Old → new:** `EMOTING` → stored `movementEmoteEndStates[slot]`, usually
  `ACTIVE`, but manual chain presentations return to their originating
  `CHILL`/`ACTIVE`/`TIRED` state.
- **Current side effects:** Advances/finishes movement commands, sound
  suppression, cry and bubble display, repeated jumps, and look-around steps;
  cancels/restores paired presentation ownership; clears timer/step/jump data;
  calls `OverworldWildSpawns_EnterActiveStateFromGenericAlert` when the end
  state is active; resets end state and visual flags. The current look-step
  early-return ordering can strand null-object `EMOTING` state.
- **Stack migration:** `EMOTING` becomes a presentation gate with an explicit
  target transition token. Completing or canonicalizing that token commits the
  pending apply/remove set once. A calm/active manual emote has no stack/timer
  mutation; a tired-origin manual emote follows D10/D11's exact-timer overwrite,
  zero, and mandatory-expiry rule. Live-logical object loss in both D10 and D11
  runs the intentional generation-authenticated quarantine/cleanup correction;
  D11 additionally does so before look-step returns. Alert completion runs active-entry actions
  once; stale tokens after slot reuse do nothing. Apart from that imported
  manual exception, migrated legacy tired/asleep candidate timers do not advance
  while the gate is present even if their logical candidate remains effective.
- **Persistence:** The presentation itself does not survive a map-header change;
  its intended end transition does.

### D07 — Alert with no reaction visual

- **Source:** `OverworldWildSpawns_TryStartSpotEmote`, no-reaction branch.
- **Trigger:** A chill Pokémon sees the player, passes alert chance/line tests,
  and `primitives.alertReaction == NONE`.
- **Old → new:** `CHILL` → `ACTIVE` immediately.
- **Current side effects:** RAM active state may be initialized before the
  branch; call-for-help children may be queued; resets hop-cry/sound flags,
  active steps, and battle-settle frames; enters generic active state, which
  clears RAM step/chain, applies decision cooldown, may initiate pickup/throw,
  schedules frame movement, and handles phantom special entry.
- **Stack migration:** Atomically apply the configured active state-candidate
  definition under owner `awareness`, then run active-entry. A separate
  `help-call` action may create child layers. No presentation token is needed.

### D08 — Alert presentation without jumps

- **Source:** `OverworldWildSpawns_TryStartSpotEmote`, `jumpCount == 0` branch.
- **Trigger:** Player detection with a non-none reaction whose configured jump
  count is zero.
- **Old → new:** `CHILL` → `EMOTING`, end state `ACTIVE`.
- **Current side effects:** Stores alert frame timer, direction, bubble and end
  state; resets active steps and battle settle; plays cry and bubble directly;
  schedules the frame task.
- **Stack migration:** Create an alert presentation token targeting application
  of the configured active state-candidate definition under `awareness`. For
  phase-0 parity it remains pending and does not enter state selection until
  presentation completion/canonicalization. Ordinary movement stays gated and
  entry actions run only once at that commit.

### D09 — Alert presentation with jumps

- **Source:** `OverworldWildSpawns_TryStartSpotEmote`, jumping branch.
- **Trigger:** Player detection with a jump-capable alert reaction.
- **Old → new:** `CHILL` → `EMOTING`, end state `ACTIVE`.
- **Current side effects:** Initializes RAM active direction before presentation
  when relevant; may queue help children; stores jump count/timer/direction/
  bubble/end state; enables cry-on-hop and partner-prep sequence; resets active
  steps and battle settle; starts the first paired movement command and frame
  task.
- **Stack migration:** Same pending `awareness` transition as D08. Cancellation
  must finish the paired partner restore command and relinquish held/native
  movement ownership.

### D10 — Manual hop-in-place presentation

- **Source:** `OverworldWildSpawns_TryStartManualHopEmote` in the spawns overlay.
- **Trigger:** Chain pause action or another explicit caller requests a manual
  hop from a required stable state.
- **Old → new:** `CHILL`, `ACTIVE`, or `TIRED` → `EMOTING` → caller-provided end
  state, normally the same state.
- **Current side effects:** Stores presentation timer/steps/direction/end state/
  bubble flags/sound policy; clears battle settle; starts paired hop and frame
  task.
- **Stack migration:** From `CHILL` or `ACTIVE`, presentation-only: preserve the
  exact layer set, timers, and effective state beneath it. From `TIRED`, retain
  the source quirk: the token authenticates the exact tired handle and timer
  generation, overwrites that candidate's remaining time with the presentation
  duration. Normal completion, explicit cancellation, and hop's intentionally
  corrected null/mismatched-object terminal path authenticate the captured
  logical presentation plus exact candidate/timer,
  set only that timer to zero, record one mandatory expiry, and consume the
  token. Object restoration runs only for a still-authenticated pointer; object
  loss records mandatory `MANUAL_PRESENTATION_OBJECT_LOSS` cleanup with exact
  presentation/candidate/timer/expected-manager/expected-object identity and quarantines object-
  dependent work without a stale write. Objectless maintenance releases logical
  task/presentation ownership without touching a replacement manager; only an
  exact `(mapGeneration,expectedManagerGeneration,expectedObjectGeneration)`
  rebind canonicalizes pose and clears quarantine. Hop's timer/end-state result
  remains source-equivalent, but authentication, typed cleanup, and quarantine
  are the intentional safety correction. A stale
  timer identity consumes the presentation diagnostically without touching a
  replacement. The first eligible tired tick runs that exact candidate's
  authored recovery to calm; the old duration is not restored. Unrelated layers
  and timers remain.

### D11 — Chain look-around presentation

- **Source:** `OverworldWildSpawns_TryStartChainPauseAction`, look-around branch.
- **Trigger:** A completed chain chooses `LOOK_AROUND`.
- **Old → new:** Stable `CHILL`, `ACTIVE`, or `TIRED` → `EMOTING` → same saved
  state.
- **Current side effects:** Uses at least three look frames; stores timer and
  look-step sequence; no bubble or cry; clears battle settle; starts first step
  and frame task.
- **Stack migration:** Uses the same calm/active preservation and tired-origin
  completion/cancellation timer-zero/mandatory-expiry contract as D10. Look
  object loss is an intentional safety correction: terminal
  handling first authenticates the logical tuple independently of the object,
  then runs before early returns for `LOOK_FIRST` through `LOOK_RETURN`. It
  consumes the token, zeros only the exact tired timer, publishes expiry plus
  `MANUAL_PRESENTATION_OBJECT_LOSS`, clears pointer ownership without
  dereference, and quarantines until objectless maintenance/an exact map-manager-
  object rebind finishes. This additionally repairs look's internal early-return
  defect, which can otherwise strand the live presentation before its terminal
  block. Destructive slot/context invalidation instead runs D01c, consumes
  the obligation, and publishes no expiry against a dead/reused slot.

### D12 — Called-for-help child becomes active

- **Source:** `OverworldWildSpawns_ApplyHelpChildSpawnState` in the spawns
  overlay; invoked after `OverworldWildSpawns_TrySpawnOneHelpChild`.
- **Trigger:** A parent's alert special action queues and successfully spawns a
  help child.
- **Old → new:** New child's `CHILL` → `ACTIVE`; if already `EMOTING`, only its
  end state changes to `ACTIVE`.
- **Current side effects:** Resets RAM step/chain; unless spawn-run/movement is
  still active, immediately enters generic active behavior; ensures frame task.
- **Stack migration:** Apply the configured active state-candidate definition
  under owner `help-call`. If startup presentation/movement still owns the
  object, defer active entry until it becomes stable. The migrated definition
  has `mapHeaderPolicy=PRESERVE_LOGICAL` and `battlePolicy=CLEAR`; preserve it
  only across an authenticated retained-primary map change, and clear it on
  battle, child reset, or despawn.

### D13 — Follower-ball aggro ABI enters active

- **Source:** `OverworldWildSpawns_EnterAggroState` is physically implemented in
  the fixed `.follower_release_aggro` section of
  `src/overworld_follower_release_overlay2/overworld_follower_release_overlay2.c`
  and imported by fixed address in the spawns overlay.
- **Trigger:** A released follower is marked aggressive, or the selector's ball
  collides with a wild target and the spawns loop consumes its pending flag.
- **Old → new:** For a newly spawned follower with a non-null object, any/reset
  state → numeric `ACTIVE` (`2`). For an existing wild target the helper marks
  `AGGRO_PENDING`; the spawns loop calls the ABI with a null object, then D12
  applies active behavior. If the target was tired, collision first zeros its
  tired timer so it can recover before pending aggro is consumed.
- **Current side effects:** Rewrites `spawn.active` to `TRUE | AGGRO_FLAG`, which
  also clears `AGGRO_PENDING`; resets active steps; follower entry sets
  `BIT_VANISH` until release presentation completes. The loop clears spot
  cooldown and runs D12. Aggro remains encoded in `spawn.active` until reset.
- **Stack migration:** The fixed bridge records/coalesces an aggro request
  before bounce-tile selection and does not reset active steps; the full
  orchestrator consumes it, resets active steps, and applies the configured active
  state-candidate definition under owner `aggro`. The migrated aggro definition
  is `mapHeaderPolicy=PRESERVE_LOGICAL`, `battlePolicy=CLEAR`. The legacy
  `OW_WILD_SPAWN_AGGRO_FLAG` remains dormant metadata through the all-slot
  battle movement reset: it is not a behavior layer, does not compete for
  effective state, and does not automatically reapply active behavior after
  battle. It clears with D01c.
- **Persistence:** Follower-release metadata preserves its aggro bit across
  release retries/clear. Per-spawn dormant aggro metadata lasts to slot reset/
  despawn, while the behavior layer follows the explicit map/battle policies.

### D14 — Picked-up target enters carried state

- **Source:** `OverworldWildHelper_StartCarriedThrowTarget` in
  `src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c`, called
  through `OverworldWildSpawns_StartCarriedThrowTarget`.
- **Trigger:** A pickup/throw carrier reaches a reserved, stable target.
- **Old → new:** Any stable non-`EMOTING` state → numeric `CHILL` (`0`) plus
  behavior class `PICKED_UP`.
- **Current side effects:** Clears target emote timer and active-step counter;
  changes behavior class, which changes cache identity/resolution; clears the
  movement chain in the wrapper; sets target pass-through and visible bits;
  records encoded carrier↔target relation and masks; clears carrier reservation
  timer; synchronizes all target tile, world-vector, facing-vector, and
  presentation coordinates to the carrier.
- **Stack migration:** Apply the picked-up state-candidate definition ID under
  owner `pickup.carrier:<slot>` and separately retain the throw relation/
  presentation handle. The definition is
  `mapHeaderPolicy=CLEAR,battlePolicy=CLEAR`. Do not overwrite the base behavior
  class. Enter action cancels target locomotion/chain safely and normalizes
  pass-through/render ownership.
- **Persistence:** Must be removed on drop/throw completion, reservation clear,
  either participant's reset/despawn, battle/capture preparation, and map-header
  transition. It must never persist to a reused slot.

### Fixed cross-overlay ABI constraints for D13 and external state readers

The follower-ball collision producer and the stack consumer cannot be joined by
an unconstrained direct call:

- `OverworldWildSpawns_StartFollowerReleaseBounce` occupies the fixed
  `0x0224F298` entry in
  `src/overworld_follower_selector_icons_overlay2/linker.ld` (called as Thumb
  address `0x0224F299`). Its linker slot is exactly `0x300` bytes, from
  `ORIGIN(rom)+0x300` through the next fixed entry at `ORIGIN(rom)+0x600`.
- `OverworldWildSpawns_EnterAggroState` occupies aligned linker/code address
  `0x0225046C`, imported/called with the Thumb bit as `0x0225046D`. Its fixed
  `.follower_release_aggro` range ends at `0x022504A0`, so its complete budget
  is exactly `0x34` bytes.
- `OverworldWildSpawnsOverlayEntry` is exactly 28 bytes at `0x023CD000` and has
  seven fixed function-pointer fields. External overlays already compile
  against those offsets.

The two direct entries retain ordinary 32-bit C/AAPCS Thumb-1/no-interwork calling convention
and these exact prototypes; they are not `LONG_CALL`, variadic, widened, or
adapter-owned:

```c
BOOL OverworldWildSpawns_StartFollowerReleaseBounce(
    FieldSystem *, OverworldWildSpawnState *, void *projectile, int slot);
void OverworldWildSpawns_EnterAggroState(
    OverworldWildSpawnState *, int slot, LocalMapObject *spawnedFollower);
```

The fixed overlay-entry layout is:

| Offset | Field and unchanged prototype |
|---:|---|
| `0` | `BOOL onPlayerStep(FieldSystem *, OverworldWildSpawnState *, OverworldWildResidentData *)` |
| `4` | `BOOL tryPrimeBattleFromTalk(FieldSystem *, OverworldWildSpawnState *, LocalMapObject *)` |
| `8` | `u8 cleanupPendingBattle(FieldSystem *, OverworldWildSpawnState *, u16 battleResult)` |
| `12` | `BOOL cleanupResidentData(void)` |
| `16` | `BOOL onPlayerFrame(FieldSystem *, OverworldWildSpawnState *)` |
| `20` | `void onFieldBusy(FieldSystem *, OverworldWildSpawnState *, OverworldWildResidentData *)` |
| `24` | `void prepareMapHeaderChange(OverworldWildSpawnState *, OverworldWildMapHeaderChangeMode)` |

Function-pointer Thumb bits and ordinary ownership remain exactly as current
producers/consumers compile them. Bounce receives `r0..r3` in declaration order
and returns 32-bit `BOOL` in `r0`; aggro receives `r0..r2` and returns no value.

Phase-0 therefore freezes this bridge:

1. Shared bridge storage is a fixed bounded
   `aggroBridge[OW_WILD_MAX_SPAWNS]`, one `EMPTY/PENDING/CLAIMED` cell per target
   slot, not a singleton mailbox. Each cell separates orchestrator-owned
   resident-readable `slotGenerationMirror[slot]` and
   `objectGenerationMirror[slot]`, their captured expected values, the frozen
   spawn's encounter generation (or equivalent resident mirror), and an
   independent nonzero per-slot `publicationSequence` used only for claim/ABA
   protection. Distinct slots never overwrite or coalesce each other; consumers
   visit pending cells in ascending slot order.
2. Duplicate key `K` is exactly `(slot,expectedSlotGeneration,
   expectedEncounterGeneration,expectedObjectGeneration)` and excludes
   `publicationSequence`. The state machine is exact: `EMPTY + K` allocates a
   fresh sequence and publishes `PENDING` last; `PENDING + same K` and
   `CLAIMED + same K` coalesce with cell bytes unchanged; `PENDING + different
   K` replaces only after the old key is proven stale, otherwise returns
   internal `BRIDGE_BUSY`; `CLAIMED + different K` always returns
   `BRIDGE_BUSY`. Because the frozen ABI returns `BOOL`, busy maps to `FALSE`
   only after publishing/coalescing exact `(K,retryGeneration,
   sourceOwnerGeneration)` into bounded
   `aggroBridgeRetry[OW_WILD_MAX_SPAWNS]`. The authenticated source owner cannot
   move/terminate/release while retry is pending. A different live retry key is
   safety quarantine; stale retry may clear. Mandatory maintenance promotes it
   when the primary cell empties. Producer code never steals/clears a claim,
   and busy changes no primary cell/aggro metadata/tile selection.
3. After target authentication and before bounce-tile selection, fixed code
   publishes both durable source metadata effects:
   `OW_WILD_SPAWN_AGGRO_FLAG` on the hit encounter and
   `OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG` on release state, then publishes the
   per-slot cell as above. A no-tile `FALSE` result retains both metadata effects
   and that pending cell. Legacy `OW_WILD_SPAWN_AGGRO_PENDING_FLAG`, if retained
   as a compatibility mirror, cannot drive behavior. Fixed code never reads the
   runtime sidecar, keeps a layer handle, or resets active steps.
4. The spawns overlay atomically claims `PENDING→CLAIMED` for exact
   `(K,publicationSequence)`, reauthenticates all generations, and attempts one
   atomic exact-tired-expiry/aggro/active-step transaction. Orchestrator `BUSY`
   conditionally restores identical `CLAIMED→PENDING`; even a published but
   uncommitted expiry remains mandatory, with no partial mutation. Success
   clears `CLAIMED→EMPTY` only after commit. Mismatch clears only the exact
   cell/claim. It never clears the unkeyed legacy pending mirror or clears/advances the
   authoritative slot/object generation mirrors, encounter generation,
   publication-sequence carrier, or either durable aggro metadata flag. Only
   destructive slot lifecycle owns those values; permanent schema failure
   quarantines rather than dropping work. Authenticated success then promotes
   any exact retry; destructive lifecycle alone may consume a stale retry owner.
5. Do not append, reorder, or repurpose fields in the 28-byte entry. Any new
   cross-overlay read-only effective-state query requires a separate versioned
   entry or must be serviced inside an existing callback. Until that ABI exists,
   the orchestrator may maintain a compatibility presentation/state mirror for
   readers; external code may not read the new sidecar by offset.
6. The fixed bounce path no longer expires tired by writing a shared timer. It
   only publishes aggro pending. If a migrated timed tired candidate is
   effective, the consumer captures and validates its exact `(runtimeEpoch,
   slotGeneration, ownerId, instanceKey, entryGeneration, timerGeneration)`
   and marks a non-droppable mandatory expiry; it never zeros a shared/current
   timer or removes by owner/profile. Aggro applies once after that exact expiry
   commits or is proven stale. Lower tired candidates remain and can still hide
   aggro until their own expiry.
7. The per-slot carrier array uses separately audited shared storage; it does not add a field
   to the 28-byte entry or change either direct prototype. Linker assertions
   for the `0x300` bounce slot, the `0x34` aggro slot/address, the 28-byte entry,
   all seven offsets, and its base address are required static verification
   gates.
8. Existing helper-private projectile fields `impactSlot` and
   `impactEncounterGeneration` remain dedicated to projectile/capture
   validation. They are not repurposed as the consumer-visible carrier; the
   consumer must be able to read the dedicated bridge carrier above.

### D15 — Picked-up target exits after landing or cancellation

- **Source:** `OverworldWildSpawns_HandleFinishedMovementCommand`,
  `OverworldWildSpawns_ClearThrowStateForSlot`, and
  `OverworldWildSpawns_RestorePickedUpBehaviorClass` in the spawns overlay;
  relation cleanup is in `OverworldWildHelper_ClearPickupThrowState`.
- **Trigger:** Carried target's throw movement finishes, a relation is canceled,
  a participant resets, or map context changes.
- **Old → new:** State byte stays `CHILL`; behavior class returns from
  `PICKED_UP` to the species/context class.
- **Current side effects:** Clears throw target mask; finishes/restores custom
  jump prep; restores behavior class; normalizes throw presentation and native
  shadow; commits landing tile; clears vanish/pass-through; may immediately
  queue a battle when landing on the player tile. Relation cleanup clears
  carrier/target masks, reservation timers, and all relationships involving the
  removed slot.
- **Stack migration:** Remove the exact pickup handle. Recomposition reveals all
  remaining layers, rather than reconstructing a class. Exit action restores
  presentation/shadow/landing state and performs the same player-tile battle
  check with `originKind=THROW_LANDING`, which may start the battle immediately
  or queue it without requiring ACTIVE/`CONTACT`. Removing a middle stack layer
  must not disturb tired, aggro, or any other owner.

## Major transition paths without additional direct writes

### Player detection: calm to alert/active

`OverworldWildSpawns_TickMovement` only permits detection while state is
`CHILL` and `movementSpotCooldowns == 0`. It decrements that cooldown in chill,
resolves the profile and primitives, checks alert chance and alert line/range,
then calls D07, D08, or D09. The alert setup may initialize attentive RAM
direction and speed and may enqueue call-for-help before active movement begins.

Migration contract:

1. Preflight the configured awareness delta and commit a generation-safe
   detection/presentation token. Do not apply awareness yet when a visual exists.
2. Run `DETECTION_ENTRY_CALL_FOR_HELP` once after token commit and before the
   optional visual. Its request carries token/slot generation and cannot
   duplicate children on retry.
3. Cancel or defer incompatible movement ownership atomically. Start the visual
   when configured; otherwise commit awareness immediately.
4. On awareness commit, reset active stamina count and battle-settle state, clear stale
   RAM/chain state, initialize the new effective locomotion, and invoke special
   attentive-entry actions. `ACTIVE_ENTRY_TRY_PICKUP_THROW` runs once on actual
   node entry; its active-loop counterpart is idempotent and does not replay on
   cache rebuild.
5. Applying an unrelated higher-priority layer during alert presentation must
   not be lost when the presentation completes.

### Active movement and stamina exhaustion

`OverworldWildSpawns_HandleFinishedMovementCommand` is the normal stamina
driver. Active non-RAM movement increments `movementActiveSteps`; the movement
that reaches `profile.stamina` calls D04 unless the slot still owns a throw
reservation. A staged-hop completion can preload the counter to `stamina - 1`
so the normal completion path triggers tired. RAM movement has its own step/
speed path and normally returns before this counter logic.

Migration contract:

- Each command records the universal origin identity
  `(runtimeEpoch,slotIndex,slotGeneration,commandGeneration,commandSerial,
  controllerId,nodeId,stateProfileId,winnerKind,winnerDefinitionId,
  winnerOwnerId,winnerInstanceKey,winnerEntryGeneration,effectiveGeneration,
  objectGeneration,staminaPolicyId,staminaPolicyGeneration)`. `winnerKind` is
  `BASE` with all four layer fields zero or `LAYER` with its exact nonzero
  handle fields, so the two forms cannot alias. Profile or
  node ID alone is insufficient because profiles may be shared and static/
  modifier rebinds may retain either ID while changing policy. A compatible
  command that completes with every identity still authenticated charges that
  policy exactly once. A state change that makes the command incompatible
  cancels it during reconciliation and charges zero; stale/duplicate
  completion is a diagnostic no-op and no later cleanup path may charge it.
- The per-live-slot movement-chain subsystem owns one inactive/active chain
  record and its nonzero `chainGeneration` carrier; it is never profile- or
  object-pointer-owned. D01d initializes inactive generation `1`. Accepted start
  advances before publishing the first action; replacement invalidates the old
  owner and publishes the new chain with exactly one atomic advance; explicit
  cancel advances once and clears direction/steps/remaining/pause/previous-tile
  state; idempotent cancel while inactive does not advance. Natural completion
  consumes the owner, and the next start advances before reuse.
- Every native/custom chain command, queued continuation, pause/manual action,
  previous-tile lease, and completion carries that identical universal tuple
  plus `(chainGeneration,chainStepSerial,artifactKind,artifactGeneration)`.
  `artifactKind` is the closed enum native command, custom command,
  continuation, pause action, previous-tile lease, or completion. The exhaustive
  map is command kinds→`commandGeneration`, continuation→
  `continuationGeneration`, pause→`actionGeneration`, lease→`leaseGeneration`,
  completion→`completionGeneration`; every counter is nonzero, sidecar-owned,
  and advances before publication/replacement. Every artifact
  authenticates the full prefix/suffix plus active owner before mutation. Any
  state-profile, winner, effective, object, stamina-policy ID/generation, chain,
  or step mismatch is stale. Step-serial wrap advances chain generation once
  and drains all old artifacts before reuse of `1`.
- Apply the configured tired state-candidate definition under owner `stamina`
  exactly once at the threshold.
- Do not let duplicate tick paths create duplicate layers for the same owner.
- Active-step accumulation pauses whenever the controller active state is not
  effective. It resumes with the same count when that state is revealed unless
  the atomic transition action explicitly resets it. A hidden stamina-tired
  entry's `PAUSE_WHILE_HIDDEN` recovery timer also pauses.

### RAM collision and crash

`OverworldWildSpawns_EndRamCrash` plays crash feedback, starts positional shake,
clears RAM direction/step/speed and chain. Chill or already-tired RAM only waits
for the shake. Active RAM calls D04 and extends movement cooldown to at least the
shake timer. A RAM impact that starts battle instead uses
`OverworldWildSpawns_TryStartRamCrashBattleImpact`, plays feedback, and clears
RAM state without applying tired before battle handoff.

Migration contract:

- `ram-crash` is distinct from `stamina` even when both select the same profile.
- RAM locomotion owns direction, step counter, speed, and chain; every RAM exit,
  tired/active/help/aggro entry, or RAM reinitialization resets all four,
  including the step counter.
- Crash shake is an independent generation-safe presentation owner. Ordinary
  tired entry/expiry and a compatible modifier change leave it running. It
  restores exact saved base coordinates before another action takes positional
  ownership, object delete/recreate/rebind, battle/map/destructive cleanup, or
  replacement shake; unauthenticated object identity clears the token without
  a pointer write.
- Battle-impact and wall-impact transitions must remain distinguishable.

### Throw carrier recovery

During an active pickup/throw path, the carrier reserves a target and its active
loop is held by that reservation. A successful launched throw clears the
relation, sets recovery cooldown, and applies D04 to the carrier. A failed/zero
distance throw releases the target and applies only recovery cooldown. The
target's pickup layer follows D14/D15 independently.

Migration contract: carrier `throw-recovery` and target
`pickup.carrier:<slot>` are separate handles. Removing either must not
implicitly remove the other or any unrelated state layer.

### Battle entry, battle result, and capture

There are exactly five semantic battle-origin routes. Queued retry is shared
fallback machinery and preserves the originating route ID; it is not another
origin.

1. **Normal/contact scan.** `battleGraceSteps != 0` blocks the complete scan
   and decrements only when the caller's `decrementBattleGrace` argument is
   true. Existing pending battle also blocks the complete scan. `justSpawned`
   is a global one-scan gate: the function clears it and returns before looking
   for contact, even when nothing touches. After those gates, slot order is
   authoritative. Only non-follower active/current objects that touch the
   player, are in `ACTIVE` (the only state for which
   `GetBattleTriggerForSpotState` returns `attentiveBattle`), and declare
   `CONTACT` qualify. `IsTouchingPlayer` additionally rejects throw
   participants, spawn-run, chill spot cooldown, movement-in-progress, and
   single movement. The first current touching `CONTACT` slot causes an
   immediate-or-queue attempt and the scan returns that result; failure of both
   paths does not continue to a later touching slot. `TryStartBattleForSlot`
   rejects follower, pending battle, player-ball activity, any active throw
   target mask, unstable player movement, a non-current object, and every
   failure in `IsSlotStableForBattle`.
**Shared queued retry.** `QueueBattleForSlot` may accept a currently unstable slot;
   it rejects follower, pending battle, player-ball activity, any active throw
   target mask, participation by the target slot, invalid field context, and a
   non-current object. `TryStartQueuedBattle` waits settle frames and repeatedly
   applies `IsSlotStableForBattle`; it cancels if context/object identity fails.
   Stability rejects throw participants, spawn-run, staged hop, RAM shake,
   `EMOTING`, `TIRED`, movement-in-progress, single movement, and hidden/flicker/
   targeted phantom presentation.
2. **Active RAM-impact route.** The effective state must be numeric/source
   `ACTIVE`, `attentiveBattle` must be `RAM_CRASH`, and the next impact tile
   must contain the player or an authenticated active follower. In the
   frame-movement-task path, direct prime rejects pending battle, player-ball
   work, or non-current target identity, then requests/defer-publishes the
   script without first running ordinary slot-stability/movement reset; failed
   publication clears the primed pending identity. Outside that path it enters
   the common immediate-or-queue machinery. Only an accepted RAM route plays
   crash feedback and clears RAM direction, step counter, speed, and chain; it
   applies no `ram-crash` tired candidate.
3. **Scripted talk prime.** `OverworldWildSpawns_TryPrimeBattleFromTalkSlot`
   rejects follower, pending battle, player-ball activity, any active throw
   target mask, participation by the target, non-current object, and an unstable
   player. It does **not** call `IsSlotStableForBattle` before the all-slot reset.
   `OverworldWildBehavior_FindBattleTalkSlot` in
   `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
   first validates field/map/manager context. An explicitly resolved talked
   object (including the last-talked variable while a task manager exists) is
   returned before `excludedMask`, spawn-run, or phantom-hidden filtering. Its
   facing-tile fallback does honor spawn-run, excluded mask, phantom hidden,
   active/object validity, current/player/previous tile selection. The later
   prime predicate still rejects follower/throw participation but deliberately
   allows scripted talk to stabilize emote, tired, movement, spawn-run, RAM,
   and phantom work through the all-slot reset. It primes pending identity but
   does not call `IsSlotStableForBattle` or request the script itself.
4. **Physical A-button route.** This is not scripted talk prime. A physical
   rising edge is required; follower-selector `ACTIVE`/`RELEASE_GATE` suppresses
   the route and copies the current A state into the latch, release clears the
   latch, and already-down blocks repeat. It calls
   `FindBattleTalkSlot(fieldSystem,state,NULL)`, so only the facing-tile fallback
   and all of its context/excluded/spawn-run/phantom/current-object gates apply.
   If stock facing-object lookup returns a different object, the attempt is
   rejected and A is latched. Otherwise it calls the common
   `TryStartBattleForSlotOrQueue`, so slot stability decides immediate versus
   queued behavior. Finder miss or failure of both immediate and queue does not
   latch A and may retry while held; success latches it.
5. **Throw-landing route.** After an authenticated carried target finishes its
   throw movement, D15 removes the exact pickup relation/handle, restores its
   landing presentation, and directly calls common immediate-or-queue when the
   landing tile is the player's tile. This route deliberately bypasses contact
   scan predicates: the target may be calm/non-`ACTIVE`, need not declare
   `attentiveBattle=CONTACT`, and does not need a contact-scan touch result. Its
   throw/slot/object generations and the common pending/player/stability gates
   must still authenticate.

On an accepted route, `originKind` is exactly one of `CONTACT`, `RAM_IMPACT`,
`SCRIPT_TALK`, `A_BUTTON`, or `THROW_LANDING` and remains part of command-origin
identity through queue/reservation diagnostics. Phantom
presentation is normalized/revealed first where required. All successful
origins converge on the same infallible all-slot battle transaction. Routes
that create or defer a script task reserve/prime before the point of no return;
`SCRIPT_TALK` instead authenticates and continues inside its already-running
script/task-manager context and creates no second script task.

The accepted origin/subroute table is closed (`CB=OVERLAY_CALLBACK_RETURN`,
`SC=SCRIPT_COMMAND_RETURN`). Queue-only publication creates no teardown plan;
the row applies when the retry is accepted.

| Origin | Accepted subroute | Mask | Required order |
| --- | --- | --- | --- |
| `CONTACT` | `IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | Origin callback ready/return/resident CB ACK, then future script command ready/return/resident SC ACK. |
| `CONTACT` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Accepted retry callback CB ACK, then future command SC ACK. |
| `RAM_IMPACT` | `ORDINARY_IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | Impact callback CB ACK, then future command SC ACK. |
| `RAM_IMPACT` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Accepted retry callback CB ACK, then future command SC ACK. |
| `RAM_IMPACT` | `FRAME_TASK_DIRECT_PRIME_DEFERRED_SCRIPT` | `CB|SC` | Accepting frame-task callback CB ACK must precede deferred script-command entry; SC ACK follows command return. |
| `A_BUTTON` | `IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | A-button callback CB ACK, then future command SC ACK. |
| `A_BUTTON` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Accepted retry callback CB ACK, then future command SC ACK. |
| `THROW_LANDING` | `IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | Landing/frame callback CB ACK, then future command SC ACK. |
| `THROW_LANDING` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Accepted retry callback CB ACK, then future command SC ACK. |
| `SCRIPT_TALK` | `NESTED_EXISTING_SCRIPT_COMMAND` | `CB|SC` | Inner overlay prime callback ready/return/resident CB ACK, then outer already-running script command ready/return/resident SC ACK. |

No other origin/subroute/mask is valid. Future-script execution before CB ACK,
or nested `SCRIPT_TALK` SC readiness/ACK before CB ACK, is rejected. No cleanup,
task release, physical unload, or overlay unload may start until every required
actual frame has returned and its exact boundary cell is ACKed, or that exact
frame has a resident quiescence proof under `RETURN_CANCELED`. Every route also
acquires a generation-scoped teardown-readiness reservation that pins the full
overlay 149/150/151/152 load/ownership closure and preflights field-service
shutdown, helper/behavior validation, both cleanup lifecycle phases, task/
resident release, overlay-conflict checks, and physical unload readiness. Any
currently mutating prepare phase must be split into non-mutating reserve plus
infallible consume. Preflight stores the lease in a fixed resident
`BattleTeardownPlan` carrying `(EMPTY|RESERVED|PUBLISHED|CLAIMED|RETURN_PENDING|RETURN_ACKED|RETURN_CANCELED|CLEANUP_DONE|TASKS_RELEASED|UNLOADED|RELEASED,planEpoch,planGeneration,runtimeEpoch,mapGeneration,pendingBattleGeneration,targetSlotGeneration,targetEncounterGeneration,originKind,originSubroute,scriptTaskGeneration,taskManagerGeneration,overlayLoadGeneration[149..152],teardownLease,leaseOwner,teardownExecutorIdentity,teardownExecutorClaimGeneration,returnBoundary[2],requiredReturnMask,readyReturnMask,returnedMask)`. Teardown execution ownership is independent of return publication. Each required `returnBoundary` cell is `(UNUSED|REQUIRED|READY|ACKED|CANCELED,boundaryKind,publisherIdentity,enclosingResidentCallerIdentity,ticketSequence)`, where `ticketSequence` is nonzero, the two required sequences are unequal, and neither may be reused before the plan is `RELEASED`.
`OVERLAY_CALLBACK_RETURN.publisherIdentity` is the exact
`(callbackStableId,callbackInvocationGeneration,overlayId,overlayLoadGeneration)`
and its enclosing caller is
`(residentOverlayCallerStableId,residentCallGeneration)`.
`SCRIPT_COMMAND_RETURN.publisherIdentity` is the exact
`(scriptCommandStableId,scriptTaskGeneration,taskManagerGeneration,scriptCommandGeneration)`
and its enclosing caller is
`(residentScriptDispatcherStableId,dispatcherGeneration)`. Commit binds these
independently, transfers lease ownership
`TRANSITION→BATTLE_TEARDOWN_PLAN`, and publishes last. Transition finish releases
only reservations it still owns. The teardown executor never owns/releases the
lease or authenticates return truth. Immediately before return, only the exact
publisher for that boundary may publish its own `REQUIRED→READY` ticket; the
first ready cell advances to `RETURN_PENDING`, later cells remain pending. Only
after actual return may that cell's exact enclosing resident caller ACK it and
set its returned bit. Callback identities cannot publish/ACK script tickets;
script identities cannot publish/ACK callback tickets. Cross-boundary spoofing
is a complete no-op. Only complete resident-observed masks transition to
`RETURN_ACKED`. Executor attempts to publish/ACK, clean up, unload, or release
are rejected. Delayed return or unload leaves the plan as lease owner and
retains overlay pins. Cleanup/task release/unload follow resident
`RETURN_ACKED`, or a distinct resident-proved `RETURN_CANCELED` after quiescence.
Only the coordinator's authenticated `UNLOADED→RELEASED` releases exactly once.
A lost teardown executor is replaced only after resident proof it cannot
execute/resume; boundary cells remain independently authoritative, and mandatory
cleanup never fabricates `RETURN_ACKED` or owns the lease.
No fallible unload-equivalent call may remain after the point of
no return. The RAM frame-
task route retains its direct-prime/deferred-publication gate but may not bypass
the global logical clear. Capture preparation is
not the all-slot battle transaction. Accepted player-ball impact authenticates
one target generation, then atomically removes **every** runtime layer on that
target, cancels each removed candidate timer and invalidates its timer
generation, clears throw relations involving the target, and clears target
movement, emote/presentation gate, staged hop, spawn-run, RAM locomotion/crash
shake (restoring authenticated base coordinates first), phantom/canopy
ownership, queued battle, and settle state. Base/static and encounter/slot
identity remain; unrelated slots retain their layers/timers, although a
cross-slot throw relation involving the target is cleaned. Removed target
layers/timers are never suspended for later restore.

Successful capture finalization runs D01c. Any breakout—including the
heap-pressure forced three-shake result or failure to authorize/finalize the
party/box destination—retains the same encounter and `slotGeneration`, restores
the target visible at controller base/calm plus static context with the impact
cooldown, and does not reconstruct any removed layer or timer.

On cleanup, defeated/caught slots are reset by the helper callback. Retained or
fled encounters receive battle grace. A fled encounter that still has a valid
object/context calls D04. A retained non-fled encounter remains in the chill
state produced by battle-entry reset.

Migration contract:

- Build one all-slot battle transaction. For every active slot, remove every
  `battlePolicy=CLEAR` entry and suspend every explicit
  `battlePolicy=PRESERVE_LOGICAL` entry from both state selection and modifier
  folding. `SYSTEM` entries are discarded and may be freshly emitted only by
  their registered owning system after return; this is independent of the
  `SYSTEM_SAFETY` channel. Existing
  migrated definitions are `CLEAR` unless individually proven otherwise, so
  the visible result is calm on all slots exactly as source.
- Clear every movement/presentation/task handle for every slot. Suspended
  logical layers keep generation-safe handles and paused timers but no object
  pointer or command ownership.
- Preserve `OW_WILD_SPAWN_AGGRO_FLAG` only as dormant encounter metadata. The
  aggro behavior layer is `CLEAR`; metadata neither selects active behavior nor
  automatically reapplies it after return.
- Preflight the complete world delta. For any route that creates or defers a
  script task, reserve/prime that handoff before the global clear reaches its
  point of no return. `SCRIPT_TALK` only authenticates its already-running
  script context. Every route additionally reserves the teardown readiness
  above; it is attached to exact origin/pending-battle/overlay generations.
  Commit transfers that lease into the exact resident `BattleTeardownPlan`.
  Script preparation claims only execution authority; it never owns/releases
  the lease or records a post-return ACK. It publishes only exact per-boundary
  `RETURN_PENDING` readiness; after actual unwind, enclosing resident callers
  record callback/script-command returns independently. Cleanup waits for
  resident `RETURN_ACKED` or proved quiescent `RETURN_CANCELED`, and only the
  coordinator's authenticated `UNLOADED→RELEASED`
  transition performs the exact-once release. Script, teardown, or
  authentication failure changes
  no layer, timer, counter, generation, cache, command, presentation, or pending/
  queued battle identity. Every acquired reservation releases exactly once.
  Publishing and teardown after a successful reservation must be infallible;
  stale/replayed consume is a diagnostic no-op. A platform that cannot prove
  both after reserve rejects during preflight and never crosses the point of no
  return; postcommit rollback is not permitted. This ordering is the corrected
  ADR's explicit safety fix over current source.
- `RETAIN` resumes allowed `PRESERVE_LOGICAL` entries and otherwise remains
  calm. `FLED` does the same, then applies/replaces the tired state-candidate
  definition under distinct owner `battle-fled` only on the retained encounter;
  it never aliases the stamina owner. Its timer uses `PAUSE_WHILE_HIDDEN` and
  its authored recovery delta uses `REMOVE_REQUIRED` on only the battle-fled
  handle plus tired exit counters/cooldown; it does not contain calm-reset owner
  removals.
- Defeated/caught/despawn invalidates every handle with the slot generation.

### Spawn, spawn-run, and follower release

`OverworldWildSpawns_InitSpawnSlotState` calls D01d, stores behavior class/limit
key, clears the profile cache, applies pass-through, and initializes canopy
render/cache state. Spawn-run is not a spot state: it suppresses normal AI,
stores a destination, and uses active speed until landing, then clears itself
and chooses a post-spawn cooldown based on current state. Help children receive
D12 after spawning. Followers may receive D13 and preserve the release-level
aggro bit across retry state.

Migration contract: install the base/controller/static stack before selecting
startup locomotion. Spawn presentation gates ordinary state entry. Runtime
state layers cannot modify population-limit identity or spawn matching.

### Despawn, follower removal, context loss, and slot reuse

`OverworldWildSpawns_ResetSlotState` routes through movement reset, restores
canopy render state, clears throw relationships and canopy proxy/cache, clears
saved HP and logical spawn identity, follower party selection, capture and
presentation masks, behavior class/limit key, profile cache, pending/queued
battle identity, and spawn-run state. `encounterGeneration` is incremented when
the slot is initialized for its next spawn.

`OverworldWildSpawns_DetachAllMovementStateOnContextLoss` cancels deferred and
pending battles and frame task; suspends/discards player-ball presentation;
restores canopy layer probe; resets capture/settle/queued battle state as
appropriate; finishes object-owned commands when the old context is safe, or
clears only code-owned tasks otherwise; clears staged hop, spawn-run, RAM,
canopy cache, emote partner, phantom state, throw state, far samples, and field
pointer.

Migration contract: add a slot generation to every layer handle. Destruction
clears the stack and advances the live→empty generation exactly once; the
immediate next assignment consumes that generation without a second advance.
Only the authenticated retained-primary map-header path preserves
compatible `PRESERVE_LOGICAL` entries; every discard/destructive context-loss
path runs D01c. All old presentation handles are invalid.

If overlay 149 is unavailable, destructive logical cleanup is explicitly
eventual but immediately quarantined. The always-resident map/field service
deletes authenticated retained primary objects, nulls their object pointers,
sets map identity invalid, records a dedicated destructive-cleanup-pending bit
in resident state, and requests/retries the existing spawns overlay. While the
bit is set, no slot query, timer, transition, assignment, refill, or AI path may
treat the old records as live. The first guaranteed existing
`onPlayerFrame`/`onPlayerStep` entry into overlay 149 runs D01c for every owned
old slot before any composition/refill, then clears the bit. This uses the
existing 28-byte entry and is eventual logical cleanup, not an appended ABI
hook. When overlay 149 is already present, D01c remains immediate.

### Forced asleep: data is live, runtime application is retired

`data/OverworldWildBehaviorData.c` still contains the “Forced asleep” override
matched by `OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP`. It writes stamina,
tired state, rest time, and special action. The live source does **not** contain
a caller that constructs this forced match or applies it to an existing slot.
The former Sing path is documented in
`documentation/overworld_wild_sing_alert_logic.md`: it required a stable chill
target, resolved/applied the forced profile, and called D04; wake-up reused D03.

Migration contract:

- Treat the data record as migration input for a dormant **state-candidate
  definition**, not a live modifier or currently live transition.
- Reintroduction applies that definition ID under owner
  `forced-sleep:<source>` and does not replace the immutable base or erase
  `aggro`, `awareness`, `pickup`, weather, or other layers.
- Forced sleep wins over ordinary controller/tired candidates while present,
  but a higher `POSSESSION`/script/system candidate may hide it. Its timer uses
  `CONTINUE_WHILE_HIDDEN`; expiry removes only its exact handle and recomposes the
  remaining stack.
- Entry cancels incompatible movement safely and owns its sleep timer/visual;
  exit removes only its handle.
- Do not retain the hardcoded assumption that override profile index zero is
  forced sleep.

Concrete hidden-timer parity sequence:

1. `awareness` and `aggro` active candidates are present, with aggro effective.
   `stamina` applies tired with four ticks remaining; tired wins and its
   `PAUSE_WHILE_HIDDEN` timer is eligible.
2. `forced-sleep:sing-7` applies asleep with two ticks remaining and wins. Then
   a stabilized `CARRIED` possession candidate applies above it and becomes
   effective. The hidden stamina-tired timer stays at four; possession is not a
   presentation gate, so forced sleep continues because it is
   `CONTINUE_WHILE_HIDDEN`.
3. On the second sleep tick, expiry removes only the hidden forced-sleep handle.
   `CARRIED` remains effective and the stamina-tired timer is still four.
4. Removing the exact pickup handle reveals stamina-tired with exactly four
   ticks remaining. After four effective tired ticks, one
   `LEGACY_RETURN_CALM` transaction
   removes the exact stamina-tired handle plus awareness and aggro from the
   generated calm-reset owner set. The base calm state wins.
5. A weather modifier and dormant legacy aggro metadata present throughout
   remain untouched; the aggro **behavior layer** is gone.

## Side-effect ownership matrix

The transition orchestrator must classify and reconcile these resources. A
profile composition alone is insufficient.

| Resource | Current owners/operations | Required transition rule |
| --- | --- | --- |
| Native held/single movement | `StartMovementCommandForSlot`, reset/canonicalize helpers | Finish or cancel once; clear `movementNativeHeldMask`, object-held movement, single-active bit, pending direction/distance, and in-progress mask before incompatible entry |
| Custom/staged hop | Custom jump state, staged-hop target/list task, canopy prep | Ordinary phase-0 transitions return `BUSY` until a stable boundary. Battle/map/destruction/system cleanup restores paired presentation, clears owned bits/task/target, and settles landing; it never hands a command to a different state winner |
| Alert/manual emote | Timer, step, end state, bubble flags, partner-prep object, hop sound suppression | Represent as a generation-safe presentation token capturing expected manager/object generations. Finish authenticated partner restore once. Live-logical hop/look object loss intentionally terminalizes without dereference, zeros only the exact tired timer, records scope-specific mandatory cleanup/expiry, and quarantines; look additionally terminalizes before its defective early returns. Destructive D01c publishes no expiry for the dead slot |
| Movement chain | Per-slot owner plus `chainGeneration`, direction/steps/remaining/pause/actions and previous-tile leases | D01d initializes inactive generation 1; start/replacement/cancel advance as frozen above; every command/continuation/completion authenticates the complete chain tuple. Clear on incompatible ownership, pickup, reset, and context loss |
| RAM locomotion | Direction, step counter, speed, chain | Reset all four on RAM exit/active/tired re-entry and reinitialize from the winning state profile; preserve wall-crash versus battle-impact distinction |
| RAM crash presentation | Generation-safe shake timer, authenticated object, saved base X/Z | Runs independently through ordinary tired enter/expiry. Restore exact base before positional handoff, replacement shake, object rebind/delete, battle/map/destruction; stale object clears token without pointer write |
| Stamina/rest | Active steps and per-entry timed state | Charge a complete command-origin identity once. Ordinary tired pauses while hidden; `LEGACY_RETURN_CALM` removes its exact handle plus the generated awareness/aggro/help-call calm-reset set. Battle-fled has authored `REMOVE_SELF`. Forced sleep continues while hidden and removes only itself |
| Phantom | Hidden flag/steps, flicker timer/object, teleport target/object, visible pause, pass-through | Reveal before tired/battle/reset; active entry normalizes the authenticated primary object and may start flicker/cooldown; cancellation may delete auxiliary flicker objects and must recompute pass-through |
| Canopy | Tree-top proxy, render override/cache, expected/settled landing, custom prep | Finish partner restore and restore render priority before object/context destruction; recompute tree-top profile after static context/layer change |
| Pickup/throw | Per-carrier relation, target/carrier masks, reservation timer, custom jump, pass-through, synchronized vectors | Layer owner and presentation relation are separate. Clear relations involving either participant; normalize shadow/render; then remove pickup layer and recompose |
| Battle | Queued slot, settle frames, pending identity/generations, grace, script-handoff lease, and resident `BattleTeardownPlan` | Every origin preflights/reserves the complete teardown closure; script-creating routes also reserve handoff. Commit transfers the lease into the exact plan and independently binds teardown executor plus CB/SC publisher/caller tickets. Boundary-ready `RETURN_PENDING` → exact resident ACKs → `RETURN_ACKED` (or resident-proved `RETURN_CANCELED`) → cleanup → task/resident release → physical unload precede the coordinator's sole `UNLOADED→RELEASED` release. Delayed/lost executors never own the lease or authenticate returns; mandatory cleanup replaces only execution authority. Failure occurs before mutation; rollback is forbidden |
| Spawn-run | Target, active flag, startup locomotion | It gates normal AI but is not a state layer. New effective state may affect post-landing cooldown; cancellation clears target and owned movement |
| Map transition | Preserve/discard/canonicalize modes, map/encounter/retention plan tuple, caller claim sequence/mode, and fixed reservation ledger | Each fixed callback atomically consumes only its exact caller claim. Authenticated retained-primary changes re-resolve behavior context/controller, translate generated tired wrappers, keep captured spawn/population identity, and release fixed-ledger reservations exactly once on every terminal path. Same-map manager replacement resets logical movement to calm; cold-overlay discard quarantines/D01c |
| Cache | Behavior class and spawn identity currently key flattened cache | Effective cache key must include base/static generation plus ordered runtime-layer generation. Apply/remove never relies on stale cached primitives or pointers |

## Required transition ordering

A centralized apply/remove operation uses the ADR's exact phases:

1. **Pure identity/delta preflight:** capture and validate every epoch,
   generation, required/if-present operation, handle, definition, capacity,
   lifetime policy, and timer action.
2. **Pure composition and planning:** build the final layer/timer set,
   prospective effective result, exact resource-stabilization plan, required
   postcommit actions, and optional-visual fallbacks.
3. **Fallible reservation:** acquire every script/object/task/child-slot/heap
   reservation without publishing visible ownership. Battle work also acquires
   its complete script/task-manager/overlay teardown-readiness lease here.
   Unavailable or unsafe work returns `BUSY`/error here.
4. **Reservation validation:** recheck captured generations/identities; failure
   releases reservations and changes nothing.
5. **Point of no return:** cross only after every remaining operation and
   required publication is proven non-allocating and infallible.
6. **Infallible stabilization:** execute the precomputed movement, RAM-shake,
   phantom, canopy/emote-partner, battle, and throw cleanup exactly once.
7. **Infallible commit:** write the complete layer/timer/effective/generation/
   cache result in one critical section.
8. **Postcommit:** run exit/entry and reserved required actions exactly once,
   rebuild work/capability masks, publish required work, and start optional
   presentation using canonical-visible fallback on optional visual failure.
9. **Finish:** record reason/winner/hash and release only transition-owned
   reservations. A committed `BattleTeardownPlan` remains resident-owned until
   boundary-specific readiness, independently resident-observed required returns and
   `RETURN_ACKED` (or proved `RETURN_CANCELED`), cleanup, task/resident release,
   unload, and exact-once release.

Every failure return occurs before phase 5 and leaves live logical and
presentation state unchanged. No failure return or rollback exists after phase
5. Postcommit actions read the committed typed result, never old flattened
state fields.

### BUSY, coalescing, and mandatory work

Optional BUSY work uses four per-slot entries. Token identity is
`(slotGeneration,eventType,ownerId,instanceKey,transitionStableId)`; only an
identical identity coalesces. Each event schema defines a total payload merge,
defaulting to the payload with greater nonzero `tokenSequence`.

Every optional, mandatory-expiry, and system-cleanup record stores immutable
typed `(workClassRank,workScopeRank,classPriority,producerStableId,workKind,
typedIdentity)`.
Comparison is lexicographic descending by declared unsigned numeric, stable-ID,
or frozen-enum order; raw C bytes, padding, endianness, and a separately encoded
byte key are forbidden. Frozen ranks are `SYSTEM_CLEANUP=2`,
`MANDATORY_EXPIRY=1`, `OPTIONAL=0`, unrelated to `SYSTEM` lifetime or the
`SYSTEM_SAFETY` channel. Frozen scope ranks are `GLOBAL=2`, `MAP=1`, `SLOT=0`;
expiry and optional records are `SLOT`. Cleanup priority/producer/kind/scope
come from checked kind registration; expiry values come from its recovery
action; optional values are dispatch priority/transition ID/event type. Typed
identities are a scope-discriminated union:

- expiry `(runtimeEpoch,slotIndex,slotGeneration,ownerId,instanceKey,
  entryGeneration,timerGeneration,recoveryTransitionStableId)`;
- global cleanup `BATTLE_TEARDOWN_PLAN` `(runtimeEpoch,mapGeneration,
  cleanupKind,obligationGeneration,planEpoch,planGeneration,
  pendingBattleGeneration,scriptTaskGeneration,taskManagerGeneration)`;
- map cleanup `RETAINED_MAP_FALLBACK` `(runtimeEpoch,mapGeneration,cleanupKind,
  obligationGeneration,retentionPlanEpoch,retentionPlanGeneration,
  claimSequence)`, with no invented slot index or slot generation;
- slot cleanup `DESTRUCTIVE_SLOT_D01C` `(runtimeEpoch,mapGeneration,slotIndex,
  slotGeneration,cleanupKind,obligationGeneration,destructiveGeneration,
  managerGeneration,objectGeneration)`;
- slot cleanup `MANUAL_PRESENTATION_OBJECT_LOSS` `(runtimeEpoch,mapGeneration,
  slotIndex,slotGeneration,cleanupKind,obligationGeneration,
  presentationGeneration,ownerId,instanceKey,entryGeneration,timerGeneration,
  expectedManagerGeneration,expectedObjectGeneration)`; and
- optional `(slotIndex,slotGeneration,eventType,ownerId,instanceKey,
  transitionStableId,tokenSequence)`.

Scope compares before cleanup priority/kind, kind compares before its remaining
identity fields, and no scope or kind invents zero-valued fields that it does
not own.

Scalar domains are frozen: rank/scope rank/slot index `u8`; priority, producer, work kind,
stable IDs, owners, instance keys, and event enums `u16`; every epoch,
generation, and sequence `u32`. Out-of-range values reject. The closed cleanup
registry is `BATTLE_TEARDOWN_PLAN(GLOBAL,kind 1,priority 0x0400,producer 1)`,
`DESTRUCTIVE_SLOT_D01C(SLOT,2,0x0300,2)`,
`RETAINED_MAP_FALLBACK(MAP,3,0x0200,3)`, and
`MANUAL_PRESENTATION_OBJECT_LOSS(SLOT,4,0x0100,4)`. Their complete identities
are exactly those above. Expiry uses work kind `1`/recovery transition as
producer; optional uses event type/transition ID. Unregistered cleanup cannot
publish.

System-cleanup staleness is dispatched by registered kind, never by a generic
drop:

| Cleanup kind | Stale/mismatch terminal behavior |
| --- | --- |
| `BATTLE_TEARDOWN_PLAN` | `TAKEOVER_AND_COMPLETE`: stale executor/task/environment or map generation immediately routes the obligation to resident mandatory cleanup but replaces executor authority only after actual unwind/exact boundary ACK or proved quiescent cancellation. Boundary tickets remain authoritative and no stale pointer is accessed; the plan/lease persists through cleanup, task release, unload, and coordinator `UNLOADED→RELEASED`. Released tombstones consume diagnostically; different plans are untouched. |
| `RETAINED_MAP_FALLBACK` | `CLAIM_FALLBACK_AND_RELEASE`: pre-claim stale/wrong invocation is a no-op. Mismatch after exact claim runs plan-scoped D01c, releases the ledger once, marks consumed, and never touches a newer plan. |
| `DESTRUCTIVE_SLOT_D01C` | `CONSUME_IF_ALREADY_INVALIDATED_ELSE_DEFER`: an already invalidated/reused old slot consumes without replacement access; an exact current quarantined slot retains mandatory cleanup until physical/sidecar completion. Stale manager/object suppresses pointer access only. |
| `MANUAL_PRESENTATION_OBJECT_LOSS` | `LOGICAL_CLEANUP_OR_DEAD_SLOT_CONSUME`: current logical ownership terminalizes objectlessly and retains quarantine; stale manager/object permits no pointer/timer/pose write. D01c, manager replacement, or dead/reused slot consumes the exact obligation without expiry or replacement access. |

Equal complete typed keys mean exact duplicate mandatory publication and occupy
one idempotent record without merging; distinct work sharing a key is invalid.
Optional semantic identity excludes `tokenSequence`: coalescing applies the
declared payload merge and atomically replaces the old optional record with a
new immutable typed key containing the selected sequence. Queue pressure may
reject/replace only optional work by this key; no mandatory record is evicted.

A candidate timer reaching zero first authenticates handle tuple
`(runtimeEpoch,slotGeneration,ownerId,instanceKey,entryGeneration,
timerGeneration)`, then creates a non-droppable `EXPIRY_PENDING` record whose
deduplication/order identity is the complete typed WorkOrderKey above, including
slot index and recovery transition. It remains at zero and pending
across `BUSY` until its required removal commits; if its complete handle later
becomes stale it consumes diagnostically without touching a replacement.
System cleanup remains until its registered terminal policy completes. System cleanup sorts before expiry, and expiry before optional,
solely through `workClassRank`. One resident scheduler spans all overworld slots
and map/system work; its globally greatest typed key is head-of-line. If it
returns `BUSY`, it stays pending and no lower key from any slot runs that pass. Compatible
expiries may share one atomic batch only in descending typed-key order; batching
cannot change the leader or remaining-work order.

### Generation wrap, invalidation, and data activation

Every nonzero generation must invalidate all dependent state before restarting
at `1`:

- entry/timer wrap advances a handle epoch or destructively invalidates the
  slot; surviving entries/timers receive fresh identities and authenticated
  mandatory expiry is rekeyed without losing remaining/zero-pending state,
  while all external old handles become stale;
- layer/effective/static-context/data wrap clears every keyed cache, primitive,
  capability mask, provenance record, and copied-value lease;
- presentation/action/command/token-sequence wrap cancels matching actions,
  BUSY work, reservations, action timers, and completion callbacks;
- before `commandSerial` restarts at `1`, `commandGeneration` advances under
  that rule and every outstanding completion/callback/policy lease from the old
  generation is canceled or consumed; a reused serial alone never authenticates;
- chain-generation wrap first cancels the per-slot active chain owner, then
  clears every captured command/continuation/completion, direction, step,
  remaining/pause counter, and previous-tile lease before restart, or
  destructively invalidates the slot when any dependent cannot be enumerated;
  an old chain artifact is never rekeyed;
- stamina-policy-generation wrap invalidates every captured command policy and
  cancels any not-yet-charged completion;
- aggro-bridge publication-sequence wrap clears both publication and consumer
  claim before restart, so an old bounce request cannot coalesce with a new
  one; the separate slot-generation mirror follows slot-generation cleanup;
- aggro-bridge retry-generation wrap promotes/drains its exact retry or
  destructively invalidates the source owner; old retry identities never rekey;
- pickup/throw relation-generation wrap clears both participants' relation,
  reservations, and presentations; object/manager/resource-authentication wrap
  cancels pointer-bearing movement, shake, phantom, canopy, and presentation
  tokens, but dispatches system cleanup through its registered stale policy;
- encounter/map wrap cancels queued/deferred battle, capture/projectile,
  affected per-slot bounce-carrier cells, and ordinary object authentication;
  retained-map and system-cleanup work must finish its registered terminal
  policy before wrap. In particular, map change transfers a battle teardown
  executor to resident cleanup and never drops the plan/lease;
- retention-plan-generation wrap atomically claims each unconsumed
  `PREPARED`/`FALLBACK` carrier, quarantines and runs D01c where required,
  releases every fixed-ledger cell exactly once, completes/ACKs the exact mode/
  claim sequence, advances retention epoch, and only then restarts plan
  generation and claim sequence at `1`; old claims/callbacks are stale, and wrap
  is forbidden while any reservation remains owned;
- battle-teardown plan wrap transfers a lost consumer to mandatory cleanup,
  waits for actual resident-observed return or proves quiescent cancellation,
  then records cleanup/task-release/unload milestones, releases the exact lease
  once, and reaches `RELEASED` before epoch/generation reuse;
- slot-generation wrap advances the runtime handle epoch and clears all
  slot-owned handles/timers/actions/commands/queues before reuse; and
- runtime-epoch wrap destructively clears all slots and request state.

The invalidation and new value commit atomically. Behavior data may be
validated/staged while play is live, but installation returns `DATA_BUSY` while
any slot is live or pending/queued/deferred battle, capture, BUSY, presentation,
cleanup, or handle work exists. Activation occurs only at a zero-live-work cold
boundary, then atomically advances data generation and invalidates all static/
effective caches.

## Persistence and cleanup contract

| Event | Base/static state | Runtime behavior layers | Presentation/task handles |
| --- | --- | --- | --- |
| Ordinary apply/remove | Preserved | Recompose all remaining layers | Reconcile only incompatible owners |
| Alert/manual presentation | Preserved | Pending/committed action; unrelated layers preserved. Timers suspend until gate release except imported tired-origin manual hop/look, which overwrites exact tired time and expires it at zero. Hop/look object loss uses intentional manager/object-authenticated safety cleanup; look additionally repairs its internal early return. Destructive invalidation uses D01c instead | New generation-safe token; removed at finish/cancel/objectless maintenance |
| Ordinary-tired completion | Preserved | One handle-targeted transaction removes tired plus the controller's generated awareness/aggro/help-call calm-reset set; unrelated entries remain | Remove tired timer/visual; active crash shake continues until its independent timer restores base position |
| Battle-fled completion | Preserved | Authored `REMOVE_SELF` removes only the exact battle-fled handle and runs tired exit counters/cooldown | Remove its timer/visual |
| Forced-sleep completion | Preserved | Remove only the exact forced-sleep handle; reveal and recompose remaining candidates | Remove its timer/visual |
| Battle start | Context identity preserved | Across all slots remove `CLEAR`, suspend `PRESERVE_LOGICAL`, discard old `SYSTEM` and allow registered owners to re-evaluate after return; aggro bit remains dormant metadata | Clear all movement, emote, phantom instability, throw, queued/settle handles |
| Battle reservation failure | Unchanged | No stack delta committed; every layer/timer/counter/generation/cache remains unchanged | Every command/presentation and pending/queued identity remains unchanged |
| Retained battle return | Preserved | Resume `PRESERVE_LOGICAL`; migrated `CLEAR` entries stay removed, so ordinary behavior is calm | Build fresh presentation/work masks |
| Fled battle return | Preserved if encounter retained | Resume allowed entries, then apply the battle-fled state-candidate definition under owner `battle-fled` | Start fresh per-entry tired presentation/timer |
| Capture preparation | Target base/static and identity preserved | Clear every target runtime layer; cancel/invalidate all target candidate timers; unrelated slot layers/timers unchanged | Clear every target-owned movement/presentation and every relation involving target |
| Capture breakout/finalization failure | Same encounter and slot generation preserved | Remain base/calm + static; never restore removed layers/timers | Restore visible target with impact cooldown |
| Caught/defeated/distance despawn | Removed | Clear all; increment slot generation | Delete/clear all verified auxiliary ownership |
| Authenticated retained-primary real map change | Re-resolve immutable context/controller/base/static after map ID changes | Remove `CLEAR`; retain only compatible `PRESERVE_LOGICAL`; registered owners may freshly emit `SYSTEM`; pickup/throw clears | Discard/canonicalize all context-bound commands/effects; `EMOTING→TIRED` reproduces zero-timer quirk |
| Same-map object-manager replacement | Preserve encounter identity; rebind base/static | Clear ordinary runtime layers/timers to calm; re-emit authenticated `SYSTEM` only | Discard all old manager/object/task ownership before rebind |
| Discard, invalid/disabled destination, or destructive context loss | Removed by D01c | Clear all and invalidate slot handles | Discard all |
| Cold-overlay destructive discard | Immediately quarantined; logical D01c eventual | No apply/query/timer/reuse while pending; first overlay-149 callback clears all before refill | Authenticated retained objects deleted immediately; fixed ABI unchanged |
| Follower recall/reselection | Removed for follower slot | Clear follower and all runtime layers | Clear release/projectile/object state as owned by existing flow |
| Slot reuse | Install new base with new encounter generation | Empty before install | No prior pointer/token may remain usable |

## Migration verification cases

Each case is binary. “Pass” includes the named state/definition/owner, entry and
slot generations, per-entry timers, object flags, movement/presentation
ownership, auxiliary pointers, queued/pending battle identity, cache generation,
and diagnostics. An unasserted or uninspectable field is a failure, not a
provisional pass.

### Core stacking and state cases

- **V01 — Calm init:** Pass iff D01d leaves zero runtime entries, selects the
  migrated controller base, and every effective field/primitive equals the old
  chill oracle for the same immutable context.
- **V02 — Immediate awareness:** Pass iff no-visual alert inserts exactly one
  configured state-candidate definition at `(awareness,0)`, runs active entry
  once, sets active-step count and cooldown to the old values, and produces no
  presentation token.
- **V03 — Alert presentations:** Pass iff both zero-jump and jumping alert modes
  gate ordinary movement; all gameplay candidate and non-presentation action
  timers remain unchanged while only the presentation action timer advances;
  an unrelated modifier applied and removed mid-emote is not lost; completion
  inserts awareness exactly once; cancellation inserts it zero times and
  finishes partner restore exactly once.
- **V04 — Manual presentation parity and object-loss safety:** For calm/active origins, pass iff manual
  hop and look-around leave runtime entries, entry generations, effective state,
  and per-entry timers byte-for-byte unchanged after completion. For both tired-
  origin hop and look, separately force natural completion and mid-action cancel.
  Exercise hop null/mismatched object as an intentional safety correction whose
  timer/end-state result remains source-equivalent. Exercise look null/mismatched
  object at first, middle, and return steps as the same safety correction plus
  the internal early-return-defect repair. Pass iff each terminal path
  authenticates the captured presentation and exact tired timer, sets only it
  to zero, records one non-droppable expiry, consumes the token, and runs that
  candidate's recovery to calm once while preserving unrelated layers/timers.
  An authenticated object restores once. Live logical identity with null/stale
  object performs no pointer write, records exact manager/object-scoped
  `MANUAL_PRESENTATION_OBJECT_LOSS`, clears logical ownership through objectless
  maintenance, and remains quarantined until authenticated rebind canonicalizes
  pose. A replacement object must remain byte-identical. For the stale-manager
  collision fixture, start under manager A and publish cleanup with
  `(expectedManagerGeneration=A,expectedObjectGeneration=X)`, then replace the
  same-map manager with B while reusing object generation X and every other
  comparable identity. Replacement must advance nonzero `managerGeneration`
  before publishing B and tombstone A's token/obligation. Delayed A work performs
  no timer, pointer, pose, quarantine, or cleanup write against B; a B obligation
  differing only by expected manager generation neither coalesces with nor can
  be consumed by A and remains byte-identical until its own cleanup. Separately destroy/
  reuse the slot before terminal delivery; D01c must consume the token/cleanup
  with no expiry or mutation against the new identity.
  With stale captured `timerGeneration`, pass iff no replacement timer is
  zeroed/expired. Restoring the old tired duration fails parity.
- **V05 — Middle removal:** With awareness + weather modifier + stamina-tired,
  pass iff removing weather by handle leaves tired the winner, leaves both state
  entries and their timers unchanged, and field provenance loses only weather.
- **V06 — Same definition, different owners:** Pass iff two permitted instances
  of one modifier definition both contribute, and removing one exact handle
  leaves the other entry/generation/contribution unchanged.
- **V07 — Deterministic tie:** Pass iff every permutation of apply order yields
  the same precedence order, effective hash, values, and provenance.
- **V08 — Capacity:** At eight runtime entries, pass iff a ninth apply returns
  `CAPACITY_EXCEEDED`, changes no byte of live entries/effective cache, and
  increments exactly one overflow diagnostic; replace of an existing owner/key
  still succeeds atomically.
- **V09 — Stale handle:** Pass iff one live→empty D01c advances slot generation
  exactly once, D01d never advances it and installs into that prepared empty
  generation, and public single `Remove(oldHandle)` returns `STALE_NOOP`
  without changing the new encounter. A stale `REMOVE_REQUIRED` inside a
  multi-operation delta must abort the complete delta.
- **V10 — Apply API typing and generated-wrapper lifecycle:** Pass iff public
  runtime apply accepts only a valid state-candidate/modifier definition ID and
  rejects a raw state-profile ID. For semantic and exact-fallback wrappers of
  each `FLED`, `RAM_CRASH`, and `THROW_RECOVERY` family, authorized initial Apply
  must copy definition→runtime the exact canonical origin pair and fixed required
  owner (`battle-fled`, `ram-crash`, `throw-recovery`) before commit. Generated
  stamina copies absent origin plus required `stamina` and performs zero
  translation lookup. Every generated tired fixture requires both multiplicity
  flags `FALSE` and `instanceKey=0`; set either flag or use a nonzero key and
  require atomic `INVALID_GENERATED_WRAPPER`. An idempotent authorized Apply reauthenticates definition,
  runtime metadata, and owner before returning the same handle; entry/timer
  generation, remaining time, and every metadata byte remain unchanged.
  Authorized same-definition Replace recopies the same metadata, issues fresh
  entry/timer generations, and restarts the authored timer exactly once.
  Wrong-owner Apply/Replace returns `OWNER_NOT_AUTHORIZED`; public
  imperative↔ordinary, stamina-generated↔ordinary, and different origin/owner-
  family Replace returns `GENERATED_WRAPPER_FAMILY_MISMATCH`. Reject a present
  origin on stamina, an absent/incorrect origin on an imperative wrapper,
  wrong-origin/required-owner mapping, noncanonical absent tag with nonzero
  value, definition/runtime-copy disagreement, and corruption of either runtime
  tag pair as `INVALID_GENERATED_WRAPPER`. Every rejected fixture—including an
  otherwise idempotent request—must leave the complete stack, timers, entry/
  timer/layer/effective generations, cache/provenance, and diagnostics other than
  the single named error byte-for-byte unchanged.

### Tired, sleep, and recovery

- **V11 — Stamina threshold:** Pass iff each compatible completed active
  non-RAM command authenticates the complete command-origin tuple, charges its
  captured stamina-policy generation at most once, the same ordinal completion
  as old code inserts exactly one stamina-tired entry through the authored
  semantic-`TIRED` origin wrapper, never the fallback, and stale or duplicate completion
  paths remain diagnostic no-ops.
- **V12 — Canceled command:** Pass iff a state transition that cancels an
  incompatible in-flight active command charges zero stamina and leaves no
  completion callback capable of charging later.
- **V13 — Staged hop exhaustion:** Pass iff finish-with-tired produces the old
  `stamina-1` preload and the single normal completion inserts one authored semantic
  tired entry; an unbound authored node disables exhaustion instead of falling back.
- **V14 — Active RAM wall crash:** Pass iff route preflight selects its ordinary
  semantic wrapper when authored tired is bound and its generated exact fallback
  wrapper otherwise, RAM direction/step-counter/speed/chain clear,
  crash shake starts from saved base position, one `ram-crash` state candidate
  wins, movement cooldown is not shorter than shake, and final shake restores
  the exact base coordinates.
- **V15 — Non-active RAM crash:** Pass iff chill or already-tired crash resets
  RAM direction/step-counter/speed/chain, starts shake/cooldown, inserts no new
  tired entry, and does not clear the independent shake timer/base during tired
  cooldown; normal/forced completion restores exact authenticated base X/Z.
- **V16 — RAM battle impact:** Pass iff battle impact clears RAM state and starts
  or queues battle with zero `ram-crash` entries inserted.
- **V17 — Tired variants:** For moving, idle, no-visual, tired-emote, and asleep
  fixtures, pass iff entry timer, movement cancel/continue, bubble/cry, cooldown,
  and frame-task mask equal the old oracle. For every controller with no authored
  tired binding, ordinary exhaustion remains disabled while FLED, active-RAM
  wall crash, and successful throw recovery select the generated fallback and
  match the source repaired tired-emote/rest-time behavior. With authored tired
  bound, each of those three imperative routes selects authored tired instead;
  both contexts must show route branch plus selected semantic/exact wrapper provenance.
- **V18 — Legacy stamina recovery:** Pass iff stamina-tired reaches zero only
  while effective, and one `LEGACY_RETURN_CALM` transaction removes its exact
  handle plus the generated awareness/aggro/help-call calm-reset set, selects
  controller calm, resets old counters/cooldowns, and preserves every unrelated
  modifier. Revealing an active-intent candidate fails phase-0 parity.
- **V19 — Hidden-timer sequence:** Using the possession-extended forced-sleep
  sequence above, pass iff tired remains at four, sleep continues beneath
  `CARRIED`, hidden sleep expiry removes only itself while `CARRIED` remains
  effective, pickup removal reveals tired still at four, and four effective
  tired ticks remove tired plus generated awareness/aggro entries to calm.
- **V20 — Battle-fled recovery:** Pass iff FLED preflight selects its generated
  semantic or exact fallback wrapper by the explicit two-wrapper rule, its timer pauses while hidden, and
  its authored `REMOVE_SELF` recovery contains one required exact-handle
  removal plus tired exit counters/cooldown, contains no awareness/aggro/help-
  call operations, and removes only `battle-fled`.
- **V21 — Aggro over tired:** Use the bounded per-slot carrier. Publish slot A,
  force no-tile `FALSE`, then publish distinct slot B before consumption. Pass
  iff both independent cells and both durable metadata effects remain pending,
  neither hit clobbers the other, and producer active steps stay unchanged.
  Exact duplicate key `(slot,expectedSlotGeneration,
  expectedEncounterGeneration,expectedObjectGeneration)` excludes sequence and
  coalesces byte-identically both while `PENDING` and while `CLAIMED`. Claim A,
  force orchestrator `BUSY`, and pass iff it returns to identical `PENDING`
  without stack/timer/counter mutation; retry is mandatory. While A is claimed,
  a different same-slot key returns internal `BRIDGE_BUSY`/ABI `FALSE`, performs
  no primary/aggro-metadata write or tile selection, cannot steal the claim,
  and creates/coalesces the exact bounded retry owner. Attempt source movement,
  cancellation, and termination; all remain blocked until promotion/consume or
  authenticated destructive invalidation, so the hit cannot disappear. Payload,
  both source metadata effects, and `PENDING` precede tile selection on every
  accepted success/no-tile path. On post-claim generation mismatch, only exact
  cell/claim: the unkeyed legacy pending mirror, authoritative slot/object
  mirrors, encounter generation, publication-sequence carrier, and both durable
  aggro flags, and retry owner remain byte-identical. Then current-key publication succeeds.
  Authenticated consume commits exact tired expiry, one aggro apply, and active-
  step reset atomically before `CLAIMED→EMPTY`.

### Special families and movement resources

- **V22 — Phantom normalization:** Pass iff chill alert, active entry, visible
  cooldown, teleport flicker, tired entry, battle stabilization, and reset keep
  the same authenticated primary object; normalize its tile/pass-through/
  visibility; delete all owned auxiliary flicker objects when required; and
  leave no stale pointer or timer.
- **V23 — Canopy interruption:** Pass iff transitions during partner prep and
  staged hop finish the paired restore once, clear owned commands/bits/tasks,
  restore render priority/proxy ownership, and set or clear tree-top settled
  coordinates to the observed landing result.
- **V24 — RAM/chain compatibility:** Pass iff changing away from RAM or a
  chainable locomotion clears direction/speed/step/remaining/pause state, while
  a modifier-only effective-generation change that preserves those capabilities
  leaves the same chain generation/counters only through atomic prefix rebind:
  advance step serial, drain every old artifact, and publish fresh universal-
  prefix artifacts. D01d initializes inactive generation `1`;
  start, replacement, and cancel follow their exact advancement counts; every
  artifact authenticates the universal command tuple plus chain suffix before
  touching counters, leases, presentation, or stamina. Exercise base and layer
  winner encodings, every artifact kind, and change stateProfileId,
  effectiveGeneration, objectGeneration, staminaPolicyId, and
  staminaPolicyGeneration one at a time; each stale artifact is a no-op. In
  particular, a stale stamina-policy generation cannot schedule, charge, reset,
  or release. Step-serial wrap advances chain generation once and drains all
  old artifacts before reusing `1`.
- **V25 — Spawn-run:** Pass iff startup continues to use the migrated spawn
  policy, normal AI remains gated until landing, and active/help-call state at
  landing selects the same post-start cooldown as old source.
- **V26 — Help child:** Pass iff immediate and startup-deferred children each
  receive exactly one `(help-call,0)` state-candidate entry and run active entry
  once after object stability.

### Pickup/throw

- **V27 — Reservation:** Pass iff reservation changes only relation masks/timer,
  inserts no target behavior entry, and prevents the carrier's ordinary active
  decision until completion/cancel.
- **V28 — Pickup entry:** Pass iff one possession state-candidate entry is
  inserted under the carrier-specific owner, base/controller/static identity is
  unchanged, target movement/chain is cleared, pass-through/visibility are
  normalized, and all synchronized coordinates equal the carrier.
- **V29 — Middle pickup removal:** Pass iff throw landing removes only the exact
  pickup handle, restores shadow/pass-through/landing, and leaves every other
  target entry, timer, and generation unchanged.
- **V30 — Player-tile landing:** Pass iff landing on the player tile invokes
  `TryStartBattleForSlotOrQueue` with `originKind=THROW_LANDING`, preserves that
  provenance through queue/reservation diagnostics, and results in either a
  valid pending battle or valid queued slot—never a silent no-op when common
  gates permit entry. Separate calm and non-`CONTACT` fixtures must pass,
  proving landing bypasses ACTIVE/contact-scan predicates.
- **V31 — Failed throw:** Pass iff target relation/presentation clear, carrier
  recovery cooldown matches old source, and no throw-recovery/tired entry is
  inserted.
- **V32 — Successful throw:** Pass iff target pickup relation clears and exactly
  one carrier `throw-recovery` state candidate is inserted after explicit
  selection between its ordinary semantic/exact fallback wrappers as an independent transaction/handle.
- **V33 — Participant destruction:** Pass iff destroying either participant
  clears every relation containing its slot, clears possession presentation,
  advances only destroyed slot generations, and no old handle affects reuse.

### Battle and lifecycle

- **V34 — Contact predicates:** Pass iff battle grace blocks the whole scan and
  decrements only when requested, pending battle blocks, `justSpawned` clears
  and suppresses exactly one whole scan, only active/contact/current/non-
  follower touching slots reach immediate-or-queue, every touch/immediate gate
  independently blocks, and the first touching `CONTACT` slot stops the scan
  even when both immediate and queue reject it. These predicates apply only to
  `originKind=CONTACT`, never `THROW_LANDING`.
- **V35 — Queue predicates:** Pass iff queue accepts a valid but temporarily
  unstable slot, settle retry never starts before `IsSlotStableForBattle`, and
  context/object generation mismatch cancels the queue.
- **V36 — Scripted talk predicates:** Pass iff explicit talked-object/last-talked
  lookup bypasses finder-level excluded/spawn-run/phantom-hidden filtering just
  as source, later prime still rejects follower/throw/player instability/current
  identity failures, and accepted unstable presentation is cleared by all-slot
  reset. Facing fallback must reject excluded/spawn-run/hidden candidates. The
  route must authenticate its already-running script/task-manager context and
  create/reserve/publish zero new script tasks, but must acquire the common
  teardown-readiness reservation. Force that reservation to fail after script
  authentication; pass iff no pending battle is consumed, no all-slot cleanup
  starts, no overlay/task state changes, and no second script task appears.
- **V36a — Physical A-button route:** Pass iff selector/release gates and the
  physical rising-edge latch match source; `FindBattleTalkSlot(...,NULL)` uses
  facing fallback gates; a different stock facing object rejects/latches; the
  selected slot uses immediate-or-queue rather than talk-prime; release clears
  the latch; finder or start failure remains retryable while held.
- **V36b — Active RAM-impact route:** Pass iff only an effective active state
  with `RAM_CRASH` battle trigger and player/authenticated-active-follower impact
  can enter; direct frame-task prime observes pending/player-ball/current-object
  gates and clears failed publication; the ordinary path uses immediate-or-
  queue; success carries `RAM_IMPACT`, runs the shared all-slot transaction,
  clears direction/step counter/speed/chain, owns crash feedback, and inserts no
  `ram-crash` tired candidate.
- **V37 — All-slot battle delta:** Pass iff every active slot loses `CLEAR`,
  every allowed `PRESERVE_LOGICAL` entry is suspended and absent from
  composition, all presentation/task ownership is zero, all visible slots are
  calm, and aggro metadata remains dormant/non-effective.
- **V38 — Reservation failure:** On each route that creates or defers a script
  task (not `SCRIPT_TALK`), force script reservation failure, then force teardown
  reservation failure after the script-handoff reservation succeeds but before
  publication. Fault field-service
  shutdown, helper validation, behavior readiness, both cleanup lifecycle
  phases, conflict checks, and physical-unload readiness; every failure must be
  observed pre-PONR. Pass iff every acquired lease releases exactly once, no
  task/publication, battle delta, or stabilization runs, and every pending/queued field, layer,
  timer, counter, generation, cache, command, and presentation byte equals its
  pre-call value. Statically prove every post-reservation operation/publication
  is infallible before the point of no return; after a valid reservation, late
  injected failure must be unreachable/assert rather than rollback. For
  every closed origin/subroute row, assert the exact mask/order, distinct
  boundary publisher identities, distinct enclosing resident caller identities,
  and nonzero unequal CB/SC tickets frozen before publication. Separately delay
  overlay-callback return, script-command return, and physical unload. Boundary
  publication may reach only its own `READY` cell/`RETURN_PENDING`; inject the
  teardown executor writing either cell, the callback publisher/caller using the
  SC ticket, the script publisher/dispatcher using the CB ticket, swapped ticket
  sequences with otherwise equal generations, and direct writes to returned
  bits/`RETURN_ACKED`. Every spoof must be a complete no-op with plan, masks,
  executor, cleanup, lease, and both cells byte-identical. While either required
  call has not actually unwound, resident code must not ACK it or advance
  cleanup/task release/unload. After each real return, only its exact enclosing
  caller may ACK the matching boundary ticket; the second required ACK alone
  permits `RETURN_ACKED`. For future-script rows, reject script entry/readiness
  before CB ACK. For nested `SCRIPT_TALK`, require inner callback CB ACK before
  the outer already-running command may publish SC ready; do not treat nesting
  as one shared return context. Queue-only publication creates no plan, while
  its accepted retry freezes the table row. Transition finish
  must leave the exact resident `BattleTeardownPlan` as lease owner and overlays
  pinned until return proof → cleanup → task/resident release → unload → release.
  The teardown executor owns only its executor claim and may never release the
  lease or publish/ACK a boundary. Cancel the executor and require takeover to
  replace only its claim while boundary cells remain unchanged. Separately lose
  each boundary publisher: only after exact resident quiescence proof may that
  cell become `CANCELED` and contribute to aggregate `RETURN_CANCELED`, never a
  fabricated ACK. Reject one stale executor tuple before claim as a diagnostic
  no-op; separately fail the exact claimed executor's own completion and require
  takeover of only that plan without changing boundary tickets or lease ownership.
  While teardown is delayed, advance map/environment
  generation and invalidate old task/object pointers; `BATTLE_TEARDOWN_PLAN`
  must transfer execution to resident mandatory cleanup, use no stale pointer,
  complete teardown, and release once rather than stale-drop. Only the coordinator's authenticated
  `UNLOADED→RELEASED` transition releases once. Force attempted release at every
  earlier milestone and require a no-op/assert with the lease retained;
  replay claim/ACK and stale plan-A ACK while plan B is live must not release or
  mutate B. No pre-PONR failure publishes a plan.
- **V39 — Battle dispositions:** Pass iff `RETAIN` resumes only explicit
  preserved entries and remains otherwise calm; `FLED` also adds exactly one
  `battle-fled` entry and grace; `CAUGHT`/`DEFEATED` run D01c and invalidate all
  target handles.
- **V40 — Capture cleanup and breakout:** For target layers/timers plus throw,
  hop, RAM shake, phantom, and canopy fixtures, pass iff target-local prep
  clears every target runtime layer, invalidates every target timer, restores/
  clears every named movement/presentation/relation owner, and leaves unrelated
  slot layers/timers unchanged. Breakout/finalization failure must retain the
  same encounter/slot generation at base/calm + static with impact cooldown and
  must not reconstruct removed layers/timers; caught finalization must D01c.
- **V41 — Retained-primary map change:** For calm, alert, active, moving tired,
  idle tired, pickup, RAM shake, phantom flicker, and canopy prep fixtures, pass
  iff static context/controller/base are re-resolved, `CLEAR` entries including
  pickup are gone, only compatible `PRESERVE_LOGICAL` entries remain, all old
  context-bound handles/pointers are zero, effective hashes derive from the
  destination behavior context, captured spawn/population IDs/group/limit stay
  unchanged, and any destination would-select values remain diagnostic only.
  For stamina plus imperative `FLED`, `RAM_CRASH`, and `THROW_RECOVERY`, separately
  retain from controller A to compatible controller B with authored `TIRED`.
  Before rebind assert that each imperative wrapper/runtime entry stores exactly
  its present closed `tiredOriginKind` and mapped required owner, and that
  stamina stores absent origin plus required `stamina` and performs zero
  translation-table lookups. Pass iff stamina's semantic wrapper re-resolves B
  directly and each imperative origin's
  internal table selects B's ordinary semantic wrapper while owner/instance/
  entry/timer generations, remaining/zero-pending time, recovery policy, and
  stored origin/required-owner metadata survive unchanged. For each imperative origin,
  also cross authored↔absent contexts and pass iff the internal retained-context
  table translates to B's exact `CUSTOM/FALLBACK_TIRED` wrapper only when B lacks authored
  tired; stamina instead becomes `CONTEXT_NO_LONGER_APPLICABLE` and never falls
  back. Wrong/missing discriminator, required-owner mismatch, or a target wrapper
  from another origin must abort before mutation.
- **V41a — Same-map manager replacement:** Pass iff encounter/slot identity
  survives but all ordinary layers/timers and old object/task/presentation
  handles clear, every old-manager manual-loss obligation is consumed/tombstoned,
  retained slots return base/calm, nonzero `managerGeneration` advances before
  the replacement manager is published, the replacement manager is
  authenticated, and only authenticated `SYSTEM` state is freshly emitted.
- **V41b — Retained-map two-phase failures:** Force `PRESERVE` planning/
  reservation failure before resident writes, then separately force
  `CANONICALIZE` authentication/consume failure after infallible resident writes.
  Pass iff the first publishes `FALLBACK` before returning, the second consumes
  the exact generation into D01c, both fixtures admit no partial retained stack
  or query/spawn before cleanup, replay is a diagnostic no-op, and a missing
  second callback is forced through D01c by the next maintenance entry. Cover
  successful `PREPARED`, partial first-half failure, mismatch with held
  reservations, replay, and missing callback; reservation acquire/release counts
  return to baseline, each acquired entry releases exactly once, and replay
  releases zero additional resources. Both `PREPARED` and `FALLBACK` must
  complete the exact `(epoch,generation,mode,claimSequence)` caller claim.
  Publish claim/plan A, reject overlapping `PRESERVE` B, then after A is consumed
  create plan B and deliver stale/replayed A claims; B remains byte-identical and
  cannot be consumed/released or sent through D01c. Explicitly reject stale A
  before `PUBLISHED→CLAIMED` while B is live: this is a complete diagnostic no-op
  with no quarantine, D01c, ledger release, or plan mutation. Separately create
  current plan C, allow its exact invocation to transition
  `PUBLISHED→CLAIMED`, then return while still `CLAIMED` and separately publish
  malformed/wrong completion. Each post-claim failure permits no middle write,
  quarantines and runs D01c/releases only C, and leaves every unrelated/newer
  plan byte-identical. An unrelated stale completion tombstone is a no-op. Missing-callback
  maintenance claims only the recorded tuple. Exercise ledger counts `0`, `46`,
  `47`, and a fault-injected 48th distinct key; overflow publishes
  `RETENTION_LEDGER_CAPACITY_EXCEEDED` before any acquire; middle writes occur
  only after the exact fallback claim completes. Exact duplicate
  keys coalesce, distinct same-kind keys do not, failure after the last legal
  acquire transfers every held cell to fallback, and all terminal/replay/wrap
  cases end with zero held cells and baseline resources.
  For both `PREPARED` and `FALLBACK`, make the enclosing availability `BOOL`
  return true and require the caller to branch only on its re-read, exact
  resident `COMPLETED` claim/result marker. A `void` return without completion
  permits no middle write; its cleanup result depends strictly on whether the
  exact invocation first acquired `CLAIMED` as frozen above.
- **V42 — EMOTING-to-TIRED map quirk:** Pass iff a retained-primary change while
  `EMOTING` with tired end state authenticates the exact presentation token,
  candidate handle, and timer generation in one delta, sets only that timer to
  zero, records mandatory expiry, and reaches calm on the first resumed eligible
  tick. Stale/ambiguous identity must abort before mutation.
- **V43 — Destructive map/context loss:** With overlay 149 loaded, pass iff
  invalid destination, failed primary authentication, discard, and destructive
  mismatch run immediate D01c. With it unavailable, pass iff resident cleanup
  immediately deletes authenticated retained objects/quarantines identities,
  blocks every apply/query/timer/reuse/refill, and the first guaranteed existing
  overlay callback completes D01c before clearing pending cleanup. Both branches
  end with zero layers, handles, presentations, and effective cache, advance
  `slotGeneration` exactly once for the live-to-empty invalidation, and do not
  change the 28-byte ABI.
- **V44 — Follower aggro lifecycle:** Pass iff release retry/bounce keeps the
  release-level aggro metadata, successful consume inserts one aggro definition,
  battle removes that behavior entry but leaves dormant metadata, and recall/
  reselection D01c clears both metadata and handles.

### Static source and ABI gates

- **V45 — Direct state writes:** Pass iff
  `rg -n --pcre2 'movementSpotStates\[[^]]+\][[:space:]]*=(?!=)' src include` returns zero
  gameplay assignments after migration; this regex is only a simple-assignment
  smoke check. The checked-in authoritative invocation is exactly
  `python3 scripts/verify_overworld_wild_state_access.py`; `Makefile`/CI calls
  that no-argument command and the script owns audited roots/flags. The exact
  legacy writer allowlist for `OverworldWildSpawnState.movementSpotStates` is
  empty. If retained, the compatibility field is exactly
  `movementSpotStateCompatibilityMirror` and its sole allowed writer symbol is
  `{OverworldWildStateOrchestrator_PublishCompatibilityMirror}`. There are no
  macro/helper/inline/bulk exceptions. The verifier fails closed on parse/type
  failure, missing audited paths, missing/duplicate allowlisted symbol, address/
  alias escape, compound/inc/dec, cast/macro/helper store, or `memcpy`/`memset`/
  whole-struct mutation; the mirror never selects behavior.
- **V46 — External numeric reads:** Pass iff follower selector/helper and all
  other overlays contain no numeric `movementSpotStates == 1/2/3` behavior
  decisions; they use presentation metadata or a versioned read-only query.
- **V47 — Fixed ABI:** Pass iff link/map assertions keep bounce code/call
  addresses `0x0224F298/0x0224F299` inside `0x300` bytes, aggro code/call
  addresses `0x0225046C/0x0225046D` inside exactly `0x34` bytes, both exact
  ordinary C/AAPCS prototypes/calling conventions, and
  `OverworldWildSpawnsOverlayEntry` exactly 28 bytes at `0x023CD000` with the
  seven unchanged prototypes at offsets `0,4,8,12,16,20,24`. The compact
  dedicated aggro bridge must be a bounded per-slot carrier, keep resident slot/
  object-generation mirrors, captured expected generations, and independent
  publication sequence distinct, include one bounded retry record/source owner
  per slot, and preserve simultaneous different-slot hits
  without a sidecar pointer/handle or entry expansion. Existing projectile
  `impactSlot`/`impactEncounterGeneration` remain untouched; stale consume
  clears only its exact cell/claim, never the unkeyed legacy pending mirror, an
  authoritative generation mirror, durable aggro flag, or retry owner.

### Data, compiler, and editor gates

- **V48 — Special import recipes:** Pass iff picked-up skips every ordinary
  override row and produces only deterministic controller-local `CARRIED`
  assets; follower performs the normal fold then force-applies exactly the
  semantically identified disabled follower row once (zero/multiple is an
  error); forced asleep discovers exactly one semantic row, captures
  `forcedRowOrdinal` (v39 oracle: one-based `10`, zero-based index `9`), forces
  it only at that order, continues through later rows, and creates no caller.
  A synthetic matching row at ordinal `> forcedRowOrdinal` overwrites one
  forced-written ASLEEP-scoped field while preserving ASLEEP kind; pass iff the
  later value and provenance win and every earlier/forced/later row applied once.
  Forced asleep still has exactly one node/bound semantic match per controller/
  context and one non-double-applying representation strategy; authored/fallback
  tired selection remains explicit.
- **V49 — Static fold and selectors:** Pass iff only the closed static-action
  union is accepted, controller assignment and every typed namespace use the
  complete ADR ordering keys, permutation of serialized rows changes nothing,
  each legacy `restTime ADD` clamps to `0..64` before the next operation,
  base-zero and late-`SET(0)` bound non-ASLEEP tired fixtures repair to finite
  `1` after the fold with repair provenance, while asleep-zero remains
  indefinite `255` and non-asleep `255` becomes finite `254`; sentinel
  conversion happens after repair, and `alertTime` affects only a
  newly captured alert-presentation duration. Exact selectors require
  `(controllerStableId,nodeStableId)`; zero semantic matches are
  `NOT_APPLICABLE`/context removal and multiple matches are
  `AMBIGUOUS_SELECTOR` with no mutation. With authored `TIRED` unbound, add
  matching tired-only and shared-movement speed/locomotion writes before and
  after the unbind plus CALM-, ATTENTIVE-, and another-CUSTOM-only controls.
  Pass iff the immutable matcher truth-vector partition selects exactly one
  fallback `BIND_NODE`, its complete profile/provenance equals the ordered
  legacy tired projection except `behaviorKind=TIRED_EMOTE`, its exact wrapper
  alone owns enabled duration `4`, no control write leaks, all three imperative
  origins select it, and ordinary exhaustion remains disabled. The emitted
  atomic matchers must serialize in the existing schema, be disjoint, and cover
  every eligible fixture exactly once. Reject missing/duplicate translation
  table keys, wrong-origin/branch/controller/node targets, dangling wrappers,
  fallback rows without a destination binding, any noncanonical generated
  origin/required-owner pair, wrong fixed mapping, authorization on an ordinary
  definition, and destination translation target whose fixed owner differs.
- **V50 — Editor CRUD and behavior-set assignment:** Pass iff create/update/
  delete and backlink/replace-reference behavior for state profiles,
  controllers, local nodes, transition rows/actions, candidate wrappers,
  modifiers, spawn policies, population policies, controller-hook sets, and
  static rules matches the ADR table in one Global Save transaction. Generated
  origin and required-owner metadata must be visible read-only and
  cannot be created, edited, redirected, replace-referenced, or deleted except
  by complete importer regeneration; ordinary authored/non-generated wrappers
  remain owner-unconstrained.
  Complete
  Behavior Set must create the previewed graph and create exactly one
  assignment only when the author
  supplies match criteria and explicit assignment priority; otherwise it
  remains unassigned.
- **V51 — Duplication graph:** Pass iff shallow and deep controller duplication
  allocate fresh IDs for the exact ADR closure, remap every internal controller,
  node, selector, row/action, wrapper/timer/recovery, owner, and selected-rule
  backlink, retain every portable semantic reference outside the closure, never
  copy static rules implicitly, and expose the complete old-to-new map before
  commit. A portable semantic definition remains shared; a definition with any
  controller-local exact selector/filter/applicability/owner/backlink is cloned
  and remapped, or shallow duplication fails atomically with deep-copy-required.
  Generated fallback wrapper/binding/internal-translation rows regenerate and
  remap with their destination controller, while each imperative wrapper/entry's
  present closed `tiredOriginKind` and fixed required system owner copy
  unchanged with frozen `FALSE/FALSE` multiplicity; stamina duplicates with
  absent origin, required `stamina`, and no
  translation row. Controller-local targets remap, but required system owner IDs
  never do; mismatched regenerated authorization fails atomically. Deep copy remaps the full selected closure.
- **V52 — Data activation and generation wrap:** Pass iff validated behavior
  data cannot replace the installed blob while any live/pending work exists,
  the cold-boundary swap invalidates every static/effective cache, and forced
  wrap of each generation family named in the ADR invalidates or rekeys every
  dependent handle, timer, mandatory expiry, command, bridge request, relation,
  object/resource token, cache, queue, reservation, and diagnostic before a
  nonzero value restarts at `1`. Forced fixtures must wrap `commandSerial` with
  an outstanding completion, advance `commandGeneration`, and cancel the old
  completion/policy lease; and wrap chain generation with pending chain work,
  clearing every command, action, counter, pause, and previous-tile lease before
  reuse; old chain artifacts are never rekeyed. Start chain A with every artifact kind, replace it with B
  (exactly one generation advance), then deliver A's stale artifacts; B's owner/
  counters/pause/lease/command/timer/stamina remain byte-identical. Deliver a
  tuple with only old `staminaPolicyGeneration` and prove zero charge/schedule/
  release; B's authenticated completion consumes once. Also wrap
  `retentionPlanGeneration` with live `PREPARED`, `FALLBACK`, and `CONSUMED`
  carriers: required D01c runs, every reservation releases once, retention epoch
  advances before restart at `1`, and old callbacks cannot consume/release the
  new carrier. Wrap `claimSequence` with a published claim, drain its exact plan,
  then create new generation-1 plan/claim B and replay old claim A in both modes;
  B and its reservation ledger remain byte-identical. Also force
  `BattleTeardownPlan` generation wrap with a live published consumer whose
  return is delayed: wrap may neither replace a still-executing consumer nor
  fabricate return ACK. It waits for actual unwind and resident ACK, or first
  proves the consumer quiescent/canceled and records `RETURN_CANCELED`; only then
  may mandatory cleanup replace its executor claim and complete cleanup,
  task/resident release, and unload while the plan retains lease ownership. The
  coordinator then performs the sole exact
  `UNLOADED→RELEASED` lease release before epoch advance/restart at `1`. An old
  claim/ACK cannot touch the new plan.
- **V53 — BUSY totality and expiry:** In every input permutation publish two
  distinct expiries, simultaneous global `BATTLE_TEARDOWN_PLAN`, map
  `RETAINED_MAP_FALLBACK`, and two slot-scoped cleanup obligations, equal-priority
  optional tokens, an optional semantic duplicate with a newer sequence/payload,
  and one exact duplicate of each mandatory identity across at least two slots.
  Exercise valid u16/enum comparison `255/256`, reject u16/stable-ID value
  `65536`, and compare valid u32 generation values `65535/65536`; include two cleanup
  registry kinds with different priorities/tails and permuted host layouts. Use
  the frozen registry values, including map-scoped fallback's lower priority
  versus slot-scoped D01c, to prove scope dominance. Pass iff
  declared field-by-field typed comparison produces one invariant order with no
  raw-byte/padding/endianness dependence: system cleanup before expiry before
  optional, and within system cleanup `GLOBAL > MAP > SLOT` because scope rank
  precedes priority/kind. The map identity contains no dummy slot fields. Two
  real slot identities order deterministically, while otherwise equal-looking
  tails from different scopes remain distinct and cannot coalesce. Publish two
  manual-loss identities differing only in `expectedManagerGeneration`; they
  remain distinct and order by that field. Exact mandatory duplicates occupy one idempotent record without
  payload merge; optional duplicate uses its declared merge and becomes one
  newly ordered replacement record; distinct work cannot share a typed key.
  Force terminal staleness for every registered cleanup kind and require exact
  policy dispatch: battle teardown routes to resident cleanup, transfers
  execution only after unwind/cancellation proof, and completes;
  retained-map pre-claim stale is no-op while post-claim mismatch runs D01c and
  releases its ledger; D01c consumes an already invalidated slot but defers a
  current quarantine; manual loss objectlessly cleans a current logical tuple or
  dead-slot consumes. For battle teardown, delay each boundary return, then change
  map/environment and stale its task/object generations: the plan and lease must
  remain owned, no stale pointer may be accessed, resident takeover waits for
  actual return or proved cancellation, and the coordinator releases exactly
  once after teardown. Generic stale-drop is a failure.
  Force the globally greatest cleanup, then greatest expiry, to return `BUSY`;
  each stays head-of-line and no lower work on either slot runs. Scope rank,
  then registry priority, fixes the expected cleanup order. Compatible batching preserves descending
  typed order/leader, optional pressure never evicts mandatory work, and zero-
  timer expiry remains non-droppable until commit or proven stale.

## Frozen phase-0 parity decisions

- Ordinary tired uses `LEGACY_RETURN_CALM`: expiry requires its exact handle and
  removes awareness plus `aggro`/`help-call` with `REMOVE_OWNER_IF_PRESENT`
  exactly when the generated controller says either may underlie tired. It does
  not reveal active. Battle and destructive resets also remove those active
  behavior layers.
- Alert presentation stores a pending awareness transition; the active state
  candidate becomes effective only when presentation completes/canonicalizes,
  matching current `EMOTING` timing. The presentation gate suspends migrated
  legacy tired/asleep timers; possession alone does not.
- Imported manual hop/look-around is the narrow exception: from tired it
  overwrites that exact candidate timer with presentation time, completes at
  zero, and drives exact-handle recovery to calm on the next eligible tired
  tick. Null/mismatched-object terminalization for both hop and look is an
  intentional phase-0 safety correction with typed manager/object-authenticated
  cleanup and quarantine. Hop retains the source-observable timer/end-state
  result; look additionally fixes the internal early return by terminalizing
  before every look step. Calm/active origins and newly authored presentation tokens retain the
  ordinary separate-timer preservation rule.
- Ordinary behavior transitions commit only at a stable command boundary. If a
  command is incompatible they return `BUSY`; battle, map, destruction, and
  system-safety paths may cancel it through their explicit cleanup transaction.
- Migrated definitions use the explicit owner-family map above. Other authored
  runtime definitions default to `mapHeaderPolicy=CLEAR`; every phase-0 runtime
  definition uses `battlePolicy=CLEAR`. Persistence exists only when declared
  and compatible.
- Battle reset is all-slot. Aggro behavior clears; the old aggro flag is dormant
  metadata and never reasserts behavior automatically.
- Fled uses owner `battle-fled`, never `stamina`, and its authored recovery is
  `REMOVE_SELF` plus tired exit counters/cooldown—not a calm-reset delta whose
  other owners merely happen to be absent.
- Failed battle reservation performs no mutation. A platform with fallible
  post-reservation publication must reject during preflight; no rollback or
  failure exists after the point of no return. This is an intentional safety
  correction to the source behavior.
- The `EMOTING → TIRED` retained-map zero-timer capture-order quirk is preserved
  with exact candidate/timer identity. Same-map manager replacement separately
  resets ordinary logical movement/layers to calm.
- Retained encounters re-resolve destination behavior context but never adopt
  destination spawn/population policies; would-select values are diagnostics.
- Capture preparation clears every target-local runtime layer/timer. Breakout
  retains that encounter at base/calm and never restores the removed stack.
- Movement completion authenticates the complete command-origin tuple, never a
  profile ID alone.
- Throw landing is a fifth battle origin and preserves `THROW_LANDING`
  provenance; it does not inherit ACTIVE/`CONTACT` predicates from contact scan.
- Definition channel/priority and the stable precedence tie-break are those in
  the architecture ADR; no caller supplies priority and apply time is irrelevant.

## Known source gaps and implementation dependencies

1. **Forced asleep is dormant:** The data record remains, but no live runtime
   caller applies it. It is migration input and a composition fixture, not a
   completed gameplay migration until Sing or another source is restored.
2. **Cross-overlay query migration:** Follower selector code checks tired and
   helper pickup validation checks numeric emote state. Phase-0 needs either the
   compatibility mirror or a separately versioned query without changing the
   28-byte entry.
3. **ABI measurements:** The fixed bounce/aggro linker sections and new bridge
   code must be measured. Failure of V47 blocks rollout; it does not permit an
   ABI semantic change.
4. **Packing and cache placement:** Exact sidecar packing, timer widths, and
   diagnostic/provenance placement remain measurements. They may not change
   ownership, timer, lifetime, or parity semantics in this matrix/ADR.
5. **Checked-in access verifier:** V45 freezes the required script path, exact
   no-argument invocation, audited roots, and symbol allowlists. The script and
   corresponding Makefile/CI hook are rollout dependencies; absence or failure
   of either blocks migration rather than weakening the gate or adding an
   ad-hoc allowlist.

## Opt-in redesign policies after parity

These are not phase-0 defaults and must be enabled by an explicit controller or
definition policy plus separate golden fixtures:

- `RECOVER_REVEAL_UNDERLYING`: stamina-tired expiry removes only tired, so an
  underlying awareness/aggro candidate becomes effective again.
- `FIX_MAP_EMOTE_TIRED_TIMER`: initialize a full tired timer when map
  canonicalization turns a pending presentation into tired, instead of
  reproducing the current zero-timer quirk.
- `PERSIST_AGGRO_THROUGH_BATTLE`: preserve/re-evaluate aggro behavior across
  battle, or add a calm removal trigger, instead of the phase-0 battle clear
  that leaves only dormant legacy metadata. Retained-primary map persistence is
  already phase-0 parity.
- `PERSIST_EFFECT_THROUGH_BATTLE`: set `battlePolicy=PRESERVE_LOGICAL` for a
  reviewed definition; its timer is suspended during battle and it owns no
  presentation pointer.
- `ALERT_STATE_EFFECTIVE_DURING_PRESENTATION`: apply awareness at alert start
  while movement remains presentation-gated, rather than at completion.
- `HANDOFF_COMPATIBLE_COMMAND`: allow an explicitly proven compatible in-flight
  command to survive a state winner change. Phase-0 returns `BUSY` or uses the
  event's broad cleanup instead.

## Completion gate for the transition-orchestrator phase

This phase is complete only when:

- no gameplay code writes `movementSpotStates` directly;
- `EMOTING` has been replaced by a separate generation-safe presentation phase;
- all behavior layers are owner-addressable and removable from any stack
  position;
- every apply/remove uses candidate composition, atomic commit, cache
  invalidation, and centralized entry/exit reconciliation;
- reset, despawn, capture, battle, follower, and map-transition paths invalidate
  the correct handles and preserve no stale object pointers;
- phantom, canopy, RAM/chain, pickup/throw, and queued-battle verification cases
  pass; and
- any intentional differences from the legacy paths above are documented as
  product decisions rather than accidental migration drift.
