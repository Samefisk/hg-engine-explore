# Overworld System Verification

## Proof rule

Static shape is not runtime behavior. A verifier that checks source text, an ABI table, or an instruction address can prove packaging, but it cannot prove movement feel, exact completion, control release, or presentation synchronization.

Every claim names its proof level:

| Level | Proves | Typical tool |
| --- | --- | --- |
| S0 Schema | Data shape, units, bounds, generated agreement | Schema validator |
| S1 Model | Resolver, planning, timing, path-advance, commit, and reason semantics | Deterministic host scenario |
| S2 Package | Overlay size, address, entry, ABI, and ROM packaging | Existing static verifiers |
| S3 ROM | Real engine objects, streaming, transitions, input, and lifecycle | Headless ROM scenario |
| S4 Visual | Sprite placement, arc, spin, effects, and control feel | melonDS visual check |
| S5 Soak | Rare races and cumulative state leaks | Bounded repeated ROM scenario |

A change uses all levels that match its risk. It does not use S4 screenshots as a substitute for S1 semantic assertions.

## Scenario contract

Scenarios are declarative data under the target path `tests/overworld/scenarios/`.

Each scenario contains:

- Stable ID and capability IDs.
- Fixture or save hash.
- Map, world revision, surfaces, and blocked tiles.
- Subjects, roles, profiles, and deterministic random seed.
- Input and lifecycle event sequence.
- Stop condition and frame budget.
- Required decisions, plans, commits, poses, and trace events.
- Forbidden events and invariant violations.
- Proof level and cost tier.
- Capture policy: none, failure only, or required visual frames.

Every run writes a manifest containing source revision, ROM hash and build
manifest ID, save hash, scenario revision, debug-descriptor version, emulator
and version, random seed, proof level, start time, and result. Evidence without
this identity is not reusable proof.

Python is an escape hatch for engine setup that cannot be described as data. Assertions remain semantic and declarative.

## Feature map

This is the current human-readable impact map. Phase 1 moves it to the
validated machine-readable source
`tools/overworld/system_features.yaml` and generates this table.

| Capability | Shared contract | Current primary sources | Required roles | Minimum proof |
| --- | --- | --- | --- | --- |
| Profile composition | Ordered layers, lanes, normalization, provenance | behavior data header/data, runtime and spawns overlays, Workshop preview | Wild, Follower, Mounted projection | S0, S1 parity |
| Exact Walk | 1-32 frame travel time, one path advance, and one commit | Walk module, runtime overlay, spawns overlay, mount overlay | Wild, Mounted | S1, S2, S3 |
| Acceleration | Count real Walk commits; halve time and clamp | runtime overlay, mount overlay | Wild, Mounted | S1 parity, S3 |
| Turn and stop skid | Direction rule, skid count, restored momentum | Walk module, runtime overlay, mount overlay | Wild, Mounted | S1 parity, S3, S4 |
| Stomp and crash | Threshold, effect, sound, reaction | runtime, spawns, mount overlays | Wild, Mounted | S1, S3, S4 |
| Diagonal Walk | Candidate order, two side tiles, one commit | Walk module, spawns overlay, mount overlay | Wild, Mounted | S1 parity, S3 |
| Hop | Candidate order, path advances, landing, arc, pause, spin, sway | Hop trajectory, spawns overlay, mount overlay | Wild, Mounted | S1 parity, S3, S4 |
| Ledge Hop | Edge direction and landing permission | spawns overlay, Hop trajectory | Wild, Mounted | S1, S3 |
| Teleport | Timing, flicker, landing, pause, one commit | spawns overlay, mount overlay | Wild, Mounted | S1 parity, S3, S4 |
| Chain movement | Count semantic actions; exclude skid/reposition | movement policy, spawns and mount overlays | Wild, Follower | S1, S3 |
| Mount lifecycle | Current follower, bind one logical motion owner, detach | selector, spawns, mount overlays | Follower, Mounted | S2, S3, S4 |
| Mounted presentation | One motion, rider seat, facing, height, shadow | mount overlay and facing bridge | Mounted | S3, S4 |
| Terrain streaming | Follow committed/interpolated player path; serialize diagonal axes | mount overlay and field engine adapter | Mounted | S3, S5 |
| Field transition | Suspend, preserve/discard, rebind, resume | map teleport, spawns and mount overlays | Wild, Follower, Mounted | S3, S5 |
| Warp gating | Trigger only at eligible commit | field engine, mount and spawns overlays | Mounted | S3 |
| Population | Time scheduling, map context, encounter terrain, deficit | spawns and helper overlays | Wild | S1, S3, S5 |
| Battle/capture | Stable actor identity and lifecycle handoff | spawns and helper overlays | Wild | S2, S3 |

## Baseline scenario set

The first declarative set must include:

- `profile.resolve.override-order`
- `profile.resolve.follower-mounted-parity`
- `walk.cardinal.frames-1-32`
- `walk.diagonal.corner-block`
- `walk.acceleration.mounted-parity`
- `walk.turn-skid.control-release`
- `chain.pause.counts-semantic-moves`
- `hop.cardinal-and-diagonal`
- `hop.ledge-up-and-down`
- `hop.mounted-single-motion`
- `teleport.fixed-and-per-tile`
- `mount.begin-current-follower`
- `mount.detach-restores-control`
- `mount.transition-mid-motion`
- `mount.streaming.cardinal-and-diagonal`
- `warp.blocked-mid-motion`
- `population.land-surf-separation`
- `population.after-fast-travel`

Every past high-impact bug should map to one of these scenarios or add a narrower permanent scenario.

## Stable observation assertions

Scenarios assert on the `Inspect` snapshot and semantic trace, never on private implementation arrays when a public semantic field exists.

Required invariant assertions:

- No actor has two motion owners.
- Authority, engine anchor, and dependent presentation have the expected relation.
- No stale actor handle or field epoch is dereferenced.
- Each accepted intent has one terminal result.
- Each motion has ordered path advances and at most one terminal commit.
- No commit occurs after cancel.
- Input ownership returns after finish or cancel.
- Chain and acceleration counters change only for eligible commits.
- Path advances and stream anchors do not skip required tile updates.
- Warps do not fire during ineligible motion phases.
- All target reservations are released.

## Affected verification

The target `tools/overworld/system_features.yaml` manifest maps:

- Source paths and symbols.
- Profile fields and schema entries.
- Actor roles and adapters.
- Trace event groups.
- Scenarios and proof levels.
- Documentation contracts.

`scripts/owctl verify affected` compares the working diff to that manifest, prints the selected proof set, and runs cheapest-first. `verify all` is reserved for releases or cross-cutting changes.

## Current verifier limits

The current `scripts/verify_overworld_mount.py` is strong package and ABI proof. Much of it checks fixed addresses, entry layout, source patterns, and instructions. It does not by itself prove smooth control, exact per-frame interpolation, terrain streaming over time, or safe repeated detach.

The current Walk verifiers protect timing policy and several source-level invariants. They do not yet prove all frame boundaries across wild and mounted roles for values 1 and 32.

Headless scripts and saved scenarios prove real engine behavior, but they currently rely on private offsets and bespoke input loops. Keep using them during migration. Replace their private assertions with the generated debug descriptor and semantic events as those become available.

## Completion gate

A migrated capability is complete only when:

1. The feature manifest names one owner.
2. Its shared contract has a model scenario.
3. Engine-specific behavior has a focused ROM scenario.
4. Mounted and wild parity is checked where the contract is shared.
5. The old implementation path and implementation-specific tests are removed.
6. The canonical docs and trace decoder match the shipped interface.
