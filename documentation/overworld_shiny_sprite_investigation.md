# Overworld Shiny Sprite Investigation

## Summary

We attempted to make shiny overworld wild Pokemon visibly use shiny overworld palettes while preserving normal battle behavior:

- A shiny overworld spawn should appear shiny before battle.
- The battle generated from that overworld spawn should be shiny.
- A normal overworld spawn should not secretly become shiny in battle.
- The temporary test rate was 1/8.

The visual goal was proven partially possible, but the implementation became unsafe. It affected normal overworld spawning, surf spawns, battle startup, and eventually unrelated UI such as the party screen. We reverted the feature and removed all special shiny handling from overworld wild spawns.

The stable system after the revert is:

- Overworld wild Pokemon always use normal overworld sprites.
- Overworld wild battles no longer pass a forced shiny flag.
- The generated overworld wild battle script is back to the pre-shiny path: it writes `0` to the script's shiny byte and does not carry any shiny state from the overworld object.
- No shiny overworld archive is generated.
- No overlay hook redirects overworld model resource loading.

## Follow-Up Implementation

The later implementation avoids the failed archive and loader-hook approaches. Overworld wild spawns now roll and store shiny state locally, pass that same state to the generated wild battle script, and seed the existing overworld Pokemon palette metadata so the spawned object can select its shiny palette.

This keeps shiny rendering dynamic by species/form without generating duplicate overworld BTX members:

- the normal `pokemonow.narc` layout is unchanged
- no shiny tag table or shiny NARC is generated
- no shared overworld model loader hook is installed
- normal spawns keep the existing special-field-object render path
- shiny spawns stay on the normal special-field-object render path and only set the palette metadata bits

One important stability note: do not set the follower render flags on overworld wild objects. Those flags make the wild object take the follower draw path without being created as a real follower object, which can make shiny spawns render invisible. The stable path is to pass the shiny palette bit through object param 2 while keeping the normal object renderer.

## What Was Tried

### 1. Forced shiny battle state

The first stage added a shiny flag to overworld spawn state:

- `OverworldWildSpawn.shiny`
- `OverworldWildSpawnState.pendingShiny`
- `OverworldWildSpawns_PopPendingBattle(..., BOOL *shiny)`

The overlay rolled shiny status on spawn using a test counter:

- `OW_WILD_SHINY_TEST_RATE 8`
- every 8th overworld spawn became shiny for testing

Then `src/script_new_cmds.c` wrote that shiny flag into the generated `wild_battle` script byte.

This did make battle shininess controllable, but it changed the wild encounter path from "the generated overworld battle script passes its normal shiny byte" into "overworld spawn owns shiny state." That was useful for testing but too invasive for a feature we are no longer pursuing.

### 2. Shiny overworld tag remapping

We tried using the normal follower/overworld tag table:

- normal sprite tag from `FollowingPokemon_GetSpriteID(species, form, 0)`
- shiny tag as `normalTag + 5000`
- generated `gOWTagToFileNum` rows in `src/field/generated_shiny_overworld_table.inc`

The idea was that the normal object creation path could request a different tag for shiny Pokemon and load a different BTX resource.

This was conceptually close, but not sufficient by itself. The tag table can point to a different gfx/member id, but the underlying resource must be present in the archive the object loader reads. If the archive member is missing or invalid, the object can render invisible or fail object creation.

### 3. Separate shiny overworld NARC

We tried generating a separate archive:

- generated assets in `build/generated_shiny_overworlds`
- converted BTX files in `build/pokemonow_shiny`
- packed NARC as `build/narc/pokemonow_shiny.narc`
- copied to filesystem target `a/2/7/0`
- added `ARC_SHINY_OVERWORLDS`

Then `src/overworld_shiny_loader.c` and `armips/asm/shiny_overworlds.s` tried to hook overlay 1's overworld model resource loader so member IDs above a shiny range would load from the shiny NARC instead of normal `pokemonow.narc`.

This approach caused instability. The hook sits in a very sensitive shared loader path used by more than just our temporary wild objects. When this went wrong, failures were not isolated to shiny OW spawns; normal OW spawns and party/follower-related behavior could be affected.

The party screen freeze is consistent with this kind of shared resource path damage. Even if the party screen itself is not spawning overworld wild Pokemon, follower/overworld resource infrastructure is shared enough that a bad hook or bad generated symbol can poison unrelated UI.

### 4. Appending shiny BTX files to `pokemonow.narc`

We then tried avoiding the separate loader by appending all shiny BTX files directly into normal `pokemonow.narc`.

That required several build changes:

- generated shiny gfx IDs after the base max ID, starting around `1553`
- converted generated shiny PNGs to BTX
- repacked `pokemonow.narc` with member IDs up to `2805`
- changed `tools/narcpy.py` to preserve numeric member IDs

This produced a ROM where `pokemonow.narc` had `2806` members and the shiny BTX files existed. We verified members such as:

- `1553`
- `1572`
- `1766`
- `1770`
- `2805`

Each existed and looked structurally like a BTX file.

However, this was too large and too risky. The ROM grew to roughly 191 MB during the append attempt, and normal overworld spawns stopped appearing. After disabling the append path, the archive returned to the normal `1553` members and ROM size dropped back to the previous range.

The likely problem is not simply "member missing." It is that the field object/resource loader, NARC table handling, memory allocation, or overlay assumptions may not tolerate a `pokemonow.narc` expanded that far.

