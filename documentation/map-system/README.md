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

   Or edit events through the CLI, which checks each edit before writing:
   `python3 -B -m tools.maps events list --map 33` shows objects, warps, signs
   and triggers with their indices. `events add-npc --map M --x X --z Z
   --sprite S --script N [--movement] [--facing up|down|left|right] [--flag F]
   [--range RX RZ]`, `add-sign`, `add-warp --to-map T --anchor A`,
   `add-trigger [--w --h] --script N --var V --value VAL`, and `move` /
   `remove --kind object|warp|bg|coord --index I` change the map's events
   bank, checking it out first if needed. They refuse shared banks unless you
   pass `--private` (a copy at the next free index plus a header override for
   this map) or `--shared`. They run lint's own checks on the tree before and
   after the edit: a new error refuses the edit unless `--force`; warnings
   (a warp that does not lead back) are printed. Removing a warp that another
   warp targets is refused, since later anchors would shift. `--dry-run`
   prints the JSON diff and writes nothing. New objects get the next free id;
   `y` defaults to 0 as in vanilla (the game places objects on the terrain).
   Each edit takes 5–8 s (two lint passes).

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
     banks replaced from `armips/scr_seq/` are not entry-checked;
   - land models whose material table does not start with the area's
     texture-animation materials (`land-anim-order`): the game binds that
     animation by material index, so other materials would scroll
     ([style-system.md](style-system.md#kit-kitpy)).

   **Warnings** do not block: warps that do not lead back (vanilla shares
   return doors on purpose). Header 4095 is the game's "return to previous map" warp and is
   always valid. To accept an intended error, add its `[key]` with a reason
   to `data/maps/lint_waivers.json`:

   ```json
   {"waivers": [{"key": "object-blocked:33:600:395", "reason": "NPC behind counter"}]}
   ```

   **Walk it offline** (optional, before building): `python3 -B -m
   tools.maps.walk --map 542 --at 20 5 --facing down --moves "DOWN 1, UP 1"`
   replays steps over `rom.nds` plus `data/maps/` (`--vanilla`: ROM only). It
   prints each step with its reason: moved, blocked by collision, object or a
   one-way behavior, map edge, height change (≥ 1.25 tiles of BDHC height),
   ledge jump (two tiles), surf needed (`--surf` allows it), or warp to
   map/anchor (with door step-out). `DIR N` is N full steps; in game a press
   in a new direction turns first and a short tap only turns. `--check
   cases.json` runs `{map, at, moves, expect: [map, x, z]}` cases and exits 1
   on a mismatch. The rules come from the field decompilation (cited in
   `walk.py`); it reproduces every walk the showcase and Route 29 proofs
   measured in melonDS. Anything not modelled stops with "unmodelled": ice and
   spin tiles, dynamic warps whose origin the walk did not see. Scripts, gym
   puzzles, HM obstacles, NPC flags and the bike are ignored. A prediction,
   not proof: still prove walking and warps in game (step 5).

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

## Look at it without building

`tools/maps/render.py` draws land models offline from `rom.nds` plus
`data/maps/`, in seconds, with no build or emulator:

```bash
python3 -B -m tools.maps.render view --map 543 --at 16 44     # the game's top screen standing there
python3 -B -m tools.maps.render overview --map 543 [--top]    # whole map, tile labels, --mark X Z TEXT
python3 -B -m tools.maps.render sheet --map 543               # 3x3 views + overview
```

Images go to `build/map-render/`. It reproduces the field camera preset of
the header's `cameraType` (`gFieldCameraPresets`), the area light file,
material lighting, all seven texture formats with repeat/flip, culling and
translucency. Checked against melonDS on Route 29, Twinwood Crossing and Echo
Cavern (2026-10-16): the same geometry and the same black void, pixel for
pixel. Cave colours were within about 7/255. Outdoor colours differed only by
the save clock's evening tint, a per-channel multiplier the renderer does not
model.

Map props (land.json `buildings`) are drawn as the game does
(`AreaDataManager_Load`, `MapPropManager_DrawWithOffset`): AreaData field 0
selects the prop list (`a/0/4/3`) and the prop textures (`a/0/7/0`); models
come from `a/0/4/0` outdoors or `a/1/4/8` in rooms, placed at their
translation (x/z from the chunk centre) with their scale. The game ignores the
stored rotation, and so does the renderer. `props=False` on `mesh`, `view`,
`overview` or `voids` gives land only. Not drawn: texture animation, fog,
sprites, billboard facing, skinning (4 room models).

`render.voids(scene)` lists tiles where the black void shows beside ground
the player can reach (from the map's warps), seen from above (`top`) or from
the camera's pitch (`camera`). The tile metrics cannot see this: open defect
D2's floating floor has clean joins. It ignores the map edge and tiles near warps
(room exits). Vanilla sample: every route, town and cave scored 0 (including
New Bark, Cherrygrove, Violet, Azalea, Goldenrod with their buildings drawn).
Rooms report the black edge outside their walls by design (D49R0107 11/9,
D24R0208 15/15, Elm's Lab 5/5). The current showcase maps score
0/2, 7/36 and 28/64 (top/camera). The generator's judge has a kit-only
version of this check, the `renderVoid` review gate
([style-system.md](style-system.md#score-scorepy)).

To see what an edit changed: `python3 -B -m tools.maps.render_diff --map 543
[--before REF|snapshot:NAME|DIR] [--after DIR] [--top] [--views]` renders the
map before and after with the same camera. Before defaults to git `HEAD`,
after to `data/maps/`. HEAD may not hold the pre-edit state, so run
`render_diff --snapshot NAME` before a `resolve` or hand edit and diff with
`--before snapshot:NAME`. It writes `build/map-render/diff/diff-M.png`
(before | after, changed tiles red, newly void magenta, fixed void green),
with `--views` the game camera at up to six changed regions, and a JSON
summary: changed chunks (land id, model, BDHC, buildings, tiles), changed
tiles with the reason (a land.json layer or changed pixels), `render.voids`
before/after with newly void and fixed tiles, and the last `resolves` entry of
the map's report. A few seconds per run.

Review page for the user: `python3 -B -m tools.maps.review --map 543` serves
`http://127.0.0.1:8765/`. It shows the overview with overlays (the judge's
tile problems, render void, hotspots, open defects). Clicking a spot shows the
game view there, `tools.maps.style inspect` and the commands to inspect or
re-solve around it. Record defect appends to the lab's `defects.jsonl`.
Reload re-reads `data/maps/` after a generate or resolve.

The renderer and review page do not replace in-game proof: walking and warps
are still proven with memory reads, and the agent's final map-look review
still uses `showcase shots` (AGENTS.md "Maps").

## Is my map work consistent?

`python3 -B -m tools.maps.status [--map M] [--json]` checks in a few seconds,
without building, that:
- every generate report in `build/map-style/` still matches the land models
  on disk (which `style resolve --write` requires) and stores its layout;
- `showcase write` would change nothing;
- lint has no errors;
- `test.nds` is newer than every file in `data/maps/`;
- the lab champion was measured on the current solver and judge code.

Each problem is listed with what is out of date and the exact command that
fixes it; exit 0 when nothing needs doing, 1 otherwise. When a report's
stored model hashes are only out of date because the compose code changed
(the lands on disk are still that report's grid), `status --refresh-hashes`
updates them without regenerating the map. Run it before handing off map
work and before trusting a melonDS observation.

## Checks for the tool itself

```bash
python3 -B -m tools.maps roundtrip          # every vanilla member re-encodes identically
python3 -B -m tools.maps check-reference    # matches the pokeheartgold decomp
python3 -B -m unittest tools.maps.test_codecs
python3 -B -m tools.maps.nsbmd roundtrip    # all 676 chunk models re-encode identically
python3 -B -m unittest tools.maps.test_nsbmd
python3 -B -m unittest tools.maps.test_render     # renderer, void check, review page
python3 -B -m unittest tools.maps.test_render_diff tools.maps.test_walk tools.maps.test_events_edit tools.maps.test_status
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
- Generated models are checked structurally and for loading; how they look
  is judged from renders and in game (the render void check is the only
  automatic look check). Animated water and translucency are not generated.
- New map IDs: 540–591 can hold their own header (52 slots, see
  [header-expansion.md](header-expansion.md)); 592–599 are valid IDs that
  behave like MAP_NOTHING. `checkout --map 540 --parts header` gives a
  template; `apply` writes it to `base/map_header_ext.bin` for armips and
  pads Rock Smash data. More than 52 needs more resident memory.
