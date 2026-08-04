# ADR: One-State Profiles and Stackable Overworld Behavior Overrides

## Status

Implemented on `feature/stackable-state-profiles`. This is the authoritative
V40 wire/runtime contract and V51 authoring contract.

The one-time V39 derivation is retained below as historical rationale and parity
evidence only. It is not a reader, writer, projection, or compatibility contract.
Production/runtime code reads V40. The editor/API authors the V51 contract, and
Global Save emits canonical V40; there is no V39 schema window or behavior
projection compatibility path in NARC member 21.

## Implemented Result

- Each state profile is one complete state. Controllers and stackable override
  definitions select states and apply independently owned effects; removing one
  override recomposes from the remaining stack.
- The V40 runtime blob is 11,028 bytes, including its fixed 216-byte section
  header. The checked header publishes checksum `0xCD843F3E` and schema
  fingerprint `0x9421CA4D`.
- The retired combined V40-plus-projection baseline was 15,052 bytes. The
  current single runtime blob is 4,024 bytes smaller (26.7%); no flattened
  compatibility payload or NARC member-21 projection remains.
- The accepted `test2600.nds` build has 196 bytes of physical headroom in
  overlays 157, 159, and 149; 6,980 bytes in overlay 156; and 204 bytes in
  overlay 158.

## Decision

The former 72-byte `OverworldWildBehaviorProfile` is replaced by a typed model
with five independent concerns:

1. A **state profile** describes one complete, runnable overworld behavior state.
2. A **controller** owns the initial state, transition graph, alert policy, stamina policy, and recovery policy.
3. A **spawn policy** owns placement and appearance behavior.
4. A **population policy** owns population identity and encounter limits.
5. An ordered set of **override layers** selects a state or modifies effective values. Multiple layers may be active at once and any layer may be removed without disturbing the others.

State selection and value modification are deliberately separate operations. Complete state layers compete to select one effective state profile. Modifier layers are then folded over that selected state. A lower-priority state layer therefore remains available underneath a higher-priority state layer, while unrelated effects continue to modify whichever state wins.

The effective behavior is:

```text
controller base state
        + active state candidates (choose one winner)
        + matching static modifiers (ordered fold)
        + active runtime modifiers (ordered fold)
        + normalization and primitive derivation
        = effective state + effective behavior + effective controller values
```

The runtime must never undo a layer by applying an inverse operation. Removal always recomposes from immutable source data and all remaining layers.

## Historical Rationale: Why the V39 Shape Changed

`OverworldWildBehaviorProfile` stored 72 one-byte fields. It combined:

- Three behavior states: chill, attentive/active, and tired.
- Alert presentation and detection.
- Stamina and recovery.
- Spawn placement and spawn animation.
- Population limiting.
- Per-state locomotion parameters.
- A numeric `profileId` that had no runtime reader.

Runtime state was held separately in `movementSpotStates`, where `CHILL`,
`ACTIVE`, and `TIRED` selected different fields in the same flattened profile.
`EMOTING` was an intermediate presentation phase. Tired changed that byte and
then read tired-prefixed fields from the same resolved profile; pickup replaced
`movementBehaviorClasses`, and follower logic suppressed a static override by
array index. These behaviors informed the one-time V40 derivation, but none of
those storage mechanisms remains an active compatibility surface.

The V39 static resolver demonstrated useful composition rules: it started with a
class profile, applied all matching overrides in authored order, supported exact,
relative, minimum, and maximum operations, and normalized once after the fold.
V40 retains recomposition and explicit operators while removing array-order
identity and the three-state record shape.

## Goals

- Represent calm, active, tired, asleep, picked-up, follower, and special behaviors as independently reusable state profiles.
- Keep multiple state and effect overrides active simultaneously.
- Make removal of the top, middle, or bottom runtime layer safe and deterministic.
- Make state identity authoritative even when modifiers change individual fields.
- Give every layer an explicit owner and a stale-safe removal handle.
- Keep spawn, population, membership, and transition topology outside ordinary runtime modifiers.
- Avoid heap allocation and table scans in the frame movement hot path.
- Preserve observable V39 behavior through the completed, deterministic one-time
  V40 derivation; do not preserve the V39 schema or its storage layout.
- Give the editor enough typed metadata to create states, controllers, transitions, and modifiers without understanding C layout.

## Non-goals

- This ADR does not freeze the visual layout of the profile editor.
- This ADR does not promise that later schema versions will retain V40 byte
  offsets; V40 itself has a fixed, validated 216-byte section header.
- This ADR does not make arbitrary script callbacks authorable from data.
- This ADR does not persist transient wild-Pokemon runtime layers in save data.
- This ADR does not make presentation phases such as alert emotes into behavior states.

## Entity Model

Every saved entity has a nonzero, stable `u16` ID. IDs do not change when an entity is renamed or reordered. Array index, display name, and source order are never identity.

### State profile

A state profile is complete and runnable without inheriting values from another state profile. It contains:

- Behavior kind.
- Locomotion and target.
- Movement speed and map-object movement range.
- Allowed tile/surface policy.
- Ledge jump capability.
- Hop, teleport, and RAM parameters.
- Chase boost, circle, arrival, previous-tile, and movement-chain parameters.
- Contact/battle behavior.

State-profile editor tags are descriptive and searchable only. A tag such as `bird`, `calm-looking`, `fast`, or `custom` has no runtime meaning. Runtime role semantics belong to controller nodes, described below, so reusing the same state profile in two differently named controller nodes cannot make a profile-global tag change behavior.

State profiles never contain alert transitions, stamina transitions, spawn destination, population limit, species membership, or override priority.

### Controller

A controller is assigned by immutable spawn context and owns:

- A roster of controller-local state nodes and one required base node.
- Alert/detection defaults and alert presentation defaults.
- Stamina budget and recovery defaults.
- A transition table of triggers, guards, owners, and atomic apply/remove actions.
- A spawn policy ID.
- A population policy ID.

The transition table is topology, not a patchable numeric profile. Runtime modifiers may adjust explicitly exposed controller values such as alert distance or stamina, but may not add transitions, change triggers, redirect targets, or change entry/exit actions.

Every controller-state node has a stable node ID, an optional state-profile binding, and exactly one semantic role:

```text
CALM, ATTENTIVE, TIRED, ASLEEP, CARRIED, FOLLOWER, or CUSTOM
```

Two nodes may reference the same state profile while retaining different semantic roles. `CUSTOM` nodes may also carry a controller-local custom role ID. Applicability role masks are evaluated against the semantic role of the **winning controller node**, never against a state profile's descriptive editor tags. The authoritative state identity is therefore `(controllerId, nodeId, stateProfileId)`.

The base node must always be bound. A non-base optional node may be statically unbound/disabled; a static node-binding rule may bind or unbind it. A candidate whose selector resolves only to an unbound node is not applicable. `behaviorKind == NONE` is migrated as an unbound optional node, not as a supposedly runnable state profile.

Reusable system nodes such as `CARRIED` are imported into each compatible controller roster and still receive controller-local node IDs. A state-candidate definition contains a node selector: either an exact `(controllerStableId, nodeStableId)` pair or a semantic role that must resolve to exactly one node in the current controller. A raw node ID is never an exact selector. A selector never introduces a free-floating profile outside the roster. Portable awareness/tired/system definitions use semantic selectors so logical intent can rebind when static context selects a new compatible controller.

Selector resolution is total and has frozen failure behavior. An exact selector whose controller or node does not match the resolved controller is `NOT_APPLICABLE`. A semantic selector with zero bound matches is also `NOT_APPLICABLE`; a semantic selector with more than one bound match is `AMBIGUOUS_SELECTOR`, is invalid authored data, and aborts a runtime delta without mutation. During retained-context revalidation, zero matches remove the preserved candidate as `CONTEXT_NO_LONGER_APPLICABLE`, while ambiguity rejects the prospective data/context before the point of no return. The validator must prove uniqueness for every semantic selector across every controller allowed by that definition's controller filter.

Legacy tired entry has one mandatory parity exception to optional-node behavior. A migrated controller whose authored `TIRED` binding can resolve absent receives a hidden controller-local fallback node with reserved `CUSTOM/FALLBACK_TIRED` role. Migration partitions the finite immutable version-39 context domain by the complete legacy matcher truth vector into mutually exclusive equivalence classes, then lowers each class into one or more disjoint atomic cells expressible by the existing conjunctive static matcher schema; inability to produce a finite disjoint lowering rejects migration. For each cell it runs the complete ordered legacy tired projection—including every tired-only and shared-movement non-kind action—then repairs the complete state profile's `behaviorKind=TIRED_EMOTE`. It materializes exactly one complete fallback profile variant/binding for the cell with existing `BIND_NODE(controllerStableId,fallbackNodeStableId,profileVariantStableId)` at a reserved post-legacy materialization priority. The generated exact fallback candidate wrapper, not the state profile, stores timer eligibility and finite duration source `OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME` (`4`); legacy source-local `stamina=1` becomes that enablement, never a controller-stamina modifier. No semantic-`TIRED` modifier is retargeted to `CUSTOM`; calm-, attentive-, and other-custom-only writes cannot enter the fallback projection. Exactly one atomic cell/binding must match every eligible context, and binding/profile provenance retains the complete contributing legacy action order. The authored and fallback nodes have distinct controller-local IDs, and a semantic `TIRED` selector can never resolve the fallback.

Ordinary exhaustion uses an origin-specific portable wrapper with the existing semantic `TIRED` selector; initial apply is enabled only when the current controller has one bound authored `TIRED` node. Because the fallback role is `CUSTOM/FALLBACK_TIRED`, semantic resolution can never select it. No `AUTHORED_TIRED_OR_FALLBACK` selector kind exists in schema, serialization, validation, or editor data. Instead, each imperative legacy entry route—`FLED`, active-RAM wall crash, and successful throw recovery—generates two ordinary read-only wrappers: a portable semantic-`TIRED` wrapper and, for each eligible controller, a controller-local exact `(controllerStableId,fallbackNodeStableId)` wrapper. Route preflight resolves semantic `TIRED`; exactly one bound match selects the semantic wrapper, zero selects that controller's exact fallback wrapper, and ambiguity rejects without mutation. Generic semantic failure never triggers fallback outside these three route-owned selection algorithms.

The stored tired-origin discriminator, not a controller-local wrapper or exact node ID, is the preserved logical identity. Each generated imperative wrapper and its runtime entry stores immutable `tiredOriginKind : u8` plus its exact required owner, whose closed mappings are frozen below; no caller/editor may override either field. During an authenticated retained controller change, stamina bypasses the origin discriminator and translation table entirely: its generated semantic wrapper retains required owner `stamina`, re-resolves `TIRED` in the destination, and is removed as `CONTEXT_NO_LONGER_APPLICABLE` only when destination authored tired is absent. The three imperative origins consult an internal generated translation table keyed by `(tiredOriginKind,destinationControllerStableId,authoredTiredBound)` and atomically remap the preserved entry only to a destination wrapper with the identical origin/required-owner family, preserving owner, instance key, entry/timer generations, remaining/zero-pending time, recovery policy, and both generated metadata pairs. This is retained-context revalidation, not serialized selector invention or public `Replace`. Because each serialized wrapper uses only an existing semantic or exact selector, ordinary validation/editor rules apply. Generated metadata is read-only, and ordinary shallow or deep controller duplication refuses a closure containing generated wrappers, importer-owned backlinks, or their translation targets; complete importer regeneration is the only operation allowed to clone and remap that family while preserving its fixed owner IDs and discriminator. Thus stamina plus all three imperative tired origins survive compatible controller rebinding while fallback remains a non-semantic `CUSTOM/FALLBACK_TIRED` node.

### Spawn policy

A spawn policy owns all values consulted before or during initial placement:

- Spawn presentation/locomotion.
- Spawn destination.
- Player-relative minimum and maximum distance.
- Spawn-hop duration.

It is resolved before slot initialization and is immutable for that encounter. A state transition cannot relocate an existing Pokemon by changing its spawn policy.

### Population policy

A population policy owns the overworld limit and a stable population-group ID. The population-group ID replaces the current behavior-limit key derived from a behavior class or override array index. It is resolved at spawn and remains stable for the encounter.

Followers do not consume ordinary wild-population limits unless their assignment explicitly opts into a population policy.

### Static context rule and action union

A static rule matches immutable context such as species, form, species group, level, encounter terrain, shiny state, or assigned class. It owns one or more stable-ID actions from this closed union:

| Static action | Typed payload and result |
|---|---|
| `ASSIGN_CONTROLLER` | `(controllerStableId)`: select one controller. |
| `BIND_NODE` | `(controllerStableId, nodeStableId, stateProfileStableId)`: replace the complete profile binding for that exact controller-local node. |
| `UNBIND_NODE` | `(controllerStableId, nodeStableId)`: remove that exact optional binding; unbinding a base node is invalid. |
| `APPLY_STATE_MODIFIER` | `(modifierStableId, controllerApplicability, semanticRoleMask)`: fold one typed state modifier over the selected roles. |
| `APPLY_CONTROLLER_MODIFIER` | `(controllerModifierStableId, controllerApplicability)`: fold typed alert, detection, stamina, or other exposed controller-scalar operators. |
| `BIND_SPAWN_POLICY` | `(spawnPolicyStableId)`: replace the complete spawn policy used only during encounter creation. |
| `APPLY_SPAWN_POLICY_PATCH` | `(spawnPolicyPatchStableId)`: fold a typed spawn-policy patch during encounter creation. |
| `BIND_POPULATION_POLICY` | `(populationPolicyStableId)`: replace complete population identity/limit data during encounter creation. |
| `APPLY_POPULATION_POLICY_PATCH` | `(populationPolicyPatchStableId)`: fold a typed population-policy patch during encounter creation. |
| `BIND_HOOK_SET` | `(controllerHookSetStableId)`: replace one complete typed controller-hook set. |
| `APPLY_CANDIDATE_TIMER_OPERATOR` | `(controllerStableId, nodeStableId, timerOperator)`: fold an operator into that exact state-candidate timer source, such as migrated `restTime`. |

The union is exhaustive. An action cannot write fields owned by another action kind, and a static rule cannot become a runtime owner, declare an ad hoc transient state, or match values produced by another override. Matching is always against the immutable context snapshot.

### Static assignment and binding precedence

Controller assignment is a single-winner operation. Every matching assignment action contributes the ordering key `(assignmentPriority, ruleStableId, actionStableId)` and carries `controllerStableId` only as its typed payload; the greatest ordering key wins. `assignmentPriority` is an explicit `u16`. A controller ID, source-array position, display name, or perceived specificity is never an implicit tie-break.

After assignment, each controller node starts with its authored state-profile binding. Every non-assignment action is totally ordered by `(staticPriority, ruleStableId, actionStableId)` ascending. Later node, spawn-policy, population-policy, and hook-set bindings replace earlier values only within their typed namespace. State/controller/policy modifiers and candidate-timer operators all fold in that order; modifier stable ID is the final field-contribution provenance key. Equal complete keys are invalid. No result depends on serialized field order or array position.

Static resolution consequently follows this exact order:

1. Snapshot immutable context.
2. Select one controller by explicit assignment precedence.
3. Resolve complete profile bindings for that controller's nodes.
4. Resolve spawn policy, population policy, and typed controller hooks.
5. Fold ordered controller values, candidate-timer sources, state modifiers, and policy patches in their typed namespaces.
6. Install the controller base node, then compose runtime layers.

No rule may match the controller, state, or field result produced by a previous static rule except through an explicit `controllerId` applicability constraint evaluated after step 2.

### Override definition

An override definition has a stable ID, kind, channel, priority, applicability filters, map/battle lifetime policies, and two explicit multiplicity flags. It is exactly one of:

- **State candidate:** contains a selector that resolves to one controller-state node. It does not carry a partial patch. It may own a timer and an expiry/recovery batch.
- **Modifier:** carries a typed partial patch. It does not declare or change state identity.

This separation is mandatory. A modifier cannot change `behaviorKind` and a state candidate cannot carry extra field writes. If behavior kind must change, author a state profile and a state-candidate definition. If a rain, script, or status effect only changes speed or alertness, author a modifier.

Modifiers are first-class V40 wire records, not editor-only previews. A modifier
definition owns one through sixteen packed 11-byte operation records carrying
stable operation ID, definition ID, signed operand, field namespace/ID,
operator, bound, and explicit `order` (`0..15`). Order values are unique and
contiguous within the definition, and runtime composition follows that order
instead of physical record position. Ordinary modifier authoring may use
`CONTROLLER_STATE` through `POSSESSION`; `STATIC_CONTEXT` is resolved from
static actions and `SYSTEM_SAFETY` remains internal.

