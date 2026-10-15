# Map system

How agents change HeartGold maps. Layouts and game limits are in
[formats.md](formats.md); the tooling research is in
[research/report.md](research/report.md).

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
   **Errors** block the build: events outside loaded land, NPCs on blocked
   tiles, duplicate object IDs, bad warp targets or anchors, matrix cells or
   header fields pointing past their archives. **Warnings** do not: warps
   that do not lead back (vanilla shares return doors on purpose) and
   script/text banks past vanilla counts (hg-engine adds banks later in the
   build). Header 4095 is the game's "return to previous map" warp and is
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
   loaded collision bit and warp table. Screenshots are never evidence.

Rerunnable end-to-end proof (test-only edit on Route 29; remove it and
rebuild afterwards):

```bash
python3 -B -m tools.maps.proof_route29 write    # then build
python3 -B -m tools.maps.proof_route29 probe    # passed:true on the edited ROM
python3 -B -m tools.maps.proof_route29 remove   # then build again
```

## Checks for the tool itself

```bash
python3 -B -m tools.maps roundtrip          # every vanilla member re-encodes identically
python3 -B -m tools.maps check-reference    # matches the pokeheartgold decomp
python3 -B -m unittest tools.maps.test_codecs
```

Run these after changing anything in `tools/maps/`.

## Known gaps

- No generic memory reader yet, so an in-game check that the loaded event
  bytes equal the override needs a new bounded devtools reader.
- Lint has no reachability check (ledges, water and height make it a
  path-search problem).
- Script, text and encounter references are counted, not resolved.
- New 3D geometry needs an NSBMD writer; see the research report.
- The ARM9 header table cannot grow; reuse an `*_UNUSED` map ID.
