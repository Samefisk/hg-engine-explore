# Overworld Wild Spawn Space Investigation

This branch is stacked on `feature/overworld-wild-spawns` by request. The feature is not on
`origin/main` yet, so this investigation should be rebased or recreated after that feature merges.

## Current Budget

The tight region is Overlay 129, not the final NDS filesystem size.

- Linker region: `src/linker.ld`
- Capacity: `0x7A00` bytes / `31,232` bytes
- Current linked load size: `31,225` bytes
- Current margin: `7` bytes

Measured with:

```sh
arm-none-eabi-size -A build/linked.o
```

Only `.text`, `.data`, and `.rodata.str1.1` were counted for the load-size comparison.

## Config Toggle Audit

Each candidate was measured by temporarily commenting out one `include/config.h` define, building only
`build/linked.o` in Docker, then restoring the config.

| Candidate disabled | Result | New margin | Bytes saved |
| --- | ---: | ---: | ---: |
| `ALLOW_SAVE_CHANGES` | pass | 5,167 | 5,160 |
| `EXPAND_PC_BOXES` | pass | 4,751 | 4,744 |
| `IMPLEMENT_REUSABLE_REPELS` | pass | 417 | 410 |
| `FIELD_MOVE_HM_COMPATIBILITY` | pass | 183 | 176 |
| `IMPLEMENT_SEASONS` | pass | 135 | 128 |
| `HIDDEN_ABILITIES` | pass | 87 | 80 |
| `ITEM_POCKET_EXPANSION` | pass | 39 | 32 |
| `MEGA_EVOLUTIONS` | pass | 7 | 0 |
| `PRIMAL_REVERSION` | pass | 7 | 0 |
| `IMPLEMENT_CAPTURE_EXPERIENCE` | pass | 7 | 0 |
| `IMPLEMENT_CRITICAL_CAPTURE` | pass | 7 | 0 |
| `IMPLEMENT_NEW_EV_IV_VIEWER` | pass | 7 | 0 |
| `UPDATE_OVERWORLD_POISON` | pass | 7 | 0 |
| `FRIENDSHIP_EFFECTS` | pass | 7 | 0 |
| `RESTORE_ITEMS_AT_BATTLE_END` | pass | 7 | 0 |
| `UPDATE_VITAMIN_EV_CAPS` | pass | 7 | 0 |
| `STATIC_HP_BAR` | pass | 7 | 0 |
| `MART_EXPANSION` | pass | 7 | 0 |
| `IMPLEMENT_RESULT_BASED_EXP` | pass | 7 | 0 |
| `UPDATE_MACHINE_MOVE_LABELS` | fail | overflowed by 19 | -26 |
| `REUSABLE_TMS` | fail | overflowed by 19 | -26 |

The two failures are useful negative results: disabling either `UPDATE_MACHINE_MOVE_LABELS` or
`REUSABLE_TMS` currently makes Overlay 129 larger.

## Combined Measurements

| Combination disabled | New margin | Bytes saved |
| --- | ---: | ---: |
| `IMPLEMENT_OVERWORLD_WILD_SPAWNS` | 2,579 | 2,572 |
| `ALLOW_SAVE_CHANGES` + `EXPAND_PC_BOXES` | 5,167 | 5,160 |
| `IMPLEMENT_REUSABLE_REPELS` + `FIELD_MOVE_HM_COMPATIBILITY` + `IMPLEMENT_SEASONS` + `HIDDEN_ABILITIES` | 793 | 786 |
| `IMPLEMENT_REUSABLE_REPELS` + `IMPLEMENT_SEASONS` + `HIDDEN_ABILITIES` + `ITEM_POCKET_EXPANSION` | 649 | 642 |

## What Deleting Content Would Actually Do

Deleting maps, sprites, music, scripts, or NARC files can shrink the final ROM filesystem, but it does
not automatically increase the Overlay 129 linker region. The repeated overflows we are hitting are
Overlay 129 code/data overflows, so content deletion is the wrong first lever unless it is paired with
a linker/insertion change that repurposes freed memory for executable code.

## Better Long-Term Option: Move Spawns Out Of Overlay 129

`overworld_wild_spawns.o` is about `2.6 KB` total and about `1.8 KB` of text. Moving most of it out of
Overlay 129 would turn the current 7-byte margin into a practical development budget.

The existing overlay build system already supports generated overlays:

- Overlay 130: battle extension, `0x14000` capacity, about `66 KB` used.
- Overlay 131: field extension, `0x18000` capacity, about `19 KB` used.
- Overlay 132: pokedex extension.
- Overlay 133-148: individual battle overlays.

A likely design:

1. Add a new overlay id, probably `OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION = 149`.
2. Add a new `src/overworld_wild_spawns_overlay/` folder with its own `linker.ld`.
3. Chain it from the field extension so it loads with field state:
   `OVERLAY_FIELD -> OVERLAY_FIELD_EXTENSION -> OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION`.
4. Keep tiny Overlay 129 stubs for the public entry points currently called by root code:
   `OverworldWildSpawns_OnPlayerStep`, `OverworldWildSpawns_PopPendingBattle`, and
   `OverworldWildSpawns_CleanupPendingBattle`.
5. Put the heavy spawn/refill/encounter/table logic in the new overlay.
6. Keep persistent pending-battle state either in Overlay 129 globals or in save/field-owned memory, so
   starting battle does not depend on a field overlay that might unload during transition.

Important caveat: normal C cross-calls from Overlay 129 into a later-linked overlay will not work
directly, because `build/linked.o` is linked before generated overlays. The stubs need to call fixed
overlay entry points, use a small jump table at the start of the new overlay, or rely on known symbols
emitted into `rom_gen.ld` after the first link. The jump-table approach is probably the most robust.

## Recommendation

For a quick space win, disabling `IMPLEMENT_REUSABLE_REPELS` is a small but clean 410-byte gain if that
QoL feature is expendable. Disabling save expansion / expanded PC boxes is much larger, but it is a
game-design decision with save compatibility impact.

For the overworld spawn project, moving the spawn system to its own field-linked overlay is the best
engineering direction. It gives room for true headbutt encounter tables, safer edge checks, richer
spawn behavior, and future polish without constantly byte-shaving Overlay 129.