State-candidate serialization contains optional tagged generated metadata `(hasTiredOriginKind:u8,tiredOriginKind:u8,hasRequiredOwnerId:u8,requiredOwnerId:u16)`. The closed `TiredOriginKind` enum is exactly `1=FLED`, `2=RAM_CRASH`, `3=THROW_RECOVERY`; an absent tag requires its value to be zero, and zero is not an enum/owner value. The immutable generated mappings are `FLED→battle-fled`, `RAM_CRASH→ram-crash`, and `THROW_RECOVERY→throw-recovery`, with both tags present. The generated stamina semantic-`TIRED` wrapper has the canonical absent origin pair and required owner `stamina`. All four generated tired families freeze `allowMultipleOwners=FALSE`, `allowMultipleInstancesPerOwner=FALSE`, and therefore `instanceKey=0`; owner authorization does not replace multiplicity validation. Every ordinary authored/shared/non-generated definition has both pairs canonically absent and remains unconstrained by required-owner authorization; its existing independently authored multiplicity rules still apply. The editor displays this generated metadata read-only and cannot add, remove, redirect, replace-reference, or change it outside complete importer regeneration.

The two multiplicity flags mean exactly:

- `allowMultipleOwners == FALSE`: at most one owner may hold this definition in a slot. An apply by another owner returns `DEFINITION_OWNED`.
- `allowMultipleOwners == TRUE`: different owners may each hold the definition.
- `allowMultipleInstancesPerOwner == FALSE`: `instanceKey` must be zero and that owner may hold at most one instance.
- `allowMultipleInstancesPerOwner == TRUE`: the owner may hold multiple entries, each with a distinct caller-supplied `instanceKey`, including zero.

The flags are independent. The default is `FALSE/FALSE`. Multiplicity is enforced by definition ID; two different definitions may reference the same state node or patch without colliding.

### Active runtime layer

An active runtime layer is a per-slot reference to an override definition plus ownership identity:

```c
typedef struct OverworldWildRuntimeLayer {
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    u16 requiredOwnerId;
    u8 hasTiredOriginKind;
    u8 tiredOriginKind;
    u8 hasRequiredOwnerId;
    u8 reserved;
    u32 entryGeneration;
} OverworldWildRuntimeLayer;
```

The checked implementation packs this identity into the fixed runtime sidecar;
its exact layout is guarded by compile-time and overlay-size checks.
`Apply`/`Replace` accepts no origin or authorization override: before idempotency, collision, or multiplicity shortcuts, preflight validates both canonical definition pairs, requires the operation owner to equal `requiredOwnerId` when its tag is present, and copies both pairs into the prospective runtime layer. Failure is `OWNER_NOT_AUTHORIZED` or `INVALID_GENERATED_WRAPPER` and changes nothing. Imperative routes must select a wrapper whose present origin and required owner match the route/recovery family; stamina copies the absent origin plus required `stamina` owner and bypasses all imperative translation. Public `Replace` may cross between generated tired wrappers only when old/new required-owner and origin pairs are byte-identical; generated↔ordinary or different-origin/owner-family replacement returns `GENERATED_WRAPPER_FAMILY_MISMATCH`. Authenticated retained-context translation is the sole internal exception: it may switch the same-origin semantic/exact wrapper while preserving owner, both generated metadata pairs, handle/timer identity, and remaining time. The semantic key remains `(ownerId, instanceKey)`, and `entryGeneration` protects handles from replacement and reuse.

### Owner

An owner identifies the subsystem responsible for a layer, not the state profile or effect being applied. Examples include:

- Player awareness.
- Aggro request.
- Stamina/exhaustion.
- Forced sleep.
- Scripted event.
- Pickup/throw system.
- Follower system.
- Internal safety recovery.

Owner IDs are stable constants or stable data IDs. One subsystem must never remove a layer owned by another subsystem merely because both layers use the same definition.

## State Selection Is Separate from Modifier Composition

The controller's base node is the implicit lowest state candidate. Every active state-candidate layer remains present until its owner removes it or its explicit lifetime policy removes it.

The effective controller node is the applicable active state candidate with the greatest precedence key. If there are no active state candidates, the controller base node wins. The node's statically resolved complete profile supplies the state values.

Only the winning state profile supplies the complete state value set. Lower state profiles do not contribute fields. This prevents a complete tired state from accidentally inheriting a RAM parameter from an active state merely because both layers remain active.

After the state winner is selected, every applicable modifier is folded over that winner. Static and runtime modifiers therefore survive state changes unless their explicit state-applicability filter excludes the new winner.

The authoritative runtime state identity is `(effectiveControllerId, effectiveNodeId, effectiveStateProfileId, effectiveSemanticRole)`. There is no second mutable `CHILL`/`ACTIVE`/`TIRED` enum that can disagree with it.

The former mechanical `movementSpotStates` byte was removed. Its only remaining
purpose was presentation, so the implementation names it
`movementPresentationStates` and exposes the typed
`OverworldWildMovementPresentationState` API (`NONE` or `SPOT_EMOTE`). This byte
never selects behavior, participates in precedence, or identifies a state
profile; authoritative behavior comes exclusively from the composed V40 stack.

## Channels and Deterministic Precedence

Channels are ordered from lowest to highest precedence:

| Rank | Channel | Purpose |
|---:|---|---|
| 0 | `STATIC_CONTEXT` | Species, group, terrain, level, or shiny modifiers resolved from immutable context. Not stored in the runtime layer array. |
| 1 | `CONTROLLER_STATE` | Ordinary awareness, aggro, recovery, and controller-driven state requests. |
| 2 | `TEMPORARY_EFFECT` | Tired, sleep, weather, status, and other temporary gameplay effects. |
| 3 | `SCRIPTED_FORCE` | Explicit scripted behavior that must beat ordinary AI and status defaults. |
| 4 | `POSSESSION` | Picked-up, thrown, follower, or another system that temporarily owns the actor. |
| 5 | `SYSTEM_SAFETY` | Internal quarantine/recovery behavior. Not authorable as ordinary content. |

Each definition also has an unsigned priority from 0 through 255. Higher values have higher precedence.

The complete precedence key is:

```text
(channel, priority, definitionStableId, ownerId, instanceKey)
```

State selection chooses the greatest key. Modifier folding sorts by the same key in ascending order, so higher-precedence exact writes occur later. Stable IDs and explicit instance keys are the tie-breakers. Push time, source array position, draft order, and handle generation never affect the result.

Equal-channel/equal-priority writes are legal because the stable tie-break is deterministic, but the validator and editor must report them as a conflict warning when they touch the same field. Authors should normally resolve the warning by assigning distinct priorities.

Definitions fix their channel and priority. Callers cannot supply ad hoc priorities when applying a layer.

## Applicability

### State candidates

A state-candidate definition may filter only on immutable context and controller ID. Its exact-node or semantic-role selector must resolve to exactly one node in the resolved controller. It may not filter on the current effective state, role, speed, or another mutable result; otherwise a lower candidate could invalidate itself when it wins.

`Apply` rejects a candidate as `NOT_APPLICABLE` when its immutable-context/controller filters do not match or its target node is absent. The rejected candidate is not stored and no generation changes.

After an authenticated context or controller change, every preserved candidate is rechecked before composition. A semantic selector rebinds to the unique node of that role in the new controller while retaining its logical handle/timer. The three migrated imperative tired origins follow the explicit ordinary-wrapper translation contract above. Any other exact selector or filter that no longer matches is removed as part of the same context-transition batch, its handle and timer become stale, and diagnostics record `CONTEXT_NO_LONGER_APPLICABLE`. `SYSTEM` lifetime definitions are not carried over; their owning system is asked to emit fresh applicable layers after the new static context is resolved.

### Modifiers

A modifier may filter on:

- Immutable spawn context.
- Controller ID.
- Effective state profile ID.
- The semantic-role mask of the winning controller node.

Applicability is evaluated after state selection and before any modifier is folded. It is not reevaluated after another modifier changes a value. A modifier cannot match on effective speed, locomotion, alertness, or another mutable result. This avoids order-dependent self-activation.

An inapplicable active modifier remains in the stack and is reported as skipped. It becomes applicable automatically when recomposition selects a matching controller node. Descriptive state-profile tags never participate.

## Atomic Stack-Delta Contract

Each slot owns a nonzero `u32 slotGeneration`. A virgin runtime initializes it to `1`. It advances exactly once when a live encounter is destructively invalidated (`live -> empty`); installing a new encounter into that already-invalidated empty slot does not advance it again. Repeated cleanup of an empty slot is idempotent. Each inserted or replaced entry receives a nonzero `u32 entryGeneration`.

An apply call returns an opaque handle containing at least:

```text
slot index
runtime handle epoch
slot generation
owner ID
instance key
entry generation
```

The primitive public operation is:

```text
ApplyStackDelta(slot, expectedSlotGeneration, operations[], reason)
```

A delta may contain multiple additions, replacements, required handle removals, explicit remove-if-present operations, owner removals, and policy removals. All handles and keys are resolved against the same pre-delta snapshot. Operation-list order has no meaning: two operations addressing the same `(ownerId, instanceKey)` are rejected as `AMBIGUOUS_DELTA`; remove-plus-add of one key must be expressed as `Replace`.

Removal intent is part of the operation. `REMOVE_REQUIRED(handle)` must resolve the exact epoch/slot/owner/instance/entry generation or the complete batch returns `STALE_HANDLE` and changes nothing. `REMOVE_IF_PRESENT(handle)` and `REMOVE_OWNER_IF_PRESENT(owner)` are the only missing/stale-tolerant batch forms; they report whether they matched and otherwise leave the scratch result unchanged. Malformed handles and handles naming another slot are still errors. Recovery batches use a required operation for the expiring entry and remove-if-present owner operations only for generated calm-reset owners that may legitimately be absent. A caller may not silently downgrade a required removal after preflight.

The delta processor:

1. Resolves every required/optional operation against one snapshot and validates every handle, definition, owner, multiplicity rule, applicability rule, timer action, and final capacity without changing live state.
2. Builds the final layer and timer-instance set simultaneously in scratch storage and composes one prospective effective result.
3. Builds the complete resource/action plan and performs the single compatibility/BUSY decision.
4. Acquires every fallible reservation while still before the point of no return, then revalidates the captured slot/context/data generations.
5. Crosses the point of no return only after the remaining stabilization, layer/timer commit, cache invalidation, and required postcommit publication have been proven infallible.
6. Runs the precomputed infallible stabilization plan, commits the complete layer/timer set and generations once, then runs required postcommit hooks exactly once. Optional visuals may degrade only through their documented canonical-visible fallback.
7. Returns handles for additions/replacements keyed by request operation ID and releases reservations.
8. On any failure before step 5, releases reservations, returns one error for the complete delta, and changes nothing. No failure return exists after step 5.

Tired recovery, map filtering, pickup cleanup, and controller transitions that touch multiple owners must use one delta. There is no observable intermediate winner.

The convenience operations are wrappers around a one-operation delta:

- `Apply(definitionId, ownerId, instanceKey)`
- `Replace(ownerId, instanceKey, definitionId)`
- `Remove(handle)`
- `RemoveOwner(ownerId)`
- `ClearAllForSlot()`
- Read-only queries for active layers, effective state, effective values, and provenance.

The rules are:

1. `(ownerId, instanceKey)` is unique within a slot.
2. Applying the same definition to an existing identical key first reauthenticates the definition/runtime generated metadata and required owner; only then is it idempotent and returns the existing handle without changing entry/timer generation or remaining time.
3. Applying a different definition to an occupied key is rejected. The caller must use atomic `Replace` so an accidental owner collision cannot silently change behavior.
4. A definition may be active under multiple owners only when `allowMultipleOwners` is true.
5. Multiple instances under one owner require `allowMultipleInstancesPerOwner` and distinct, caller-supplied stable instance keys; otherwise the key must be zero.
6. The public one-operation `Remove(handle)` wrapper compiles to `REMOVE_IF_PRESENT`: a well-formed stale handle returns `STALE_NOOP`, changes no generation/cache state, and increments only its diagnostic. Atomic multi-operation actions must name `REMOVE_REQUIRED` or `REMOVE_IF_PRESENT` explicitly; a stale required handle aborts the complete delta.
7. `RemoveOwner` removes all entries belonging to that owner in one recomposition and one transition transaction.
8. `Replace` computes the prospective result, including required-owner and generated-family compatibility, before mutating the live array and does not require an unused capacity slot. Same-definition authorized `Replace` recopies the immutable metadata, issues fresh entry/timer generations, and restarts the authored timer.
9. A batch, apply, replace, remove, or clear either commits the complete new effective result or leaves the old stack and behavior untouched.
10. Direct mutation of runtime layer arrays outside these APIs is forbidden.

`Replace` is intentional even when the replacement definition ID is unchanged: it issues a new entry generation and restarts that candidate's timer from its authored source. This is the only timer-refresh operation. Ordinary idempotent `Apply` never extends a timer.

Transition actions must use stable owners. For example, awareness can replace its own `bird-active` request without affecting a simultaneous stamina-owned `bird-tired` request.

Battle start and destructive context operations may need deltas for several slots. `ApplyStackDeltaSet` preflights every addressed slot, acquires all external reservations, revalidates all captured generations, and then performs one infallible world commit. If any slot is invalid or BUSY or any reservation fails, none of the slot deltas or resource cleanup runs.

## Fixed Capacity and Overflow

The runtime capacity is frozen at:

```c
#define OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT 8
```

The controller base state and static context modifiers do not consume these eight entries. All runtime state candidates and runtime modifiers do.

The implementation uses fixed sidecar arrays for all ten spawn slots. Composition and queries perform no heap allocation during gameplay ticks.

When an insertion would exceed capacity:

- Do not evict a lower-priority layer.
- Do not partially apply the new layer.
- Return `CAPACITY_EXCEEDED` and an invalid handle.
- Preserve the old stack and effective behavior.
- Increment a per-slot overflow diagnostic counter.

Atomic replacement of an existing owner/instance entry remains possible at capacity. Data validation and stress fixtures must prove that normal controllers do not require more than eight simultaneous runtime layers.

## Layer Lifetime and Owner-Safe Timers

Every override definition declares separate map and battle policies:

| Policy | Map meaning | Battle meaning |
|---|---|---|
| `CLEAR` | Remove on a map-context boundary. This is the default and is mandatory for pickup/throw and other map-local ownership. | Remove at battle start. This is the phase-0 default for every ordinary runtime layer. |
| `PRESERVE_LOGICAL` | Preserve only when the logical encounter/slot is authenticated across the boundary; discard all object/task/presentation handles, then recheck applicability against the new context. | Preserve only logical layer/timer intent while all object/task/presentation handles are cleared. This is an explicit behavior-change exception to phase-0 parity. |
| `SYSTEM` | Do not copy the old entry or handle. After new static resolution, ask the registered owning system to emit a fresh layer if still applicable. | Do not carry the old entry. Ask the registered system to re-evaluate only after battle return. |

`SYSTEM_SAFETY` channel does not imply `SYSTEM` lifetime; both fields are explicit. A destructive slot reset clears everything regardless of policy.

The phase-0 definitions use these exact defaults:

| Definition/owner family | Map policy | Battle policy |
|---|---|---|
| `awareness`, `aggro`, `help-call` active candidates | `PRESERVE_LOGICAL` | `CLEAR` |
| `stamina`, `ram-crash`, `battle-fled`, `throw-recovery` tired candidates | `PRESERVE_LOGICAL` | `CLEAR` |
| `forced-sleep` | `PRESERVE_LOGICAL` | `CLEAR` |
| `pickup.carrier:*` and throw-related modifiers | `CLEAR` | `CLEAR` |
| `follower` | `SYSTEM` | `CLEAR` |
| Authored/scripted runtime candidates and modifiers | `CLEAR` unless explicitly reviewed | `CLEAR` unless explicitly marked as a parity exception |
| Static-context modifiers | Re-resolved; not copied as runtime layers | Remain part of static resolution |

Thus a valid retained-slot map-header change preserves legacy active/tired intent and tired time, while pickup always clears. A real destructive map transition that destroys the slot still clears all entries.

A state-candidate definition may own a timer policy and atomic expiry/recovery delta. A whitelisted transition or presentation action may separately own an action timer for resources such as an alert gate, reservation, cooldown, or RAM shake. Timer ownership is exhaustive: timers belong to a candidate entry or a generation-safe action record, never to a controller node, state profile, slot-global "current state," or unrelated presentation byte. A candidate layer entry owns this timer identity:

```text
owner ID + instance key + entry generation
remaining ticks
timer clock
hidden policy
timer generation
```

An action timer is keyed by `(slotGeneration, actionKind, actionInstanceKey, actionGeneration)` and may complete only its owning action. A candidate timer can remove or replace only handles/owners named by its authored recovery delta. It never removes “the current tired profile” by profile ID. Replacing or removing the layer invalidates its timer generation.

Timer clocks are explicit (`FRAME`, `COMPLETED_MOVEMENT`, or another whitelisted engine clock). A timer also declares one hidden policy:

- `PAUSE_WHILE_HIDDEN`: decrement only while its candidate is the effective node.
- `CONTINUE_WHILE_HIDDEN`: decrement whenever the layer remains active; expiry may remove a hidden middle layer without changing the effective state.
- `EXPIRE_ON_HIDE`: the first recomposition that hides the candidate queues its expiry delta before another controller event is dispatched.

Phase-0 defaults are frozen as follows:

