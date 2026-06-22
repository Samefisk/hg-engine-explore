# Map Teleportation Investigation

## Scope

The MVP needs a reusable overworld helper that can teleport to a caller-provided
map, tile, and facing direction. Presentation is intentionally out of scope: no
sound, visual effect, menu, or destination picker work is included. The L+R
overworld trigger is only a verification hook.

## Existing Warp Path

Directly mutating `FieldSystem->location` is unsafe. The live map also has loaded
event data, matrix data, object-manager state, player-avatar state, and
follow-mon state. Changing only the location would leave those structures
desynchronized and risks loading an incomplete or stale map.

The helper therefore queues a stock field warp task instead of adding a custom
transition implementation. The script `warp` command (`176`) calls the same
family of transition tasks through an existing `TaskManager *`, which is
fragile from a SysTask verification trigger because it requires the correct
active task-manager node. The helper therefore builds the same small env shape
used by the script warp path (`state` plus `Location`) and schedules stock
`Task_ScriptWarp` with `FieldSystem_CreateTask` once `fieldSystem->taskman` is
idle. That uses the common warp loader without the Fly-style landing
presentation used by `sub_020538C0`/`FlyAnimation` (`180`), so the L+R
transition remains presentation-free.

The decomp confirms that the stock wrappers build a `Location` from their
arguments and that script warp-style callers pass `mapId, x, y` without
coordinate conversion. Only `warpId != -1` makes the loader replace x/y from
map warp events, so this helper uses `warpId = -1` for explicit tile
destinations.

## Coordinate Convention

`MapTeleportDestination.x` and `MapTeleportDestination.y` are field `Location`
coordinates consumed by the stock field warp task. They are not Pokegear
world-map grid coordinates and they are not the small display `x/y` values from
the Pokegear flypoint table.

For example, New Bark's Pokegear flypoint table has display coordinates like
`21,12`, but the stock outdoor landing coordinate is `0x02B7,0x018D`
(`695,397`). Passing the display coordinates to `sub_020538C0` can produce a
black screen because the map is loaded around the wrong field position.

Future callers that start from Pokegear/world-map data must convert to field
`Location` coordinates or use vetted spawn-table values before calling
`MapTeleport_Request`.

Representative known-good outdoor field coordinates from the stock spawn/fly
table are:

| Map | Field `Location.x,y` |
| --- | --- |
| `MAP_T20` / New Bark | `0x02B7,0x018D` (`695,397`) |
| `MAP_T21` / Cherrygrove | `0x0234,0x0188` (`564,392`) |
| `MAP_T22` / Violet | `0x01F1,0x0110` (`497,272`) |
| `MAP_T23` / Azalea | `0x019A,0x01CD` (`410,461`) |
| `MAP_T25` / Goldenrod | `0x0160,0x0171` (`352,369`) |

## Safe Call Site

The verification trigger is registered from the existing field-system-ready
hook. That always-built hook only starts the overlay 131 debug task once the
field system is ready. Overlay 131 owns the L+R polling task and the writable
`MapTeleportDestination`, so headless verification can patch different
caller-provided destinations without adding UI, presentation code, or a debug
destination in the always-built main output.

The helper only queues a teleport when:

- the `FieldSystem` is still the global live field system,
- location, map events, and map matrix pointers are present,
- no map teleport request is already pending,
- the stock field task manager is idle,
- the destination map id and direction are in valid ranges, and
- same-map destinations pass a loaded collision/land check.

This keeps the L+R hook an overworld-only verification path and keeps the core
helper usable from future overworld triggers such as "if X then teleport to this
map/tile".

## Overlay And Space Constraints

Overlay 149 is the visible-overworld-wild spawn overlay and is already a tight,
large overlay. This feature does not add code or data to overlay 149.

