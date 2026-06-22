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
transition implementation. The script `warp` command calls the same family of
transition tasks through `TaskManager_Jump`, which is fragile from a SysTask
verification trigger because it requires the correct active task-manager node.
The MVP uses the nearby vanilla entry `sub_020538C0(FieldSystem *, mapId,
warpId, x, y, direction)`, which allocates the same warp task environment but
queues it with `FieldSystem_CreateTask`. That keeps the trigger from deriving a
task-manager pointer from live field internals.

The decomp confirms that `sub_020538C0` builds a `Location` from its arguments
and that `ScrCmd_180` passes `mapId, x, y` to it without coordinate conversion.
Only `warpId != -1` makes the loader replace x/y from map warp events, so this
helper uses `warpId = -1` for explicit tile destinations.

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
- the destination map id and direction are in valid ranges, and
- same-map destinations pass a loaded collision/land check.

This keeps the L+R hook an overworld-only verification path and keeps the core
helper usable from future overworld triggers such as "if X then teleport to this
map/tile".

## Overlay And Space Constraints

Overlay 149 is the visible-overworld-wild spawn overlay and is already a tight,
large overlay. This feature does not add code or data to overlay 149.

The reusable helper lives in overlay 131, the field extension overlay, behind a
small fixed-address entry table. The always-built field-ready hook only calls
that entry table to start the verifier task; the verifier poller and writable
debug destination also live in overlay 131. Public callers can use
`MapTeleport_Request`. No common script entry, destination UI, effect code,
sound code, or overlay 149 code/data is added for teleportation.

## Validation Limits And Caller Contract

`MapTeleport_Request` accepts any caller-provided `mapId`, field `Location.x`,
field `Location.y`, and `direction`, subject to cheap safety checks:

- map IDs must be in the known map constant range and must not be the early
  special placeholder/direct maps,
- direction must be north, south, west, or east,
- the live field system must be present, and
- if the destination is on the currently loaded map, the helper verifies that
  the target tile is not blocked and is not a surf or headbutt tile.

The helper does not load arbitrary destination maps just to inspect collision
before warping. Doing so would add more map-loading surface area and code size
than the MVP needs. For cross-map calls, callers must pass a vetted destination:
the target map must be complete and loadable, and the target field `Location`
coordinate must be in-bounds, unoccupied, and known-safe land.

The L+R debug destination is writable on purpose. The default is New Bark
(`MAP_T20`, `0x02B7`, `0x018D`, south), and the headless matrix patches that
struct to verify multiple distinct known-good outdoor destinations.

## Final Implementation Plan

1. Add `include/map_teleport.h` with the destination struct, result enum, and
   `MapTeleport_Request`.
2. Add `src/field/map_teleport.c` in overlay 131, not overlay 149.
3. Expose the helper through a fixed-address overlay entry table.
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
Candidate tiles reject high-bit blocked permissions and the same low-byte
headbutt/surf behaviors that the runtime same-map check rejects:
`6, 16, 18, 21, 42`. Warps and trigger rectangles from the target event file
are excluded when event data exists.

A few destinations are runtime-verified fixed coordinates because the static
permission grid alone chooses a bad loaded tile or marks a proven runtime tile
as blocked. These are recorded in the audit JSON with `source:
verified:derived`. The final L+R verifier is the acceptance proof for these
rows.

The generated runtime table is checked in at
`src/field/map_teleport_encounter_destinations.c`, and the audit JSON is
checked in at `documentation/verification/encounter_map_teleport_destinations.json`.
Future overworld callers can use
`MapTeleport_GetEncounterDestinationByIndex`,
`MapTeleport_GetEncounterDestinationByMapId`, and `MapTeleport_Request` to
teleport to the vetted destination for an encounter map.

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

## Runtime Verifier

The L+R debug path remains the verification trigger. Overlay 131 now exposes a
small fixed debug status block at `0x023C801C` beside the writable debug
destination at `0x023C8014`. The status block records magic/version/size,
whether the live field system is ready, the current field `location` map/x/y,
the last `MapTeleport_Request` result, and a request counter.

`scripts/headless-all-encounter-teleport-verifier.py` boots `test.nds` with the
test save, patches the writable debug destination for each generated
encounter-map destination, presses L+R, waits for the debug status block to
match the expected map/x/y, checks that the screenshot is nonblack, writes one
JSONL result per map, and writes a summary JSON. Each destination is checked by
a short-lived worker process with a fresh emulator/save import so a bad or busy
transition cannot poison later rows.

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

Final verification on this branch produced:

- `expected_count`: 150
- `authoritative_count`: 150
- `generated_destination_count`: 150
- `runtime_checked_count`: 150
- `runtime_pass_count`: 150
- `runtime_fail_count`: 0
- `passed`: true

## Space Impact

This version still adds no code or data to overlay 149. The all-map destination
table and verifier-facing status/lookup entries live in overlay 131 with the
existing map teleport helper. To keep overlay 131 below the `0x5000` boundary
before overlay 149, the destination table is 150 packed `u32` records: 10 bits
for map ID, 11 bits for x, 10 bits for y, and implicit south direction. The
generator asserts those bounds before writing the C table and the lookup API
decodes into overlay-local scratch storage.

Heavy derivation code, JSON artifacts, and the headless verifier stay outside
the ROM. After the packed-table build, `build/output_field.bin` and
`base/overlay/overlay_0131.bin` are 20,180 bytes (`0x4ED4`), below the
20,480-byte (`0x5000`) limit; overlay 149 remains 44,928 bytes (`0xAF80`).
The all-map verifier includes the field overlay size report in its JSON summary
and fails the acceptance gate if any existing checked field overlay artifact is
`>= 0x5000`.
