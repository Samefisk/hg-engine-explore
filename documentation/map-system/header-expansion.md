# Map header expansion (map IDs 540+)

Vanilla HeartGold has 540 map headers: 24-byte rows in an ARM9 table at
`0x020F6BE0`, which is file offset `0xF6BE0` in the decompressed `arm9.bin`.
The patch [`armips/asm/map_header_expansion.s`](../../armips/asm/map_header_expansion.s)
raises the number of valid map IDs to `MAP_HEADER_COUNT`, 600 by default.
It also gives up to 52 new maps their own header. The Python side is
[`tools/maps/header_table.py`](../../tools/maps/header_table.py).

Status: the patch is checked byte for byte against the production armips, and
the unit tests pass. No ROM has been built with it yet, and it has not been
proven in game. See [In-game proof](#in-game-proof).

## Why the table cannot simply be relocated

A 600-row table needs 14,400 bytes that stay resident at all times. The
getters run from the field, from menus, from the Pokégear radio and from
battle setup. Nothing that size is free:

| Region | Measured free space |
| --- | --- |
| Main arena above the FNT/FAT archive | 8 bytes below the `0xC00` guard before overlay 158 at `0x023B65C0`. This uses the arena arithmetic from `verify_pokemon_move_history.py` with the current FNT `0xB56` and FAT `0x1110`. |
| Overlay 129 (`0x023D8000..0x023E0000`) | 6 bytes (`0x7FFA` used) |
| Resident overlays 149, 153 and 155–161 | each within bytes of full (see the project notes) |
| ITCM | the arena starts at `0x02000000`, so it is full |
| Heap 3 / save heap / FNT-FAT cache | must not shrink (`NEW_HEAP3_SIZE` is pinned) |

A new filesystem file is also ruled out: its FAT and FNT bytes would push the
archive past that 8-byte slack.

The patch therefore leaves the 540 vanilla rows and all 27 getters where they
are. Only the extension rows move into vanilla ARM9 data that hg-engine no
longer reads.

## Design

All 27 `MapHeader_*` getters (`0x0203B27C..0x0203B540`) do the same thing:

```
bl   0x0203B268              ; static MapNumberBoundsCheck, its only callers
movs r1, #24 ; muls r1, r0
ldr  r0, =0x020F6BE0 + field ; ldr{b,h} r0, [r0, r1]
```

The bounds check (20 bytes) becomes a stub, `ldr r1,=routine|1; bx r1`, that
jumps to a 56-byte routine. The routine returns the **row** that the getter
multiplies by 24:

| Map ID | Row returned | Header read |
| --- | --- | --- |
| `< 540` | the ID | vanilla row (unchanged) |
| `540 .. 540+B-1` | `1538 + (id-540)` | slot block B |
| `540+B .. 540+D-1` | `A_ROW + (id-540)` | slot block A |
| `540+D .. COUNT-1` | `1` | MAP_NOTHING (same result as vanilla, without the assert) |
| `>= COUNT` | `1` after `GF_AssertFail` | vanilla behavior |

`D` is the number of extension headers supplied (contiguous from 540).
`B = min(D, 20)`. Both slot blocks sit at a whole number of rows from
`0x020F6BE0`, so every row lands on an exact 24-byte boundary.

| Block | Address | Capacity | Why it is free |
| --- | --- | --- | --- |
| B | `0x020FFC10..0x020FFDF0` (slots), routine `0x020FFDF0..0x020FFE28`, live data from `0x020FFE2B` | 20 headers | stock icon-palette table `sPokemonPalNoBySpeciesAndForm` (`0x020FFC10..0x020FFE30`). Reader `GetMonIconPaletteEx` (`0x02074364`) is replaced by the `IconPalGet`/`GetMonIconPalette` hooks. `GetBattleMonIconPaletteEx` (`0x0207440C`) is **not** hooked and still reads entries 540..543 (`0x020FFE2C..0x020FFE2F`), so the slots and routine must end at or before `0x020FFE2B` |
| A | top-aligned, ending at `0x020FF460`; lowest start `0x020FF160` | 32 headers | tail of the retired `gSpeciesToOWNum` table (`0x020FF088 + 0x3DA`). `pokedex.s` code uses `0x020FF088..0x020FF134`, and armips stops the build if block A would reach `get_dex_num_patch + 0x20` |

When the build supplies no extension headers, block A is not written. Unused
B slots are zero-filled.

### Every patched address

| Address | File | Before | After |
| --- | --- | --- | --- |
| `0x0203B268..0x0203B27B` | arm9 | MapNumberBoundsCheck (`cmp #540`) | stub to `0x020FFDF0` (`00490847 f1fd0f02` then zeros) |
| `0x020FFC10..0x020FFE27` | arm9 | dead icon-palette bytes | B slots + routine + pool (`B_ROW`=1538, `A_ROW`) |
| `A_BASE..0x020FF45F` | arm9 | dead gSpeciesToOWNum bytes | A slots, only when D > 20 |
| `0x0202F376` (1 byte) | arm9 | `movs r0,#0x87` (540) | `movs r0,#COUNT/4` in MapMarkingsSave_MapIDisValid |
| `0x021F707C` (1 byte) | overlay 101 | `movs r0,#0x87` | `movs r0,#COUNT/4` in the Pokémon Talk landmark loop. Applied only when overlay 101 is decompressed; otherwise armips prints a warning (see below) |

Unchanged and checked by `verify`: the vanilla table, the 27 getter literals
(`0x020F6BE0 + field`) and the 27 getter `bl`s to `0x0203B268`.

Only two Thumb immediates hold the count, so `MAP_HEADER_COUNT` must be a
multiple of 4 between 544 and 792.

## Inventory: what indexes by map ID

The sources are the pokeheartgold decomp, scans of the stock ARM9 and all 129
stock overlays (every `#540`/`0x21C`/`0x21B` constant and every pointer into the
table), and the hg-engine sources. Status is for IDs 540+ once this patch
is in.

| Site | What | ID ≥ 540 today | With this patch |
| --- | --- | --- | --- |
| `0x0203B268` MapNumberBoundsCheck, 27 getters `0x0203B27C..0x0203B540` | header table | assert → MAP_NOTHING | patched |
| `0x0202F376` MapMarkingsSave_MapIDisValid | Pokégear map markings | marking treated as empty | patched |
| ov101 `0x021F707C` Pokémon Talk loop (`pokemon_talk.c:201`) | radio landmarks | new maps never sampled | patched only if overlay 101 is decompressed |
| `a/2/5/2` headbutt NARC, member = map ID (`field/headbutt.c:117`, hg-engine `overworld_wild_helper_overlay.c:192,678`) | 540 members built from `armips/data/headbutt.s` | **out-of-bounds member read** | **coordinator: add `headbuttheader 540.., 0, 0` records** |
| `a/2/5/3` Rock Smash NARC, member = map ID (`overlay_01_rock_smash_item.c:136`) | 540 × 4-byte vanilla members | **out-of-bounds read into a 4-byte stack buffer** | **coordinator: pad to COUNT** (`header_table.pad_narc(data, COUNT, b"\0"*4)`) |
| `fielddata/maptable/mapname.bin` | 16-byte names | no game reader (only a GameSpy key string matches "mapname") | tools only; extend to name new maps |
| Spawn/fly table `0x020F9E80` (`unk_0203BA5C`) | keyed by spawn ID, stores map IDs as u16 | fine | – |
| Roamers, swarms, Pokémon Center list, music overrides, Pokédex area lists, phone/radio lists | linear lists of u16 map IDs | fine | – |
| Location, saved objects, follower, photo, phone, battle setup | map ID stored in ≥ 16 bits | fine | – |
| hg-engine `OverworldWildEncounterLookupData` (`mapIds[150]`, searched linearly) | wild data by map | new map has no wild data until added | – |
| hg-engine C | uses only the vanilla getters (`rom.ld` `MapHeader_*`) | redirected | patched through the getters |
| `tools/maps` `codecs.HEADER_COUNT=540`, `cli.validate_tree`, `world.apply_overrides` length check, `decode_header_table` fixed offset | tooling | rejects or misreads 540+ | coordinator: switch to `header_table` (below) |
| devtools teleport cap 539 (`devtools_runtime.py:3647`, `devtools_contract.py:154`, movement predicates, cadence tools, tests) | tooling | rejects 540+ | coordinator: raise to `configured_count() - 1` |

The other `#540` constants in overlays 1, 2, 5, 12, 14 (the 540 PC box slots),
18, 27, 28, 40, 44, 70, 82, 85, 86, 93, 102, 119 and 121 are struct offsets or
non-map compares. None of them is a map bound.

## Adding map 540+

1. Give the new map its data as usual: matrix, events, scripts, text and
   land, each appended at the next free member.
2. Write header overrides `data/maps/headers/0540.json` and so on. IDs must be
   contiguous from 540; a gap is filled with a copy of MAP_NOTHING.
3. The build step, before armips, writes `base/map_header_ext.bin`:
   ```python
   from tools.maps import header_table, codecs
   header_table.write_extension_file(arm9_path, {i: codecs.encode_header(h) for i, h in ext.items()},
                                     nothing=arm9[0xF6BE0 + 24:0xF6BE0 + 48])
   ```
   The patch includes it, and an absent or empty file means no extension headers.
   The number of headers is `filesize / 24`, at most 52 and at most COUNT − 540.
4. Add headbutt records and Rock Smash members for the new IDs (see the inventory).
5. After the build:
   `python3 -B -m tools.maps.header_table verify --arm9 base/arm9.bin --root base/root`.

Library API: `configured_count()`, `locate(arm9) -> Layout | None` (count,
stored count, slot rows), `Layout.address/file_offset/row(map_id)`,
`read_entry`, `write_entry` (a post-armips edit of a stored row),
`logical_headers(arm9, names)` (works on stock and patched ARM9),
`extension_blob`, `write_extension_file`, `pad_narc`, and
`apply_reference_patch` (a byte-identical Python mirror of the armips output,
used by the tests).

## Coordinator integration (not done by this change)

- `tools/maps/cli.py cmd_apply`: send header overrides ≥ 540 to
  `write_extension_file` rather than writing past `0xF6BE0 + 540*24`, which would
  overwrite live ARM9 data. Always call it so a stale file cannot survive.
  `base/` is wiped at the start of every build anyway.
- `tools/maps/world.py` and `codecs.py`: build the base header list with
  `header_table.logical_headers` (COUNT entries), and lift `HEADER_COUNT` and the
  `validate_tree` "exactly 540" rule.
- The build manifest (`scripts/pokemon_move_history_build_manifest.py`) only
  tracks `.incbin` paths written as string literals. The patch includes
  `base/map_header_ext.bin` through a symbol, so the manifest does not record
  it; its content follows from `data/maps/`.
- No Makefile, `narcs.mk` or hash-gate change is needed for the patch itself.
  The new `.s` file is picked up through `armips/global.s`.
- Optional: add overlay 101 to `OVERLAYS_TO_DECOMPRESS` in `scripts/make.py`.
  The Pokémon Talk bound is then raised; the patch detects this from the y9
  compression flag.

## In-game proof

Prerequisites: a build with one extension header, for map 540. Copy an
existing outdoor map's header, for example Route 29 (`MAP_ROUTE_29`), and
change one field you can observe, such as `dayMusicId`/`nightMusicId` or
`weather`. Then raise the devtools teleport cap.

1. Static: `verify` passes. `show` prints `map 540: 0x020FFC10`.
2. `scripts/owctl dev teleport 540 X Z`, using Route 29 matrix coordinates.
3. Read memory and confirm:
   - the field location map ID is 540;
   - `0x020FFC10..0x020FFC27` equals the supplied header bytes;
   - the matrix and terrain loaded (`scripts/owctl dev terrain --x X --z Z` returns tiles);
   - the changed field took effect (music or weather).
4. Negative check: teleport to 599 (stored only as an alias). The game must
   behave as it does for MAP_NOTHING, with no hang. IDs ≥ COUNT still assert.

## Remaining risks

- Capacity is 52 stored extension headers (IDs 540..591), not 60. Rows
  592..599 are valid IDs that alias MAP_NOTHING. More rows need more dead or
  reclaimed resident RAM; every option here was measured as full.
- Block A shares the retired gSpeciesToOWNum block with `pokedex.s`. armips
  only warns when two areas overlap, so the explicit `.error` guard against
  `get_dex_num_patch` is what protects it. If code is added after that
  function, the guard must move.
- `verify` checks that the hook stubs over both retired readers are present
  (`make.py` skips a hook whose symbol is missing). Block B relies on the icon-palette hooks staying in
  `hooks`.
- The headbutt and Rock Smash archives must grow with the stored IDs.
  `verify --root` reports an error until they do.
- A map ID from 540 up to COUNT is now "valid" to map markings and the radio.
  A saved marking on such a map survives a later build only if COUNT stays at
  least that high.
