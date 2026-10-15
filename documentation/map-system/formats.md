# HeartGold map data formats

Reference for the map archives that `tools/maps` reads and writes. Every layout
below is **verified** by `python3 -B -m tools.maps roundtrip`: decoding each
vanilla member to its JSON spec and encoding it again gives identical bytes,
with no raw fallback fields in use. `check-reference` compares decoded event
and header fields with the pokeheartgold decomp in `.codex-reference/` and
matrix files byte for byte; land and area data have no decomp source to
compare against.

The encoders also enforce the rules below on edited specs (field ranges, the
event size limit, BDHC references, matrix size and section flags,
background-sound alignment). `pack` then checks references between archives
(header → matrix/area/events, matrix → land) before writing anything.

Background research and sources: the research report and notes in
[research/](research/report.md).

## How the pieces connect

```
map header (ARM9 table, by map ID)
 ├─ matrixId ──────► map matrix (a/0/4/1) ── cell ──► land data (a/0/6/5)
 │                                                     ├─ tiles (collision + behavior)
 │                                                     ├─ buildings ──► bm_field models (a/0/4/0)
 │                                                     ├─ NSBMD map model
 │                                                     └─ BDHC terrain heights
 ├─ areaDataBank ──► area data (a/0/4/2) ──► map textures (a/0/4/4), building set (a/0/4/3, a/0/7/0)
 ├─ eventsBank ────► zone events (a/0/3/2)
 ├─ scriptsBank / scriptHeaderBank ──► scr_seq (a/0/1/2)
 ├─ msgBank ───────► text (a/0/2/7)
 └─ wildEncounterBank ──► encounters (a/0/3/7), managed by armips/data/encounters.s
```

## Map header — ARM9 table

- USA table at `arm9.bin` offset `0xF6BE0`, 540 entries × 24 bytes. Entry
  count comes from `fielddata/maptable/mapname.bin` (16-byte names).
- Layout matches `struct MapHeader` in pokeheartgold `include/map_header.h`:
  `u8 wildEncounterBank` (0xFF = none), `u8 areaDataBank`,
  `u16 moveModelBank:4 worldMapX:6 worldMapY:6`, then u16 `matrixId`,
  `scriptsBank`, `scriptHeaderBank`, `msgBank`, `dayMusicId`, `nightMusicId`,
  `eventsBank`, `u16 mapsec:8 areaIcon:4 momCallIntroParam:4`, and a u32 of
  flags packed from bit 0: `regionNo:1 weather:7 mapType:4 cameraType:6
  followMode:2 battleBg:5 bikeAllowed runningAllowed_Unused escapeRopeAllowed
  flyAllowed outgoingCalls incomingCalls radioSignal`.
- IDs at or past the table end are redirected to `MAP_NOTHING` (1) by the
  game's bounds check, so new IDs need a larger table, not just new data.
- pokeheartgold names 39 `*_UNUSED` IDs (for example 8, 82, 128–130,
  208–213, 254–262, 538) that can be reused before growing the table.

## Map matrix — a/0/4/1 (288 files)

`u8 width, u8 height, u8 hasHeaders, u8 hasAltitudes, u8 nameLen, name`, then
row-major `u16 headers[w*h]` (optional), `u8 altitudes[w*h]` (optional),
`u16 landDataIds[w*h]`.

- Byte 0 is **width**: matrix 0 (the Johto/Kanto overworld) is 47 × 17.
  pokeplatinum's doc names these bytes the other way round.
- Limits: at most 799 cells, name at most 16 bytes. Land ID `0xFFFF` = no chunk.
- Matrix 0 is patched at run time (Mahogany tree, Lake of Rage, Safari Zone).

## Land data — a/0/6/5 (676 files)

| Offset | Content |
|---|---|
| 0x00 | u32 sizes: tiles (always 0x800), buildings, NSBMD, BDHC |
| 0x10 | HGSS background-sound block: `u16 0x1234`, `u16 length`, `length` bytes |
| after BGS | tiles, buildings, NSBMD, BDHC, in that order |