- Stamina, RAM-crash, throw-recovery, and battle-fled tired candidates use `PAUSE_WHILE_HIDDEN`.
- Forced sleep uses `CONTINUE_WHILE_HIDDEN` and removes only its own handle at expiry.
- Awareness, aggro, help-call, pickup, and follower candidates have no timer unless a controller explicitly authors one.
- A tired candidate hidden by forced sleep retains its remaining time and resumes after sleep is removed.
- A forced-sleep timer continues under a higher `POSSESSION` candidate; if it expires while hidden, only forced sleep is removed and possession remains effective.

A blocking presentation gate is an additional clock gate, not a state candidate. While an alert emote, active pickup/throw animation, player-ball capture animation, spawn presentation, or another declared blocking presentation token owns the slot, every gameplay candidate timer and non-presentation action timer for that slot is suspended regardless of `PAUSE_WHILE_HIDDEN` or `CONTINUE_WHILE_HIDDEN`; only the presentation's own action timer advances. A stable `CARRIED` possession layer without an active presentation token is not itself a clock gate, so forced sleep can continue while hidden beneath it. Hidden-policy evaluation resumes after the gate releases.

Migrated manual hop-in-place and chain look-around share one source-parity timer quirk. When either starts from tired, the legacy presentation reuses and overwrites the exact tired timer with its presentation duration; normal completion or explicit cancellation leaves it at zero and records mandatory expiry. Null or mismatched object terminalization for **both** hop and look is an intentional phase-0 safety correction: hop preserves the source-observable timer/end-state outcome while adding logical authentication, no-dereference cleanup, and quarantine, and look adds those protections while also repairing an internal early-return defect that can bypass its later null-object/timer-zero terminal branch and strand `EMOTING`.

Every terminal path first authenticates the logical tuple `(runtimeEpoch,slotGeneration,ownerId,instanceKey,entryGeneration,timerGeneration,presentationGeneration)` independently of object identity. Each object-owning presentation token also captures `(mapGeneration,expectedManagerGeneration,expectedObjectGeneration)`. If the logical tuple is current, terminalization consumes the token, sets only that timer to zero, records the exact mandatory expiry, and clears pointer-bearing presentation ownership. Pointer restore, pose canonicalization, quarantine release, and object cleanup additionally require the exact captured map/manager/object tuple; an exact current object is restored once. A null/mismatched object is never dereferenced; it publishes mandatory cleanup kind `MANUAL_PRESENTATION_OBJECT_LOSS` with its scope-specific typed identity, quarantines object-dependent AI/interaction/reuse, and lets objectless resident maintenance release logical task/presentation ownership without touching a replacement manager or object. Only an authenticated object rebind/recreation may canonicalize pose/movement and clear quarantine. If the logical slot/candidate was destructively invalidated, D01c wins: it consumes the presentation/cleanup obligation and creates no tired expiry against the dead or reused slot. A stale presentation, manager, object, or replacement candidate cannot zero or restore anything. The pre-presentation tired duration is never restored. From calm or active, the action remains presentation-only and preserves the complete layer set. Newly authored presentation tokens use the ordinary separate-timer gate.

Timer ticks do not recompose or bump layer/effective cache generations. Crossing expiry produces one normal atomic stack delta. Map-preserved timers retain their remaining value; cleared/system-recreated layers do not inherit the old timer.

Initial remaining time is captured from the candidate's composed timer source when its entry is applied/replaced. Candidate-timer static actions fold in the same total static-action order as other numeric values, and the completed candidate-timer fold is the sole authoritative source for the new timer; no later flat-profile value may replace it. Migrated legacy `restTime` supports exact `SET` and plain relative `ADD` only; `AT_LEAST`, `AT_MOST`, and compound relative-bound operations are invalid for that source field. Each legacy `ADD` clamps immediately to `0..64`, and later timer operators see that clamped result. Exact `SET` retains the full byte until the complete fold ends. After the ordered fold, but before sentinel conversion, a bound non-`ASLEEP` tired node with folded `restTime == 0` is repaired to finite `1`, including when the last matching action was `SET(0)`. Only after that repair does conversion map asleep plus zero to explicit indefinite `255` and every other value at least `255` to finite `254`. `alertTime` is not a candidate/action timer source: it remains numeric `controller.alertPresentationDuration` (`0` means the legacy automatic/default presentation duration), folds with controller modifiers, and is copied into a presentation action timer only when a new alert token is created. A later modifier or static rebind changing a timer default does not rescale an already-running timer. `Replace` explicitly restarts it from the newly composed duration. A `PRESERVE_LOGICAL` map transition keeps remaining time even when the candidate semantically rebinds to the new controller's corresponding role.

### Tired recovery policy

For phase-0 legacy parity, every migrated ordinary tired candidate uses `LEGACY_RETURN_CALM`. Its expiry delta atomically:

1. Removes the exact tired candidate handle and timer with `REMOVE_REQUIRED`.
2. Uses `REMOVE_OWNER_IF_PRESENT` for `awareness` in the same slot. The generated phase-0 calm-reset owner set also optionally removes `aggro` or `help-call` when either can be the active intent underneath that controller's tired node.
3. Resets the active-step counter, tired presentation, RAM/chain state, and spot cooldown.
4. Applies the 24-frame post-tired movement cooldown.

The result is the controller base/calm node. A higher possession/scripted candidate hides the tired timer under the default pause policy, so ordinary tired expiry cannot occur until that higher candidate is gone. The validator rejects a `LEGACY_RETURN_CALM` recovery delta if any lower active-intent owner could become effective but is absent from the controller's explicit calm-reset owner set. There is no intermediate reveal of attentive behavior.

`battle-fled` uses a distinct generated recovery delta: required removal of its exact handle plus the same tired exit counter/cooldown actions, with no awareness/aggro/help-call removal operations because battle entry already cleared those layers. `REVEAL_UNDERLYING` is an explicit opt-in recovery policy that removes only the expiring candidate. It is a documented parity exception and requires a dedicated controller flag, editor warning, and verification fixture. Forced sleep uses a separate `REMOVE_SELF` recovery policy and is not treated as ordinary tired recovery.

## Modifier Operators and Removal

Each patched field uses one of these explicit operations:

- `SET(value)`
- `ADD(signedDelta)`
- `AT_LEAST(value)`
- `AT_MOST(value)`
- `ADD_AT_LEAST(delta, floor)`
- `ADD_AT_MOST(delta, ceiling)`

`AT_LEAST` and `AT_MOST` are mutually exclusive for one field in one layer. `ADD` saturates to the field's legal scalar domain before its optional bound is applied. Enum, ID, bitmask, and boolean fields support `SET` only. Numeric operator eligibility is field metadata shared by the data validator, runtime resolver, migration tool, and editor.

Operations are applied layer by layer in ascending precedence. They are not algebraically combined ahead of time. Relative and bounded operations are therefore deterministic even when they overlap.

Removing a layer always performs:

```text
select state winner again
clone that immutable state profile
clone immutable controller defaults
apply every remaining applicable modifier in order
normalize once
derive primitives and provenance
commit atomically
```

No inverse delta is stored or applied. No snapshot of the previously visible lower layer is needed.

## Normalization Contract

Complete state profiles, controller defaults, spawn policies, and modifier definitions must pass load-time validation. Invalid authored data rejects the new behavior blob rather than being silently accepted.

Runtime composition uses a scratch result and follows this exact order:

1. Validate the slot identity and referenced definitions.
2. Select the effective state candidate.
3. Copy the winning complete state profile and controller runtime defaults.
4. Collect applicable static and active runtime modifiers.
5. Sort modifiers by the explicit precedence key.
6. Apply all field operators without intermediate cross-field repair.
7. Apply the documented post-fold normalization once after the complete fold.
8. Derive locomotion, target, alert, reaction, capability, cache, and provenance values.
9. Compare with the previous effective result and build a transition plan. Composition itself performs no side effects and does not commit.

Normalization includes, at minimum:

- Enum and boolean range validation.
- Movement speed domain enforcement.
- Hop maximum distance greater than or equal to hop minimum distance.
- Chase distance, circle radius, RAM acceleration, and movement variance bounds.
- Allowed-tile/surface validation.
- Cross-field locomotion requirements.
- Controller constraints such as nonzero stamina when an exhaustion transition is enabled.
- Controller constraints such as nonzero recovery when a non-sleep tired state can recover.

The exact authored-versus-composed policy is:

| Field family | Authored complete value | Modifier definition | Post-fold result |
|---|---|---|---|
| Enum/ID (`behaviorKind`, locomotion, target, jump level, battle trigger, alert mode/range, spawn mode/destination, chain action) | Must be a listed enum member; gaps are invalid | `SET` only and operand must be a listed member | Invalid/corrupt result rejects the delta; no enum is silently mapped to zero |
| Boolean | Must be 0 or 1 | `SET` only | Invalid/corrupt result rejects the delta |
| Movement speed | 1..4 | Numeric operators; operands validated | Saturate each numeric operation to 1..4 |
| Chase boost speed | 0 (disabled) or 1..4 | Numeric operators | Saturate to 0..4 |
| Chance | 0..100 | Numeric operators | Saturate to 0..100 |
| Detection distance, stamina, movement range | 0..64 | Numeric operators | Saturate to 0..64; when an exhaustion transition is enabled, effective stamina 0 is normalized to 1 |
| Recovery duration | 0 (disabled), 1..254 finite, or 255 indefinite-asleep sentinel | `SET` and finite numeric operators; arithmetic may not enter or leave 255 | Finite arithmetic saturates to 0..254. Value 255 is valid only for an `ASLEEP` candidate with an indefinite timer policy |
| Hop min/max distance | 0..12 | Numeric operators | Saturate to 0..12, then set max to min when max is lower |
| Hop/teleport timing | Hop time and teleport time 0..64; pauses 0..255 | Numeric operators | Saturate to the same domains |
| RAM | Acceleration 0..32; maximum speed byte 0..255 | Numeric operators | Saturate to the same domains |
| Circle/chase distances | Circle radius 0..8; chase boost distance 0..32 | Numeric operators | Saturate to the same domains |
| Hop spin | 0..15 | Numeric operators | Saturate to 0..15 |
| Chain variance | Movement 0..32; pause 0..255 | Numeric operators | Saturate to the same domains |
| Allowed tile/surface | Listed tile value, including explicit `NONE`; duplicates are allowed but canonicalized | `SET` only | Invalid values reject; duplicate secondary becomes `NONE` |
| Player-adjacent mask | Only low F/B/L/R bits (`0x0..0xF`) | `SET` only | Unknown bits reject |
| Spawn relative distance | 1..8 and min <= max | Runtime-forbidden | Invalid authored policy rejects; no runtime repair |
| Population limit | 0..10 | Runtime-forbidden | Invalid authored policy rejects |

Complete authored records are rejected rather than repaired. Modifier operands are rejected at data-load/editor-validation time. Post-fold normalization is limited to the explicit saturations and pair canonicalizations above; any other incompatible cross-field result returns `INVALID_COMPOSITION` and leaves the live stack unchanged.

The legacy asleep sentinel is source-sensitive. Current code stores `255` in the **runtime tired timer** when `behaviorKind == ASLEEP` and legacy `restTime == 0`, and that timer does not decrement while the object exists. Migration converts that case to explicit recovery duration `255` plus an indefinite timer policy. Any literal legacy `restTime >= 255` that is not the asleep-zero special case migrates to finite `254`, matching `GetRestFrameCount`; it must not accidentally become indefinite.

The current asleep repair rules must not survive as hidden behavior mutation. Asleep is a complete state profile, and entering or leaving it is an explicit state-candidate transition.

Corrupt loaded data rejects the behavior blob and activates the existing known-safe fallback. Corruption discovered in a runtime delta rejects that delta. Defensive fallback must increment diagnostics and is not a substitute for authoring validation.

## Historical V39 Field Taxonomy

This taxonomy records how the former 72-byte record was interpreted during the
one-time derivation. It is parity evidence, not a V39 runtime representation and
not a requirement to preserve legacy fields in V40 authoring.

Every former `OverworldWildBehaviorProfile` field is assigned below. “Numeric”
means `SET`, relative, and bounded operations are eligible subject to field-domain
metadata. “Exact” means `SET` only. “Forbidden” means an ordinary runtime
modifier cannot address the field.

| Current field(s) | New owner and field | Runtime modifier | Migration rule |
|---|---|---|---|
| `chillState`, `attentiveState`, `tiredState` | Controller-node-bound state profile `behaviorKind` | Forbidden; use a state-candidate layer | Generate separate `CALM`, `ATTENTIVE`, and `TIRED` nodes with complete profiles. `EMOTING` is not generated as a state node. |
| `alertState` | Controller alert-presentation mode | Exact | Copy to controller defaults; presentation phase remains separate from state. |
| `alertEmote` | Controller alert-presentation bubble/effect | Exact | Copy to controller defaults. |
| `alertTime` | Controller alert-presentation duration (`0` = legacy automatic/default duration) | Numeric controller scalar, not a candidate timer | Fold in the controller namespace and copy into a new presentation token only at alert start. |
| `alertness` | Controller detection distance/sensitivity | Numeric | Copy to controller defaults. |
| `stamina` | Controller stamina budget | Numeric | Copy to controller defaults and generate exhaustion guard. |
| `restTime` | State-candidate timer/recovery source | Legacy `SET` or `ADD` only; no bounded/compound forms | Fold all matching actions in static order and clamp after each `ADD` to 0..64; repair a bound non-`ASLEEP` tired result of zero to finite 1; then map asleep+zero to explicit indefinite 255 and every other value >=255 to finite 254. |
| `chillSpeed`, `attentiveSpeed`, `tiredSpeed` | State profile `speed` | Numeric | Copy the corresponding value into each generated state profile. |
| `range` | State profile `movementRange` | Numeric | Copy into every generated state profile. A changed effective value must reconcile map-object X/Y range. |
| `jumpLevel` | State profile `jumpLevel` | Exact | Copy into every generated state profile. |
| `profileId` | Retired legacy identity | Forbidden | Replaced by stable entity IDs and explicit controller/population IDs; it had no V39 runtime reader. |
| `spawnState` | Spawn policy `presentation` | Forbidden | Copy once to the controller's spawn policy. |
| `chillAction`, `movementStyle`, `specialAction` | State profile `locomotion` | Exact | Map chill, attentive, and tired values respectively. |
| `chillTarget`, `targetSelector` | State profile `target` | Exact | Map chill and attentive values. Generate tired target from the same behavior-kind derivation used by the current primitive resolver. |
| `alertRange` | Controller detection shape/range mode | Exact | Copy to controller defaults. |
| `playerAdjacentDirectionMasks` | State profile `playerAdjacentDirectionMask` | Exact | Copy into every generated state that targets `NEXT_TO_PLAYER`; retain a default in all generated states for parity. |
| `alertChance` | Controller detection chance | Numeric | Copy to controller defaults. |
| `spawnDestination` | Spawn policy `destination` | Forbidden | Copy once to spawn policy. |
| `attentiveBattle` | State profile `battleTrigger` | Exact | Copy to the `ATTENTIVE` node. Set every generated non-attentive node to `NONE`, matching the current active-only reader. |
| `hopAllowNonCardinal`, `hopMinDistance`, `hopMaxDistance`, `hopPause` | State profile `hop.*` | Boolean exact; distances/pause numeric | Copy to chill state. |
| `attentiveHopAllowNonCardinal`, `attentiveHopMinDistance`, `attentiveHopMaxDistance`, `attentiveHopPause` | State profile `hop.*` | Boolean exact; distances/pause numeric | Copy to attentive state. |
| `tiredHopAllowNonCardinal`, `tiredHopMinDistance`, `tiredHopMaxDistance`, `tiredHopPause` | State profile `hop.*` | Boolean exact; distances/pause numeric | Copy to tired state. |
| `teleportTime`, `teleportPause` | State profile `teleport.*` | Numeric | Copy to chill state. |
| `attentiveTeleportTime`, `attentiveTeleportPause` | State profile `teleport.*` | Numeric | Copy to attentive state. |
| `tiredTeleportTime`, `tiredTeleportPause` | State profile `teleport.*` | Numeric | Copy to tired state. |
| `alertSpecialAction` | Typed controller invocation hooks | Forbidden | `CALL_FOR_HELP` becomes a once-only `DETECTION_ENTRY` hook. `PICKUP_THROW` becomes both `ACTIVE_ENTRY_TRY_PICKUP_THROW` and idempotent `ACTIVE_LOOP_TRY_PICKUP_THROW` hooks. `NONE` generates neither. |
| `overworldLimit` | Population policy `limit` | Forbidden | Copy with a stable population-group ID independent of class and override array position. |
| `spawnDestinationMinDistance`, `spawnDestinationMaxDistance` | Spawn policy `distanceRange` | Forbidden | Copy once and validate max greater than or equal to min. |
| `ramAccelerationSteps`, `ramMaxSpeed` | State profile `ram.*` | Numeric | Copy to chill state. |
| `attentiveRamAccelerationSteps`, `attentiveRamMaxSpeed` | State profile `ram.*` | Numeric | Copy to attentive state. |
| `tiredRamAccelerationSteps`, `tiredRamMaxSpeed` | State profile `ram.*` | Numeric | Copy to tired state. |
| `chainPauseAction` | State profile `movementChain.pauseAction` | Exact | Copy into every generated state. |
| `chillAllowedTile`, `chillAllowedTile2` | State profile `allowedTiles[0..1]` | Exact | Copy to chill state. |
| `attentiveAllowedTile`, `attentiveAllowedTile2` | State profile `allowedTiles[0..1]` | Exact | Copy to attentive state. |
| `tiredAllowedTile`, `tiredAllowedTile2` | State profile `allowedTiles[0..1]` | Exact | Copy to tired state. |
| `hopTime` | State profile `hop.timePerTile` | Numeric | Copy into all generated states. |
| `attentiveChaseBoostDistance`, `attentiveChaseBoostSpeed` | State profile `chaseBoost.*` | Numeric | Copy to attentive state; other states default to disabled. |
| `hopSpinSpeed`, `attentiveHopSpinSpeed` | State profile `hop.spinSpeed` | Numeric | Use `hopSpinSpeed` for chill and tired, matching current selection; use `attentiveHopSpinSpeed` for attentive. |
| `spawnHopTime` | Spawn policy `hopTimePerTile` | Forbidden | Copy once to spawn policy. |
| `attentiveCircleRadius` | State profile `circleRadius` | Numeric | Copy to attentive state; other states default to disabled. |
| `attentiveContinueWhenArrived` | State profile `continueWhenArrived` | Boolean exact | Copy the legacy byte exactly to the `ATTENTIVE` node. Set every generated non-attentive node to `FALSE`; the current consumer exists only in active circle targeting. |
| `attentiveAvoidPreviousTile` | Retired dead legacy byte; new state profile `avoidPreviousTile` is derived | Boolean exact in the new schema | The current byte has no runtime reader. For parity set `ATTENTIVE.avoidPreviousTile = TRUE` exactly when the resolved legacy attentive behavior is `CHASE` and target is not `RANDOM_NEARBY`; otherwise false. Set all non-attentive nodes false and report ignored nonzero legacy bytes in migration diagnostics. |
| `chainMovementVariance`, `chainPauseVariance` | State profile `movementChain.*Variance` | Numeric | Copy into every generated state. |

