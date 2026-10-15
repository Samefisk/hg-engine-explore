# Map system

How agents change HeartGold maps. Layouts and game limits are in
[formats.md](formats.md); the tooling research is in
[research/report.md](research/report.md). For how the game loads maps, read
the field overlays in `.codex-reference/pokeheartgold-full/src/field/`
(full decompilation; see `.codex-reference/README.local.md`) before guessing
from binaries.

## Edit loop

Agent commands read the pristine `rom.nds` by default. Do not point them at
`base/`: after a build it holds the patched output, so a checkout or lint
baseline taken from it would already contain your edits. Only the build
passes `--root base/root --arm9 base/arm9.bin`.

1. **Check out** the parts you need into the override tree `data/maps/`:

   ```bash
   python3 -B -m tools.maps checkout --map 33 --parts events,land,header
   ```

   Map IDs are in `.codex-reference/pokeheartgold/include/constants/maps.h`.
   `land` copies only the chunks this map owns in its matrix.
   Delete override files you do not change; the tree should hold only edits.

   Checkout refuses members other maps also use. Every unused map shares
   event bank 0, for example. For a private copy, add the member at the next
   free index (`events/0491.json`, `land/0676/…` with its `model.nsbmd`) and
   check out `header` to point the map at it. Use `--shared` only when the
   change should apply to every listed map.

2. **Edit** the JSON. Event coordinates are matrix-wide tiles; a land chunk at
   matrix cell (cx, cz) covers x `cx*32 … cx*32+31`, z `cz*32 … cz*32+31`.
   Tile layers are text rows: `collision` (`#` blocked, `.` open), `behavior`
   and `secondary` (hex). Behavior IDs are `enum TILE_BEHAVIOR` in
   pokeheartgold `include/constants/metatile_behavior.h`.

3. **Lint**:

   ```bash
   python3 -B -m tools.maps lint
   ```

   It reports only problems that vanilla does not already have.
   **Errors** block the build:
   - events outside loaded land, NPCs on blocked tiles, duplicate object IDs;
   - events that cannot be reached: a flood fill from every warp of the
     matrix, with ledges one-way and water, Rock Climb, Whirlpool, Waterfall
     and behavior 128 passable (see `tools/maps/reach.py`). Height layers
     are ignored; vanilla still has 86 such events (gym puzzles, special
     dungeons), which is why only new ones count;
   - bad warp targets or anchors;
   - local script IDs (1–1999) past the map's `scr_seq` entry count, and
     script/text banks or matrix cells past their archives. Bank counts
     include what the build adds from `data/text/` and `armips/scr_seq/`;
     banks replaced from `armips/scr_seq/` are not entry-checked.

   **Warnings** do not block: warps that do not lead back (vanilla shares
   return doors on purpose). Header 4095 is the game's "return to previous map" warp and is
   always valid. To accept an intended error, add its `[key]` with a reason
   to `data/maps/lint_waivers.json`:

   ```json
   {"waivers": [{"key": "object-blocked:33:600:395", "reason": "NPC behind counter"}]}
   ```

4. **Build** with the `hg-engine-delta-build` skill. The Makefile runs
   `tools.maps apply --in-place` right after `scripts/make.py`. It rewrites
   only archives with overrides and patches only overridden header entries
   in `base/arm9.bin`. It refuses to build when lint has new findings. With
   an empty `data/maps/` it writes nothing.

5. **Prove it in game** through the shared melonDS tools (`scripts/owctl`):
   teleport next to the change, press a direction, and read the player's map
   and tile position. `owctl dev terrain --x X --z Z --radius 0` reads the
   loaded collision bit, the warp table, and `events`: the SHA-256 of the
   zone-event file the game loaded (layout-checked against the game's own
   array pointers). Right after a map load it equals the SHA-256 of the
   encoded events member; scripts that move NPCs later change it.
   Screenshots are never evidence.

Rerunnable end-to-end proof (test-only edit on Route 29; remove it and
rebuild afterwards):

```bash
python3 -B -m tools.maps.proof_route29 write    # then build
python3 -B -m tools.maps.proof_route29 probe    # passed:true on the edited ROM
python3 -B -m tools.maps.proof_route29 remove   # then build again
```

New 3D geometry: `python3 -B -m tools.maps.nsbmd generate --area ID --spec
grid.json --out model.nsbmd` builds a chunk model from a tile grid using the
area's texture names ([nsbmd.md](nsbmd.md)); put it beside `land.json` as
`model.nsbmd`. Keep collision and BDHC consistent with the new floor yourself.
`owctl dev terrain` reports `landModels`: the name and size of the model each
loaded chunk points at. `tools.maps.proof_model` (write / probe / remove)
proves a generated model loads in Elm's lab.

## Checks for the tool itself

```bash
python3 -B -m tools.maps roundtrip          # every vanilla member re-encodes identically
python3 -B -m tools.maps check-reference    # matches the pokeheartgold decomp
python3 -B -m unittest tools.maps.test_codecs
python3 -B -m tools.maps.nsbmd roundtrip    # all 676 chunk models re-encode identically
python3 -B -m unittest tools.maps.test_nsbmd
```

Run these after changing anything in `tools/maps/`.

## Known gaps

- The overworld roof/canopy catalog (`data/overworld_wild_roof_catalog_manifest.json`)
  covers only the 288 vanilla matrices. New maps from `data/maps/` stay
  outside it, because its counts are compiled into packaged overworld code
  whose verifiers pin exact addresses: including a new map shifts that code.
  Adding a new map to the overworld system is a separate, deliberate change
  that needs the overworld proofs re-run.

- Message indices used inside scripts are not checked; only text banks are.
- Reachability ignores height layers, so bridges over-approximate it.
- Generated models are checked structurally and for loading, not for how
  they look; a person has to judge that. Animated water and translucency are
  not generated.
- New map IDs: 540–591 can hold their own header (52 slots, see
  [header-expansion.md](header-expansion.md)); 592–599 are valid IDs that
  behave like MAP_NOTHING. `checkout --map 540 --parts header` gives a
  template; `apply` writes it to `base/map_header_ext.bin` for armips and
  pads Rock Smash data. More than 52 needs more resident memory.