**The tiles do not always start at 0x14.** 230 vanilla files have a non-empty
background-sound block. Read its length; `scripts/dump-route29-tree-grid.py`
assumes the fixed offset and is only right for maps whose block is empty.

The game itself has a fixed-offset reader: `TerrainAttributes_Load` reads tiles
at `0x14` (pokeheartgold `src/terrain_attributes.c`). It is used only in the
field modes that set `unk0_10` in `field_warp_tasks.c` (modes 3 and 4, which
look Battle Tower related). Do not add background sound to land data loaded
in those modes. The block length must stay a multiple of 4 so the model stays
4-byte aligned; the encoder enforces this.

**Tiles**: 32 × 32 little-endian u16, row-major. Bits 0–7 = tile behavior
(`enum TILE_BEHAVIOR`, pokeheartgold `include/constants/metatile_behavior.h`),
bits 8–14 = secondary value (community: footstep sound; not confirmed in code),
bit 15 = collision. The spec stores these as three 32-row text layers:
`collision` (`#` blocked, `.` open), `behavior` and `secondary` (hex bytes).

**Buildings**: 48-byte records — `u32 modelId`, position `x y z`, rotation
`rotX rotY rotZ`, scale `scaleX scaleY scaleZ` (fx32 / angle ints), two unused
words. Vanilla maximum is 30 per file; the game's real limit is in
undecompiled code, so the encoder does not enforce one yet.

**NSBMD**: kept as `model.nsbmd` beside `land.json`; textures come from the
area's map texture set, not the file. No open tool writes NSBMD yet.

**BDHC**: `"BDHC"`, six u16 counts, then arrays in this order:
points (fx32 x, z), normals (fx32 x, y, z), constants (fx32), plates
(u16 point1, point2, normal, constant), strips (fx32 scanline, u16 count,
u16 start), access list (u16 plate indices). HGSS uses the same 8-byte strip as
Platinum. The encoder requires every plate, strip and access reference to be
in range and strips sorted by scanline, as in all 676 vanilla files.
pokeplatinum `docs/maps/bdhc.md` explains the height lookup.

## Area data — a/0/4/2 (106 files)

8 bytes: `u16 buildingsTileset` (a/0/4/3 and a/0/7/0), `u16 mapTileset`
(a/0/4/4), `u16 dynamicTextureType` (meaning unknown), `u8 areaType`
(0 indoor, 1 outdoor), `u8 lightType`.

## Zone events — a/0/3/2 (491 files)

Four arrays, each prefixed by a u32 count:

| Array | Size | Fields |
|---|---|---|
| `bgs` (signs, hidden items) | 20 | `u16 scriptId, u16 type, s32 x, s32 z, s32 y, u16 dir, u16 dirPadding` |
| `objects` (NPCs) | 32 | `u16 id, spriteId, movement, type, eventFlag, scriptId; s16 facingDirection; u16 param0–2; s16 xRange, yRange; u16 x, z; s32 y` |
| `warps` | 12 | `u16 x, z, header (destination map), anchor (destination warp index); u32 y` |
| `coords` (step triggers) | 16 | `u16 scriptId; s16 x, z; u16 w, h, y, val, var` |

Field names match pokeheartgold's `zone_event/*.json`, which uses symbols where
we store numbers. **The whole file must be smaller than 0x800 bytes**; the
encoder refuses larger files. The largest vanilla file is 1,660 bytes.

## Other limits to respect

- 64 live map objects, which includes the player, the follower and
  script-spawned objects.
- Level-script header bank (`scriptHeaderBank`) must be under 0x100 bytes.
- hg-engine has changed the field heap layout, so vanilla heap sizes do not
  apply. Measure on the current ROM.

## Not covered yet

- `bm_field` / `bm_room` building models, `area_build`, `map_tex_set` NSBTX,
  area lights, `move_model_list`, Pokégear town-map and fly tables
  (overlay 101), spawn table `sSpawnMaps`.
- Writing the ARM9 header table back into a build. `pack` writes
  `map_headers.bin`; there is no build hook for it yet. `pack` requires
  exactly 540 entries until the table can grow.
- References into scripts, text, music and encounters are not range-checked.
