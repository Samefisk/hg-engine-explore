# Overworld Wild Sing Alert Logic

This note documents the removed Sing alert special action so it can be rebuilt later without rediscovering the behavior.

## Purpose

Sing was an alert-time special action selected through `alertSpecialAction`. It was meant for Pokemon such as Igglybuff: the Pokemon would perform the normal alert presentation first, then Sing would fire and put nearby overworld Pokemon into an asleep tired state.

It was removed to save overlay 149 space.

## Data And UI Shape

The alert special enum used these values:

- `OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE = 0`
- `OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP = 1`
- `OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW = 2`
- `OW_WILD_BEHAVIOR_ALERT_SPECIAL_SING = 3`

The viewer exposed Sing only in the alert-scoped special-action selector. The active scoped selector allowed only `None` and `Pick up and throw`; the alert scoped selector allowed `None`, `Call for help`, and `Sing`.

Relevant viewer concepts:

- `ALERT_SPECIAL_SING_RAW = "OW_WILD_BEHAVIOR_ALERT_SPECIAL_SING"`
- `alertSpecialActionSings(raw)`
- `scopedSpecialActionOptions(fieldKey)`
- `scopedSpecialActionRaw(fieldKey, raw)`
- raw/display labels for `"Sing"`

## Runtime Constants

The removed runtime constants were:

- `OW_WILD_SPAWNER_SING_SLEEP_RADIUS = 7`
- `OW_WILD_SPAWNER_SING_SLEEP_REST_TIME = 4`
- `OW_WILD_SPAWNER_SING_CHANCE_PERCENT = 50`
- `OW_WILD_SPAWNER_SING_SE = SEQ_SE_OW_SING`

`OW_WILD_SPAWNER_ASLEEP_REST_TIMER = 255` was shared with general asleep/tired behavior and was not Sing-specific.

## Alert Timing

Sing did not replace the normal alert emote. It ran after the alert presentation finished.

There were two trigger paths:

1. If the alert had no visual reaction, `OverworldWildSpawns_TryStartSpotEmote` immediately entered active state and tried Sing before `OverworldWildSpawns_EnterActiveStateFromGenericAlert`.
2. If the alert had the normal hop/speech emote, `OverworldWildSpawns_TickSpotEmote` waited until the emote timer reached zero, then tried Sing before entering active state.

So the intended sequence was:

1. Alert condition detects the player.
2. Normal alert bubble/hop/cry presentation plays.
3. When alert presentation is done, Sing rolls its chance.
4. If the chance succeeds, nearby Pokemon are forced into asleep tired state.
5. Sing sound plays.
6. Singer enters the normal active state.

## Sing Application

The top-level function was:

```c
static BOOL OverworldWildSpawns_TryApplySingAlertSpecialAction(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile)
```

It returned `FALSE` unless:

- `state`, `profile`, and `object` were valid.
- `slot` was inside `0..OW_WILD_MAX_SPAWNS - 1`.
- `profile->alertSpecialAction == OW_WILD_BEHAVIOR_ALERT_SPECIAL_SING`.
- `OverworldWildSpawns_RollBehaviorChance(OW_WILD_SPAWNER_SING_CHANCE_PERCENT)` succeeded.

On success it:

1. Called `OverworldWildSpawns_ForceNearbySpawnsAsleepTired(state, slot, object)`.
2. Loaded the Sing sequence with `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_SING_SE, NNS_SND_ARC_LOAD_ALL)`.
3. Played `OW_WILD_SPAWNER_SING_SE` with `PlaySE`.
4. Returned `TRUE`.

The return value was not used for branching in the alert flow; Sing was a side effect.

## Target Selection

`OverworldWildSpawns_ForceNearbySpawnsAsleepTired` used the singer object's current tile as the center.

For every active spawn slot:

- It skipped the singer slot.
- It skipped inactive slots.
- It skipped slots without an object.
- It measured Chebyshev distance: `max(abs(targetX - singerX), abs(targetY - singerY))`.
- If that distance was `<= OW_WILD_SPAWNER_SING_SLEEP_RADIUS`, the target was forced asleep.

This means the area was a square radius, not a circular radius and not a pathfinding radius.

## Forcing A Target Asleep

`OverworldWildSpawns_ForceSlotAsleepTired` did the actual per-target state transition.

It ignored:

- Invalid state.
- Invalid slot.
- Inactive slot.
- Slot queued for battle.
- Slot with no map object.

If the target was not already tired, and it was not safely idle in chill state, it reset movement first with:

```c
OverworldWildSpawns_ResetSlotMovementCommand(state, slot, TRUE);
```

The reset happened when the target was:

- Not in chill state, or
- Running spawn movement, or
- Waiting on staged hop movement, or
- In a spawner-owned movement command, or
- In a map-object single movement command.

Then it resolved a forced-asleep profile and called:

```c
OverworldWildSpawns_StartTiredEmoteWithProfile(state, slot, &profile);
```

## Forced-Asleep Profile

The forced-asleep profile logic was:

- Start from the target's resolved behavior profile if possible.
- Apply override profile `behaviorData->overrideProfiles[0]`.
- If that override could not be applied, fall back to hardcoded asleep fields:
  - `tiredState = OW_WILD_BEHAVIOR_KIND_ASLEEP`
  - `stamina = 1`
  - `restTime = OW_WILD_SPAWNER_SING_SLEEP_REST_TIME`
  - `tiredBattle = OW_WILD_BEHAVIOR_BATTLE_TRIGGER_NONE`
  - `specialAction = OW_WILD_BEHAVIOR_LOCOMOTION_NONE`

The normalization pass ensured:

- Invalid tired states became `OW_WILD_BEHAVIOR_KIND_ASLEEP`.
- `OW_WILD_BEHAVIOR_KIND_NONE` tired state became asleep.
- Missing tired speed inherited chill speed.
- Missing tired speed after that became `OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT`.
- If the tired state used asleep, stamina was forced to `1`.
- If it did not use asleep and `restTime == 0`, rest time was forced to `1`.

At the time, the behavior-data side had a separate rule matching `OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP` to override profile index `0`. In data version 32, that representation is consolidated: the forced-asleep override profile itself owns the shared class condition and uses all-Pokémon target mode. It remains one profile layer, not a profile plus a separate executable rule.

## Asleep Runtime Behavior

The asleep state reused the tired-state machinery:

- `OverworldWildSpawns_StartTiredEmoteWithProfile` entered `OW_WILD_SPAWNER_SPOT_STATE_TIRED`.
- It computed rest frames from `restTime * tired step frame count`.
- If asleep with `restTime == 0`, it used `OW_WILD_SPAWNER_ASLEEP_REST_TIMER`.
- It cleared active single movement before asleep visuals when needed.
- It started the tired/asleep visual or directly queued frame-task handling depending on the profile.

Wake-up was not a separate Sing-specific system. The Pokemon left tired/asleep when the normal tired timer/cooldown flow completed.

## Reimplementation Checklist

To restore Sing later:

1. Re-add `OW_WILD_BEHAVIOR_ALERT_SPECIAL_SING` after `PICKUP_THROW`.
2. Re-add the viewer raw/display option and alert-scoped filtering.
3. Re-add constants for radius, chance, rest time, and sound sequence.
4. Re-add forced-asleep helper functions or replace them with a smaller profile-override application path.
5. Re-add `TryApplySingAlertSpecialAction` after alert emote completion and in the no-alert-visual fast path.
6. Decide whether forced-asleep should still use `overrideProfiles[0]`; if not, document the new profile lookup rule and avoid hardcoded profile index assumptions.
7. Rebuild and check overlay 149 size before adding polish.