The reusable helper lives in overlay 131, the field extension overlay. The
fixed-address entry table stays deliberately small: it exposes request,
same-loaded-map land validation, and debug-task start. The random-loaded-land
selector is exposed as the overlay-131 provider symbol
`MapTeleport_TrySelectRandomLoadedLandTile`, and the public
`MapTeleport_RequestRandomLoadedLandTile` wrapper combines that selector with
`MapTeleport_Request`. This keeps a real hook path for future field/overworld
triggers without spending the extra four bytes that a fourth entry-table
function pointer would cost. No common script entry, destination UI, effect
code, sound code, or overlay 149 code/data is added for teleportation.

## Validation Limits And Caller Contract

`MapTeleport_Request` accepts any caller-provided `mapId`, field `Location.x`,
field `Location.y`, and `direction`, subject to cheap safety checks:

- map IDs must be in the known map constant range and must not be the early
  special placeholder/direct maps,
- direction must be north, south, west, or east,
- the live field system must be present, and
- if the destination is on the currently loaded map, the helper verifies that
  the target tile is not blocked and uses a low normal-land behavior below
  the surf/special range, excluding headbutt.

The helper does not load arbitrary destination maps just to inspect collision
before warping. Doing so would add more map-loading surface area and code size
than the MVP needs. For cross-map calls, callers must pass a vetted destination:
the target map must be complete and loadable, and the target field `Location`
coordinate must be in-bounds and known-safe land.

The random-land API is deliberately scoped to the current loaded map:
`MapTeleport_TrySelectRandomLoadedLandTile` fills a
`MapTeleportDestination` for a random loaded land tile, and
`MapTeleport_RequestRandomLoadedLandTile` is the public request wrapper for
future callers that only need "move me somewhere safe on this map". The current
implementation is conservative and table-backed for encounter maps: it scans the
existing 150-row generated encounter table for the current loaded map ID, then
chooses one member of that row's audited strict horizontal pair. If the current
map has no generated encounter row, the helper returns `FALSE` rather than
falling back to broad live-cell sampling. That avoids T24-style live-helper
drift onto static `0x8000` permission tiles while keeping the public hook
available for the supported encounter-map surface.

The selector currently validates generated terrain/event evidence, not dynamic
object occupancy. That keeps overlay 131 under the `0x5000` acceptance ceiling
while still fixing the reported water, void/out-of-bounds,
one-way-ledge/special-behavior, and blocked-terrain failure modes. A future
caller that needs NPC/follower exclusion can layer that check on top of
`MapTeleport_TrySelectRandomLoadedLandTile` or broaden the provider when there
is overlay budget for it.

The normal L+R debug path uses one plain `Task_ScriptWarp`. It chooses a random
destination from the 150 generated encounter-map entries, then flips one random
bit to choose one member of that map's generated strict horizontal pair. The
pair is selected before the warp because the target map is not loaded yet and
the earlier after-load overlay-task state proved too fragile across map reloads.
Numeric destination indexes use the same compact-pair path for cross-map
coverage. If a numeric-index press already starts on the selected map, the debug
path calls `MapTeleport_TrySelectRandomLoadedLandTile` instead, so repeated
forced-index verifier runs exercise the public current-map helper while still
remaining inside the generated strict pair.

The exact-destination headless verifier still patches the writable debug
destination and writes `MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED` before
pressing L+R. That `0xFFFE` path remains deterministic and bypasses the compact
pair selector.

## Final Implementation Plan

1. Add `include/map_teleport.h` with the destination struct, result enum, and
   `MapTeleport_Request`.
2. Add `src/field/map_teleport.c` in overlay 131, not overlay 149.
3. Expose the request/validation/debug hooks through a fixed-address overlay
   entry table, and expose the random-loaded-land selector as an overlay-131
   provider symbol to avoid widening that table.
4. Register the L+R verification request from the existing field-ready hook.
5. Build the ROM and verify the writable debug destination across a matrix of
   known-good field `Location` coordinates: New Bark, Cherrygrove, Violet,
   Azalea, and Goldenrod.

