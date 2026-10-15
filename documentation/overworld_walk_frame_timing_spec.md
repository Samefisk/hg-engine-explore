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
  displayed time does not limit the next value. In legacy Frame reduction and
  `/2` modes, acceleration below maximum speed changes only nominal time. The
  first maximum-speed tile keeps full variance. Each subsequent committed normal Walk reduces the available
  range by `walkAccelerationStep`, down to zero, independently of
  `tilesToAccelerate`. For `/2`, each such commit halves the remaining range,
  rounding down. Linear speed fades variance during the same moving-time ramp
  as speed. Disabled acceleration preserves the full range.
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

- In Frame reduction mode, `tilesToAccelerate` remains the number of consecutive real Walk tiles in the
  same direction needed for one acceleration step.
- `walkAccelerationStep` selects the acceleration rule. Zero disables
  acceleration. Values 1 through 32 remove that many travel frames per step.
  Value 33 is shown as `/2` and keeps the old `ceil(current / 2)` rule. The
  profile default is 1 frame.
- Value 34 adds the opt-in **Linear speed** mode. Existing profiles retain
  their saved mode. Movement Style shows **Acceleration mode**, the existing
  starting and fastest Walk times, and **Time to full speed** (1..255 moving
  frames). In this mode the packed `tilesToAccelerate` byte holds that duration;
  it is not a tile count. Legacy counts still normalize to 1..32.
  Build validation accepts the packed interval and its bounds through 255,
  including overrides that inherit Linear mode from another profile. It
  accepts mode 34 only as an exact replacement; legacy operators keep their
  existing limits.
  Only an exact replacement of `walkAccelerationStep` with 34 selects Linear
  speed. Legacy arithmetic and bounds remain capped at 33. Arithmetic and
  bounds on an inherited Linear mode do nothing; replacing it with 0..33
  selects the disabled or legacy rule again.
- Linear speed interpolates speed, not travel time: at elapsed moving time
  `e` within duration `T`, speed is `1/base + (1/fastest - 1/base) * e/T`.
  The shared policy samples that speed at each tile boundary. Accepted Motion
  retains its fixed integer duration; this does not accelerate inside a tile.
  Q8 reciprocal times keep a fractional carry across accepted tiles, so early
  rounding does not force all intermediate speeds into the same duration.
- Only completed normal Walk durations advance Linear elapsed time. Waiting,
  blocked starts, duplicate commits, skids, repositioning, and post-skid
  recovery do not advance it. An accepted turn rewinds elapsed time by the
  preceding displayed normal Walk duration and clears fractional carry. A
  blocked turn changes neither. Stops and a change of mode/base/lane reset it.
- Linear speed and variance use the same elapsed moving time. At a continuing
  normal Walk admission, the variance width is
  `V - floor(min(e, T) * V / T)`, where `V` is the authored variance. The
  first tile admitted after elapsed time reaches `T` uses the fastest nominal
  time and zero variance. Sprint uses `T = 60`: there is no second fade ramp
  after those 60 moving frames. An active tile keeps its accepted duration;
  both values are sampled at the next tile boundary. A fresh run or accepted
  braking turn restores full variance under the existing reset rule.
- The actor policy appends four bytes for Linear elapsed time, fractional
  carry, mode identity, and a reserved zero byte. Policy size is 36 bytes; actor stride is
  176 bytes. Existing policy offsets and the 28-byte public Walk call stay fixed.
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
  variance fading. In legacy modes, the existing acceleration counter stores completed
  maximum-speed Walks only while at the cap; it saturates at 255.
- A turn skid restores one acceleration step slower than the displayed Walk
  time that was active before the skid.
- Skid and reposition tiles do not count for acceleration or Movement Chain.

## Skid and feedback policy

- `turnSkidOneTime`, `turnSkidTwoTime`, and `stopSkidTime` are independent
  profile thresholds in displayed frames per tile. Each accepts 0 (Off) or
  1..127; a lower time is faster. Defaults are 6, 4, and 6.
- A turn uses two tiles when the two-turn threshold admits its time; otherwise
  it uses one tile when the one-turn threshold admits it. Both Off means no
  turn skid. The existing straight-step gate and 45-degree exemption remain.
- A stop skids only when its own threshold admits the time. Its distance is
  two tiles at time 4 or faster and one tile at a slower admitted time.
- At time 1, an admitted two-turn or stop skid keeps the legacy four tiles.
  A one-turn-only selection stays one tile. There is no fourth threshold.
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