The migration oracle, not assumptions in this table, is authoritative when a legacy consumer gives a shared field state-specific behavior. Any discovered mismatch must be documented and resolved before the old schema is removed.

### External fields that are also runtime-forbidden

The following are not members of the 72-byte profile but are part of the existing resolver and must remain immutable for a live encounter:

- Species and form.
- Species-group membership.
- Encounter terrain and map context.
- Spawn level and shiny identity.
- Behavior-class and controller assignment.
- Static rule membership lists and match definitions.
- Stable entity IDs.
- Spawn and population policy IDs.
- Transition triggers, targets, guards, owner IDs, and entry/exit action definitions.

Changing any of these requires an explicit encounter rebind/reinitialization API, not an ordinary runtime modifier.

## Central Transition and Reconciliation Contract

Every stack mutation flows through one transition orchestrator. The orchestrator composes the prospective result in scratch memory before touching live state.

The transition transaction has one exact ordering and a strict point of no return:

1. **Pure identity/delta preflight:** capture and validate data/runtime epochs, slot/context generations, the complete required/optional operation set, handles, final capacity, definitions, applicability, and timer actions.
2. **Pure composition and planning:** build the final layer/timer set, prospective state/controller values, primitives, capabilities, provenance, hashes, exact stabilization plan, required postcommit action list, and canonical fallback for each optional visual.
3. **Fallible reservation:** acquire every script, object, task, child-slot, heap, and other external reservation named by the plan. Reservation does not mutate gameplay-visible ownership. Any unavailable resource or unsafe command returns `BUSY`/error here.
4. **Reservation validation:** recheck all captured generations and reservation identities. Failure releases every reservation and changes nothing.
5. **Point of no return:** cross it only after steps 1–4 prove every remaining stabilization, logical write, generation/cache update, and required publication is non-allocating and infallible. Rollback is not an alternative to this proof.
6. **Infallible stabilization:** finish/cancel incompatible movement, restore RAM shake, reveal phantom, restore canopy/emote partners, clear invalid battle/throw ownership, and run old-state pre-exit cleanup exactly as planned.
7. **Infallible commit:** write the complete layer/timer set, effective node/values, generations, cache metadata, and generation-safe handles in one critical section.
8. **Postcommit:** run old-node exit/new-node entry and other required reserved actions exactly once, rebuild frame-work/capability masks, publish required script/child work, then start optional presentation. Optional visual failure must take its precomputed canonical-visible fallback, clear auxiliary ownership, and record diagnostics; it cannot fail the logical transaction.
9. **Finish:** record transition reason/winner/hash and release only reservations still owned by the transition. A reservation transferred at commit to a resident lifecycle plan is not released here. No error return is permitted after step 5.

No sound, script request, child spawn, or other externally visible one-shot action runs before commit. Reservation may hold capacity but may not publish the action. Battle planning must also pin the complete overlay 149/150/151/152 ownership/load-generation closure and acquire a teardown-readiness lease covering field-service shutdown, helper/behavior validation, both cleanup lifecycle phases, task/resident release, overlay-conflict checks, command return, and physical unload. The lease proves every postcommit detach/unload/release is non-allocating and infallible; any currently mutating prepare phase must be split into non-mutating reserve plus infallible consume. A script-creating/deferred route acquires both its script-task reservation and teardown lease; `SCRIPT_TALK` acquires only the lease for its already-running authenticated script/task-manager context. If any unload/teardown path remains fallible or cannot be reserved before step 5, the transaction fails before the point of no return. There is no post-point-of-no-return rollback or “best effort” partially committed transition.

Battle preflight stores that lease in a fixed resident `BattleTeardownPlan` carrying `(EMPTY|RESERVED|PUBLISHED|CLAIMED|RETURN_PENDING|RETURN_ACKED|RETURN_CANCELED|CLEANUP_DONE|TASKS_RELEASED|UNLOADED|RELEASED,planEpoch,planGeneration,runtimeEpoch,mapGeneration,pendingBattleGeneration,targetSlotGeneration,targetEncounterGeneration,originKind,originSubroute,scriptTaskGeneration,taskManagerGeneration,overlayLoadGeneration[149..152],teardownLease,leaseOwner,teardownExecutorIdentity,teardownExecutorClaimGeneration,returnBoundary[2],requiredReturnMask,readyReturnMask,returnedMask)`. Teardown execution ownership is independent of return publication. Each required `returnBoundary` cell is `(UNUSED|REQUIRED|READY|ACKED|CANCELED,boundaryKind,publisherIdentity,enclosingResidentCallerIdentity,ticketSequence)`, where `ticketSequence` is nonzero, the two required sequences are unequal, and neither may be reused before the plan is `RELEASED`. `OVERLAY_CALLBACK_RETURN.publisherIdentity` is the exact `(callbackStableId,callbackInvocationGeneration,overlayId,overlayLoadGeneration)` and its enclosing caller is `(residentOverlayCallerStableId,residentCallGeneration)`. `SCRIPT_COMMAND_RETURN.publisherIdentity` is the exact `(scriptCommandStableId,scriptTaskGeneration,taskManagerGeneration,scriptCommandGeneration)` and its enclosing caller is `(residentScriptDispatcherStableId,dispatcherGeneration)`. Route preflight freezes both cells and the exact mask from the closed origin/subroute table below. Before the point of no return the transition owns `RESERVED`; precommit failure releases it without publication. Commit transfers lease ownership `TRANSITION→BATTLE_TEARDOWN_PLAN`, binds the teardown executor separately, freezes the boundary tickets, and publishes `PUBLISHED` last. A script-creating/deferred route binds its reserved future task into the script boundary cell, while `SCRIPT_TALK` binds its already-running script command there.

The teardown executor may claim teardown execution authority but never owns/releases the lease or authenticates either return boundary. Immediately before a required boundary returns, only that boundary's exact publisher may compare/exchange its own cell `REQUIRED→READY` using the complete publisher identity and nonzero ticket; the first ready cell advances the aggregate plan `CLAIMED→RETURN_PENDING`, and later ready cells remain pending. After control has actually unwound, only that cell's exact enclosing resident caller may compare/exchange `READY→ACKED`, then set the matching `returnedMask` bit. Overlay publisher/caller identity can never publish or ACK the script cell, script publisher/dispatcher identity can never publish or ACK the overlay cell, and callback→script or script→callback spoof attempts are diagnostic no-ops with no cell, mask, executor, cleanup, or lease mutation. One observed boundary can never satisfy the other. Only when `readyReturnMask` and `returnedMask` both cover `requiredReturnMask` may resident code transition `RETURN_PENDING→RETURN_ACKED`. A teardown-executor attempt to publish/ACK a boundary, clean up early, unload, or release is rejected without milestone mutation. Cleanup, task/resident release, and physical unload run only after `RETURN_ACKED` or the distinct cancellation proof below. The plan remains lease owner and overlays remain pinned throughout; the coordinator releases exactly once only by authenticated `UNLOADED→RELEASED`.

A stale plan/executor tuple rejected before teardown-executor claim is a diagnostic no-op. Once the exact executor has claimed, its completion failure invalidates only that executor and queues mandatory takeover for the exact plan; boundary cells/tickets remain independently authoritative. If an executor or boundary publisher is canceled/lost, resident cancellation must first prove the corresponding callback/task/command cannot be executing or resume, then marks only the exact required cell `CANCELED` and publishes aggregate `RETURN_CANCELED` when every outstanding required frame has either actually returned or been proved quiescent. Mandatory cleanup may replace only teardown execution after that proof and can never fabricate a boundary ACK. Duplicate/stale/cross-boundary tickets or ACKs are no-ops, and a later plan cannot overwrite a non-released predecessor. Mandatory cleanup completes the reserved cleanup/task-release/unload sequence without taking lease ownership; only the coordinator's final `UNLOADED→RELEASED` releases.

If the effective controller node changes, old/new node lifecycle hooks run. If only the bound profile ID changes because static context rebinding selected a different complete profile for the same node, it is treated as a node re-entry for capability/resource reconciliation but not as a controller transition event.

If effective node/profile identity is unchanged but effective fields changed, it performs field reconciliation without repeating state exit/entry actions. Examples include updating map-object movement range, clearing a RAM acceleration chain when locomotion no longer supports RAM, or ending a teleport presentation when teleport capability is removed.

Every movement command carries one immutable universal command-origin identity:

```text
(runtimeEpoch, slotIndex, slotGeneration, commandGeneration, commandSerial,
 controllerId, nodeId, stateProfileId, winnerKind,
 winnerDefinitionId, winnerOwnerId, winnerInstanceKey, winnerEntryGeneration,
 effectiveGeneration, objectGeneration, staminaPolicyId,
 staminaPolicyGeneration)
```

`winnerKind` is exactly `BASE` or `LAYER`. `BASE` requires the four layer
identity fields to be zero; `LAYER` requires their exact nonzero handle values.
This discriminant prevents base/layer aliasing. No pointer is part of identity.

Completion charges the captured stamina/capability policy at most once and only after authenticating the same slot, command generation/serial, effective command owner, and policy generation. An incompatible state/capability transition cancels the command during reconciliation and charges zero; a stale or duplicate completion is a diagnostic no-op. Node or profile ID alone is insufficient because a rebind or modifier change may reuse it under a different effective/policy generation.

Each slot runtime sidecar owns one nonzero `chainGeneration` carrier and at most one `movement-chain` action owner. Virgin sidecar/D01d initialization sets the carrier to `1` with no active owner. Starting a chain advances the carrier and installs the owner; replacing an active chain advances it exactly once atomically (not once for cancel plus again for start); explicit cancel of an active owner advances it exactly once and clears all chain direction/step/remaining/pause/previous-tile state, while idempotent cancel of an inactive record does not advance. Natural completion consumes the active owner; the next start advances before reuse. Wrap follows the generation table below.

Every chain-owned command, continuation, pause action, previous-tile lease, and completion carries the identical universal command-origin tuple above plus `(chainGeneration,chainStepSerial,artifactKind,artifactGeneration)`, where `artifactKind` is the closed enum `NATIVE_COMMAND`, `CUSTOM_COMMAND`, `CONTINUATION`, `PAUSE_ACTION`, `PREVIOUS_TILE_LEASE`, or `COMPLETION`. The exhaustive generation map is: both command kinds use `commandGeneration`; continuation uses `continuationGeneration`; pause uses `actionGeneration`; previous-tile lease uses `leaseGeneration`; completion uses `completionGeneration`. Each is a nonzero sidecar-owned counter advanced before publication/replacement; wrap drains the active step and advances `chainGeneration` before reuse. Every artifact authenticates the complete universal prefix, active chain owner, chain generation/step, kind, and mapped artifact generation before reading or mutating counters, scheduling, charging stamina, releasing a lease, or clearing the owner. A changed state profile, effective generation, object generation, stamina policy ID/generation, or discriminated winner invalidates every old-prefix artifact. If capabilities remain compatible, reconciliation may retain the owner/counters and `chainGeneration` only by atomically rebinding the prefix, advancing `chainStepSerial`, draining old artifacts, and publishing fresh artifacts; otherwise it cancels/replaces the chain. Before step serial reuses `1`, atomically replace the chain with one generation advance and drain every old artifact.

RAM wall-crash shake is a distinct generation-safe action owner, separate from the `ram-crash` candidate and its recovery timer. Its action record owns the authenticated object identity, timer, saved base X/Z, and action generation; only that record may tick, restore, or clear those coordinates. Tired completion may reset RAM direction, RAM step counter, speed, chain, active-step counter where the source route does so, and cooldown without canceling a still-live shake. Any object rebind/destruction or incompatible positional action must first authenticate the shake owner and restore its saved base coordinates. Active RAM impact accepted for battle clears direction, step counter, speed, and chain through its own route and inserts no tired candidate.

A transition that cannot safely reconcile at the current moment returns `BUSY` or is queued by the controller; it does not expose a partially changed stack. System-safety transitions may use a dedicated forced-cleanup path, but still commit atomically.

The reconciliation audit must cover:

- Native held movement and single-movement ownership.
- Custom and staged hops.
- Movement chains and previous-tile locks.
- RAM direction, acceleration, speed, and crash shake.
- Alert timers, bubbles, cries, and partner animations.
- Phantom hidden/flicker/teleport presentation.
- Canopy proxy and render state.
- Pickup/throw target and carrier reservations.
- Queued and deferred battle identity.
- Frame-task eligibility and cached capability masks.

Unavailable overlay code cannot turn cleanup into a diagnostic-only no-op. Logical D01a-style reset may zero phantom flags/pointers, but it must not claim that a primary object was revealed or an auxiliary object was deleted unless an authenticated `clearObjectCommand=TRUE` path actually performed that normalization. Resident code must record a generation-scoped `cleanupRequired`/`presentationRestorePending` obligation, quarantine affected slots from AI, interaction, and reuse, and clear any resident-owned request publication. The first maintenance pass on which the owning overlay is callable must authenticate the recorded slot/object generations and run the required reveal/delete/canonical cleanup before unquarantining. Destructive context loss additionally invalidates the live slot identity in resident state immediately; when the overlay next loads, it must clear all inaccessible sidecar layers/timers/tokens/caches before any spawn, transition, or query is accepted. Stale pointer-bearing presentation tokens can never act on a reused generation; registered system-cleanup obligations are consumed, deferred, or taken over only by their cleanup-kind terminal policy below.

### Typed invocation hooks

Controller hooks are whitelisted engine action IDs with fixed invocation points. They are not arbitrary callbacks and do not live in modifier data.

- `DETECTION_ENTRY_CALL_FOR_HELP` runs once after the detection transaction has committed its generation-safe pending-transition/presentation token and before the optional visual begins. Its help-spawn request carries the slot/presentation generation so retries cannot duplicate children; no child is spawned during preflight.
- `ACTIVE_ENTRY_TRY_PICKUP_THROW` runs once after a committed transition makes the `ATTENTIVE` node effective.
- `ACTIVE_LOOP_TRY_PICKUP_THROW` is an idempotent loop hook evaluated only while that node remains effective and no existing pickup reservation is owned.

The legacy `CALL_FOR_HELP` value generates only the first hook. The legacy `PICKUP_THROW` value generates both pickup hooks. Applying an unrelated modifier, revealing a hidden attentive layer, or rebuilding a cache must not replay a once-only entry hook unless the effective node actually enters.

Static hook binding is exact replacement of one complete hook set, not additive merging. At a later static priority, legacy `NONE` replaces the set with empty, `CALL_FOR_HELP` replaces it with only detection-entry help, and `PICKUP_THROW` replaces it with the two pickup hooks. This preserves overlapping legacy last-write behavior.

Alert presentations freeze awareness timing as follows: detection creates a generation-safe presentation token whose pending delta applies `awareness`; `CALL_FOR_HELP` runs at detection entry; awareness commits and attentive entry hooks run only when presentation completes. A no-visual alert commits immediately. Map canonicalization commits a still-valid pending awareness delta once before discarding the presentation token. A stale token after slot/context change does nothing.

