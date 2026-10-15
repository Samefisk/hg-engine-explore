# HGSS map data formats, decompilation representation, and extension limits

Scope: Pokémon HeartGold/SoulSilver (USA, IPKE/IPGE), compared with pret/pokeplatinum and DSPRE. Primary evidence is the pret/pokeheartgold source tree (local read-only checkout at `.codex-reference/pokeheartgold`, `master` commit `f02bd74646ec`, dated 2026-07-13), pret/pokeplatinum `main` (read through the GitHub API, 2026-10), DSPRE `main` C# sources, and the DS-Pokemon-Hacking wiki repository. "Local measurement" means a byte-level parse I ran on the binary NARCs committed in pokeheartgold (they are the vanilla archives). URL abbreviations used below:
- PHG = https://github.com/pret/pokeheartgold/blob/master/
- PP = https://github.com/pret/pokeplatinum/blob/main/
- DSPRE = https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/
- DSPH = https://github.com/DS-Pokemon-Hacking/ds-pokemon-hacking.github.io/blob/main/

## Q1. Archive paths and binary formats of each HGSS map structure

### Takeaway
A HGSS map is a 24-byte ARM9 map header that points to a map matrix (a/0/4/1), area data (a/0/4/2), scripts (a/0/1/2), events (a/0/3/2), text (a/0/2/7) and encounters (a/0/3/7 HG or a/1/3/6 SS). Each matrix cell points to a land_data file (a/0/6/5). That file holds 32x32 u16 terrain attributes, building props, an NSBMD and a BDHC. HGSS differs from Platinum in two ways. It adds a background-sound (BGS) block after the 16-byte land-data header. Its area data is also 8 bytes, with an indoor/outdoor byte and a light byte.

### Cited Findings

