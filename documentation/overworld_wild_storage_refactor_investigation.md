# Overworld Wild Storage Refactor Investigation

Branch: `codex/investigate-ow-wild-storage`

Goal: investigate how to stop overworld wild behavior work from being boxed in by the current overlay space limit. The main question is storage: what can live somewhere else, whether it can be split across multiple places, and what migration path leaves the engine safer instead of more fragile.

Measurements below use the existing build artifacts on this branch. No new build was run for this investigation.

## Executive Summary

The current space problem is not one generic ROM-size problem. It is several storage ceilings stacked on top of each other:

- Overlay 149, `overworld_wild_spawns_overlay`, is the critical limit. It is `44,984` bytes in a `45,056` byte window, leaving about `72` bytes.
- Overlay 150, `overworld_wild_behavior_data_overlay`, is not the critical limit. It is `1,424` bytes in a `4,096` byte window, leaving about `2,672` bytes.
- Full encounter data and headbutt tree data already live in NARC archives. The remaining pressure is mostly overlay 149 code plus a few overlay-local tables and caches.
- We can store things in multiple places, but each place should have one job:
  - NARC resource members for large authored behavior/profile/rule data.
  - Overlay 150 for small resident data and, possibly, pure resolver-library code.
  - A new linked overlay for larger cold helper code, only through fixed entry tables.
  - Heap-backed decoded caches for data loaded from NARC.
  - Overlay 149 only for the active task owner, battle handoff, frame task entry points, and tight movement orchestration.

Recommended direction:

1. Move authored behavior/profile/rule data out of C initializers and into a generated pointerless binary resource.
2. Keep overlay 150 as the first bridge so runtime changes are small.
3. Move small overlay-149 read-only tables to the same data module or to NARC.
4. Move behavior resolution code out of overlay 149 if the fixed entry-table shape stays stable.
5. For real breathing room, split one bulky code cluster into a new linked helper overlay.

## Current Storage Map

| Area | Role | Fixed window | Current artifact | Headroom | Notes |
|---|---:|---:|---:|---:|---|
| Overlay 129 | ARM9 extension | `0x023D8600-0x023E0000` | about `0x79C4` code, Y9 mem about `0x7FC4` | about `0x3C` | Not useful as expansion room. |
| Overlay 131 | field extension | linker says `0x023C8000-0x023E0000` | about `0x48EA` | effectively about `0x716` before 149 | It is co-loaded before 149, so its nominal linker length is misleading. |
| Overlay 149 | OW wild runtime | `0x023CD000-0x023D8000` | `44,984` bytes | about `72` bytes | Main bottleneck. |
| Overlay 150 | OW behavior data | `0x023C3000-0x023C4000` | `1,424` bytes | about `2,672` bytes | Useful for data and small library code. |

Key local evidence:

- Overlay 149 linker window is `ORIGIN = 0x023CD000, LENGTH = 0xB000` in `src/overworld_wild_spawns_overlay/linker.ld`.
- Overlay 150 linker window is `ORIGIN = 0x023C3000, LENGTH = 0x1000` in `src/overworld_wild_behavior_data_overlay/linker.ld`.
- Overlay ids are `149` and `150` in `include/constants/file.h`, and `MAX_ACTIVE_OVERLAYS` is `8`.
- The overlay chain in `src/overlay.c` currently links `FIELD_EXTENSION -> OVERWORLD_WILD_SPAWNS_EXTENSION -> OVERWORLD_WILD_BEHAVIOR_DATA`.
- `include/types.h` already exposes `ArchiveDataLoad`, `ArchiveDataLoadOfs`, `ArchiveDataLoadMalloc`, `ArchiveDataLoadMallocOfs`, and lower-level NARC reads.

One important detail: the overlay linker scripts put `.text`, `.rodata`, `COMMON`, and `.bss` into the loaded overlay image. That means zeroed overlay statics still cost bytes in the overlay artifact.

## Biggest Current Spenders

Overlay 149 is full because it contains the runtime engine, not because the behavior data is huge.

Largest observed symbols from `build/overworld_wild_spawns_overlay_linked.o`:

| Symbol | Approx size | Meaning |
|---|---:|---|
| `OverworldWildSpawns_TickMovementParams` | `5,204` bytes | Main movement tick and behavior state work. |
| `OverworldWildSpawns_TryStartHeadbuttTreeHop` | `3,068` bytes | Headbutt/canopy hop selection and setup. |
| `OverworldWildSpawns_SpawnPreparedEncounter` | `2,900` bytes | Spawn/object setup path. |
| `OverworldWildSpawns_FrameMovementTask` | `1,288` bytes | Per-frame task owner. |
| `OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand` | `1,108` bytes | Hop planner step handling. |
| `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand` | `840` bytes | Phantom teleport movement. |
| `OverworldWildSpawns_ResolveBehaviorProfileForContext` | `678` bytes | Behavior data resolver in 149. |
| `OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot` | `654` bytes | Resolver plus primitive preparation in 149. |