## Deterministic Transition Dispatch

Controller events never mutate the stack directly. For each eligible slot/dispatch pass, the dispatcher captures one immutable guard snapshot containing slot/context generations, effective controller/node/role, counters, timers, positions, cooldowns, and event payload. Every candidate guard in that pass reads the same snapshot.

Eligible transition rows are sorted by `(dispatchPriority, transitionStableId)` descending. The first matching row wins. Its complete ordered action list is compiled into one order-independent stack delta and committed as one transition. Lower rows do not chain against the newly composed state in the same pass; they may be reconsidered from a fresh snapshot in a later pass. Reset, map, battle, and safety transactions are mandatory system events above all authored dispatch priorities.

BUSY requests use a fixed four-entry per-slot optional queue plus non-droppable mandatory-pending records:

- An optional token stores slot generation, event type, owner/instance key, transition ID, priority, payload, and a nonzero per-slot `tokenSequence`—not a stale guard result.
- Token identity is `(slotGeneration, eventType, ownerId, instanceKey, transitionStableId)`. Only identical identities coalesce. The event schema declares a total payload merge; the default is replacement by the greater `tokenSequence` (the precisely defined newest event), never an ad hoc byte overwrite.
- Retrying captures a fresh snapshot and reevaluates applicability and guards.
- Every optional, mandatory-expiry, and system-cleanup record stores the immutable typed key `(workClassRank,workScopeRank,classPriority,producerStableId,workKind,typedIdentity)`. Comparison is lexicographic descending using each field's declared unsigned numeric, stable-ID, or frozen-enum order; raw structure bytes, padding, endianness, and a separately serialized byte key never participate. Frozen class ranks are `2=SYSTEM_CLEANUP`, `1=MANDATORY_EXPIRY`, `0=OPTIONAL`; frozen scope ranks are `2=GLOBAL`, `1=MAP`, `0=SLOT`. Expiry and optional work are always `SLOT`. These ranks are unrelated to `SYSTEM` lifetime or the `SYSTEM_SAFETY` layer channel. System cleanup priority/producer/kind/scope come from its checked cleanup-kind registration; expiry values come from the authored recovery action; optional values are dispatch priority/transition ID/event type.
- `typedIdentity` is a scope-discriminated, class-tagged union; a field absent from a scope/kind is not represented and is never invented as zero. Expiry is exactly `(runtimeEpoch,slotIndex,slotGeneration,ownerId,instanceKey,entryGeneration,timerGeneration,recoveryTransitionStableId)`. Optional is exactly `(slotIndex,slotGeneration,eventType,ownerId,instanceKey,transitionStableId,tokenSequence)`. System cleanup identities are kind-specific: global `BATTLE_TEARDOWN_PLAN` is `(runtimeEpoch,mapGeneration,cleanupKind,obligationGeneration,planEpoch,planGeneration,pendingBattleGeneration,scriptTaskGeneration,taskManagerGeneration)`; map-scoped `RETAINED_MAP_FALLBACK` is `(runtimeEpoch,mapGeneration,cleanupKind,obligationGeneration,retentionPlanEpoch,retentionPlanGeneration,claimSequence)` and contains no slot fields; slot-scoped `DESTRUCTIVE_SLOT_D01C` is `(runtimeEpoch,mapGeneration,slotIndex,slotGeneration,cleanupKind,obligationGeneration,destructiveGeneration,managerGeneration,objectGeneration)`; slot-scoped `MANUAL_PRESENTATION_OBJECT_LOSS` is `(runtimeEpoch,mapGeneration,slotIndex,slotGeneration,cleanupKind,obligationGeneration,presentationGeneration,ownerId,instanceKey,entryGeneration,timerGeneration,expectedManagerGeneration,expectedObjectGeneration)`. Scope is compared before cleanup priority/kind, and kind is compared before its remaining identity fields. Exact equality of the complete typed key is legal only for duplicate publication of the same mandatory identity and occupies one idempotent record without payload merge; identities from different scopes or kinds cannot coalesce. Optional coalescing instead uses its semantic identity without `tokenSequence`, applies the event schema's payload merge, and atomically replaces the old record with one newly ordered immutable key containing the selected sequence.
- Frozen scalar domains are `workClassRank:u8`, `workScopeRank:u8`, `classPriority:u16`, `producerStableId:u16`, `workKind:u16`, every stable ID/owner/instance/event enum `u16`, `slotIndex:u8`, and every epoch/generation/sequence `u32`. Out-of-range data is rejected, not truncated. The closed phase-0 cleanup registry is: `BATTLE_TEARDOWN_PLAN(scope=GLOBAL,kind=1,priority=0x0400,producer=1)`; `DESTRUCTIVE_SLOT_D01C(scope=SLOT,kind=2,priority=0x0300,producer=2)`; `RETAINED_MAP_FALLBACK(scope=MAP,kind=3,priority=0x0200,producer=3)`; `MANUAL_PRESENTATION_OBJECT_LOSS(scope=SLOT,kind=4,priority=0x0100,producer=4)`. Their complete identities are frozen above. Expiry `workKind=1` means recovery and its producer is `recoveryTransitionStableId`; optional `workKind=eventType` and producer is `transitionStableId`. No unregistered cleanup kind may publish.
- If the optional queue is full, an incoming optional token replaces the lowest optional token only when its complete key is greater; otherwise it returns `QUEUE_FULL`. No mandatory token can be evicted to admit optional work.
- Optional-work slot-generation mismatch drops that optional token as stale. A missing transition row or no-longer-matching guard consumes it with a diagnostic. Mandatory expiry and system cleanup do not use this optional-token rule. A newly arrived higher-key request is considered before an older lower-key request.

Every registered system-cleanup kind has one closed terminal-staleness policy; dispatch is by authenticated `cleanupKind`, never a generic stale drop:

| Cleanup kind | Frozen stale/mismatch terminal policy |
|---|---|
| `BATTLE_TEARDOWN_PLAN` | `TAKEOVER_AND_COMPLETE`: executor/boundary-task/environment or map-generation mismatch never drops the plan or lease and immediately routes the obligation to resident mandatory cleanup. Executor authority is replaced independently; boundary cells still require actual unwind/exact resident ACK or proved quiescent `RETURN_CANCELED`, never while the callback/command may execute. Cleanup avoids stale pointers, completes reserved cleanup/task release/unload, and lets the coordinator release once at `UNLOADED→RELEASED`. An already `RELEASED` exact tombstone is diagnostic consume; a different plan tuple is untouched. |
| `RETAINED_MAP_FALLBACK` | `CLAIM_FALLBACK_AND_RELEASE`: a wrong/stale invocation rejected before exact claim is a no-op. Mismatch found after claiming the exact unconsumed plan runs plan-scoped D01c without stale pointer access, releases every ledger cell once, marks `CONSUMED`, and never touches a newer plan. An already consumed/released exact tombstone is diagnostic consume. |
| `DESTRUCTIVE_SLOT_D01C` | `CONSUME_IF_ALREADY_INVALIDATED_ELSE_DEFER`: if the recorded old slot is already destructively invalidated/reused, consume/tombstone without touching the replacement slot/object. If its exact quarantined logical slot remains current, retain mandatory work until physical/sidecar cleanup completes; stale manager/object identity suppresses pointer access, not logical cleanup. |
| `MANUAL_PRESENTATION_OBJECT_LOSS` | `LOGICAL_CLEANUP_OR_DEAD_SLOT_CONSUME`: for a current logical tuple, clear logical presentation ownership objectlessly and retain quarantine until authenticated rebind; stale manager/object identity permits no pointer/timer/pose write. D01c, manager replacement, or a dead/reused logical slot consumes/tombstones the exact obligation with no new expiry and no replacement-object access. |

Timer zero does not enter the four-entry optional queue. It atomically marks an `EXPIRY_PENDING` record with its exact identity, authored recovery transition, and typed key above. An expiry whose complete handle is later stale is consumed diagnostically without affecting a replacement; otherwise it remains mandatory until commit. System cleanup likewise records its complete authenticated typed identity/key and remains pending until its registered terminal policy completes. One resident scheduler domain spans all overworld slots and map/system work; the globally greatest key is head-of-line. If it returns `BUSY`, it remains pending and no lower-key work from any slot executes in that pass. The timer stays at zero and cannot decrement, refresh, be dropped, or be evicted. System cleanup sorts above expiry, and expiry above optional BUSY, solely by `workClassRank`. Compatible expiry batching includes only descending-key records and cannot change the chosen leader or remaining order. A fixed bounce “expire tired now” request creates exact-handle mandatory work in the spawns consumer; it never writes a shared timer or removes by owner/profile.

## Slot, Map, Battle, and Save Lifetime

Runtime layers belong to one live spawn-slot generation. They do not belong to a species, map object pointer, or profile globally.

### Slot reuse and despawn

- Every destructive slot reset, successful capture, defeat, distance despawn, follower recall, or reuse clears all runtime layers before the slot can be assigned again. Player-ball capture preparation is non-destructive and follows the separate target-local rule below.
- The destructive `live -> empty` invalidation advances `slotGeneration` exactly once, invalidates every outstanding handle, and clears effective caches and transition diagnostics associated with the old encounter. New assignment into that empty slot does not advance it again.
- A new encounter starts from its resolved controller base state plus matching static modifiers only.
- Current `encounterGeneration` continues to protect battle work; runtime-layer handles use the dedicated `slotGeneration` plus runtime-handle epoch contract.

### Map-header and object-manager changes

- A same-map object-manager replacement follows current context-loss parity, not retained-real-map policy: it clears every runtime layer and timer to calm in one all-slot transaction without advancing `slotGeneration`, consumes/tombstones every old-manager presentation token and `MANUAL_PRESENTATION_OBJECT_LOSS` obligation, advances the resident nonzero `managerGeneration` before publishing the replacement manager, discards all remaining object/task ownership, authenticates the replacement manager/objects, and rebuilds from the captured base/static encounter identity. It does not preserve awareness, tired, pickup, or another runtime layer merely because the map ID is unchanged. Reuse of the same object-generation value by the replacement manager cannot authenticate or coalesce with an old-manager token or cleanup identity.
- The frozen `void prepareMapHeaderChange(state, mode)` ABI implements a generation-keyed `PREPARED`/`FALLBACK`/`CONSUMED` two-phase protocol. The resident retention coordinator owns the plan carrier `(retentionPlanEpoch,retentionPlanGeneration,state,plan)`, initializes both counters to nonzero `1`, and includes both in every plan authentication. The virgin plan uses generation `1`; after a plan is `CONSUMED`, the next `PRESERVE` advances generation exactly once, and no request may overwrite an unconsumed plan.
- The resident map caller separately owns one fixed `RetainedMapCallbackClaim` with `(EMPTY|PUBLISHED|CLAIMED|COMPLETED|ACKED,retentionPlanEpoch,retentionPlanGeneration,mode,claimSequence,runtimeEpoch,stateIdentity,sourceMapGeneration,sourceManagerGeneration,requestedDestinationMapId,installedDestinationMapGeneration,installedManagerGeneration,resultMarker)`. Before either fixed callback invocation, the caller allocates a fresh nonzero `claimSequence`, writes the exact expected plan tuple and mode, then publishes `PUBLISHED` last. The callback may act only by one atomic compare/exchange of that complete identity from `PUBLISHED` to `CLAIMED`; it records `COMPLETED` before returning, and the caller acknowledges only its exact completed sequence. After the `PRESERVE` claim is ACKed, the carrier may return to `EMPTY` only to publish `CANONICALIZE` for that same plan tuple; the plan retains the last mode/sequence tombstone. A direct call, duplicate claim, wrong mode, wrong tuple, or old sequence is a diagnostic no-op and cannot inspect, consume, release, or mark another plan.
- For `PRESERVE`, the resident caller allocates the plan tuple before publishing its claim. The callback captures source map/manager/slot/object generations, precomputes and reserves the complete retained-map plan, and publishes both the plan's `PREPARED` marker and the claim's matching result before returning. If planning, reservation, authentication, or storage fails after exact claim, it publishes `FALLBACK` for that same tuple before returning. The caller performs middle writes only after its exact completed claim reports `PREPARED` or `FALLBACK`. A rejection before `PUBLISHED→CLAIMED` is a complete diagnostic no-op: it performs no middle write, quarantine, D01c, plan mutation, or reservation release. Once the exact current invocation has claimed, returning with the claim still `CLAIMED`, publishing malformed/wrong completion, or otherwise failing exact `COMPLETED` publication quarantines and takes D01c only for that claimed plan, with no middle writes. After infallible middle writes, the caller stores installed destination generations and publishes a fresh `CANONICALIZE` claim for the same plan tuple. Thus the second half cannot consume merely whichever coordinator plan is current.
- Retention reservations use an embedded fixed ledger. The closed per-slot kinds are `OBJECT_COMMAND`, `MOVEMENT_STABILIZATION`, `PRESENTATION_RESTORE`, and `STACK_REBIND`, each with maximum one cell per slot: `OW_WILD_RETENTION_SLOT_CELLS_PER_SLOT=4`. Closed global kinds are `MAP_MANAGER` (1), `OVERLAY_PIN` (4, exactly overlay IDs 149–152), `BEHAVIOR_DATA_SNAPSHOT` (1), and `CLEANUP_PUBLICATION` (1): `OW_WILD_RETENTION_GLOBAL_CELLS=7`. With source-frozen `OW_WILD_MAX_SPAWNS=10`, `OW_WILD_RETENTION_LEDGER_CAPACITY = 10*4+7 = 47`; static assertions freeze all four values and each per-kind maximum. Before the first lease acquisition, `PRESERVE` enumerates and deduplicates the complete required keys into a 47-cell scratch array. Only exactly equal typed `(reservationKind,slot-or-resource identity,authentication generations)` keys coalesce. A 48th distinct key publishes `FALLBACK/RETENTION_LEDGER_CAPACITY_EXCEEDED` before acquiring any lease; there is no heap spill, truncation, eviction, replacement, or kind multiplicity beyond the table. The resident caller may perform ordinary infallible middle writes only after observing that exact completed fallback claim. A ledger cell is claimed before its external acquire begins, so every lease always has one owner cell. Later failure transfers all cells intact to `FALLBACK`. Published count/keys/held identities are immutable; release changes each `HELD` cell to `RELEASED` once.
- Between callbacks, resident map-ID/object-manager/object writes are the only permitted middle phase. The fixed callback's C return type is `void` and therefore conveys no status; any enclosing `BOOL` reports only function/overlay availability, never `PREPARED` versus `FALLBACK`. After the callback returns, the resident caller re-reads the claim carrier. If its invocation never left `PUBLISHED`, or a stale/wrong-mode/wrong-sequence invocation was rejected before claim, the caller tombstones only that rejected invocation and performs no middle write, quarantine, D01c, or plan mutation. If the exact carrier is `COMPLETED`, the caller authenticates and ACKs it; only an exact `PREPARED` or `FALLBACK` result authorizes unconditional, non-allocating, infallible middle writes. If and only if the exact current invocation reached `CLAIMED` but returned without a valid exact completion, the caller quarantines and routes that claimed plan through D01c/release. An unrelated stale completion tombstone is a no-op. Resident writes do not mutate layers or consume the plan marker.
- `CANONICALIZE` first claims its exact caller carrier, then authenticates the published `(retentionPlanEpoch,retentionPlanGeneration)` plus captured source and installed destination generations and consumes it exactly once. Failure to claim because mode, sequence, tuple, or state is missing/stale/wrong/replayed is a diagnostic no-op and cannot run D01c or touch the coordinator's current plan. After a current claim succeeds, `PREPARED` executes its reserved infallible canonicalization; `FALLBACK`, a captured/installed authentication mismatch inside that exact claimed plan, or a missing second callback executes D01c for that plan before later work. Every terminal path calls one tuple-authenticated `ReleaseRetentionPlanReservations` operation that claims each ledger cell, releases it exactly once, atomically sets `reservationsReleased`, marks the plan `CONSUMED`, and completes the exact callback claim. Replay observes only the consumed/released plan and mode/sequence tombstones. Missing-callback maintenance synthesizes and atomically claims a system-owned claim for that exact plan tuple; it never consumes the coordinator's merely-current plan. No unrelated claim/plan can overwrite an unconsumed predecessor. Before `claimSequence` or plan-generation reuse of `1`, the coordinator drains and releases the exact outstanding claim/plan, advances `retentionPlanEpoch`, and only then restarts; an old claim replay after a newer plan exists is stale.
- The retained plan canonicalizes a pending alert token to its intended transition, then discards presentation/task ownership.
- On any real map-context change for a retained logical slot, remove every `CLEAR` layer, including pickup/throw; retain only `PRESERVE_LOGICAL` entries and their logical timers; discard old `SYSTEM` entries.
- Capture timer remaining values before presentation canonicalization. Consequently, a retained `EMOTING` token whose end transition is `TIRED` canonicalizes with zero remaining ticks and returns calm on the first resumed eligible timer tick. This is one atomic, handle-safe action: preflight authenticates the presentation token and the exact candidate `(runtimeEpoch, slotGeneration, ownerId, instanceKey, entryGeneration, timerGeneration)`, commits the pending end delta, sets only that candidate timer to zero, and records its mandatory expiry. It never writes a slot-global/current-tired timer. A stale or ambiguous target aborts the retained-map transaction before the point of no return. This phase-0 quirk applies only to the real retained-map preserve/canonicalize path; it is not repaired into a full timer.
- Install the new immutable destination context, increment static-context generation, reselect the controller by explicit assignment precedence, re-resolve node bindings/static modifiers, remove preserved candidates that are no longer applicable, ask registered systems for fresh `SYSTEM` entries, and perform one recomposition/transition transaction.
- Preserve the encounter-captured `spawnPolicyId`, `populationPolicyId`, population-group ID, and population limit. They describe how/under which quota this already-existing encounter was created and cannot change on a retained map. Destination static resolution may compute `wouldSelectSpawnPolicyId` and `wouldSelectPopulationPolicyId/group` for diagnostics; a mismatch is reported but never adopted, never relocates the object, and never moves its population accounting.
- A `PRESERVE_LOGICAL` layer preserves intent, not object pointers, movement commands, presentation tokens, throw relations, queued battles, or cache entries.
- `OW_WILD_MAP_HEADER_CHANGE_DISCARD`, destructive context loss, or a map change that does not retain the logical slot clears all layers with the slot regardless of policy.
- Runtime layers never migrate by matching species into an unrelated newly spawned slot on the destination map.

