# Overworld Walk frame timing specification

> **Status: active subordinate contract.** It is owned by the Motion Module in
> [`documentation/overworld-system/architecture.md`](overworld-system/architecture.md).
> If this contract changes, update the system feature map and wild/mounted
> parity scenarios in
> [`documentation/overworld-system/verification.md`](overworld-system/verification.md).

## Scope

This change replaces the four Walk speed tiers with an exact travel time. It
applies to wild Pokemon, followers, mounted Pokemon, behavior overrides, chase
movement, chain repositioning, and Walk feedback.

## Profile values

- A Walk travel time is an integer from 1 through 32 frames per tile.
- A lower value is faster. Zero is invalid.
- Existing tier values migrate as follows: 1 to 16, 2 to 8, 3 to 4, and 4 to 2.
- Chill, Active, and Tired Walk lanes each store a travel time.
- The existing `maxWalkSpeed` C member can retain its name for binary-interface
  stability, but its meaning is the fastest permitted Walk travel time. It must
  be less than or equal to the lane's base travel time.
- The mounted profile uses the resolved mounted override profile's main Walk
  lane. Active and Tired AI lanes do not control player input.

## Acceleration and momentum

- `tilesToAccelerate` remains the number of consecutive real Walk tiles in the
  same direction needed for one acceleration step.
- One acceleration step changes the current time to `ceil(current / 2)`, then
  clamps it so it cannot become faster than the configured fastest time.
- Examples: 20 to 10 to 5 to 3 to 2 to 1; 16 to 8 to 4 to 2.
- An ordinary turn preserves the current travel time and resets the acceleration
  tile counter.
- Stopping resets the travel time to the base value.
- A turn skid restores the travel time that was active before the skid.
- Skid and reposition tiles do not count for acceleration or Movement Chain.

## Skid and feedback policy

- Travel times 5 through 32 have no speed-based skid.
- Travel times 3 through 4 skid for 1 tile.
- Travel time 2 skids for 2 tiles.
- Travel time 1 skids for 4 tiles.
- A skid tile uses twice the current travel time, capped at 32 frames.
- Stomp at time is off at 0. Values 1 through 32 emit the existing skid dust
  particle and configured stomp sound when `currentTime <= threshold`.
- Override addition is direct time arithmetic: positive is slower and negative
  is faster. Bounds are presented as `no slower than` and `no faster than`.

## Flat Walk motion

- Walk uses the custom-motion scheduler and interpolation storage already used
  by Jump, but has its own flat `WALK` mode.
- Walk has no height arc and does not add a Pokemon leg-animation system.
- Cardinal and diagonal Walk use the exact configured travel time.
- A completed Walk tile runs collision, player-step, streaming, and warp effects
  once at tile completion. Intermediate frames do not run a warp.
- Mounted movement has one player-authoritative motion. The Pokemon and rider
  presentation follow that same motion instance.

## Diagonal movement

- A profile that allows diagonal Walk enables it for wild and mounted Pokemon.
- A diagonal destination is valid only when the destination and both adjacent
  cardinal side tiles are clear.
- If a mounted diagonal is blocked, try a cardinal component. Prefer the
  current-facing component, then the newest pressed component. Stop only when
  both components are blocked.
- A diagonal object keeps its current cardinal facing when that facing is one
  component. Otherwise it faces the newest pressed component.
- A 45-degree direction adjustment does not skid, but it resets the acceleration
  counter. A turn of 90 degrees or more can skid.
- One completed diagonal tile counts as one Walk tile for Movement Chain,
  acceleration, stomp, and player step processing.
