# Pokémon palette tint

Use the two exact current-ROM cases. Native palette upload bytes and the actual
material command supply proof. A tint record, configured option or screenshot
alone cannot pass. Both tests use private ROM/save copies and no capture.

- Run `scripts/owctl scenario run pokemon-appearance.damage-palette --json`.
  Ordinary Ambush must hit mounted Cyndaquil twice and Wild Snorlax once.
  Real HP and the current Actor clock set the softer red strength. At unchanged
  HP, the same private palette must get both a rising and a falling pulse.
  Pulse changes cannot count as a second hit. Half of the pulse is fully off:
  the same Pokémon's MAT word5 must retain its normal palette address then.
  The real stock Field VBlank callback must upload tint bytes through the SDK
  before a later MAT uses them. Pending transfers cannot count as proof. Normal nurse input
  heals the same party member. The new Follower identity must have full HP,
  no tint record/callback, and the original palette. This proves clear after
  a genuine field rebind; it does not claim item healing in place.
- Run `scripts/owctl scenario run pokemon-appearance.cooldown-palette --json`.
  Bind a healthy Onix, observe its first natural Ram, dodge, and retain the
  real Crash. Its entire remaining prepared set must contain the current Ram
  condition in its own100-frame cooldown. Complete the exact blue SDK upload
  and MAT use, then observe natural expiry clearing the record/callback.
- Run `scripts/owctl scenario run pokemon-appearance.ambush-cooldown-palette --json`.
  Bind a healthy Weepinbell at the existing adjacent native fixture. Observe
  its90-frame Ambush and its own126-frame cooldown from activation, with
  completed blue upload/MAT use and natural deadline clear.
  Notice Player and its long overlap window were removed in TKT-0040. Both
  independent blue-tint requirements remain. Never omit a remaining condition
  or write timers, HP, masks or RNG to make blue appear.