## All-Encounter Destination V2

The all-encounter map version makes `data/OverworldWildEncounterLookupData.c`
the authoritative source of encounter-bearing maps. The expected count is
`OWED_ENCOUNTER_AREA_COUNT`, currently 150, and generation fails if that source
does not contain exactly 150 unique map IDs with 150 matching encounter data
IDs.

`scripts/generate_encounter_map_teleport_destinations.py` parses the
authoritative lookup, `include/constants/maps.h`, the English HGSS map headers
in `base/arm9.bin` at `0xF6BE0`, matrix NARC `base/root/a/0/4/1`, land
permission NARC `base/root/a/0/6/5`, and event NARC `base/root/a/0/3/2`.
For each map it derives field `Location.x,z` coordinates from matrix cells and
32x32 land permission grids. Exact matrix cells whose value equals the map ID
are preferred across all matrices. Header-matrix wildcard cells are used only
when exact stamps do not yield a safe static candidate, which covers a small
set of interiors whose header matrix cells are land IDs rather than map IDs.
Candidate tiles reject high-bit blocked permissions and require a low behavior
byte below `16`, excluding headbutt behavior `6`. That keeps standard low
normal-land and grass-like terrain eligible while excluding surf/water, one-way
ledges, and other higher-numbered special traversal surfaces. Warps and trigger
rectangles from the target event file are excluded when event data exists. Static
and active object occupancy are intentionally not part of this predicate; the
host generator and runtime helper agree on warp/coord-event exclusion.

A few destinations are runtime-verified fixed coordinates because the static
permission grid alone chooses a bad loaded tile or marks a proven runtime tile
as blocked. These are recorded in the audit JSON with `source:
verified:derived`. The final L+R verifier is the acceptance proof for these
rows.

The generated runtime table is checked in at
`src/field/map_teleport_encounter_destinations.c`, and the audit JSON is
checked in at `documentation/verification/encounter_map_teleport_destinations.json`.
The table stores one packed base coordinate per encounter map. The generator
fails unless that base coordinate and `x + 1` form a strict horizontal land pair
under the same predicate; the static audit reports 150/150 pair coverage and
the `MAP_T24` pair `(177,370)` / `(178,370)`. Future overworld callers can use
`MapTeleport_TrySelectEncounterDestinationByIndex` and `MapTeleport_Request` to
teleport to a vetted encounter-map entry, or use
`MapTeleport_TrySelectRandomLoadedLandTile` /
`MapTeleport_RequestRandomLoadedLandTile` when the current loaded map should
choose the landing tile.

Two authoritative maps have inconsistent static data:

- `MAP_D24`
- `MAP_D24R0201`

Both are in the encounter lookup with data ID 10, both point at matrix 0 and
event file 0 in the English HGSS headers, and neither has a matrix-0 cell whose
matrix value equals its own map ID. The generator therefore documents explicit
fallback coordinates derived from the matrix-0 `MAP_D24R0101` stamps. These
maps are still emitted under their exact authoritative map IDs, are still
counted toward 150, and must pass the runtime L+R verifier; the verifier fails
hard if either fallback does not load as the exact requested map ID.

## Random Land Verification

The random-land verifier uses
`documentation/verification/encounter_map_teleport_destinations.json` as the
compact audit fixture for the 150 generated destinations. To avoid checking a
multi-megabyte coordinate database into the repo, the JSON stores only the
random loaded-window count, coordinate bounds, and SHA-256 hash for each
destination. The focused verifier recomputes the bounded loaded-window
membership for the requested map from the local ROM-derived header, matrix,
land, and event NARCs at runtime.

