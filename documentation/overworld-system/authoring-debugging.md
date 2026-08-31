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
that the ROM uses. All profile saves go through the named authoring catalog at
`data/overworld_behavior_profiles.json`. The Workshop regenerates the compact
C compatibility data after each save.

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
scripts/owctl actor inspect build/actor-state.bin
scripts/owctl actor trace build/actor-state.bin
scripts/owctl actor capture build/actor-state.bin \
  --scenario-id <scenario-id> --rom test.nds --save test.dsv --seed 0 \
  --output build/actor-observation.json
scripts/owctl verify affected
scripts/owctl verify affected --run
```

Scenario runs and affected verification write identity-bearing run manifests
when they execute. A scenario with status `planned` is a contract only and
cannot be reported as runtime proof.

`actor-state.bin` is a raw dump that starts at the generated descriptor's
`state.address`. Use `--base 0x02000000` for a full ARM9 memory dump. The actor
commands read the public snapshot mirror and trace ring through
`build/overworld-system.debug.json`; they do not contain overlay-private
offsets. `inspect` and `trace` also accept the JSON written by `actor capture`.

A scenario can use the semantic adapter instead of a private-offset runner.
Reusable evidence is version 2 and must name the scenario, seed, and exact ROM
and save hashes that produced it. Scenario execution rejects missing or stale
provenance instead of assigning the current files to an old capture.

The adapter selects exactly one actor and one complete motion window. Required
events are an ordered subsequence in that window. Forbidden events are checked
in the same window. Evidence is ambiguous when two motion windows match.

```json
"adapter": {
  "kind": "actor-observation",
  "checks": [
    "trace-window-complete",
    "terminal-result",
    "no-commit-after-cancel",
    "control-returned"
  ]
}
```

Run that adapter with reusable evidence:

```bash
scripts/owctl scenario run <scenario-id> --evidence build/actor-observation.json
```

The adapter checks required and forbidden semantic events, then runs the named
public invariants. Free-text invariant prose is not executable. Each invariant
must exactly match a registered entry in
`tools.overworld.validation.ACTOR_INVARIANT_CHECKS`, and the adapter must name
all checks registered for it. The run manifest records the evidence path, size,
and hash.

`trace-window-complete` fails closed unless the trace was cleared, did not
overwrite, its bounded capture window finished, and its actor and event filters
included the selected motion contract. A snapshot taken while the trace is
still armed is diagnostic data, not reusable scenario proof.

## One source model

The generated field schema lives in `tools/overworld/behavior_schema.json`.
Its generator emits matching ROM and host metadata. Named values live in
`data/overworld_behavior_profiles.json`. Each class profile names every schema
field. Each override names only the fields it changes and gives each field an
explicit `replace`, `relative`, `atLeast`, or `atMost` operator. Targets,
members, matches, class rules, and conditional states also use named objects.
Conditional behavior is authored only in the top-level `conditionalStates`
table. The obsolete per-override condition object is not part of catalog v1.

`data/OverworldWildBehaviorData.c` is generated compatibility output. Do not
edit its profile arrays by hand. Use the Workshop, edit the catalog, or use the
migration/generator:

```bash
# One-time import after recovering an older C-only revision.
python3 scripts/generate_overworld_behavior_catalog.py --import-c

# Generate C/header data after a catalog edit.
python3 scripts/generate_overworld_behavior_catalog.py

# Read-only synchronization check.
python3 scripts/generate_overworld_behavior_catalog.py --check
```

The catalog shape is documented by
`tools/overworld/schemas/behavior-authoring-v1.schema.json`. The generator
also validates schema field names, profile symbols, match fields, members,
operators, and fixed-layout counts before it writes output.

`lib/overworld/overworld_behavior_resolver.c` is the canonical composition
implementation used by the ROM and `/api/v2/resolve`. It compiles for ARM and
as `build/overworld_behavior_resolver_host`. It returns the resolved lanes,
mechanical primitives, fingerprint, and ordered provenance. The Workshop V2
endpoint decodes that result for display. Authoring changes storage only; they
do not create a second composition implementation.

The resolve endpoint accepts the complete resolver context. In addition to
species, level, terrain, and shiny state, agents can pass
`conditionTerrainMask`, `forcedOverrideMask`, and `behaviorClass`. Values can
be integers or known C symbols and flag expressions. Omit `behaviorClass`, or
use `auto`, to run class rules.

`scripts/verify_overworld_behavior_resolver.py` runs the committed golden
corpus through both single and batch Workshop adapters. It also checks that the
ROM overlay and host tool compile the same resolver source and that the actor
service publishes those callbacks. This is source and host proof. A packaged
ROM run is still required before claiming live parity.

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

`tools.overworld.actor_probe.capture_observation` is the shared Python adapter
for live emulator drivers. Give it a memory reader with the interface
`read(address, size) -> bytes`; it returns the same evidence document as
`scripts/owctl actor capture`. Boot and input control stay separate from
public observation decoding.

A live driver arms one exact window with
`configure_runtime_trace(read, write, descriptor, ...)`, performs its input,
then calls `finish_runtime_trace(...)` before `capture_observation(...)`. The
write callback runs only while the emulator is paused between frames. Both
helpers use the versioned public trace header and generated descriptor; they do
not know actor-system private offsets. The generic headless driver exposes this
path through `--actor-evidence`, `--actor-scenario-id`,
`--actor-event-mask`, and `--actor-trace-frames`.

## Semantic trace

The observation module uses a fixed-size binary ring. It contains
no strings and allocates no memory per frame. A host decoder maps stable
event and reason IDs to names.

`ACTOR_DETACHED` is a terminal release when an actor disappears during a
motion. It replaces a separate cancel/control-return pair because no actor or
input claim remains after detach.

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
