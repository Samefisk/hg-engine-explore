# Trainer Type Mastery

This feature gives trainers persistent experience with each of the 18 standard
Pokemon types. Every qualified mastery is active at the same time. The party's
commitment to each type multiplies that type's trainer Type Level into an
effective Boon Level.

## Foundation rules

- Type Levels range from 0 through 5.
- Only the 18 standard types, Normal through Dark, are eligible.
- Typeless and Stellar are not mastery types.
- Type EXP is stored; Type Level is derived from cumulative EXP thresholds.
- Eggs and empty party slots do not count toward commitment.
- Fainted Pokemon do count because commitment describes the registered roster,
  not the Pokemon still able to battle.
- A dual-type Pokemon counts once for each of its two natural types.
- Temporary in-battle type changes do not change commitment.
- Mastery state is locked when the battle starts; switching, fainting, or
  catching a Pokemon does not recalculate the commitment multiplier.

The initial cumulative Type EXP thresholds are deliberately isolated in
`include/type_mastery.h` for later tuning:

| Type Level | Total Type EXP |
|---:|---:|
| 0 | 0 |
| 1 | 1,000 |
| 2 | 7,500 |
| 3 | 25,000 |
| 4 | 75,000 |
| 5 | 175,000 |

Whenever a Pokemon receives battle EXP, its trainer earns Type EXP from the
same final amount:

- A single-type Pokemon gives the full awarded amount to its type.
- A dual-type Pokemon gives `floor(awarded EXP / 2)` to each type. Any odd
  remainder is discarded.
- A Pokemon that receives no actual EXP gives no Type EXP.
- EXP All, participation/contribution adjustments, capture EXP, held-item
  modifiers, traded-Pokemon modifiers, and other recipient modifiers are
  inherited because Type EXP observes the final change to the Pokemon's EXP.
- The Pokemon's natural current-form party types are used. Temporary battle
  type changes do not redirect Type EXP.
- Type EXP earned during a battle does not recalculate that battle's cached
  Boon Levels. Newly earned levels take effect next battle.

## Commitment and Boon Level

`Boon Level = Type Level * Commitment Multiplier`

| Matching Pokemon | Multiplier |
|---:|---:|
| 0-1 | 0 |
| 2-3 | 1 |
| 4-5 | 2 |
| 6 | 3 |

Boon Levels 1-5 are the core band, 6-10 the specialist band, and 11-15 the
master band. Individual types should have one coherent boon package that gains
a specialist upgrade at Boon Level 6 and a master upgrade at Boon Level 11.
They should not have 15 unrelated boon effects.

Mastery packages should primarily intensify a type's established strengths,
not erase its weaknesses. For example, a future Rock package should reward
moving last or improve durability rather than simply making Rock Pokemon fast.

All qualified packages may modify the same event. Each package applies its own
type and condition gates, so a dual-type Pokemon can receive both effects when
both qualify. Code must not use global exclusivity or an `else if` chain between
types. Same-category percentage modifiers should be accumulated before one
application; mechanically distinct effects run in a documented phase order.

## Implemented in the foundation slice

- Persistent player Type EXP for all 18 types in the expanded misc save block.
- Zeroed new-save storage plus lazy initialization through a versioned save
  magic value when `TypeMastery_GetSaveData` first reads it.
- Type EXP and Type Level accessors plus the five-level progression curve.
- Type EXP awards derived from each Pokemon's actual final battle EXP gain.
- Party commitment counting.
- Commitment multiplier and Boon Level calculation.
- A shared battle-state builder that calculates all 18 keyed type states for
  either player or enemy trainers.
- Per-battler mastery state cached once during battle initialization. Local
  player battlers sharing a party receive the same calculated state, while tag
  and multi-battle partners retain independent cache entries.
- A shared battle cache API that enemy metadata populates using the same
  party-counting and Boon Level rules as the player. Sparse metadata supports
  multiple Type Levels for one trainer.
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

- Enemy mastery authoring beyond the initial Misty prototype.
- Boon packages for the other 17 types.
- Menus, battle-intro presentation, and messages.

Enemy mastery metadata lives in a separate sparse table keyed by trainer ID and
type; the native fixed-size trainer archive records are not expanded.

Story-trainer metadata is deliberately ignored in wild, wireless, and Battle
Tower battles. Wireless mastery needs explicit synchronization, and facilities
may use overlapping trainer-ID namespaces that require their own metadata.

## Save compatibility

The data is appended to the existing `ALLOW_SAVE_CHANGES` misc save block. The
Type Mastery payload remains exactly `0x50` bytes. The former prototype
active-type byte is now reserved, so Type EXP from that prototype layout is
preserved. Saves from builds predating the expanded misc save block still need
the existing conversion or a new save.
