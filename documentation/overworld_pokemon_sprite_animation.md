# Overworld Pokemon Sprite Animation

## Purpose

This note tracks what is known about overworld Pokemon sprite animation speed and how it differs from movement speed. Sprite animation speed is useful as a future behavior/profile tool, but it should be controlled deliberately rather than inherited from hop or landing state.

## Current model

- Movement speed and sprite animation speed are separate concerns.
- Profile movement values decide how often a Pokemon chooses or executes movement.
- Sprite animation speed is presentation state on the map object/OAM path.
- Custom hops use map-object movement/render state during travel, then must restore normal presentation state on landing.

## Custom Hop Landing Fix

The custom hop landing path previously wrote `0x00020028` for a two-frame
post-landing pulse. Those bits are stock movement transition/completion state,
not a supported sprite-animation API. If the frame task paused for a script or
the overlay unloaded before the timer expired, the pulse could outlive its
custom hop and make only the sprite animate at the faster hop cadence.

The custom landing pulse has been removed. Custom jumps now clear only the bits
that their direct-render carrier explicitly owns (`BIT_JUMP_START`,
`BIT_MOVE_START`, and `MAPOBJECTFLAG_UNK13`) after the carrier finishes. Stock
movement completion flags and partner-wrapper state are left to their stock
command lifecycle.

## Persistent Regression Hardening

The spot-emote `0x49` partner-prep command now has explicit, object-bound
ownership. Normal completion closes it with `0x4A`; timeout, reset, object
replacement, despawn, battle teardown, and overlay unload all use the same
finish-and-restore path. Binding ownership to the object pointer prevents a
late cleanup for one spawn generation from changing a replacement object in
the same slot.

Do not add a generic map-object "presentation mask" or a timer that clears
stock flags later. In particular, movement start/end events and the movement
completion latch must be produced and consumed by the command that owns them.
Durable cleanup means completing or cancelling the command transaction and
running its paired restore command, not guessing which raw flags look visual.

## Future Intentional Speed Control

If overworld Pokemon sprite animation speed becomes a profile option, use a scoped apply/restore path:

1. Store the original animation pacing/state for the map object.
2. Apply the requested animation speed while the behavior is active.
3. Restore the saved state when the behavior ends, the Pokemon lands, despawns, is picked up, or enters battle.

Avoid piggybacking on custom hop landing flags for permanent animation speed changes. Hop flags are stock movement lifecycle state, not an animation-speed control surface.

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
- Do not synthesize stock movement transition/completion bits as landing
  feedback. Let the owning movement command produce and consume them.

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
