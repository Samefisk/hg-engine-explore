# Overworld Authoring and Debugging

## Goal

An agent should be able to answer five questions with one control surface:

1. What profile did this Pokémon resolve?
2. Why did each layer apply?
3. What intent and candidates were considered?
4. Why did motion start, wait, reject, commit, or cancel?
5. What is the first difference between wild and mounted behavior?

## Workflow available today

Start the Workshop from the repository root:

```bash
OPEN_PAGE=0 scripts/keyboard-maestro-start-overworld-viewer.sh
```

Open <http://127.0.0.1:8766/>. `/api/v2/resolve` calls the portable C resolver
that the ROM uses. The Workshop still parses source for names, editor data, and
context inputs. Older Workshop and source-editing endpoints still use the
Python compatibility resolver. Phase 2 is complete only after those endpoints
move to the portable resolver and the Python composition path is deleted.

Use the existing focused live runner after an authorized build:

```bash
python3 scripts/verify_overworld_walk_runtime.py --scenario mounted_diagonal_streaming
python3 scripts/verify_overworld_walk_runtime.py --scenario mankey_control_stress
python3 scripts/verify_overworld_mount.py --rom test.nds
```

Mankey scenarios import the raw melonDS `test.sav`. The
`--include-mankey-save` option adds those scenarios when running
`--scenario all`; a named Mankey scenario does not need the option. Other
current live scenarios use the configured headless save path. These scripts
use private symbols and offsets, so record the ROM, save, and source revision
with the result.

## Agent control workflow

`scripts/owctl` is the host facade for readiness, scenario contracts, trace
decoding, and affected verification.

```bash
scripts/owctl doctor
scripts/owctl scenario list
scripts/owctl scenario validate
scripts/owctl scenario run mount.detach-restores-control --dry-run
scripts/owctl trace decode tests/overworld/traces/semantic-trace-v1.json
scripts/owctl verify affected
scripts/owctl verify affected --run
```

Scenario runs and affected verification write identity-bearing run manifests
when they execute. A scenario with status `planned` is a contract only and
cannot be reported as runtime proof.

## One source model

The generated field schema lives in `tools/overworld/behavior_schema.json`.
Its generator emits matching ROM and host metadata. The positional C profile
data remains the current value source.

`lib/overworld/overworld_behavior_resolver.c` is the canonical composition
implementation used by the ROM and `/api/v2/resolve`. It compiles for ARM and
as `build/overworld_behavior_resolver_host`. It returns the resolved lanes,
mechanical primitives, fingerprint, and ordered provenance. The Workshop V2
endpoint decodes that result for display. The older compatibility endpoints
still use the Python path named above.

## Resolution explanation

A resolution explanation must show:

- Subject and field context.
- Base behavior class and why it matched.
- Every layer in source order.
- Applied, skipped, and conditionally selected layers.
- Each changed field with old value, operator, and new value.
- Active and Tired linked profile selection.
- Normalization changes.
- Mechanical primitives.
- Final fingerprint.

Example:

```text
SPECIES_CYNDAQUIL / forced Follower layer / Mounted projection / Land

Base: Default
Layer 05: Fire group                 APPLIED
Layer: Follower Pokémon              APPLIED

Owner.walk.travelTime: 16 -> 8      no slower than 8
Owner.chain.pause: Hop -> None       Follower Pokémon layer

Mounted controller: Owner movement values consumed; AI chain policy ignored

Fingerprint: 4d2a7e91
```

Mounted is not a profile type or resolver role. Current mount begin resolves
the current follower with the forced `Follower Pokemon` layer, snapshots the
resolved Owner lane, then selects the rider-input controller. AI-only values
stay resolved but that controller does not consume them.

## Stable observation

`OverworldActorSnapshot` exposes:

- Actor handle and field epoch.
- Subject identity and role.
- Authority, engine-anchor, and dependent-presentation generations.
- Selected lane.
- Resolved behavior fingerprint and matched layer IDs.
- Controller state and last intent.
- Motion kind, phase, origin, target, elapsed, and duration.
- Logical and rendered positions.
- Input ownership and target reservation.
- Stream anchor and loader-busy state.
- Last plan decision, commit sequence, and cancel reason.
- Population scheduler state when requested.

`scripts/generate_overworld_actor_system_debug.py` emits snapshot layout,
fixed entries, enum IDs, symbols, and offsets to
`build/overworld-system.debug.json`. Live adapters must read that descriptor
instead of adding private offsets.

## Semantic trace

The observation module uses a fixed-size binary ring. It contains
no strings and allocates no memory per frame. A host decoder maps stable
event and reason IDs to names.

Core events:

- `ACTOR_ATTACHED`
- `ACTOR_DETACHED`
- `CONTROL_REBOUND`
- `PROFILE_RESOLVED`
- `LANE_CHANGED`
- `INTENT_CREATED`
- `CANDIDATE_REJECTED`
- `PLAN_ACCEPTED`
- `MOTION_STARTED`
- `STREAM_WAITING`
- `STREAM_ADVANCED`
- `PATH_ADVANCED`
- `LOGICAL_COMMIT`
- `WORLD_EFFECT`
- `PRESENTATION_SYNCED`
- `MOTION_FINISHED`
- `MOTION_CANCELED`
- `CONTEXT_CHANGED`
- `ACTOR_REBOUND`
- `CONTROL_RETURNED`

Each event stores sequence, frame, actor handle, role, event ID, reason ID, and two event-specific values. Trace filters select actors, event groups, and duration. Unarmed tracing has near-zero work.

Every trace header also stores the oldest sequence, next sequence,
overwritten-event count, active filter, and field epoch. A scenario warns or
fails when its required event window was overwritten.

## First-divergence report

Wild and mounted parity compares only shared contracts:

- Resolved Owner profile.
- Candidate ordering and target validity.
- Travel time, arc, facing, acceleration, and skid.
- One logical commit.
- Path-advance, player-step, and streaming counts where the role uses them.

It does not compare AI intent selection or rider presentation.

```text
FAIL mounted.walk.accelerate

Profile parity: PASS
Plan parity: PASS
Commit parity: FAIL at tile 4

Wild:    LOGICAL_COMMIT -> CONTROL_RETURNED
Mounted: LOGICAL_COMMIT -> pendingStep retained

First divergence:
Mounted executor did not release the movement-end boundary.
```

This report is the normal diagnosis artifact. Screenshots and raw memory inspection are follow-up tools when the first divergence is presentation or engine integration.

## Accretive change rule

Every change adds reusable knowledge in the smallest durable form:

- New profile field: schema entry, generated metadata, resolution vector, feature-map link.
- New locomotion: planner contract, trace events, model scenario, ROM integration scenario.
- Fixed bug: scenario that fails before the fix and names the violated invariant.
- New engine fact: adapter contract or cited historical note, not an unexplained offset in a verifier.
- New failure mode: stable reason code and decoder text.

Do not add long narrative attempt logs for ordinary work. Keep short failure evidence only when it prevents a likely repeated experiment, then link it from the owning feature.

## Agent resource policy

Use the least expensive proof that can reject the change:

1. Schema and source validation.
2. Portable resolver or motion-model scenario.
3. Package and ABI verification.
4. One focused headless ROM scenario.
5. melonDS visual check for rendering, input feel, or emulator-specific behavior.
6. Long soak only for transitions, streaming, population, or lifecycle races.

Stop at the first failed layer. Decode the semantic trace before opening broad source areas.
