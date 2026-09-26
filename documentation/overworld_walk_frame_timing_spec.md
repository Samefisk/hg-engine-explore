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
- `walkTimeVariance` is an integer from 0 through 32. Zero disables it. A
  nonzero value adds a value from 0 through `walkTimeVariance` to each accepted
  normal Walk tile, including a braking turn. The result is capped at 32
  frames. Consecutive tiles select their values independently; the previous
  displayed time does not limit the next value. Below maximum speed,
  acceleration changes only nominal time. The first maximum-speed tile keeps
  full variance. Each subsequent committed normal Walk reduces the available
  range by `walkAccelerationStep`, down to zero, independently of
  `tilesToAccelerate`. For `/2`, each such commit halves the remaining range,
  rounding down. Disabled acceleration preserves the full range.
- The variance value is selected once when the tile starts. A rejected or
  blocked start does not consume a value, and an active tile does not reroll.
  Walk uses a pseudorandom value keyed by the actor identity and committed
  step number. Thus the same actor and step reproduce the same value; a
  blocked retry cannot reroll it. Skids and zero variance do not use the
  value. The Movement Chain random phase and the game's general random stream
  are not used for Walk time variance.
- Variance changes the normal tile's duration without adding an acceleration
  step or changing Movement Chain counts, chain repositioning, Hop, Teleport,
  stomp checks, or pause timing. A later turn or stop uses the last displayed
  Walk time to choose its braking time and skid distance. This keeps its speed
  continuous with the tile the player just saw.
- Wild, follower, and mounted Walk use the same rule. A mounted rider and its
  Pokemon use the same selected duration because they share one motion.
- A continuing mounted Walk keeps its selected frame count, but eases its
  render path from the preceding tile's displayed speed toward the new tile's
  speed. It still reaches the next tile center on its last frame. Fresh starts,
  changed headings, Skid, and other motions use their existing paths. The
  limited one-frame travel time still moves one full tile in one frame.

## Acceleration and momentum

- `tilesToAccelerate` remains the number of consecutive real Walk tiles in the
  same direction needed for one acceleration step.
- `walkAccelerationStep` selects the acceleration rule. Zero disables
  acceleration. Values 1 through 32 remove that many travel frames per step.
  Value 33 is shown as `/2` and keeps the old `ceil(current / 2)` rule. The
  profile default is 1 frame.
- Every result clamps at `maxWalkSpeed`, so it cannot become faster than the
  configured fastest time.
- Examples: step 0 stays at 20. `/2` gives 20 to 10 to 5 to 3 to 2 to 1.
  Step 3 gives 20 to 17 to 14 to 11 to 8 to 5 to 2 to 1.
- An accepted turn loses one acceleration step and resets the acceleration tile
  counter. A blocked turn does not change speed or the counter. With `/2`, a
  turn from 3 restores 5. With step 3, a turn from 8 restores 11. The result
  cannot be slower than the base travel time.
- Stopping resets the travel time to the base value.
- Stopping, an accepted turn, and a momentum reset restore full variance.
  A rejected start, duplicate commit, skid, or reposition does not advance
  variance fading. The existing acceleration counter stores completed
  maximum-speed Walks only while at the cap; it saturates at 255.
- A turn skid restores one acceleration step slower than the displayed Walk
  time that was active before the skid.
- Skid and reposition tiles do not count for acceleration or Movement Chain.

## Skid and feedback policy

- Travel times 7 through 32 have no speed-based skid.
- Travel times 5 through 6 skid for 1 tile.
- Travel times 2 through 4 skid for 2 tiles.
- Travel time 1 skids for 4 tiles.
- A skid tile uses twice the current travel time, capped at 32 frames.
- During a turn skid, the actor faces the requested new heading while it
  continues to travel along the committed old heading. The first recovery
  Walk travels along the new heading. Wild and mounted Walk use this same
  split between facing and travel; a stop skid keeps the old facing.
- Stomp at time is off at 0. Values 1 through 32 emit the existing skid dust
  particle and configured stomp sound when `currentTime <= threshold`.
- Override addition is direct time arithmetic: positive is slower and negative
  is faster. Bounds are presented as `no slower than` and `no faster than`.

## Flat Walk motion

- Walk uses the custom-motion scheduler and interpolation storage already used
  by Jump, but has its own flat `WALK` mode.
- Walk's ground trajectory has no height arc. Mounted Walk can add a small
  presentation-only gait; it does not add a Pokemon leg-animation system or
  change the ground trajectory, collision, speed variance, camera or shadow.
- Cardinal and diagonal Walk use the exact configured travel time.
- A completed Walk tile runs collision, player-step, streaming, and warp effects
  once at tile completion. Intermediate frames do not run a warp.
- Mounted movement has one player-authoritative motion. The Pokemon and rider
  presentation follow that same motion instance.
- A one-frame mounted Walk finishes its stationary held command at the actor's
  target sample. The normal player END and step checks run on the next field
  frame, so two held one-frame tiles do not add a stationary frame between them.

## Diagonal movement

- A profile that allows diagonal Walk enables it for wild and mounted Pokemon.
- A diagonal destination is valid only when the destination and both adjacent
  cardinal side tiles are clear.
- A blocked diagonal is a rejected candidate, not a cardinal fallback or a
  stop command. Report the side or destination reason and preserve momentum.
  A later cardinal input can move through the clear side.
- Locked Ram uses its committed direction before checking a new raw direction;
  blocked committed movement retains the existing crash rule.
- A diagonal object keeps its current cardinal facing when that facing is one
  component. Otherwise it faces the newest pressed component.
- A 45-degree direction adjustment does not skid, but it resets the acceleration
  counter. A turn of 90 degrees or more can skid.
- One completed diagonal tile counts as one Walk tile for Movement Chain,
  acceleration, stomp, and player step processing.
