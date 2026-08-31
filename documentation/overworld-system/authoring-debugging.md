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

Open <http://127.0.0.1:8766/>. Treat its context resolution as a source
preview. `/api/v2/resolve` does not yet reproduce the forced follower layer,
conditional physical-surface selection, or complete Active/Tired linked-profile
resolution exactly like the ROM.

Use the existing focused live runner after an authorized build:

```bash
python3 scripts/verify_overworld_walk_runtime.py --scenario mounted_diagonal_streaming
python3 scripts/verify_overworld_walk_runtime.py --scenario mankey_control_stress --include-mankey
python3 scripts/verify_overworld_mount.py --rom test.nds
```

Mankey scenarios import the raw melonDS `test.sav`; they require
`--include-mankey`. Other current live scenarios use the configured headless
save path. These scripts use private symbols and offsets, so record the ROM,
save, and source revision with the result.

## Target workflow

The target host command is `scripts/owctl`. It is a facade over profile authoring, the portable resolver, scenario execution, trace decoding, and affected verification.

```bash
scripts/owctl profile resolve SPECIES_CYNDAQUIL --forced-layer follower --projection wild,mounted --encounter-terrain land --surface-mask native-land
scripts/owctl scenario run mounted.walk.accelerate --trace why
scripts/owctl compare wild,mounted --contract motion --species SPECIES_MANKEY
scripts/owctl verify affected
scripts/owctl doctor
```

These commands are a design target in the active roadmap. They do not exist yet.

## One source model

The current profile schema is repeated in C structs, masks, Python field lists, JavaScript metadata, bounds, migrations, and verifiers. The current Workshop also has a host resolver that can drift from the ROM resolver.

The target is one generated Behavior Schema and one portable resolver:

- Named source data is the authoring truth.
- The schema generates C layout, binary masks, enum metadata, host types, editor fields, bounds, trace labels, and compatibility writers.
- The same portable resolver source compiles for ARM and the host.
- The resolver returns a complete `Resolved behavior`, a fingerprint, and ordered provenance.
- The Workshop displays that result. It does not implement another resolver.

During migration, the positional C data remains the ROM input. The ROM resolver is runtime truth. Workshop results must be labeled as previews and checked against golden resolver vectors.

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

`OverworldActorSnapshot` must expose:

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

The target generator will emit snapshot layout and enum metadata to
`build/overworld-system.debug.json`. Live tools will read that descriptor
instead of hard-coded private offsets.

## Semantic trace

The target observation module will use a fixed-size binary ring. It will contain
no strings and allocate no memory per frame. A host decoder will map stable
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