Good data candidates still in overlay 149:

- `sOverworldWildEncounterAreaMapIds`: about `300` bytes.
- `sOverworldWildEncounterAreaDataIds`: about `150` bytes.
- Overlay-local `.bss`: about `464` bytes, if it can become real heap/state storage instead of overlay image storage.

Behavior data in overlay 150 is modest:

- Class profiles: about `528` bytes.
- Species class rules: about `440` bytes.
- Variable overrides: about `184` bytes.
- Class rules: about `32` bytes.
- Entry table: about `40` bytes.

So moving the current profile arrays elsewhere is architecturally good, but it does not by itself solve overlay 149.

## Storage Options

### Option A: NARC-backed Authored Data

Best use:

- Behavior profiles.
- Class rules.
- Species class rules.
- Variable overrides.
- Encounter area map-id to encounter-data-id lookup.
- Future UI-authored behavior metadata.
- Small movement tuning tables, if they are not needed every frame before cache.

Existing pattern:

- `ARC_CODE_ADDONS` (`a/0/2/8`) is already extracted and rebuilt during normal build.
- `data/codetables.mk` already writes raw binary members such as hidden abilities, base experience, and form tables.
- Runtime code already reads NARC members with fixed offsets, for example Pokemon form/overworld graphics tables.

Recommended format:

- Add a pointerless `OWBD` binary blob.
- Use a fixed little-endian header:
  - magic
  - version
  - total size
  - counts
  - offsets
  - element sizes
  - checksum if useful
- Store relative offsets, never absolute pointers.
- Load once per field session or first behavior use.
- Validate magic/version/counts/offset bounds before use.
- Cache decoded pointers as `base + offset`, or copy into runtime structs if alignment becomes risky.

Pros:

- Breaks editable behavior data out of the overlay window.
- Makes profile/rule growth mostly ROM/filesystem storage, not overlay storage.
- Matches the editor direction better than rewriting C.
- Can keep old overlay 150 path as fallback during migration.

Cons:

- Needs generator and validation code.
- Needs heap lifetime/cleanup policy.
- Raw binary is harder to review unless the JSON/source dump remains authoritative.
- Direct many-small NARC reads in frame paths would be bad, so load/cache once.

### Option A2: Compact Existing Archives

This is a useful adjacent track, but it solves a different problem.

Current raw archive sizes:

- Encounter NARC data: about `27.8 KB`.
- Headbutt tree data: about `27.4 KB`.

Possible raw savings:

- Headbutt tree archive: about `11-14 KB` if coordinate lists become count-prefixed and unused/sparse special-tree blocks are omitted.
- Encounter archive: about `12 KB` if an overworld-only compact record format is introduced, or about `4 KB` with a safer fixed-size subset.
- Species behavior rules: about `220` bytes from packing species/class pairs into one `u16`; up to about `400` bytes if broad semantic rules replace many explicit species rules.
- Sparse behavior overrides: about `200` bytes today if overrides become `(field,value)` patches instead of profile-shaped payloads.

Important distinction:

- Compressing encounter/headbutt archive members saves ROM/filesystem bytes.
- It does not by itself solve overlay 149's loaded-code window.
- It can help future data growth and can make generated assets cleaner, but overlay 149 still needs code/data relocation.

Risks:

- Fixed-offset `ArchiveDataLoadOfs` reads currently assume specific layouts.
- Stock encounter readers may expect the existing `196` byte encounter layout, so compact encounter data is safest as an overworld-only resource unless every consumer migrates.
- Headbutt tree data has special-case layout assumptions and at least one suspicious/inconsistent member, so migration needs a validator before it rewrites the archive shape.

Implementation note from the experiment stack:

- Headbutt tree members are the safe first in-place compression target. The compact builder preserves map-id member indexing and the fixed 4-byte header plus 18 encounter-slot offsets, then stores each tree as a count-prefixed coordinate list. This measured `27,408 -> 16,680` raw member bytes, saving `10,728` bytes before NARC container overhead.
- Route 34's headbutt header declared one special tree without a matching coordinate record; the compact builder rejects that class of mismatch, so the authored header was corrected to `15` normal trees and `0` special trees.
- Encounter archive 37 remains legacy-compatible for now. It is likely still read by normal encounter code, so in-place compression should wait for either a proven complete reader migration or an overworld-only compact sidecar with a later legacy-removal gate.