For random landing membership, the host-side oracle scans only the same
`[-32,+31]` window the ROM helper can sample and clamps the scan to the same
32x32 matrix cell as the center tile. It reads that loaded destination cell's
land-file permissions, rejects high-bit blocked permissions, excludes static
warp/coord-event tiles, and stores the predicate label
`same_loaded_cell_passable_low_land_non_headbutt_no_warp_coord_event_v3` in the
compact JSON. The public current-map random helper uses that generated evidence
directly for encounter maps. The lower-level loaded-tile validator also
dispatches through the live field permission provider at `fieldSystem + 0x60`
with raw tile coordinates and rejects high-bit permissions, then calls
`IsMetatileBlockedAt`, `GetMetatileBehaviorAt`, and current-map
warp/coord-event scans. The direct `0x02054824` permission implementation was
not used because it can bypass the active field callback that the stock helpers
use, and the broad live sampler was removed after T24 showed it could still pick
static high-bit permission tiles.

This is a space-conscious MVP tradeoff. Cross-map L+R gets meaningful random
land relocation on the selected map without storing whole-map or whole-route
tile tables in overlay 131, and it avoids the connection-cell mismatch that can
admit water, padding, high-bit blocked tiles, or non-walkable terrain. The
public random-loaded-land API remains available for same-map and future
overworld triggers on generated encounter maps; it can be broadened later if a
future feature can afford a wider, fully audited current-map search.

Exact focused command:

```bash
scripts/headless-random-land-teleport-verifier.py \
  --rom test.nds \
  --map-symbol MAP_T24 \
  --runs 8 \
  --min-unique-coordinates 2 \
  --destinations documentation/verification/encounter_map_teleport_destinations.json \
  --json /tmp/random_MAP_T24_final_counter.json \
  --jsonl /tmp/random_MAP_T24_final_counter.jsonl
```

Final focused random-land verification on this branch produced:

- `passed`: true
- `passed_run_count`: 16
- `failed_run_count`: 0
- `unique_coordinate_count`: 4
- destination coverage: `MAP_T24` and `MAP_R29`, each run in a fresh emulator
  process with 8/8 passing runs
- observed strict compact land pairs: `MAP_T24` `(177,370)` / `(178,370)` and
  `MAP_R29` `(576,396)` / `(577,396)`

## Runtime Verifier

The L+R debug path remains the verification trigger. Overlay 131 exposes a
small fixed debug status block at `0x023C801C` beside the writable debug
destination at `0x023C8014`. The status block records magic/version/size,
whether the live field system is ready, the current field `location` map/x/y,
the last `MapTeleport_Request` result, a request counter, and the selected
encounter destination index or deterministic-force sentinel. The debug task
publishes `requestResult` before incrementing `requestCount`, so a sampled count
advance cannot observe the previous result. Random-land acceptance does not
depend solely on counters because overlay reloads can reset them; that verifier
uses relocation, map/index, strict host classification, and non-stale screen
evidence. The transition verifier intentionally uses the request counter/result
pair for the deterministic `0xFFFE` exact path, where the request evidence is
visible before the overlay reload clears the later status.

`scripts/headless-all-encounter-teleport-verifier.py` boots `test.nds` with the
test save, writes each generated encounter-map destination into the debug
destination block, selects the deterministic `0xFFFE` forced path, presses L+R,
waits for the debug status block to match the expected map/x/y, checks that the
screenshot is nonblack, writes one JSONL result per map, and writes a summary
JSON. Each destination is checked by a short-lived worker process with a fresh
emulator/save import so a bad or busy transition cannot poison later rows. The
runtime all-encounter verifier therefore proves exact destination warp coverage;
the static audit below covers numeric table parity and zero random-candidate
checks for all 150 generated rows.

Final map/x/y and a nonblack screen are not enough by themselves, because a
fresh save can already start at a destination. Each passed row must also have
one of two evidence paths: the debug request counter changed and the last
request result is `MAP_TELEPORT_RESULT_OK`, or the initial ready location did
not already match the target and the final location changed exactly to the
target. If the initial location already matched the target and no OK request was
observed, the row fails as a stale match.

