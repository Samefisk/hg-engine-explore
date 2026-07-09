# Overworld Pokemon Sprite Animation

## Purpose

This note tracks what is known about overworld Pokemon sprite animation speed and how it differs from movement speed. Sprite animation speed is useful as a future behavior/profile tool, but it should be controlled deliberately rather than inherited from hop or landing state.

## Current model

- Movement speed and sprite animation speed are separate concerns.
- Profile movement values decide how often a Pokemon chooses or executes movement.
- Sprite animation speed is presentation state on the map object/OAM path.
- Custom hops use map-object movement/render state during travel, then must restore normal presentation state on landing.

## Custom Hop Landing Fix

The custom hop landing path previously set `0x00020028` after landing as `OW_WILD_SPAWNER_CUSTOM_JUMP_LANDING_SET_BITS`. Those bits correspond to map-object flags 3, 5, and 17. Leaving them raised after a custom hop can make the Pokemon sprite animation continue at the faster hop pacing.

The landing path now treats those bits as short-lived animation state:

- `OW_WILD_SPAWNER_CUSTOM_JUMP_LANDING_ANIM_BITS`
- cleared by `OverworldWildSpawns_SetObjectLandingTile`
- pulsed by `OverworldWildSpawns_PlayCustomJumpLandingFeedback`
- cleared by `OverworldWildSpawns_TickCustomJumpLandingFeedback`

This keeps custom hops from permanently speeding up the Pokemon's idle/walk
sprite animation after landing, while still giving the stock landing animation
state a rendered window.

## Persistent Regression Hardening

The landing pulse now has its own `movementCustomJumpLandingAnimFrames` timer.
Do not reuse the custom jump elapsed timer for post-landing animation feedback:
that field is jump-progress state, and sharing it with the landing pulse lets
cleanup, object recreation, or context-loss paths accidentally leave the
`0x00020028` presentation bits alive longer than intended.

The custom jump cleanup path clears the whole custom-jump presentation bit set,
including the landing animation bits. Landing feedback must be re-applied with
`OverworldWildSpawns_PlayCustomJumpLandingFeedback` after cleanup when a short
landing pulse is actually desired.

## Future Intentional Speed Control

If overworld Pokemon sprite animation speed becomes a profile option, use a scoped apply/restore path:

1. Store the original animation pacing/state for the map object.
2. Apply the requested animation speed while the behavior is active.
3. Restore the saved state when the behavior ends, the Pokemon lands, despawns, is picked up, or enters battle.

Avoid piggybacking on custom hop landing flags for permanent animation speed changes. Hop flags are transient movement state and should be normalized at landing.

## Useful Symbols And Findings

- `sub_0205F6AC(object, value)` toggles `MAPOBJECTFLAG_UNK18`; it is not a general sprite animation speed setter.
- The stock jump movement path uses map-object scratch state around `object->unkF8`.
- `OAM_ObjectAnimeSeqSetCap` appears to be OAM-level animation control, but the safe map-object owner path for overworld Pokemon has not been mapped yet.

## Deeper Animation-Speed Investigation

### Movement speed tiers

The existing profile movement speed fields are safe for making Pokemon move
faster or slower across tiles. They are movement-command choices, not visual
animation-speed knobs.

Disassembly of the stock movement command table shows these practical tiers:

| Profile speed | Command base | Initializer | Movement frame argument |
| --- | --- | --- | --- |
| 1 | `0x08` walk | `0x020625B8` | `16` |
| 2 | `0x0C` fast walk | `0x02062608` | `8` |
| 3 | `0x10` very fast | `0x0206265C` | `4` |
| 4 | `0x14` run | `0x020626AC` | `2` |

This is the cheapest way to make a Pokemon feel faster or slower while moving.
It changes travel pacing and likely the stock walk-cycle cadence together. It
does not give independent "same movement speed, different sprite animation
speed" control.

There is also a stock slow-walk command family around `0x04`. Using it could
support slower-than-current speed 1 locomotion, but it should be introduced as
a movement-speed tier, not as sprite-only animation control.

### Hop timing

Custom hop `hopTime` controls the duration of the custom hop carrier and arc.
It is appropriate for faster or slower jumps through the air. It is not a
general sprite animation-speed field, and it should not leave map-object hop or
landing flags behind after the hop completes.

### OAM animation sequence selection

`OAM_ObjectAnimeSeqSetCap` is real OAM-level animation control, but it is not a
simple speed scalar.

Findings:

- The public symbol at `0x0200DC4C` is a wrapper that expects a `CATS_ACT_PTR`
  and dereferences `[r0]`.
- The internal actor routine at `0x020248F0` validates the requested sequence,
  stores it at actor `+0xF0`, and rebuilds the NNS animation state.
- For normal small overworld Pokemon, the primary render actor appears to live
  through the map-object render data at `object + 0x108`; the normal small
  Pokemon draw callback uses `[object + 0x108]` as primary actor and
  `[object + 0x10C]` as secondary actor.

Risk:

- Sequence indexes are resource-specific. A "slow" sequence exists only if the
  overworld resource has one.
- Passing the wrong pointer to the public wrapper can crash, because it
  dereferences once before reaching the actor routine.
- Actor pointers may be null before first render and may change after sprite
  recreation, form changes, despawn, pickup, or battle transitions.

### Recommended path

For now:

- Use existing movement speed tiers for movement feel.
- Use `hopTime` only for jump travel/arc feel.
- Keep clearing transient custom-hop landing bits so hop state does not become
  accidental permanent animation-speed state.

For a future dedicated sprite-animation-speed feature:

1. Add a profile field only after deciding whether it should be global or
   per-state (`chill`, `active`, `tired`).
2. First map a safe per-object render actor accessor for spawned overworld
   Pokemon.
3. Probe `OAM_ObjectAnimeSeqSetCap` on one Pokemon at spawn/state-transition
   time only.
4. Restore the original sequence on landing, behavior change, despawn, pickup,
   throw, battle transition, and sprite recreation.

The safer long-term model is "movement speed controls travel" and "animation
sequence/mode controls sprite cadence", with explicit restore points between
them.