### 5. Build-system mistakes discovered

While debugging, we also found a build command issue:

```make
BTX := $(PYTHON) tools/overworld-btx.py -n $(GFX)
GFX := tools/nitrogfx
```

Because `:=` expands immediately, `$(GFX)` was empty when `BTX` was assigned. Docker then ran commands shaped like:

```text
python3 tools/overworld-btx.py -n data/graphics/overworlds/0408.png build/pokemonow/1_0408.btx0
```

`overworld-btx.py` interpreted the PNG path as the `-n` argument and the output BTX path as the input PNG, causing errors like:

```text
Error: build/pokemonow/1_0412.btx0 is not a valid path for input png
```

The script exited successfully despite those errors because it used `exit()` with no nonzero code and did not check subprocess failures. This created false-positive builds.

We fixed that during investigation, but reverted it along with the shiny experiment because the final request was to return to the pre-shiny path. If we need to harden build tools later, that should be a separate task.

### 6. `narcpy.py` numeric member IDs were too global

To append shiny members, we changed `tools/narcpy.py` so filenames like `1_1770.btx0` became NARC member `1770`.

That behavior was initially global. This was dangerous because many other NARCs use filenames with numeric suffixes, such as `9_10`, where sorted file order and member identity are part of existing assumptions. Applying numeric-member preservation globally can silently rearrange unrelated NARCs.

That is a plausible cause for weird runtime behavior outside overworld spawns.

Lesson: if numeric-member preservation is ever needed again, it must be an explicit archive-specific mode, not a default behavior.

## What Actually Worked

We did prove a few useful things:

- Normal Pokemon overworld assets do contain shiny palette files for many species.
- BTX generation can produce structurally valid shiny overworld files.
- The tag table can address extra overworld entries.
- Battle shininess can be forced through the generated script's shiny byte.
- The game can display a shiny battle generated from an overworld spawn.

The failure was not "shiny overworld sprites are impossible." The failure was that our integration path touched too much shared resource-loading infrastructure and archive layout.

## What Failed

The feature became unstable in several distinct ways:

- shiny overworld sprites rendered as normal
- shiny overworld sprites rendered invisible
- all overworld spawns disappeared
- battles from overworld spawns crashed
- surf spawns overpopulated and behaved inconsistently
- later, the party screen froze

Those symptoms point to shared resource and object-loader risk rather than one small palette selection bug.

## Why We Reverted

The current overworld spawn feature is valuable and already touches many sensitive systems:

- field objects
- map transitions
- wild encounter tables
- battle script startup
- follower object-like behavior
- overlay 149 extension logic
- NARC packaging

The shiny overworld work added more risk on top:

- generated thousands of extra assets
- changed archive layout
- introduced loader hooks
- introduced forced shiny battle state
- touched palette parameters on special field objects
- made normal and shiny object creation diverge

That made debugging too noisy. The safest path is to remove shiny-specific behavior entirely and return to the stable non-shiny overworld spawn feature.

## Reverted / Removed Pieces

Removed runtime shiny handling:

- no `OverworldWildSpawn.shiny`
- no `OverworldWildSpawnState.pendingShiny`
- no `OW_WILD_SHINY_TEST_RATE`
- no `OverworldWildSpawns_RollShiny`
- no shiny sprite ID lookup
- no `spriteId + 5000`
- no shiny palette params passed to `CreateSpecialFieldObjectWithParams`
- no forced shiny byte passed into the generated wild battle script

Removed shiny resource integration:

- no separate shiny overworld NARC
- no `ARC_SHINY_OVERWORLDS`
- no shiny loader hook
- no generated armips symbol for `OverworldWildSpawns_LoadOverworldModelResource`
- no generated shiny overworld include files
- no shiny overworld asset generator
- no shiny NARC copy in `Makefile`

## Future Approach If We Ever Revisit This

Do not restart from the append-all-assets or shared-loader-hook approach.

A safer future design would need these constraints:

1. Keep battle shininess independent at first.
   First make visual shiny loading work for one hardcoded species/object without changing battle generation.

2. Do not modify normal `pokemonow.narc` layout.
   The normal archive is too central and too easy to break.

3. Do not hook a shared loader globally.
   If a hook is unavoidable, it must be restricted to our wild object IDs or an explicit marker on the object, not every overworld resource load.

4. Test one known species only.
   Use one species with known normal and shiny palettes, such as Hoothoot or Spinarak, before generating all species.

5. Avoid generated thousands of files until one object works.
   The generation pipeline hid problems behind huge output and long builds.

6. Find the real palette selection path.
   The correct solution may be to alter palette selection for an already-loaded object resource rather than loading a different BTX member.

7. Instrument object creation before changing resources.
   Record requested sprite tag, resolved gfx ID, object ID, movement type, param0/1/2, and whether resource allocation succeeds.

8. Keep `narcpy.py` behavior archive-local.
   Any member-ID preservation must be opt-in per NARC.

## Recommended Next Steps

For now, treat shiny overworld sprites as out of scope.

The overworld spawn feature should focus on stability:

- normal visible spawns
- normal battles
- clean party/follower behavior
- map transition safety
- spawn rates and lifecycle tuning
- surf/headbutt/fishing behavior

If shiny OW sprites return later, start a new branch and implement a one-species proof of concept with no generated archive expansion and no forced shiny battle behavior.
