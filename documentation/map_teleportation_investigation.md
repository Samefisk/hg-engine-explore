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