**Archive map (HGSS USA)**
- The pokeheartgold build maps named sources to numbered archives: `zone_event.narc`→a/0/3/2, `map_matrix.narc`→a/0/4/1, `scr_seq.narc`→a/0/1/2, `msg.narc`→a/0/2/7, `g_enc_data.narc`→a/0/3/7, `s_enc_data.narc`→a/1/3/6, `headbutt.<ver>.narc`→a/2/5/2, `safari_enc.narc`→a/2/3/0, `mmodel.narc`→a/0/8/1, `gs_areawindow.narc`→a/1/6/3, `pgmap_gra.narc`→a/1/4/4 — [PHG filesystem.mk](https://github.com/pret/pokeheartgold/blob/master/filesystem.mk)
- NARC id 65 is named `NARC_fielddata_landdata_land_data`, so a/0/6/5 is land_data. Id 41 is the map matrix and id 32 is zone_event — [PHG include/filesystem_files_def.h](https://github.com/pret/pokeheartgold/blob/master/include/filesystem_files_def.h)
- DSPRE's HGSS directory table lists these paths: maps a/0/6/5, matrices a/0/4/1, area data a/0/4/2, building config (area_build) a/0/4/3, map textures a/0/4/4, building textures (areabm_texset) a/0/7/0, exterior buildings a/0/4/0, interior buildings a/1/4/8, events a/0/3/2, scripts a/0/1/2, text a/0/2/7, OW sprites a/0/8/1, headbutt a/2/5/2, rock smash a/2/5/3, safari a/2/3/0, encounters a/0/3/7 (HG) or a/1/3/6 (SS). Its dynamic-headers patch uses a/0/5/0 as the header container — [DSPRE DS_Map/RomInfo.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/RomInfo.cs)
- The wiki's HGSS file-structure table adds these paths: a/1/0/6 bm_anime, a/1/0/7 bm_field_anime_list, a/1/0/8 bm_room_anime_list, a/0/4/7 and a/0/9/2 move_model_list ("(?)"), a/1/0/3 fldeff, a/1/3/9 fldtanime, `/fielddata/build_model/{bm_field,bm_room}.narc` (a "necessary duplicate"), `bm_field_matshp.dat`, `bm_room_matshp.dat` and `/fielddata/maptable/mapname.bin` — [DSPH hgss-file_structure.mdx](https://github.com/DS-Pokemon-Hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/resources/hgss-file_structure/hgss-file_structure.mdx)
- Vanilla archive member counts (local measurement of the committed archives): a/0/6/5 has 676 files, a/0/4/2 has 106, a/0/4/4 has 106, a/0/4/3 has 104, a/0/7/0 has 104, a/0/4/0 (bm_field) has 340 and a/1/4/8 (bm_room) has 222 — [PHG files/a/0/6/5](https://github.com/pret/pokeheartgold/tree/master/files/a/0/6)
- `files/fielddata/mapmatrix/map_matrix/` holds 288 matrix files, `files/fielddata/eventdata/zone_event/` holds 491 event JSON files, and `mapname.bin` is 8640 bytes (540 entries x 16 bytes) — [PHG files/fielddata](https://github.com/pret/pokeheartgold/tree/master/files/fielddata)

**Map header (ARM9 table, not a file)**
- `struct MapHeader` (24 bytes) contains: `u8 wildEncounterBank; u8 areaDataBank; u16 moveModelBank:4, worldMapX:6, worldMapY:6; u16 matrixId, scriptsBank, scriptHeaderBank (level/init scripts), msgBank, dayMusicId, nightMusicId, eventsBank; u16 mapsec:8, areaIcon:4, momCallIntroParam:4; u32 regionNo:1, weather:7, mapType:4, cameraType:6, followMode:2, battleBg:5, bikeAllowed:1, runningAllowed_Unused:1, escapeRopeAllowed:1, flyAllowed:1, outgoingCalls:1, incomingCalls:1, radioSignal:1` — [PHG include/map_header.h](https://github.com/pret/pokeheartgold/blob/master/include/map_header.h)
- `mapType` values are INVALID, CITY_TOWN, ROUTE, CAVE, INTERIOR, POKEMON_CENTER (unused in HGSS) and UNDERGROUND (a Sinnoh leftover). `followMode` values are PREVENT=0, HEIGHT_RESTRICT=1 and ALLOW=2. `wildEncounterBank` equal to `ENCDATA_NA` (0xFF) means no encounters — [PHG include/map_header.h](https://github.com/pret/pokeheartgold/blob/master/include/map_header.h), [PHG src/map_header.c](https://github.com/pret/pokeheartgold/blob/master/src/map_header.c); DSPRE also uses `HGSS_NULL_ENCOUNTER_FILE_ID = 0xff` — [DSPRE DS_Map/ROMFiles/MapHeader.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapHeader.cs)
- In pokeheartgold the table is the C array `sMapHeaders[]` in `src/data/map_headers.h`, using designated initializers (`[MAP_EVERYWHERE] = {...}`) with symbolic NARC member constants. Every getter calls `MapNumberBoundsCheck`, which asserts `mapId < NELEMS(sMapHeaders)` and otherwise falls back to `MAP_NOTHING` — [PHG src/data/map_headers.h](https://github.com/pret/pokeheartgold/blob/master/src/data/map_headers.h), [PHG src/map_header.c](https://github.com/pret/pokeheartgold/blob/master/src/map_header.c)
- DSPRE puts the HGSS header table at ARM9 offset 0xF6BE0 for English, 0xF6BC8/0xF6BD0 for Spanish HG/SS, 0xF6B58 for Italian, 0xF6BC4 for French, 0xF6B94 for German and 0xF6390 for Japanese. Header stride is 0x18. Its HGSS bit-unpacking matches the decomp struct. DSPRE counts headers as `mapname.bin` length / 16 — [DSPRE DS_Map/RomInfo.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/RomInfo.cs), [DSPRE MapHeader.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapHeader.cs)
- The map ID count is `MAP_ID_MAX = 540` (IDs 0..539). 0 is `MAP_EVERYWHERE` and 1 is `MAP_NOTHING` — [PHG include/constants/maps.h](https://github.com/pret/pokeheartgold/blob/master/include/constants/maps.h)
- For comparison, the Platinum header uses a different layout: `u8 areaDataArchiveID; u8 unk; u16 matrix, scripts, initScripts, msg, dayMusic, nightMusic, wildEncounters (u16), events; u16 mapLabelTextID:8, mapLabelWindowID:8; u8 weather; u8 cameraType; u16 mapType:7, battleBG:5, bike, running, escapeRope, fly` — [PP docs/maps/file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md)

**Map matrix (a/0/4/1)**
- File layout: `u8 width; u8 height; u8 hasHeaders; u8 hasAltitudes; u8 nameLen; char name[nameLen]`, then optional `u16 headers[w*h]`, optional `u8 altitudes[w*h]`, then required `u16 landDataIds[w*h]`, all row-major. If there is no header section, every cell is filled with the current map ID. Name length is asserted to be at most 16 — [PHG src/map_matrix.c](https://github.com/pret/pokeheartgold/blob/master/src/map_matrix.c)
- Conflict: the Platinum doc labels byte 0 `height` and byte 1 `width` — [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md). The HGSS decomp reads byte 0 as width and byte 1 as height — [PHG src/map_matrix.c](https://github.com/pret/pokeheartgold/blob/master/src/map_matrix.c). Verify against a known non-square matrix before writing a tool.
- `MAP_MATRIX_MAX_SIZE = 799` cells. The in-RAM `MAPMATRIXDATA` holds headers, altitudes and models arrays of that size plus a 16-byte name — [PHG include/map_matrix.h](https://github.com/pret/pokeheartgold/blob/master/include/map_matrix.h)
- Matrix 0 (`EVERYWHERE`) is the overworld. ARM9 code patches it at runtime: Mahogany antenna tree (model 86 at row 5, column 16), Lake of Rage water level (models 89–100) and Safari Zone area placement — [PHG src/map_matrix.c](https://github.com/pret/pokeheartgold/blob/master/src/map_matrix.c)

**Land data (a/0/6/5)**
- DPPt/HGSS layout: 4 u32 section lengths (permissions, always 2048; buildings; NSBMD; BDHC). **HGSS only:** a BGS block follows at 0x10, made of a `u16 0x1234` signature, a `u16 length` and `length` bytes. After that come permissions (1024 x {u8 type/behavior, u8 collision}), buildings (48 bytes each), the NSBMD and the BDHC. DSPRE strips embedded textures from NSBMDs that have more than one block — [DSPRE DS_Map/ROMFiles/MapFile.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapFile.cs)
- The HGSS decomp hard-codes `TERRAIN_ATTRIBUTES_OFFSET 0x14` ("was 0x10 in platinum, but is 0x14 in hg/ss"), `TERRAIN_ATTRIBUTES_SIZE 0x800`, 32x32 tiles, `TERRAIN_ATTRIBUTES_MAX_BLOCK_COUNT 16` and `TERRAIN_ATTRIBUTES_MAP_MATRIX_COUNT 225` — [PHG include/terrain_attributes.h](https://github.com/pret/pokeheartgold/blob/master/include/terrain_attributes.h)
- Local measurement over all 676 vanilla land_data files: every file has the 0x1234 BGS signature, 230 of them have a non-empty BGS payload, every permissions length is 2048, and the maximum building count in one file is 30 — [PHG files/a/0/6/5](https://github.com/pret/pokeheartgold/tree/master/files/a/0/6)
- Platinum's land-data header order is `terrainAttributesSize, mapPropsSize, mapModelSize, bdhcSize`, followed by attributes at 0x10, props (at most 32 per map), the NSBMD and the BDHC. A `MapProp` is `u32 modelID; VecFx32 position; VecFx32 rotation (0–65535); VecFx32 scale; u32 dummy[2]` (48 bytes) — [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md), [PP src/overlay005/land_data.c](https://github.com/pret/pokeplatinum/blob/main/src/overlay005/land_data.c). DSPRE's comment describes the building record with position, scale and filler fields. Its writer also emits three rotation ints. The pret struct is the more precise source.
- BDHC layout: magic `BDHC`, then u16 counts (points, normals, constants, plates, strips, accessList). The arrays follow: points (fx32 x,z), normals (VecFx32), constants (fx32), plates (u16 p1, p2, normal, constant), strips (fx32 scanline, u16 count, u16 start; sorted by scanline) and a u16 access list. BDHC coordinates run from (-256,-256) to (256,256) per map — [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md); background on the method is in [PP docs/maps/bdhc.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/bdhc.md)

**Area data, textures, buildings, lights**
- HGSS area data (8 bytes): `u16 buildingsTileset` (index into area_build a/0/4/3 and areabm_texset a/0/7/0), `u16 mapTileset` (map_tex_set a/0/4/4), `u16 dynamicTextureType`, `u8 areaType` (0 indoor, 1 outdoor) and `u8 lightType`. Platinum uses `u16, u16, u16 unknown, u16 light` — [DSPRE DS_Map/ROMFiles/AreaData.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/AreaData.cs). Local measurement: all 106 HGSS area files are 8 bytes, for example `0000 0000 ffff 01 01` — [PHG files/a/0/4/2](https://github.com/pret/pokeheartgold/tree/master/files/a/0/4)
- area_build is `u16 count; u16 modelIds[count]` (indices into build_model). Map/prop textures are whole-file NSBTX. `bm_*_matshp.dat` is `u16 locatorCount; u16 idsCount; {u16 count, u16 index}[]; {u16 material, u16 shape}[]`. anime_list entries are `bool hasAnim; u8 flags; bool isBicycleSlope; u32 animIds[4]` (Platinum doc) — [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md). In HGSS the corresponding files are `files/fielddata/build_model/bm_field.narc`, `bm_field_matshp.dat`, `bm_room.narc` and `bm_room_matshp.dat` — [PHG files/fielddata/build_model](https://github.com/pret/pokeheartgold/tree/master/files/fielddata/build_model)
- Area light files are CRLF text in 9-line blocks: end time (seconds/2), 4 lights (valid, RGB5, fx16 direction), then diffuse, ambient, specular and emission colors. HGSS ships `files/data/area00light.txt`–`area02light.txt` and `arealight.narc` — [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md), [PHG files/data](https://github.com/pret/pokeheartgold/tree/master/files/data)

**Zone events (a/0/3/2)**
- The binary is a sequence of 4 counted arrays, each prefixed by a u32 count. BG events are 20 bytes: `u16 scriptId, u16 type, s32 x, s32 z, s32 y, u16 dir` (padded). Object events are 32 bytes: `u16 id, spriteId, movement, type, eventFlag, scriptId; s16 facing; u16 param[3]; s16 xRange, yRange; u16 x, z; s32 y`. Warps are 12 bytes: `u16 x, z, header (dest map), anchor (dest warp idx); u32 y`. Coord triggers are 16 bytes: `u16 scriptId; s16 x, z; u16 w, h, y, val, var` — [PHG include/map_events_internal.h](https://github.com/pret/pokeheartgold/blob/master/include/map_events_internal.h), [PHG zone_event.json.txt](https://github.com/pret/pokeheartgold/blob/master/files/fielddata/eventdata/zone_event.json.txt)

**Scripts / level scripts (a/0/1/2)**
- `scr_seq` contains both script banks and "hdr" (init/level-script) banks. The header field `scriptHeaderBank` points to `scr_seq_NNNN_<MAP>_hdr` files, written in assembly with macros such as `InitScriptEntry_OnTransition <label>`, `InitScriptEntryEnd` and `InitScriptEnd`. Vanilla has 468 hdr sources. The loader asserts that the hdr bank is under 0x100 bytes — [PHG files/fielddata/script/scr_seq](https://github.com/pret/pokeheartgold/tree/master/files/fielddata/script), [PHG src/map_events.c](https://github.com/pret/pokeheartgold/blob/master/src/map_events.c)

**Map names, town map / fly, encounters, headbutt**
- `mapname.bin` holds 16-byte internal names, one per header (540) — [PHG files/fielddata/maptable](https://github.com/pret/pokeheartgold/tree/master/files/fielddata/maptable); DSPRE uses `internalNameLength = 16` — [DSPRE RomInfo.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/RomInfo.cs)
- Fly and blackout spawns live in the ARM9 table `sSpawnMaps`. Each 18-byte entry packs `flagIdx:8 | isBlackoutSpawn<<8 | isFlyPoint<<9`, followed by deathSpawnMap, deathSpawnX|Y<<8, flyPointMap/X/Y and specialWarpMap/X/Y. There are 31 entries; `SPAWN_*` constants are in `constants/spawns.h` — [PHG asm/unk_0203BA5C.s](https://github.com/pret/pokeheartgold/blob/master/asm/unk_0203BA5C.s), [PHG include/constants/spawns.h](https://github.com/pret/pokeheartgold/blob/master/include/constants/spawns.h)
- Pokégear town-map location and flypoint tables live in overlay 101 (`MapFlypointParam`, `PokegearMapLocationSpec`) — [PHG include/application/pokegear/map/pokegear_map_internal.h](https://github.com/pret/pokeheartgold/blob/master/include/application/pokegear/map/pokegear_map_internal.h). A community guide documents hex edits to the overlay 101 tables, such as the red-to-gray town table at ov101 0x10274 (0x021F79B4), and town-map graphics in a/1/4/4 — [DSPH hgss-town_map.md](https://github.com/DS-Pokemon-Hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/hgss-town_map/hgss-town_map.md)
- Encounters: one JSON source (`gs_enc_data.json`, entries keyed by map with land/surf/... rate+mons) builds both `g_enc_data.narc` and `s_enc_data.narc` through jsonproc → C → mwcc → o2narc, with `-DENC_HEARTGOLD/ENC_SOULSILVER` — [PHG files/fielddata/encountdata/gs_enc_data.mk](https://github.com/pret/pokeheartgold/blob/master/files/fielddata/encountdata/gs_enc_data.mk)
- Headbutt: `files/arc/headbutt.json` (per map: CommonMons, RareMons, SecretMons, Trees, SecretTrees) is built through a jsonproc template into `headbutt.<ver>.narc` → a/2/5/2. The first two shorts are the tree count and the secret-tree count — [PHG files/arc/headbutt.json.txt](https://github.com/pret/pokeheartgold/blob/master/files/arc/headbutt.json.txt)

**Dynamic map features**
- Platinum documents a "dynamic map features" system (runtime data plus a 32-byte persisted save buffer; only one feature active at a time) — [PP docs/maps/dynamic_map_features.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/dynamic_map_features.md). In HGSS, matrix-level runtime edits (Mahogany tree, Lake of Rage, Safari) are hard-coded in `map_matrix.c` — [PHG src/map_matrix.c](https://github.com/pret/pokeheartgold/blob/master/src/map_matrix.c)

### Inferences
- The pokeheartgold `TerrainAttributes` loader reads at a fixed 0x14. That is correct only when the BGS block is empty, yet 230 vanilla files have a non-empty BGS. The loader is only called when a field-mode table flag is set (`field_warp_tasks.c`, `unk74->unk0_10`). The general streaming loader is still undecompiled overlay code and presumably honours the BGS length. A new tool should parse BGS length rather than assume 0x14.
- The map header is 24 bytes, so the 540-entry table occupies 12,960 bytes in ARM9 (0x020F6BE0 in RAM for USA, given the ARM9 load address 0x02000000). This RAM address is derived from the DSPRE file offset and was not checked against a symbol map.

### Gaps
- No decompiled C exists in pokeheartgold for the HGSS streaming land-data loader (BDHC, building and NSBMD loading in HGSS overlays). The HGSS-specific building struct and the exact BGS semantics are therefore known only from DSPRE and Platinum.
- I did not find format documentation for HGSS `dynamicTextureType`, for `move_model_list` (a/0/4/7, a/0/9/2), or for the HGSS dynamic-feature equivalents.
- ProjectPokemon and the Kodewerx wiki were not reached in this pass. The DSPH wiki and DSPRE source cover the same material in more current form.

## Q2. Collision/permission layout and tile-behavior values

### Takeaway
Each tile is one little-endian u16. Bits 0–7 are the tile behavior (MapAttr), bits 8–14 are a 7-bit secondary field (community says "sound/footstep"), and bit 15 is the collision bit. Behavior IDs come from `enum TILE_BEHAVIOR` in pokeheartgold.

### Cited Findings
- HGSS ARM9 accessors read the u16 three ways. `GetMetatileBehavior` returns `attr & 0xFF` (0xFF if invalid). A sibling returns `(attr >> 8) & 0x7F`. Another returns `(attr >> 15) & 1` as the collision boolean — [PHG asm/unk_02054648.s](https://github.com/pret/pokeheartgold/blob/master/asm/unk_02054648.s)
- Platinum defines `TERRAIN_ATTRIBUTES_COLLISION_SHIFT 15`, `COLLISION_MASK 0x8000`, `TILE_BEHAVIOR_MASK 0xFF`, `INVALID_LAND_DATA_ID 0xFFFF` and `TERRAIN_ATTRIBUTES_OFFSET 0x10` — [PP include/constants/field/map.h](https://github.com/pret/pokeplatinum/blob/main/include/constants/field/map.h)
- DSPRE stores each tile as byte 0 = type (behavior) and byte 1 = collision ("00 walkable, 80 blocked") — [DSPRE MapFile.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapFile.cs). The DSPH FAQ says collision 0x80 is blocked and other collision IDs are walkable but produce different sounds (grass, metal, rock) — [DSPH mapping_faqs.mdx](https://github.com/DS-Pokemon-Hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping_faqs.mdx)
- Local measurement of the bits 8–14 values across all vanilla HGSS tiles: 0 (600,984 tiles), 6 (44,524), 4 (27,496), 10 (13,431), 7 (2,538), 13 (1,145), 5 (1,098), 1 (546), 2 (240), 11 (153), 9 (45) and 3 (24) — [PHG files/a/0/6/5](https://github.com/pret/pokeheartgold/tree/master/files/a/0/6)
- The behavior enum (`enum TILE_BEHAVIOR`) is partly named: 0, 1 (unused), 2 TALL_GRASS, 3 VERY_TALL_GRASS, 6 HEADBUTT, 8 CAVE_FLOOR, 16 WATER_RIVER, 17 WHIRLPOOL, 19 WATERFALL, 21 WATER_SEA, 22 PUDDLE, 23 SHALLOW_WATER, 29 PUDDLE_NO_SPLASHING, 32 ICE, and so on. There are also flags `TILE_BEHAVIOR_FLAG_SURFABLE (1<<0)` and `TILE_BEHAVIOR_FLAG_ENCOUNTER (1<<1)` — [PHG include/constants/metatile_behavior.h](https://github.com/pret/pokeheartgold/blob/master/include/constants/metatile_behavior.h); the classifier functions are in [PHG src/metatile_behavior.c](https://github.com/pret/pokeheartgold/blob/master/src/metatile_behavior.c)

### Inferences
- "Collision byte 0x80" in DSPRE is the high byte of the u16, so it equals bit 15. Values 0x00–0x7F in that byte are the 7-bit secondary field. A tile can be blocked and still carry a non-zero secondary value (for example 0x84).

### Gaps
- No primary source names the semantics of each secondary (bits 8–14) value. "Sound" is a community claim; the consuming code (`sub_020548EC` callers) was not traced.

## Q3. How pokeheartgold and pokeplatinum represent map data as source

### Takeaway
pokeheartgold makes only the "logical" layer editable. Zone events, encounters, headbutt and map headers are JSON or C built with `jsonproc`; scripts are assembly. Map matrices are per-file `.bin` packed into a NARC. land_data, area_data, map textures, area_build and building textures stay opaque committed NARCs. pokeplatinum has gone further: matrices and area data are JSON, and events go through datagen. Land data is still raw `.bin`, one file per map.

### Cited Findings
- Zone events in pokeheartgold use one JSON file per bank (`NNN_<MAP>.json`) with keys `header`, `bgs`, `objects`, `warps` and `coords`. Scripts and IDs are symbolic, for example `"scriptId": "std_hiddenitem_..."`, `"id": "obj_D17R1101_..."` and `"spriteId": "SPRITE_..."`. The build runs `jsonproc file.json zone_event.json.txt file.s`, assembles with mwasm `-DPM_ASM`, objcopies to raw `.bin`, and packs into `zone_event.narc` → a/0/3/2. The JSON is therefore the editable source and is compiled one way; there is no bin→json step in the build — [PHG zone_event.mk](https://github.com/pret/pokeheartgold/blob/master/files/fielddata/eventdata/zone_event.mk), [PHG zone_event.json.txt](https://github.com/pret/pokeheartgold/blob/master/files/fielddata/eventdata/zone_event.json.txt), [PHG zone_event/004_D17R1101.json](https://github.com/pret/pokeheartgold/blob/master/files/fielddata/eventdata/zone_event/004_D17R1101.json)
- `jsonproc` is a pret tool (inja templating of JSON into text) at `tools/jsonproc`, invoked as `$(JSONPROC)`. pokeheartgold uses it for zone events, encounters, headbutt and others — [PHG common.mk](https://github.com/pret/pokeheartgold/blob/master/common.mk), [PHG tools/](https://github.com/pret/pokeheartgold/tree/master/tools)
- Map matrices are `files/fielddata/mapmatrix/map_matrix/map_matrix_NNNN[_NAME].bin` (288 files). The Makefile only packs the directory into a NARC; there is no JSON — [PHG map_matrix.mk](https://github.com/pret/pokeheartgold/blob/master/files/fielddata/mapmatrix/map_matrix.mk)
- In pokeheartgold, `files/a/0/6/5` (land_data, about 19.5 MB), `files/a/0/4/2` (area_data) and `files/a/0/4/4` are committed binary archives under `git ls-files`. They are not in the `arc_strip_name` source→archive list, and no `files/fielddata/landdata` or `areadata` source directory exists — [PHG filesystem.mk](https://github.com/pret/pokeheartgold/blob/master/filesystem.mk)
- Map headers in pokeheartgold are C (`src/data/map_headers.h`) that reference generated `.naix` member enums (`NARC_map_matrix_map_matrix_0000_EVERYWHERE_bin`, `NARC_zone_event_000_DUMMY_bin`, `NARC_scr_seq_..._hdr_bin`) — [PHG src/data/map_headers.h](https://github.com/pret/pokeheartgold/blob/master/src/data/map_headers.h)
- pokeplatinum (Meson build):
  - Matrices are `res/field/matrices/map_matrix_NNN.json` with `name` and `headers` 2D arrays of `MAP_HEADER_*` symbols, plus land data and altitudes, converted by `tools/jsoncnv/map_matrix.py`.
  - Area data is `res/field/area_data/area_data_NNN.json` with symbolic `mapPropSet`, `mapTextureSet` and `lightingSet`.
  - Land data is `res/field/maps/data/map_data_NNN.bin`, copied verbatim, about 666 files.
  - Events go through `tools/datagen/datagen_events.cpp` and `tools/jsoncnv/event.py`.
  - The map-header enum is generated from `generated/map_headers.txt`.
  - Sources: [PP res/field/matrices/map_matrix_000.json](https://github.com/pret/pokeplatinum/blob/main/res/field/matrices/map_matrix_000.json), [PP res/field/area_data/area_data_000.json](https://github.com/pret/pokeplatinum/blob/main/res/field/area_data/area_data_000.json), [PP res/field/maps/data/meson.build](https://github.com/pret/pokeplatinum/blob/main/res/field/maps/data/meson.build), [PP tools/jsoncnv](https://github.com/pret/pokeplatinum/tree/main/tools/jsoncnv), [PP tools/datagen](https://github.com/pret/pokeplatinum/tree/main/tools/datagen)
- pokeplatinum also has map documentation in `docs/maps/` (README, maps.md, loading_maps.md, bdhc.md, dynamic_map_features.md, file_format_specifications.md) — [PP docs/maps](https://github.com/pret/pokeplatinum/tree/main/docs/maps)

### Inferences
- The tools most worth reusing for HGSS are pokeplatinum's `jsoncnv/map_matrix.py` and its matrix JSON schema. The HGSS matrix binary has the same layout, though byte-0 width/height naming needs confirming. pokeheartgold's own zone_event JSON with `jsonproc` already gives an editable events source.
- Neither decomp turns land_data into editable geometry sources. For land_data, DSPRE/PDSMS (NSBMD, .per, .bld, .bdhc import/export) remains the editing path.

### Gaps
- I did not inspect pokeplatinum's matrix-JSON land-data and altitudes key names or the `map_matrix.py` code in detail.
- I did not check whether pret/pokediamond has diverged; it was not examined in this pass.

## Q4. Extending maps: new headers, unused IDs, and limits

### Takeaway
Vanilla HGSS has exactly 540 header slots, a fixed 24-byte ARM9 table, and a bounds check that redirects out-of-range IDs to MAP_NOTHING. There are two ways to add maps. In a decomp, append entries to `sMapHeaders` plus `maps.h`/`mapname.bin`. On a binary ROM, use DSPRE's "Dynamic Header Allocation" patch, which moves headers into a/0/5/0, one file per header. Alternatively, repurpose one of the 39 maps that pokeheartgold itself labels `*_UNUSED`.

### Cited Findings
- Unused map IDs that pokeheartgold names `*_UNUSED` (ID, internal name):
  - 8 D24; 82 T27R0101; 105 T27R0601; 128–130 T27PC0102–0104; 148 R09R0101; 150 D22R0201; 161 T22R0501; 175 T27R0301
  - 208–213 T25R1301–1306; 218 D24R0201
  - 254–262 C11/C11PC0101/C11PC0102/C11FS0101/C11R0101–0401/C11PC0103 (Fight Area, a Platinum leftover); 263–264 D31/D31R0101; Battle Tower unused 267, 269, 270 and further entries, plus 274 D32R0201
  - 406 T11R0901; 416 W20R0101; 458 D11R0107; 468 R05R0101; 488 D22R0103; 538 R00 (`MAP_UNUSED`)
  - Also `MAP_NOTHING` = 1.
  - Source: [PHG include/constants/maps.h](https://github.com/pret/pokeheartgold/blob/master/include/constants/maps.h)
- The decomp bounds check is `if (mapId >= NELEMS(sMapHeaders)) { GF_ASSERT(FALSE); mapId = MAP_NOTHING; }`. Growing the C array therefore grows the valid range automatically for these getters — [PHG src/map_header.c](https://github.com/pret/pokeheartgold/blob/master/src/map_header.c)
- DSPRE's Dynamic Headers patch:
  - It writes a small ARM9 routine at 0x3B268 (HG USA) that loads the header for an ID from a NARC (a/0/5/0 in HGSS).
  - It replaces each `mov r1,#0x18; mul r1,r0` (headerID*0x18) with a no-op so the base offset is 0.
  - It rewrites field pointers from `ARM9_HEADER_TABLE_OFFSET+n` to `0+n`; there are 26 pointer pairs listed for HGSS.
  - It has special cases at 0x3B522/0x3B526/0x3B53C for non-JP/ES HGSS.
  - It then splits the table into one file per header.
  - Sources: [DSPRE DS_Map/Resources/ROMToolboxDB/ToolboxDB.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/Resources/ROMToolboxDB/ToolboxDB.cs), [DSPRE DS_Map/PatchToolboxDialog.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/PatchToolboxDialog.cs)
- The DSPH mapping FAQ says new headers cannot be added in DSPRE until the Dynamic Header Allocation patch is applied from the Patch Toolbox — [DSPH mapping_faqs.mdx](https://github.com/DS-Pokemon-Hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping_faqs.mdx)
- DSPRE also has an HGSS-only "matrix expansion" ARM9 patch. It writes immediates at 0x0203AEBE–0x0203B25C (values such as 0x1FF, 0x176, 0x1C9, 0x149, 0x63E, 0x1F3C, 0x1F50, 0x12C4, 0xC84, 0xC7C), with +8 for IPKE/IPGE/IPGS. It is disabled for DP and Pt — [DSPRE ToolboxDB.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/Resources/ROMToolboxDB/ToolboxDB.cs), [DSPRE PatchToolboxDialog.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/PatchToolboxDialog.cs)
- Limits found in source:
  - Matrix: at most 799 cells (`MAP_MATRIX_MAX_SIZE`), and a matrix name of at most 16 bytes. Source: [PHG include/map_matrix.h](https://github.com/pret/pokeheartgold/blob/master/include/map_matrix.h)
  - TerrainAttributes path: at most 225 matrix cells and at most 16 distinct land_data blocks. Source: [PHG include/terrain_attributes.h](https://github.com/pret/pokeheartgold/blob/master/include/terrain_attributes.h)
  - Zone event file: must be **strictly smaller than 0x800 bytes**. The assert is `GetNarcMemberSizeByIdPair(...) < sizeof(events->event_data)`, and the buffer is 0x800. That allows `16 + 20*bg + 32*obj + 12*warp + 16*coord < 2048`. Source: [PHG src/map_events.c](https://github.com/pret/pokeheartgold/blob/master/src/map_events.c), [PHG include/map_events_internal.h](https://github.com/pret/pokeheartgold/blob/master/include/map_events_internal.h)
  - Level-script header bank: must be under 0x100 bytes. Source: [PHG src/map_events.c](https://github.com/pret/pokeheartgold/blob/master/src/map_events.c)
  - Map props: Platinum documents at most 32 per map. Source: [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md)
- Local computation over the 491 vanilla HGSS zone_event JSONs: the largest is `001_UNION.json` (51 objects, 1 warp) at 1,660 bytes, which leaves 387 bytes of headroom under the 0x800 limit — [PHG zone_event/](https://github.com/pret/pokeheartgold/tree/master/files/fielddata/eventdata/zone_event)

### Inferences
- An unused ID that already has headers, matrices and scripts can serve as a ready slot for a new map. Its existing data (matrix, events, music, mapsec) must be overwritten, and other code may still reference it by ID; Fight Area and Battle Park are Platinum leftovers. A new ID beyond 539 also needs `mapname.bin`, encounters, headbutt and any per-map ARM9 tables (spawns, Pokégear location specs) to tolerate the larger ID.
- hg-engine applies to a binary HGSS ROM, not the decomp. Its practical choices are therefore DSPRE's dynamic-header approach or relocating `sMapHeaders` and patching the getters in `rom.ld` (`MapHeader_*` at about 0x0203B3xx). hg-engine's `rom.ld` already exposes symbols such as `MapHeader_GetWildEncounterBank = 0x0203B344` and `MapHeader_GetMapSec = 0x0203B36C`.

### Gaps
- I found no authoritative statement of the matrix-expansion patch's new limits (what the immediates represent).
- I found no list of every ARM9/overlay table indexed by map ID, which a header expansion would need to cover.
- TCRF's "Unused Maps" page could not be used. The fetch returned agent-directed instructions instead of map content, so that page was disregarded.

## Q5. Community documentation

### Takeaway
The current, maintained sources are the DS-Pokemon-Hacking wiki (HGSS file structure, mapping guide and FAQ, town map, headbutt, rock smash), DSPRE's C# parsers (the most concrete binary layouts for HGSS headers, land data and area data), and pokeplatinum's `docs/maps` (the most rigorous format spec, written for Platinum).

### Cited Findings
- The DSPH wiki has HGSS file structure, mapping (`mapping.md`, `models.md`, `animations.md`, `tiles_and_tilesets.md`, `mapping_faqs.mdx`), `hgss-town_map.md`, `hgss-headbutt_trees.md`, `hgss-rock_smash.md`, `hgss-new_overworlds.md` and `hgss-town_map_spots.md` — [DSPH docs/generation-iv](https://github.com/DS-Pokemon-Hacking/ds-pokemon-hacking.github.io/tree/main/docs/generation-iv)
- DSPRE lists HeartGold/SoulSilver (English) as fully supported and hg-engine ROMs as partially supported (per its README, via search) — [DSPRE](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- pokeplatinum's `docs/maps/` contains a mermaid graph of how header → area_data/matrix → land_data → build_model and related files point to each other — [PP file_format_specifications.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/file_format_specifications.md)

### Inferences
- For HGSS, combine sources: take struct layouts from pokeheartgold, the BGS and area-data variants from DSPRE, and BDHC and prop details from the pokeplatinum docs.

### Gaps
- I did not retrieve ProjectPokemon or Kodewerx pages. They are older and may be superseded by the sources above.

## Q6. Field heap and memory limits for NPCs and events per map

### Takeaway
On map load HGSS creates the map-object manager with 64 slots. Zone event data for a map must fit in a 0x800-byte buffer. The FIELD2 heap is created at 0x1C000 bytes in vanilla.

### Cited Findings
- `MapObjectManager_Init(fieldSystem, 64, 5)` is called in both field-init paths, which sets a maximum of 64 live map objects — [PHG src/field_warp_tasks.c](https://github.com/pret/pokeheartgold/blob/master/src/field_warp_tasks.c), [PHG src/map_object.c](https://github.com/pret/pokeheartgold/blob/master/src/map_object.c)
- `MapEvents` contains `u8 event_data[0x800]`, `u8 script_header[0x100]` and `EncounterData`. It is loaded with an assert that the zone_event member size is below 0x800 — [PHG include/map_events_internal.h](https://github.com/pret/pokeheartgold/blob/master/include/map_events_internal.h), [PHG src/map_events.c](https://github.com/pret/pokeheartgold/blob/master/src/map_events.c)
- `Heap_Create(HEAP_ID_3, HEAP_ID_FIELD2, 0x1C000)` and `Heap_Create(HEAP_ID_3, HEAP_ID_FIELD1, 0x20000)` (the latter in game_clear) — [PHG src/field_system.c](https://github.com/pret/pokeheartgold/blob/master/src/field_system.c), [PHG src/game_clear.c](https://github.com/pret/pokeheartgold/blob/master/src/game_clear.c)
- The map matrix and terrain-attribute buffers are allocated from HEAP_ID_FIELD2. MAPMATRIXDATA is sized for 799 cells, and `TerrainAttributes` holds up to 16 x 0x800 bytes = 32 KB — [PHG src/map_matrix.c](https://github.com/pret/pokeheartgold/blob/master/src/map_matrix.c), [PHG src/terrain_attributes.c](https://github.com/pret/pokeheartgold/blob/master/src/terrain_attributes.c)

### Inferences
- The binding per-map limit on events is the 2,047-byte zone_event size, not a count. For example, objects alone could reach (2047-16)/32 = 63, close to the 64-object manager cap. The 64 cap also covers the player, the follower and any script-spawned objects.
- hg-engine has already changed the field heap layout (this project's notes say FIELD2 = 0x28000 and FIELD1 = 0xB8000), so the vanilla 0x1C000 figure does not apply to the current ROM.

### Gaps
- I did not find a documented maximum number of BG, warp or coord events beyond the shared 0x800 budget, or the per-object heap cost of LocalMapObject in HGSS.