### Battle handoff and return

Five source routes may originate battle work, and route identity is carried through reservation/diagnostics even though all successful routes converge on the same all-slot transaction:

1. **Contact scan:** battle grace, pending-battle, and just-spawned gates pass; a non-follower current object touches the player; the effective node is attentive/active and its battle trigger is `CONTACT`; all touch and common stability gates pass.
2. **A-button facing:** the follower selector/release gate is clear, a physical A-button rising edge resolves a valid battle-talk slot, no different facing object owns the interaction, and the common immediate-or-queue gates pass.
3. **Script/talk prime:** explicit talked-object or last-talked identity may bypass finder-level excluded/spawn-run/phantom-hidden filters, while facing fallback may not. Prime still rejects follower, pending battle, player-ball work, any throw target/participant, non-current identity, or unstable player, but deliberately skips slot-stability so the all-slot stabilization transaction can canonicalize it. This route is invoked by an already-running authenticated script task; it authenticates that script context but does not reserve, create, or defer another script task.
4. **Active RAM impact:** the effective active state declares `RAM_CRASH`, the impact tile contains the player or active follower, and the RAM-specific gates pass. The frame-task path may prime without a movement reset and defer script publication; the ordinary path uses common immediate-or-queue. Successful entry owns crash feedback and RAM counter cleanup without inserting `ram-crash` tired.
5. **Throw landing:** an authenticated carried target lands on the player tile and the throw relation/target generations are current. This source path calls common immediate-or-queue directly and deliberately bypasses ACTIVE-state and `CONTACT`-trigger predicates. It retains `originKind=THROW_LANDING` through queue, reservation, and diagnostics.

Queued battle is shared retry machinery, not another origin route. `originKind` is exactly `CONTACT`, `A_BUTTON`, `SCRIPT_TALK`, `RAM_IMPACT`, or `THROW_LANDING`. The five values remain distinct even when they share immediate-or-queue and all-slot handoff machinery.

The accepted origin/subroute domain and return contract are closed. `CB` means `OVERLAY_CALLBACK_RETURN`; `SC` means `SCRIPT_COMMAND_RETURN`. A queue-only publication has no committed teardown plan and therefore no mask; when its retry is accepted, the accepted row below becomes authoritative.

| Origin | Accepted `originSubroute` | `requiredReturnMask` | Frozen execution/return order |
|---|---|---|---|
| `CONTACT` | `IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | Originating overlay/frame callback publishes CB ready, returns, and its resident caller ACKs CB before the reserved future script task may enter the battle command; that command publishes SC ready, returns, then the resident script dispatcher ACKs SC. |
| `CONTACT` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Initial queue-only attempt creates no plan. The later accepting overlay/frame callback follows CB return/ACK → future script-command return/ACK. |
| `RAM_IMPACT` | `ORDINARY_IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | Ordinary impact callback returns/ACKs CB before the future script command may run and return/ACK SC. |
| `RAM_IMPACT` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Initial queue-only attempt creates no plan; accepted retry follows CB return/ACK → future SC return/ACK. |
| `RAM_IMPACT` | `FRAME_TASK_DIRECT_PRIME_DEFERRED_SCRIPT` | `CB|SC` | The accepting overlay frame-task callback must return and receive CB ACK before its deferred/reserved script command may begin; SC ACK follows that command's actual return. |
| `A_BUTTON` | `IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | A-button overlay callback returns/ACKs CB before the future script command begins; SC ACK follows command return. |
| `A_BUTTON` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Initial queue-only attempt creates no plan; accepted retry follows CB return/ACK → future SC return/ACK. |
| `THROW_LANDING` | `IMMEDIATE_SCRIPT_CREATE` | `CB|SC` | Landing/frame callback returns/ACKs CB before the future script command begins; SC ACK follows command return. |
| `THROW_LANDING` | `QUEUED_RETRY_SCRIPT_CREATE` | `CB|SC` | Initial queue-only attempt creates no plan; accepted retry follows CB return/ACK → future SC return/ACK. |
| `SCRIPT_TALK` | `NESTED_EXISTING_SCRIPT_COMMAND` | `CB|SC` | The already-running script command calls the overlay prime callback synchronously. The inner callback publishes CB ready, returns, and its resident caller ACKs CB; only afterward may the outer script command publish SC ready, return, and receive SC ACK. No new script task exists. |

No other origin/subroute/mask tuple is valid. For future-script rows, SC execution before CB ACK is rejected. For nested `SCRIPT_TALK`, SC ready/ACK before CB ACK is rejected. Cleanup, task release, physical unload, and overlay unload are forbidden until both required cells are actually `ACKED` or their exact frames have independent resident quiescence proofs under `RETURN_CANCELED`; plan state or executor ownership alone can never prove a stack frame returned.

- Phase-0 parity intentionally mirrors the current global `ResetAllMovementCommands`: after a script-creating/deferred route's request is successfully reserved, or `SCRIPT_TALK` has authenticated its already-running script context, battle start applies one multi-slot transaction that removes every runtime layer with battle policy `CLEAR` across **all** live slots. Ordinary awareness, aggro, help-call, tired, modifiers, and their timers use `CLEAR` by default, so retained encounters return calm.
- A definition marked `PRESERVE_LOGICAL` may survive battle only as an explicitly reviewed behavior-change exception. Its object/task/presentation ownership is still discarded. `SYSTEM` definitions are freshly reevaluated after return.
- The pending encounter identity and static controller assignment remain, but no cache pointer or in-flight command survives handoff.
- `RETAIN` leaves the retained encounter at its recomposed post-clear base/calm node unless a declared exception wins.
- `FLED` first validates that the original encounter and field context were retained, then applies a new `battle-fled` tired candidate and fresh timer. It does not restore pre-battle awareness or another cleared layer.
- `DEFEATED` and `CAUGHT` clear the slot, all policies, and all handles.
- Deferred battle work continues to validate map, encounter, slot, and stack generations.

Battle request failure is mutation-free and intentionally improves on the current source. A route that creates or defers a script task must reserve/prime that handoff before the global clear transaction reaches its point of no return. `SCRIPT_TALK` authenticates the already-running script task and needs no new script-task reservation. Every route, including `SCRIPT_TALK`, must reserve teardown readiness for all script/task-manager/overlay work that the all-slot transition will detach or unload. Script reservation, teardown-readiness, or teardown-authentication failure leaves every layer, timer, counter, cache, command, presentation, overlay lease, and pending/queued identity untouched. At commit the lease transfers to the resident `BattleTeardownPlan`; transition finish cannot release it. Boundary-specific ready publication/`RETURN_PENDING`, exact resident-observed callback and script-command returns, aggregate `RETURN_ACKED`/proved `RETURN_CANCELED`, cleanup, task/resident release, and physical unload are separately authenticated milestones according to the closed subroute mask/order, and only `UNLOADED→RELEASED` releases once. Publishing and later teardown for a successfully reserved/authenticated route are required to be infallible, though an executor or boundary may be delayed; a platform path that cannot prove both must reject during preflight and may not cross the point of no return.

Player-ball capture preparation is a separate target-local parity transaction. On accepted impact it atomically clears every runtime layer and candidate timer for the target, applies D01a movement/presentation cleanup, and leaves the target at controller base/calm without advancing `slotGeneration`; unrelated slots are unchanged. Breakout therefore resumes calm. Successful caught finalization later performs the destructive `live -> empty` invalidation and advances `slotGeneration` exactly once.

### Follower, pickup, and throw

- Picked-up and follower behavior become `POSSESSION` state-candidate and/or modifier layers. They do not replace behavior class.
- Pickup removal reveals the next state candidate without reconstructing it.
- Follower recall clears the follower slot and its runtime layers.
- A later follower release installs into the already-invalidated empty slot generation and reconstructs only explicitly defined follower/controller layers; it does not advance `slotGeneration` again, copy stale handles, or copy arbitrary effects from the recalled slot.
- Throw reservations and presentation state remain runtime side effects, not profile fields.

### Save/load

- Runtime layers, owners, handles, state winner, and effect timers are not serialized.
- Existing explicitly saved encounter identity, such as saved shiny handling, may cause a new encounter to be reconstructed, but reconstruction starts from static data and controller defaults.
- A future persistent event must save its own game-state flag and reapply a layer through its owner after spawn. Raw layer arrays are never save data.

## Cache Contract

Static context resolution and dynamic stack composition use separate cache generations.

Each slot/runtime uses distinct counters:

- `slotGeneration`: changes exactly once on destructive live-encounter invalidation and invalidates handles, presentation tokens, timers, queued transitions, and deferred battle identity; assignment into the invalidated empty slot does not change it.
- `staticContextGeneration`: changes when the immutable context snapshot or loaded behavior-data generation changes. Supplying an identical already-current snapshot is idempotent.
- `layerGeneration`: changes exactly once for a successful batch whose stored layer or timer-instance set changes.
- `effectiveGeneration`: changes exactly once when normalized effective node/profile/controller values, derived primitives, or capability masks change.
- `timerGeneration`: belongs to one timer instance and changes when that timer is armed/replaced/cancelled, not on ordinary decrements.

Per live slot, cache at least:

- Resolved controller, spawn policy, population policy, and static modifier set/hash.
- Active-layer generation.
- Effective state profile ID.
- Effective state values and effective controller values.
- Derived behavior primitives and capability masks.
- Effective hash and field provenance in diagnostic builds.

Static cache invalidation is required when species, form, level, terrain, shiny state, map context, data generation, or controller assignment changes. Runtime apply/remove normally invalidates only dynamic composition.

Generation edge semantics are fixed:

- Idempotent apply, rejected delta, stale handle, `BUSY`, failed battle reservation, and guard no-match change no generation and invalidate no cache.
- A successful batch that changes a hidden/lower layer but leaves normalized effective output unchanged increments `layerGeneration` once, invalidates active-stack/provenance metadata, and leaves `effectiveGeneration` and capability caches intact after their key metadata is refreshed.
- A modifier-only change that alters speed, policy, locomotion, target, or any derived capability increments both layer and effective generations even when the node ID is unchanged.
- Timer decrement changes only remaining timer state. Timer expiry/removal is a normal batch and follows the rules above.
- Static-context change increments `staticContextGeneration`, invalidates assignment/node-binding/static-modifier/effective caches, rechecks preserved candidates, and increments `effectiveGeneration` only if the recomposed effective output changes.
- Capability/frame-work masks are invalidated whenever their derived inputs change, even if the effective state profile ID does not.

Every identity/cache generation is nonzero and has an explicit wrap invalidation; no counter may merely wrap to `1`:

| Generation | Required action before reuse of `1` |
|---|---|
| Behavior-data/static-data generation | Allowed to change only with zero live/pending work; clear every static/effective cache and diagnostic provenance reference. |
| `staticContextGeneration` | Clear assignment, node-binding, static modifier/timer-source, destination-diagnostic, and effective-cache valid bits for the slot. |
| `layerGeneration` | Clear active-stack/provenance/composition valid bits and every dependent effective/capability cache before restarting at `1`. |
| `effectiveGeneration` | Clear every cached hash, primitive/capability/frame-work mask, copied-value lease, and command-origin snapshot keyed by it before restarting at `1`; consumers must reacquire. |
| `entryGeneration` / candidate `timerGeneration` | Advance the slot's handle epoch (or destructively invalidate the slot), assign fresh nonzero generations to surviving entries/timers, and atomically rekey authenticated internal mandatory-expiry records while preserving remaining ticks/zero-pending state. Every previously returned external handle/token becomes stale; mandatory expiry is never lost. |
| Presentation/`actionGeneration`/`commandGeneration` and `tokenSequence` | Cancel/clear all matching action tokens, BUSY records, command completions, reservations, and action timers before restarting at `1`. |
| `commandSerial` | Before serial restarts at `1`, advance `commandGeneration` under its wrap rule and cancel/consume every outstanding completion carrying the old generation. No completion may authenticate by a reused serial alone. |
| Movement `chainGeneration` | The per-slot movement-chain owner/carrier follows the start/replacement/cancel rules above. Before reuse of `1`, cancel the active owner and clear every command, continuation, completion, direction/step/remaining/pause counter, and previous-tile lease keyed by the old generation. If cleanup cannot enumerate all dependents, destructively invalidate the slot; old chain artifacts are never rekeyed. |
| `staminaPolicyGeneration` | Invalidate every captured command-origin policy lease and cancel any completion that has not already charged; a later command must capture the restarted generation. |
| Per-slot aggro-bridge `publicationSequence` | Clear that slot's published request and consumer claim before restarting at `1`; an old bounce publication can never coalesce with or satisfy the restarted carrier. The separately mirrored slot generation follows `slotGeneration`, not this sequence. Other slots' pending requests are unchanged. |
| Per-slot aggro-bridge `retryGeneration` | Promote/drain the exact pending retry or destructively invalidate its authenticated source owner before restart. Never rekey a retry to a new owner/generation. |
| Pickup/throw relation generation | Clear both participants' relation handles, reservations, and presentation ownership before restarting at `1`; neither participant may retain a half-relation. |
| Object/manager/resource authentication generation | Cancel ordinary movement, shake, phantom, canopy, and presentation tokens before restart; dispatch every system-cleanup obligation through its registered stale policy rather than canceling it generically. Never write through a stale object pointer. |
| `encounterGeneration` | Cancel queued/deferred battle, projectile, capture, and legacy bridge identities that carry it before restarting at `1`. |
| Field `mapGeneration` | Invalidate ordinary object/presentation authentication, queued/deferred battle, capture/projectile, and bounce work carrying the old generation. Before restart, route retained-map and every system-cleanup obligation through its registered terminal policy. A `BattleTeardownPlan` survives as resident mandatory takeover until teardown/release completes; map-generation change never drops its lease. |
| `retentionPlanEpoch` + `retentionPlanGeneration` + callback `claimSequence` | The resident retention coordinator owns all three nonzero counters. Before either inner counter reuses `1`, atomically claim the exact outstanding mode/sequence/plan, force `PREPARED`/`FALLBACK` through D01c as needed, release every fixed-ledger cell exactly once, mark plan and claim consumed/ACKed, then advance the nonzero epoch. Only then may generation/sequence restart at `1`; every old claim/callback/maintenance replay is stale against the new plan. Epoch wrap recreates the coordinator only after the same drain. |
| `BattleTeardownPlan` epoch/generation | Before reuse, mandatory cleanup must replace any lost executor claim, obtain resident-observed `RETURN_ACKED` or prove `RETURN_CANCELED`, and complete cleanup/task-release/unload while the exact plan remains lease owner. Only the coordinator's authenticated `UNLOADED→RELEASED` transition releases once; then the epoch/generation may advance. A stale plan claim/return ticket cannot release the old or new plan. |
| `slotGeneration` | Wrap is handled only inside destructive `live -> empty` invalidation: advance the runtime-wide handle epoch, clear all handles/timers/actions/commands/queues for the now-empty slot, then restart at `1` before any later assignment. |
| Runtime-wide handle epoch | Destructively clear every slot and all handle/token/request state before restarting at `1`. |

The invalidation and new value are one critical operation. Any consumer that cannot be enumerated makes wrap a destructive global clear. This rule covers candidate, action, presentation, command, cache, context, encounter, slot, data, and epoch generations alike.

A behavior-data blob may be validated and staged while gameplay is live, but it may not replace the installed blob while any slot is live or any pending/queued/deferred battle, presentation, cleanup obligation, or runtime handle exists. Installation returns `DATA_BUSY` in that case. With zero live work, installation atomically swaps the validated blob, advances the behavior-data generation under the wrap rule above, and invalidates all static/effective caches before a new slot can be created.

Consumers may copy effective values for one operation, but may not retain a pointer across a transition, layer mutation, map-header change, battle handoff, or slot reset.

## Provenance and Diagnostics

The composer records enough provenance to answer:

- Which state candidate won and why.
- Which state candidates remained underneath it.
- Which modifiers applied or were skipped, and the skip reason.
- Which layer last set each exact field.
- Which ordered layers contributed to a relative/bounded field.
- Which normalization rule changed a composed value.
- The effective hash and active-layer generation.

Each slot exposes diagnostics for base state, active layers, owners, priorities, effective state, last transition reason, stale-handle count, duplicate-apply count, capacity overflow count, invalid-definition count, and cache status. A 16-entry transition ring buffer retains recent old/new controller-node/profile IDs, winning owners, reasons, and generation values.

## Worked Examples

### Bird active, rain, and tired

Initial data:

```text
controller base state: bird-chill
STATIC_CONTEXT modifier: flying-species (allowed tiles += canopy)
```

The awareness owner applies `bird-active` in `CONTROLLER_STATE`. Weather applies `rain-skittish` as a modifier, then stamina applies `bird-tired` in `TEMPORARY_EFFECT`:

```text
active state candidates:
  bird-active  owner=awareness  channel=CONTROLLER_STATE  priority=100
  bird-tired   owner=stamina    channel=TEMPORARY_EFFECT  priority=100  <- winner

