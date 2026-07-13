# Trainer Type Mastery

This feature gives trainers persistent experience with each of the 18 standard
Pokemon types. A trainer selects one active type mastery for a battle. The
party's commitment to that type multiplies the trainer's Type Level into an
effective Boon Level.

## Foundation rules

- Type Levels range from 0 through 5.
- Only the 18 standard types, Normal through Dark, are eligible.
- Typeless and Stellar are not mastery types.
- Type EXP is stored; Type Level is derived from cumulative EXP thresholds.
- One active type is stored for the player. `0xFF` means no active mastery.
- Eggs and empty party slots do not count toward commitment.
- Fainted Pokemon do count because commitment describes the registered roster,
  not the Pokemon still able to battle.
- A dual-type Pokemon counts once when either natural type matches the active
  mastery.
- Temporary in-battle type changes do not change commitment.
- Mastery state is locked when the battle starts; switching, fainting, or
  catching a Pokemon does not recalculate the commitment multiplier.

The initial cumulative Type EXP thresholds are deliberately isolated in
`include/type_mastery.h` for later tuning:

| Type Level | Total Type EXP |
|---:|---:|
| 0 | 0 |
| 1 | 100 |
| 2 | 300 |
| 3 | 700 |
| 4 | 1,500 |
| 5 | 3,000 |

## Commitment and Boon Level

`Boon Level = Type Level * Commitment Multiplier`

| Matching Pokemon | Multiplier |
|---:|---:|
| 0 | 0 |
| 1-2 | 1 |
| 3-4 | 2 |
| 5-6 | 3 |

Boon Levels 1-5 are the core band, 6-10 the specialist band, and 11-15 the
master band. Individual types should have one coherent boon package that gains
a specialist upgrade at Boon Level 6 and a master upgrade at Boon Level 11.
They should not have 15 unrelated boon effects.

## Implemented in the foundation slice

- Persistent player Type EXP and active-type storage in the expanded misc save
  block.
- Zeroed new-save storage plus lazy initialization through a versioned save
  magic value when `TypeMastery_GetSaveData` first reads it.
- Type EXP, Type Level, and active-type accessors.
- Party commitment counting.
- Commitment multiplier and Boon Level calculation.
- A shared battle-state builder that can be used for either player or enemy
  trainers once their active type and Type Level are known.
- Per-battler mastery state cached once during battle initialization. Local
  player battlers sharing a party receive the same calculated state, while tag
  and multi-battle partners retain independent cache entries.
- A shared battle cache API that additional enemy metadata can populate using
  the same party-counting and Boon Level rules as the player.
- Sparse enemy-trainer metadata keyed by resolved trainer ID. Misty has Water
  Type LV 5 in both battles. Four matching Pokemon cap her Cerulean Gym battle
  at Boon LV 10, while six let her rematch reach Boon LV 15.
- Authored NPC mastery works independently of player save availability and
  supports enemy trainers and NPC multi/tag partners through the same runtime
  cache path.
- The first complete boon package, Water's **Rising Tide**:
  - A Water Pokemon using a Water attack gains damage equal to Boon LV, capped
    at 15%.
  - Core, Boon LV 1-5: active at one-third HP or lower.
  - Specialist, Boon LV 6-10: active at one-half HP or lower.
  - Master, Boon LV 11-15: always active.
  - The effect uses the adjusted in-battle move and Pokemon types, so type
    changes are respected without recalculating roster commitment.

## Deliberately deferred

- Rules for earning Type EXP.
- Enemy mastery authoring beyond the initial Misty prototype.
- Boon packages for the other 17 types.
- Menus, battle-intro presentation, and messages.

The enemy trainer implementation must use the same battle-state builder and
boon rules as the player. Enemy mastery metadata should live in a separate table
keyed by trainer ID; the native fixed-size trainer archive records must not be
expanded.

Story-trainer metadata is deliberately ignored in wild, wireless, and Battle
Tower battles. Wireless mastery needs explicit synchronization, and facilities
may use overlapping trainer-ID namespaces that require their own metadata.

## Save compatibility

The data is appended to the existing `ALLOW_SAVE_CHANGES` misc save block. This
changes that block's size, so saves created by builds with the earlier layout
are incompatible and require conversion before this feature build can load
them. Without a converter, a new save is required. The magic value safely
initializes data only after the new save layout has been loaded.