### Option B: Overlay 150 As Data And Resolver Module

Best use:

- Existing profile/rule entry table.
- More read-only behavior tables.
- Small pure resolver/helper functions.
- Fixed entry points consumed by overlay 149.

Current proof:

- Overlay 150 already loads synchronously as a linked child of overlay 149.
- Overlay 149 already validates `magic`, `version`, `size`, and table pointers before using it.
- Overlay 150 has about `2.6 KB` free.

Strong candidate move:

- Move behavior resolution helpers from overlay 149 into overlay 150:
  - profile context resolution
  - behavior group flags
  - override matching
  - compact override decode

Potential win:

- Around `1.5-2 KB` from overlay 149 if the entry table grows into a small resolver-library API.

Main constraint:

- Calls must go through fixed entry tables or function pointers from the validated overlay-150 entry. Do not rely on loose direct calls into another overlay unless load/lifetime and Thumb-bit mechanics are proven.

### Option C: New Linked Helper Overlay

Best use:

- One bulky, mostly synchronous code cluster.
- Code that is called by overlay 149 while both overlays are guaranteed loaded.
- Code that does not own long-lived callbacks.

Candidate clusters:

- Headbutt/canopy tree-hop selection.
- Spawn-position preparation.
- Behavior matching/resolution if it outgrows overlay 150.
- Some target validation/planning helpers.

Risk boundary:

- Keep SysTask entry points, draw callbacks, battle handoff, map-object callback-facing code, and movement descriptor-facing code in overlay 149 or resident ARM9 code.
- Helper overlays should not leave their function pointers stored in objects/tasks that might survive unload.

Practical shape:

- Add overlay 151 with its own fixed linker window.
- Add an entry struct with magic/version/size and function pointers.
- Load it through `gLinkedOverlayList` after overlay 149, or lazy-load synchronously before first use.
- Validate its address and entry before calling.

This is the first route that can create real code room beyond the 2.6 KB available in overlay 150.

### Option D: Heap-backed Runtime State

Best use:

- Overlay-local `.bss`.
- Decoded behavior blobs.
- Caches that are only valid while field/overlay is active.
- Per-route lookup tables loaded from NARC.

Why it matters:

- Current linker scripts include `.bss` inside the loaded overlay image.
- Moving statics into explicit runtime allocation can free overlay bytes even when runtime RAM usage stays similar.

Risks:

- Needs clear ownership and cleanup when the field overlay unloads.
- Must not leave stale pointers after battle handoff or overlay unload.

### Option E: Repartition Overlay Windows

Possible but not the first move.

Current fixed windows are tightly packed:

- Overlay 149 cannot simply grow upward because overlay 129 starts above it.
- Moving overlay 149 downward only finds a small gap unless field overlay 131 and the linked chain are planned together.
- Overlay 150 cannot grow upward because battle extension overlay 130 starts at `0x023C4000`.

This is a larger memory-layout task. It may be worth doing later, but it should not be the first storage refactor.

## Do Not Use As Primary Storage

### ARM9 Extension Overlay 129

It is nearly full. Treat it as unavailable for overworld wild expansion.

### Save Data

Do not store baseline behavior definitions in save data. Save data is version-sensitive player state, not engine-authored config. It is fine for runtime/player progress, not for core profile definitions.

### Per-frame NARC Reads

NARC is good for storage, not hot-loop access. Load once, validate, then use cached memory.

### Pointer-bearing Binary Assets

Do not store raw C structs with absolute pointers in NARC. Use offsets or separate members.

## Recommended Multi-step Architecture

### Phase 0: Keep Size Measurements Cheap

Add a small size-report script or Make target that prints:

- overlay 149 current size/headroom
- overlay 150 current size/headroom
- top `nm --size-sort` symbols
- behavior data blob/member size

This should run without a full ROM boot and should become the first check after every storage refactor.

### Phase 1: Move Easy Overlay-149 Tables

Move the encounter-area lookup pair out of overlay 149:

- `sOverworldWildEncounterAreaMapIds`
- `sOverworldWildEncounterAreaDataIds`

Storage choices:

- Smallest code churn: move them into overlay 150 entry data.
- Better long-term: store them in the `OWBD` resource blob or a separate `ARC_CODE_ADDONS` member.

Expected overlay-149 win:

- About `450` bytes.

### Phase 2: Generated Behavior Data Source

Stop making the UI rewrite C initializer tables directly.

Suggested source of truth:

- `data/overworld_wild_behavior/profiles.json`

Suggested generated outputs:

- A compact `OWBD` binary member in `ARC_CODE_ADDONS`.
- A generated readable dump for review.
- Optionally a generated header for stable ids and version constants.