modifiers:
  flying-species
  rain-skittish

effective result:
  bird-tired + flying-species + rain-skittish
```

Removing the awareness layer from the middle does not disturb tired or rain. If awareness remains and a script/manual delta removes only the tired handle, recomposition selects `bird-active` and produces:

```text
bird-active + flying-species + rain-skittish
```

No active-state snapshot was saved and no tired inverse was applied. This demonstrates mechanical middle-layer removal, not phase-0 timer expiry: `LEGACY_RETURN_CALM` expiry removes tired and awareness together, yielding `bird-chill + flying-species + rain-skittish`. A controller using `REVEAL_UNDERLYING` opts into the active-reveal result as a parity exception.

### Aggro, tired, and forced sleep

```text
bird-active  owner=aggro         channel=CONTROLLER_STATE priority=200
bird-tired   owner=stamina       channel=TEMPORARY_EFFECT priority=100
bird-asleep  owner=forced-sleep  channel=TEMPORARY_EFFECT priority=200 <- winner
```

Asleep wins by priority within the higher channel. Tired and aggro remain active. Removing forced sleep reveals tired. Removing tired then reveals active. Removing aggro returns to the controller base state.

A rain modifier can declare that it does not apply to the asleep role. It remains stored but is reported as skipped until another state wins.

The required hidden-timer fixture adds a stable carried candidate above all three layers, with no pickup/throw presentation gate currently active:

```text
bird-carried owner=pickup channel=POSSESSION <- winner
bird-asleep owner=forced-sleep remaining=2 CONTINUE_WHILE_HIDDEN
bird-tired  owner=stamina      remaining=4 PAUSE_WHILE_HIDDEN
```

Two eligible gameplay ticks leave tired at `4`, advance forced sleep to zero, and commit required removal of only the exact forced-sleep handle while carried remains effective. Removing carried later reveals tired with `4`. This is distinct from the active pickup/throw animation gate: while that presentation token owns the slot, both gameplay timers suspend and only the presentation action timer advances.

### Picked up over scripted behavior

```text
scripted-guard  owner=event-42  channel=SCRIPTED_FORCE priority=80
picked-up       owner=pickup    channel=POSSESSION     priority=200 <- winner
```

Pickup wins while the actor is carried. Releasing it removes only the pickup owner's layer, revealing the still-active scripted state. Population identity never changed during either transition.

### The same modifier from different owners

If `slow-by-one` sets `allowMultipleOwners=TRUE` and `allowMultipleInstancesPerOwner=FALSE`, weather and a status system may both apply it:

```text
slow-by-one owner=weather instance=0
slow-by-one owner=status  instance=0
```

Both deltas apply in deterministic owner-ID order with `instanceKey=0`. Reapplying the weather entry is idempotent. Removing the weather handle leaves the status slow active. If multiple owners are disabled, the second owner receives `DEFINITION_OWNED`; if per-owner instances are disabled, a nonzero key is invalid.

### Exact, relative, and bounded writes

Given state speed `2`:

```text
STATIC_CONTEXT: SET speed 3
TEMPORARY_EFFECT priority 20: ADD speed -2
SCRIPTED_FORCE priority 10: ADD_AT_LEAST speed -1, floor 2
```

The ordered result is `3 -> 1 -> 2`. Removing the temporary effect recomposes `3 -> 2`; it does not add `2` back to the old result. Field provenance reports the state base, the static exact writer, and both ordered numeric contributors.

## Required Invariants

The runtime and validator must enforce all of the following:

1. Every live slot has exactly one valid controller and one complete base state.
2. Every effective state ID references a complete state profile.
3. A modifier never changes state identity or `behaviorKind`.
4. A state-candidate definition never carries a partial patch.
5. Active layer order is independent of apply time and source array position.
6. `(ownerId, instanceKey)` is unique per slot.
7. No subsystem removes another owner's layer by profile ID or display name.
8. A stale handle cannot mutate a reused slot or replacement entry.
9. Runtime layer count never exceeds eight; overflow never evicts.
10. Removal recomposes from immutable source data and remaining layers.
11. Normalization runs after the full fold, never between layers.
12. A failed composition or unsafe transition leaves the previous live result intact.
13. Spawn, population, membership, identity, and transition-topology fields are unreachable from runtime modifier masks.
14. Presentation phases cannot become the authoritative behavior state.
15. Population-group identity does not change when state or possession layers change.
16. Inactive slots contain no runtime layers, effective cache, owner entries, or valid handles.
17. Cache keys include both static-data generation and active-layer generation.
18. No consumer retains an effective-profile pointer across a possible stack mutation.
19. Entry and exit side effects run at most once per committed effective-state change.
20. A modifier-only change does not spuriously rerun state entry/exit actions.
21. Semantic-role filters read the winning controller node, never descriptive profile tags.
22. A batch is order-independent, prevalidated at final capacity, and increments layer generation at most once.
23. Every timer is bound to one owner/instance/entry generation and cannot remove a replacement entry.
24. Phase-0 tired expiry commits its calm-reset owner removals in the same batch as tired removal.
25. Map and battle lifetime are definition metadata; object/task handles never survive a logical preserve.
26. All BUSY/error decisions precede transition side effects, and every post-point-of-no-return required operation is infallible; rollback is not a permitted post-PONR strategy.
27. Transition guards in one dispatch pass read one immutable snapshot and only the highest deterministic matching row commits.
28. Idempotent, rejected, stale, BUSY, and no-guard-match requests do not change generations.
29. The checked-in live-runtime verifier rejects presentation data as behavior authority. `movementPresentationStates` is byte-sized for ABI stability, is accessed only through the typed `OverworldWildSpawns_GetMovementPresentationState`/`OverworldWildSpawns_SetMovementPresentationState` boundary, and has no `CHILL`/`ACTIVE`/`TIRED` compatibility values. The source mutation fixtures reject direct field access and numeric presentation comparisons.

## Validation Requirements

The generated data validator and editor must reject:

- Zero, duplicate, or dangling stable IDs.
- Incomplete state profiles.
- Modifiers with `behaviorKind` or forbidden target paths.
- State-candidate definitions with patch fields.
- Unsupported operators for a field.
- Both minimum and maximum operators on the same field in one layer.
- Invalid enum, boolean, numeric, distance, and cross-field values.
- Controller transitions that reference missing owners, states, definitions, or safe action IDs.
- Controllers without a valid base state or spawn policy.
- Population policies without stable group identity.
- Definitions assigned to `SYSTEM_SAFETY` by ordinary authored content.
- Multiple instances for definitions that disallow multiplicity.
- Controller paths whose documented maximum simultaneous runtime layers exceed eight.
- Exact candidate selectors with a zero/missing controller ID, dangling node, or mismatched controller applicability filter.
- Semantic selectors with more than one matching bound node in any eligible controller. Zero matches are rejected for a definition explicitly scoped to that controller, but are allowed for a broad portable definition and mean `NOT_APPLICABLE` there.
- Fallback tired context partitions that cannot lower into finite disjoint
  existing-matcher cells, leave a context uncovered, or allow multiple bindings.
- Noncanonical origin or `(hasRequiredOwnerId,requiredOwnerId)` tag/value pair;
  missing/invalid generated metadata; any definition/runtime copy mismatch;
  any generated wrapper whose exact mapping is not `FLED→battle-fled`,
  `RAM_CRASH→ram-crash`, `THROW_RECOVERY→throw-recovery`, or absent-origin
  generated-stamina→`stamina`; any ordinary authored/shared definition carrying
  required-owner metadata; any runtime owner unequal to a present required
  owner; any generated tired wrapper with either multiplicity flag set or any
  generated tired operation/runtime entry with nonzero `instanceKey`; mismatch
  between route, wrapper, entry, or recovery origin; any stamina
  wrapper/entry carrying a present discriminator or any stamina table row;
  missing or duplicate
  imperative-tired translation rows for any
  `(tiredOriginKind,destinationControllerStableId,authoredTiredBound)` key;
  dangling, wrong-origin, wrong-branch/controller/node wrappers; or a fallback
  row whose destination has no exact fallback binding.
- `LEGACY_RETURN_CALM` recovery sets that can reveal a lower active-intent node.
- Indefinite timer sentinel 255 on a non-asleep candidate, or arithmetic that crosses the sentinel.
- Missing/invalid map policy, battle policy, hidden-timer policy, or timer clock.
- Ambiguous batch operations addressing the same owner/instance key.
- Duplicate transition IDs or non-deterministic dispatch priorities.
- Duplicate static action IDs or static action tuples whose complete ordering key is equal.
- Shallow controller duplication when controller-local definitions, selectors,
  node/owner/action IDs, backlinks, or applicability would need remapping; an
  ordinary authored closure must use deep copy. Importer-owned or generated
  required-owner/tired-origin closures reject both editor modes and require
  importer regeneration.

The editor may warn rather than reject deterministic equal-priority conflicts,
unreachable states, and missing recovery paths. Global Save blocks on material
whole-graph validation failures before writing V40 source or generated data.

## Historical One-Time V39 Derivation

The rules in this section document how the checked-in V40 model was originally
derived and parity-checked. The derivation is complete. These rules do not
authorize a V39 runtime reader, V39 writer, projection generator, member-21
payload, or dual-schema compatibility window.

The version-39 derivation was deterministic and initially one-to-one:

- Each assignable legacy class profile produces a controller with a bound `CALM` node and optional `ATTENTIVE`/authored-`TIRED` roster nodes, plus separate complete state profiles, spawn policy, and population policy. A legacy `NONE` behavior leaves the authored optional node unbound; a matching kind override may bind/enable it, and a later `NONE` kind write unbinds it. The separately generated `CUSTOM/FALLBACK_TIRED` node remains exact-route-only for the imperative routes defined above.
- `OW_WILD_BEHAVIOR_CLASS_PICKED_UP` is exempt from that ordinary class/controller import. Resolve its class profile exactly as source does—skip **all** ordinary override rows—project its chill fields into one non-AI complete `CARRIED` system profile, and generate the `POSSESSION` candidate wrapper used by pickup. Do not generate a spawn assignment, population identity, or ordinary static-rule target for the pseudo-class. Import the controller-local `CARRIED` node/reference into each pickup-compatible controller with deterministic IDs derived from `(controllerStableId, carried-templateStableId)`.
- Follower import first performs the ordinary species/class/static fold, then force-applies exactly the semantically identified stable legacy `Follower Pokemon` override at its legacy priority even though its matcher is `TARGET_DISABLED`. Zero or multiple records with that semantic identity are a migration error. It generates the follower spawn policy plus controller-local `FOLLOWER` node and `SYSTEM` possession definition; it does not make the disabled override a generally matching static rule and does not consume ordinary population limits unless explicitly authored.
- Forced-asleep import first discovers the unique dormant row by semantic identity `OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP`, then captures its order as `forcedRowOrdinal`; the number is never lookup identity or a stable-ID input. Version-39 source evidence is one-based ordinal `10`, zero-based source index `9`. For each target controller/context, one legacy ordered loop forces that semantic row when the loop reaches the captured ordinal, applies every normal match before/after exactly once, and normalizes once. The importer must not normal-fold first and append the forced row: a row with ordinal greater than `forcedRowOrdinal` may replace a forced-row field. Zero/multiple semantic rows are migration errors. The result materializes exactly one controller-local `ASLEEP` node and one semantic wrapper with `CONTINUE_WHILE_HIDDEN`/`REMOVE_SELF`, with either context-scoped complete post-loop `BIND_NODE` variants or one pre-loop binding plus replicated ASLEEP-scoped actions—never both.
- The default class assignment receives priority `0`. Legacy generic class rule ordinal `i` becomes explicit assignment priority `0x1000 + i`. Legacy species-class rule ordinal `i` becomes `0x2000 + i`, preserving the current “all generic, then all species; later wins” result without runtime array-position identity. Generated stable rule ID is the final tie-break only.
- Legacy override zero-based source index `i` becomes explicit static priority `0x4000 + i`; its human-facing one-based ordinal is `i + 1`. All migrated rule application uses the stored priority; neither displayed ordinal nor later serialized position is identity.
- A legacy override write to `chillState`, `attentiveState`, or `tiredState` cannot become a modifier. For each controller it can target, a non-`NONE` write creates a complete profile variant that differs in the addressed role's `behaviorKind` and emits a static node binding for `CALM`, `ATTENTIVE`, or `TIRED`; a `NONE` write emits an unbind. Later matching kind writes replace earlier bindings at explicit priority. Unbinding `CALM` is invalid because the base must remain runnable.
- Every other chill-prefixed field becomes a static modifier scoped to semantic role `CALM`; every attentive-prefixed field becomes role `ATTENTIVE`; every tired-prefixed field becomes role `TIRED`.
- Shared movement fields become one modifier with role mask `CALM|ATTENTIVE|TIRED`, except current source-specific selection is preserved: `hopSpinSpeed` targets `CALM|TIRED`, `attentiveHopSpinSpeed` targets `ATTENTIVE`, and fields with a documented single-state consumer retain that scope.
- Controller scalar writes (`alertState`, `alertEmote`, `alertTime`, `alertness`, `stamina`, `alertRange`, `alertChance`) become typed static controller-value modifiers at the same priority. `alertTime` remains the controller's alert-presentation duration and never becomes a recovery timer. Every `restTime` write becomes an ordered candidate-timer-source action: legacy `SET` preserves the byte, legacy `ADD` clamps after that operation to `0..64`, and bounded/compound forms are rejected. After the full fold, a bound non-`ASLEEP` tired result of zero is repaired to finite `1` even when produced by a late `SET(0)`; sentinel conversion runs only after that repair. `alertSpecialAction` becomes the typed hook bindings defined above, never a numeric callback field.
- Spawn writes become ordered spawn-policy bindings/patches. `overworldLimit` becomes an ordered population-policy binding with a stable population-group ID derived from the migrated override stable ID, not its array offset.
- Exact, relative, at-least, at-most, and compound relative-bound operators are preserved on the split target field and priority. The migration compiler rejects an operator that is no longer legal for that typed field.
- Overlapping matches all remain active. Controller assignment chooses one explicit winner; role bindings choose the last explicit priority; modifiers all fold ascending. Nothing relies on serialized order after migration.
- `profileId` is not reused as a stable entity ID unless the migration can prove uniqueness and semantics; generated stable IDs are preferred.
- Follower, picked-up, forced-asleep, phantom, canopy, RAM, playful, and aggressive families receive explicit parity fixtures.
- The one-time importer may coalesce exactly identical bodies only through its
  explicit identity-collapse mode. Ordinary V51 authoring never infers shared
  ownership from equal values; authors choose shallow sharing or deep identity.

The special imports are deterministic and bypass generic static matching only through these named recipes:

| Imported family | Complete profile/node | Typed modifier | Spawn/population policy | Candidate wrapper | Owner semantics |
|---|---|---|---|---|---|
| `CARRIED` | Create one complete reusable system profile from the picked-up row's calm/non-state values. Canonicalize the legacy marker kind `NONE` to runnable `IDLE`; force locomotion, target, battle trigger, and state-owned movement capabilities off. Bind each compatible controller-local `CARRIED` node to that profile. | None. Pass-through, synchronized coordinates, render/shadow state, and throw relations are transition-owned resources, not modifier fields. | None; carrying is never a spawn/population reassignment. | Generated `POSSESSION` candidate, priority `200`, semantic selector `CARRIED`, no timer, `CLEAR/CLEAR`. | `(ownerId=pickup.carrier, instanceKey=carrierSlotIdentity)`; apply/remove authenticates both participant slot generations and the relation generation. |
| `FOLLOWER` | For each compatible controller, create a controller-local `FOLLOWER` node from its normally resolved `CALM` profile, then replace the kind/target/front-mask values with the forced follower record (`CHASE`, `NEXT_TO_PLAYER`, front-only). | A follower-role modifier preserves `chillSpeed AT_LEAST 2` and controller `alertChance SET 0` in the legacy operation order. | Generate `APPEAR_HOP` plus `ONE_TILE_BEHIND_PLAYER` and the documented follower placement fallback. No ordinary population policy unless the follower assignment explicitly opts in. | Generated `POSSESSION` candidate, priority `100`, semantic selector `FOLLOWER`, no timer, `SYSTEM/CLEAR`; it is recreated only after follower identity is authenticated. | `(ownerId=follower, instanceKey=0)`; recall destroys the slot, and release emits a fresh entry rather than copying a handle. |
| Forced asleep | For each eligible controller, create exactly one controller-local `ASLEEP` node from one ordered legacy loop in which the forced row matches at its original ordinal and later matching rows still apply. Represent context differences with either complete post-loop `BIND_NODE` variants or one pre-loop binding plus replicated actions; never both for one field namespace. | Only under the pre-loop-binding strategy, replicate ASLEEP-scoped modifiers/timer actions with original matchers/ordinals/order/priorities. Under post-loop bindings, none of those fields are reapplied. Legacy `stamina=1` is timer enablement, not a controller-stamina patch. | None. | Generated `TEMPORARY_EFFECT` candidate, priority `200`, semantic selector `ASLEEP`, duration `4`, `CONTINUE_WHILE_HIDDEN`, `REMOVE_SELF`, `PRESERVE_LOGICAL/CLEAR`. It remains dormant until an authenticated caller applies it. | `(ownerId=forced-sleep, instanceKey=sourceStableId)` with per-owner multiplicity enabled; expiry removes the exact handle only. |

Generated priority values above are stored definition data, not caller-supplied priority. Generated stable IDs and controller-local node/profile IDs come from a deterministic migration namespace keyed by `(legacyDataVersion, controllerStableId, importedFamily, role)`; serialized array position is not identity.

For every golden context, the derivation first ran the version-39 resolver to a
fully normalized 72-byte result and recorded the legacy behavior-limit key. It
then resolved the generated controller, node bindings, modifiers, spawn policy,
and population policy and compared the split result role by role. A kind-binding
variant began from its class role's complete state values; all matching non-kind
modifiers were then folded over the winning binding, so an earlier speed write
survived a later kind write exactly as it did in the flat resolver.

The retired old-versus-new oracle compared effective fields, derived primitives,
spawn behavior, transition results, population grouping, typed hooks, and
special-family side effects across contexts and event sequences.
`attentiveAvoidPreviousTile` was compared by observed behavior, not dead-byte
equality, using the taxonomy above. Runtime validation now targets only the
canonical V40 model and blob.

## Implemented V51 Authoring Contract over the V40 Wire

V51 is the editor/API format. It preserves the validated V40 runtime wire format:
Global Save converts the V51 authoring transaction into one canonical V40 model,
encodes the V40 blob, decodes it again, merges only approved authoring metadata,
and requires semantic round-trip equality before replacing any file. V51 does
not introduce a second runtime model or restore flattened-profile compatibility.

The Profile Deck has first-class **State Profiles**, **Controllers**, and
**Modifiers** views:

- A state profile is one complete typed state. There are no chill/active/tired
  tabs or inherited runtime values. Names and descriptive tags remain
  presentation/search metadata only.
- A controller binds complete state profiles to controller-local nodes and
  owns scalar defaults, policies, transitions, guards, atomic stack operations,
  transition/recovery actions, and state-candidate applicability and lifetime.
- A modifier definition is independently authorable runtime/editor data. It
  owns applicability, channel, priority, multiplicity, map/battle lifetime, and
  a contiguous explicit operation order. Its typed operations are folded after
  the winning complete state without changing state identity.

### Explicit body identity and duplication

Profile identity and state-body identity are separate. V51 never merges equal
bodies merely because their bytes happen to match:

- **Shallow duplicate** creates a new profile identity that references the same
  body ID. Editing any alias visibly edits all profiles sharing that body.
- **Deep duplicate** creates both a new profile identity and a new body ID. It
  remains independent even when its initial values equal the source.
- Deleting or remapping a profile retires a body registry key only after the
  prospective graph proves that no profile still references that body. Conflicting
  edits to the same shared body in one transaction are rejected.

Controller duplication has a different closure boundary. A shallow controller
copy shares reusable references and is refused when controller-local transitions
would need remapping. An ordinary authored deep copy clones the controller-local
candidate closure and remaps its nodes, definitions, applicability, operations,
actions, recovery actions, and backlinks. Both modes refuse importer-owned
backlinks and generated required-owner/tired-origin families; those identities
must be recreated by importer regeneration and are never silently omitted.

Changing a controller node's profile binding first produces a mapping preview.
The preview names the old/new profile and body IDs, says whether the bodies are
shared or independent, and reports the affected node and authoritative backlinks.
The graph changes only after explicit Apply; a blocked preview cannot apply, and
Reset reverses profile-mapping changes already applied to the local draft.

### Effective state promotion and preview

The deterministic Stack Preview supports Saved, Draft, and Saved ↔ Draft modes.
It resolves entity context once, selects the state-candidate winner by
`(channel, priority, definitionStableId, ownerId, instanceKey)`, folds every
applicable modifier in ascending explicit order, normalizes once, and displays
effective fields plus winning, hidden, skipped, and contributing provenance. It
also replays bounded transition-event sequences, including timers, expiry, and
recovery batches, without writing files.

**Effective → state** promotes the final successful preview result into a new
independent deep state profile. Promotion copies exactly the complete normalized
state fields, never controller or runtime-layer identity. Bounded authoring
provenance records the source profile/body, winning layer when present,
normalizations, and per-field base/override/modifier contributors. This
`promotionProvenance`, together with names and descriptive tags, stays in the
canonical authoring JSON and is deliberately absent from V40 runtime wire bytes.

Draft identity is `draft:<uuid>` and never a display name or array index. Global
Save validates the complete graph, allocates persistent stable IDs and body IDs,
returns the draft-to-persistent map, and atomically rewrites the canonical JSON,
generated blob include, and checked constants header. A source-revision conflict
or any validation/write/reparse failure leaves the saved model unchanged and
preserves the editor draft for correction. There are no V39 save endpoints.

Deletion is reference-safe. The UI refuses state-profile deletion while an
authoritative controller-node backlink remains. The writer validates the whole
prospective graph, so controller, transition, owned definition/applicability,
modifier, and body removals cannot commit with dangling references. Reordering
edits explicit order/priority values; it never changes stable identity.

## Implemented Cross-Overlay ABI Gates

The implementation preserves the existing ARM/Thumb ABI exactly:

- `OverworldWildSpawns_EnterAggroState` has aligned linker/code address `0x0225046C`, callable Thumb address `0x0225046D`, and the exact half-open budget `[0x0225046C, 0x022504A0)` (`0x34` bytes). Its prototype remains `void (OverworldWildSpawnState *state, int slot, LocalMapObject *spawnedFollower)`.
- `OverworldWildSpawns_StartFollowerReleaseBounce` has aligned linker/code address `0x0224F298`, callable Thumb address `0x0224F299`, and its fixed entry must fit the `0x300`-byte slot before `0x0224F598`. Its prototype remains `BOOL (FieldSystem *fieldSystem, OverworldWildSpawnState *state, void *projectile, int slot)`.
- Both functions retain AAPCS argument order/widths. Aggro receives `r0/r1/r2` and returns no value. Bounce receives `r0..r3` and returns 32-bit `BOOL` in `r0`. The build remains Thumb-1/no-interwork: linker assertions use even symbols and every callable alias/function pointer retains the odd Thumb bit. Prototype, return type, argument order, calling mode, and slot size may not change.

`OverworldWildSpawnsOverlayEntry` remains exactly 28 bytes at `0x023CD000` with these fixed offsets and signatures:

| Offset | Field | Exact prototype |
|---:|---|---|
| `0` | `onPlayerStep` | `BOOL (FieldSystem *, OverworldWildSpawnState *, OverworldWildResidentData *)` |
| `4` | `tryPrimeBattleFromTalk` | `BOOL (FieldSystem *, OverworldWildSpawnState *, LocalMapObject *)` |
| `8` | `cleanupPendingBattle` | `u8 (FieldSystem *, OverworldWildSpawnState *, u16)` |
| `12` | `cleanupResidentData` | `BOOL (void)` |
| `16` | `onPlayerFrame` | `BOOL (FieldSystem *, OverworldWildSpawnState *)` |
| `20` | `onFieldBusy` | `void (FieldSystem *, OverworldWildSpawnState *, OverworldWildResidentData *)` |
| `24` | `prepareMapHeaderChange` | `void (OverworldWildSpawnState *, OverworldWildMapHeaderChangeMode)` |

Compile-time `sizeof` and `offsetof` assertions, linker address/budget assertions, and Thumb-bit verification are required. No field may be appended, reordered, repurposed, or widened.

Because the four-argument fixed bounce cannot see the new sidecar and the frozen 28-byte entry cannot grow, aggro publication uses fixed bounded storage outside that entry: exactly `OW_WILD_MAX_SPAWNS` primary request cells plus `OW_WILD_MAX_SPAWNS` source-owned retry records, never one global overwrite mailbox. Each primary cell separates orchestrator-maintained nonzero slot- and object-generation mirrors readable by fixed code; `expectedSlotGeneration`/`expectedObjectGeneration` captured from them; the frozen spawn's encounter generation (or an equivalent resident mirror); and an independent nonzero per-slot `publicationSequence` used only as the claim/ABA token. Distinct pending hits for different slots coexist and are consumed in ascending slot order, preserving source slot traversal.

Duplicate key `K` is exactly `(slot,expectedSlotGeneration,expectedEncounterGeneration,expectedObjectGeneration)` and deliberately excludes `publicationSequence`. The per-slot state machine is frozen: `EMPTY + K` allocates a fresh sequence, writes payload, and publishes `PENDING` last; `PENDING + same K` and `CLAIMED + same K` coalesce with byte-identical payload/sequence/state; `PENDING + different K` may replace only after fixed-visible generations prove the old key stale, otherwise it returns `BRIDGE_BUSY`; `CLAIMED + different K` always returns `BRIDGE_BUSY`. A producer never steals, clears, refreshes, or republishes a claimed cell.

Busy durability uses a second bounded fixed array `aggroBridgeRetry[OW_WILD_MAX_SPAWNS]`, one `EMPTY/RETRY_PENDING` record per source slot carrying `(K,retryGeneration,sourceOwnerGeneration)`. Before returning ABI `FALSE` for `BRIDGE_BUSY`, producer code atomically publishes/coalesces that exact retry record but does not change the primary cell, aggro metadata, or tile selection. The source projectile/release owner is generation-authenticated and cannot move, terminate, or relinquish the relation while its retry is pending. A live different retry key for the same slot is invalid/system-safety quarantine; a provably stale retry may clear. When the primary cell becomes `EMPTY`, mandatory maintenance promotes the exact retry and re-enters the full producer path; destructive source/slot invalidation consumes it diagnostically. Retry-generation wrap drains/promotes or destructively invalidates the owner before reuse. Thus BUSY cannot lose a hit and never enters the optional queue.

After authenticating an accepted target, fixed code sets both durable source-parity metadata effects—`OW_WILD_SPAWN_AGGRO_FLAG` on the hit encounter and `OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG` on release state—writes the complete cell payload/sequence, and publishes `PENDING` last, all **before** attempting bounce-tile selection. A no-tile `FALSE` result retains both effects and the cell; another slot may publish independently. The retained `OW_WILD_SPAWN_AGGRO_PENDING_FLAG` is a bounded presentation/dispatch bridge request; it is not a behavior state, profile-schema mirror, or V39 compatibility reader. Fixed code never changes active-step counters.

Only the spawns consumer may atomically claim `PENDING→CLAIMED` for exact `(K,publicationSequence)`. It reauthenticates authoritative slot/encounter/object generations and attempts one atomic tired-expiry-plus-aggro-plus-active-step transaction. If required orchestration returns `BUSY`—including a published tired expiry that has not committed—the consumer conditionally restores `CLAIMED→PENDING` with identical key, sequence, and payload; the retry remains mandatory and no stack/timer/counter change commits. Success conditionally clears `CLAIMED→EMPTY` only after the whole transaction commits, then promotes any retry. Reauthentication mismatch conditionally clears only that exact primary cell/claim. It never clears the unkeyed legacy pending compatibility bit on mismatch and never clears, zeros, or advances `slotGenerationMirror`, `objectGenerationMirror`, authoritative encounter generation, the publication-sequence carrier, either durable aggro flag, or the retry owner; only authenticated success or destructive slot lifecycle owns those values. Permanent schema failure enters system-safety quarantine rather than dropping the request. The carrier contains no sidecar pointer or layer handle. Existing projectile-prefix `impactSlot` and `impactEncounterGeneration` remain dedicated to projectile/capture presentation validation and may not be repurposed as this carrier.

## 21-Task Completion Crosswalk

This is the audit trail for the original implementation plan. A checked item
means the outcome exists in the branch and has commit-level evidence; later
hardening commits are listed after the original task that they strengthen.

| # | Completed outcome | Primary evidence |
|---:|---|---|
| 1 | ☑ One-state/stackable contract and parity oracle | `8896c8822` |
| 2 | ☑ Executable stack reference model | `c80ce682c` |
| 3 | ☑ Compact stable-ID V40 schema | `722dc39f3` |
| 4 | ☑ Fixed-capacity per-slot runtime sidecars | `e3a7591df` |
| 5 | ☑ Owner-safe atomic apply/remove/replace | `ee9c0c332` |
| 6 | ☑ State-winner selection and modifier recomposition | `0ea36cdb0` |
| 7 | ☑ Layer timers, expiry, and recovery policies | `43d902bb0` |
| 8 | ☑ Production overworld runtime cut over to stack profiles | `c43be6e6a` |
| 9 | ☑ One-complete-state Profile Deck editor | `b46c1cf1d` |
| 10 | ☑ Typed controller/node editor | `b35fd2c9c` |
| 11 | ☑ Possession and state transitions migrated | `f98449409` |
| 12 | ☑ Deterministic saved/draft stack preview | `6862ec2d6` |
| 13 | ☑ Canonical V40 encode/decode codec | `cdce627f9` |
| 14 | ☑ Whole-graph model validation | `51f0bf733` |
| 15 | ☑ Atomic behavior-model writer | `a33faf6e3` |
| 16 | ☑ Atomic map/battle stack lifecycles | `5680f01c3` |
| 17 | ☑ One all-or-nothing Global Save transaction | `3706adcec` |
| 18 | ☑ Bounded runtime verification fixtures | `c4f1258b3` |
| 19 | ☑ Flattened profile projection and compatibility endpoints removed | `c34fa2315`, `d831aacee` |
| 20 | ☑ Presentation byte separated from behavior authority | `042a5e444` |
| 21 | ☑ Complete authoring workflow and traceable editor contract | `77d89b728`, `673c5baa3` |

Post-plan hardening completed the long-term authoring shape: cold reconstruction
and stack-use fixes (`c2d5e161c`, `4d64c16d0`), full CRUD and generalized
catalogs (`84321832e`, `4bdababda`), first-class modifier authoring/runtime fold
(`a51bb4993`), and explicit shallow/deep duplication, mapping preview, and
Effective → state promotion (`f3c51f977`).

## Final Implementation and Verification Evidence

- Canonical V40 runtime blob: 11,028 bytes with a fixed 216-byte header.
- Checked header checksum: `0xCD843F3E`; schema fingerprint: `0x9421CA4D`.
- Retired combined runtime-plus-projection baseline: 15,052 bytes. Current
  footprint is 4,024 bytes smaller (26.7%), with no flattened compatibility
  payload.
- Accepted `test2600.nds` overlay measurements, expressed as raw bytes / physical
  headroom: overlay 157 `6,588 / 196`; 156 `540 / 6,980`; 159 `3,772 / 196`;
  149 `44,860 / 196`; and 158 `13,492 / 204`.
- Focused verification passed: 25,419 runtime-layer checks, 204 catalog checks,
  14 timer checks, 20/20 Python model/codec tests, 31/31 writer tests, all three
  focused Node suites, and 5,000/5,000 malformed-parity cases plus structured
  malformed variants. Full V2 Python discovery passed 51/51 tests (12 model,
  5 commit, 31 writer, and 3 retired-HTTP tests).
- The final managed build passed and copied `test2600.nds` to Delta. Only
  documentation changed after the preceding authoring/UI build, so it preserved
  the accepted runtime overlay sizes and hashes; no new walking run is claimed
  for it.
- The preceding exact-runtime build passed a 15,720-frame real-save
  walking/spawn regression with the player and spawned Pokémon still visible and
  the source save checksum unchanged.

These are checked implementation facts, not rollout questions. Any later change
to capacity, precedence, lifetime, ownership, composition, authoring identity,
or serialized ABI must update this contract and its validators together.