The verifier exits successfully only when all of these are true:

- authoritative encounter count is 150,
- generated destination count is 150,
- runtime checked count is 150,
- runtime pass count is 150, and
- every passed row has request or movement evidence, and
- the built field overlay artifacts are below `0x5000` bytes, and
- the overlay encounter-destination entry reports count 150.

For review worktrees without `rom.nds` or DeSmuME available, the same script
also supports a static audit:

```bash
scripts/headless-all-encounter-teleport-verifier.py \
  --static-only \
  --destinations documentation/verification/encounter_map_teleport_destinations.json \
  --expect-count 150
```

That static audit parses the packed C destination table, compares all 150 rows
against the compact JSON, checks the authoritative encounter-symbol order,
recomputes the compact random-tile count/hash/bounds from ROM-derived
matrix/land/event data, proves every row has a generated strict horizontal
pair, and fails if any generated destination has `random_tile_count: 0`, stale
random-tile evidence, or a runtime predicate mismatch. The final static audit
produced `packed_table_matches_json: true`, `zero_random_tile_count: 0`,
`compact_pair_coverage_count: 150`, `compact_pair_mismatch_count: 0`,
`compact_pair_t24.pair: [(177,370), (178,370)]`,
`runtime_permission_active_callback_scan_detected: true`,
`runtime_generated_current_map_selector_detected: true`, and `passed: true`.

Exact commands:

```bash
python3 scripts/generate_encounter_map_teleport_destinations.py
```

```bash
scripts/headless-all-encounter-teleport-verifier.py \
  --rom test.nds \
  --destinations documentation/verification/encounter_map_teleport_destinations.json \
  --json documentation/verification/all_encounter_teleport_verifier.json \
  --jsonl documentation/verification/all_encounter_teleport_verifier.jsonl \
  --expect-count 150 \
  --max-wait-frames 720 \
  --post-ready-wait-frames 180
```

The L+R transition also has a focused aesthetic regression verifier:

```bash
scripts/headless-map-teleport-transition-verifier.py \
  --rom test.nds \
  --json documentation/verification/map_teleport_transition_verifier.json
```

It samples from the initial L+R key-down through hold, release, and the
post-release transition window. Each sampled screenshot is checked as a whole
frame and as separate top and bottom DS screens, so a Fly-style solid-white
landing frame on either screen fails the verifier. Before the plain
`Task_ScriptWarp` scheduler, the old `sub_020538C0` path landed successfully
but failed this check with `solid_white_frames: [60]`.

The focused transition verifier on this branch produced:

- `passed`: true
- `request_evidence.frame`: 3
- `request_evidence.request_result`: `MAP_TELEPORT_RESULT_OK`
- `request_frame_ok`: true
- `solid_white_whole_frame_count`: 0
- `solid_white_top_frame_count`: 0
- `solid_white_bottom_frame_count`: 0

## Space Impact

This version still adds no code or data to overlay 149. The all-map destination
table and verifier-facing status/lookup entries live in overlay 131 with the
existing map teleport helper. To keep overlay 131 below the `0x5000` boundary
before overlay 149, the destination table is 150 packed `u32` records: 10 bits
for map ID, 11 bits for x, 10 bits for y, and implicit south direction. The
generator asserts those bounds before writing the C table and the indexed API
decodes directly into caller-provided storage.

Heavy derivation code, JSON artifacts, and the headless verifier stay outside
the ROM. The compact destination audit JSON is 88,390 bytes and stores
count/hash/bounds evidence instead of full random-coordinate arrays for all 150
maps.

After the final Docker build, `build/output_field.bin` and
`base/overlay/overlay_0131.bin` are 20,326 bytes (`0x4F66`), 154 bytes below the
20,480-byte (`0x5000`) limit. Overlay 149 remains unchanged at 44,928 bytes
(`0xAF80`).