Bridge strategy:

1. Generate the current overlay-150 C arrays from JSON first.
2. Then switch overlay 150 to `.incbin` a generated binary payload.
3. Then switch runtime from pointer tables to offset-based blob access.
4. Then remove the old C initializer parser from the viewer.

This keeps behavior changes reviewable and lets runtime migration happen in smaller steps.

### Phase 3: Compact Overrides And Rules

Current overrides are large because each override carries a profile-shaped payload plus masks.

Better file format:

- Match rule.
- Field-count.
- Repeated compact field id/value pairs.

Runtime can decode to a full `OverworldWildBehaviorProfile` cache after applying a base profile.

Important placement:

- Put decode code in overlay 150 or a helper module if possible, not in overlay 149.

Expected win:

- Small today because there are only two overrides.
- Important for future growth because UI-driven overrides can multiply quickly.

Optional extra compaction:

- Pack species/class rules into one `u16` if behavior class ids stay under 8 and species ids stay under 8192.
- Consider broad type/group rules only when the semantic behavior is actually desired. For example, replacing a long list of explicit Ghost species with one Ghost-type rule saves space, but it changes future behavior for every Ghost-type species.

### Phase 4: Move Resolver Library Out Of Overlay 149

Move these concepts behind overlay 150's entry table:

- group flag calculation
- class/species rule lookup
- override matching
- primitive/profile resolution

Overlay 149 should ask a module:

```c
const OverworldWildBehaviorProfile *ResolveProfile(const OverworldWildBehaviorContext *context);
void ResolvePrimitives(const OverworldWildBehaviorProfile *profile, OverworldWildBehaviorPrimitives *out);
```

Expected overlay-149 win:

- Around `1.5-2 KB`, depending on entry-table overhead and inlining changes.

Risks:

- The resolver must not capture pointers to unloadable memory without validation.
- The entry table must be versioned and validated before use.
- Any function-pointer call must preserve Thumb/interworking correctness.

### Phase 5: Split One Bulky Code Cluster

If Phase 1-4 are not enough, add a new helper overlay.

First candidate:

- Headbutt/canopy tree-hop selection and related pure helper logic.

Why:

- It is a large cluster.
- It is not the root task owner.
- Headbutt data is already external; the remaining spend is code.

Second candidate:

- Spawn-position preparation.

Third candidate:

- Target validation/planning helpers, if they stabilize.

Avoid moving:

- `OverworldWildSpawns_FrameMovementTask`
- battle handoff callbacks
- map-object callbacks
- any callback that can survive overlay unload

### Phase 6: Revisit Memory Window Repartitioning

Only after data migration and one helper split should we consider moving overlay windows.

Reason:

- Address replanning affects multiple overlays at once.
- It can create subtle load overlaps.
- It needs built-ROM Y9 inspection plus headless runtime checks.

## Concrete Migration Plan

1. Add size-report tooling.
2. Move encounter lookup tables out of overlay 149.
3. Add `data/overworld_wild_behavior/profiles.json`.
4. Add a Python codec/generator for `OWBD`.
5. Make the UI read/write the JSON source instead of C.
6. Generate overlay-150 C or `.incbin` from `OWBD` as a compatibility bridge.
7. Add offset-based runtime validation and access.
8. Move resolver library into overlay 150 entry functions.
9. Add a helper overlay only for one bounded pure-code cluster.
10. Reconsider linker-window repartition only if helper overlays still leave us cramped.

## Verification Needed Per Phase

For each phase:

- Run the size-report script.
- Build the ROM with the normal Delta build flow.
- Inspect overlay sizes and Y9 load addresses.
- Headless boot to overworld.
- Verify overlay 150 magic/version if still used.
- Spawn a few species across default, canopy, phantom, ram, playful, swarm, and call-for-help profiles.
- Verify route encounter UI still saves and reloads behavior data.

Specific failure checks:

- No per-frame NARC reads.
- No helper-overlay callback pointers stored in long-lived tasks or map objects.
- No stale heap pointer after overlay unload/battle handoff.
- No overlay address overlap.
- No version mismatch silently falling back to default behavior unless explicitly intended.

## Final Recommendation

The storage answer is yes, we should store this in multiple places:

- Authored behavior definitions in NARC-backed binary data.
- Small resident module data and resolver APIs in overlay 150.
- Runtime caches on heap.
- Optional large behavior helper code in a new fixed-address linked overlay.
- Core orchestration in overlay 149.

The biggest conceptual shift is to stop treating overlay 149 as both the engine and the data warehouse. Overlay 149 should become the core coordinator: it owns the frame task and high-risk lifetime edges, while data and cold helpers live in modules that can grow independently.
