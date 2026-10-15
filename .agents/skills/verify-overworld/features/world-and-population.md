# Terrain, streaming, transitions, and population

World tests prove traversal against current terrain, complete streaming along
fast paths, safe area transitions, warp gating, and valid wild population.

## Sub-features

- `terrain-selection` separates Land, Surf, and catalogued physical surfaces.
- `streaming-path` loads every crossed cardinal and diagonal axis.
- `world-transition` completes or cancels one owned motion cleanly.
- `warp-gating` blocks a warp during mounted motion.
- `population` refills valid actors after fast travel without a burst.
- `distance-despawn` retains far samples during normal motion, waits for the
  terminal idle boundary, blocks a same-frame AI restart, and keeps both
  off-screen spawn entry modes protected.

## How to get to it (user POV)

- Walk or ride between land and water encounter areas.
- Move quickly toward a map-streaming edge.
- Cross an area boundary during mounted motion.
- Cross a warp tile during and after a custom motion.

## Driving it with owctl

Preconditions:

- Use the scenario's declared map and save fixture.
- S5 scenarios observe at least 5000 emulator frames.

- **Land and Surf.** Run `scripts/owctl scenario run population.land-surf-separation --json`. Surf attempts occur and Tentacool land spawns stay at zero.
- **Streaming.** Run `scripts/owctl scenario run mount.streaming.cardinal-and-diagonal --json`. Both stream axes load and native stream pointers restore.
- **Mounted Stantler terrain-loss route.** Run `scripts/owctl scenario run world.streaming.stantler-mounted-route --json`. One prepared level-10 Stantler follows RIGHT, RIGHT, UP, LEFT, LEFT, UP, DOWN for 120 completed frames each from map 33 (585,402). The native radius-one terrain grid at the route endpoint must be 9/9 loaded. After RIGHT120, the player must advance at least eight tiles east and the radius-two grid must be 25/25 loaded. This checks the old frozen endpoint and recovery, not every intermediate terrain frame.
- **Transition.** Run `scripts/owctl scenario run mount.walk-transition-mid-motion --json`. The map and field epoch change while the one motion completes and releases control.
- **Warp gate.** Run `scripts/owctl scenario run warp.blocked-mid-motion --json`. The warp stays blocked during custom motion and works after normal movement.
- **Population refill.** Run `scripts/owctl scenario run population.after-fast-travel --json`. Refill occurs and new actors per frame stay within the cap.
- **Distance despawn.** Run
  `python3 -m unittest tools.overworld.test_distance_despawn -v`. It proves
  that two moving far samples become pending, terminal cleanup blocks an
  immediate AI restart, returning within16 tiles cancels cleanup, and Move and
  Hop From Off Screen do not collect pending samples. Then run
  `scripts/owctl scenario run spawn.ledyba-pool-site --json` on the current ROM
  to keep the full off-screen Hop arrival and control-return contract green.
- **Spawn-work budget.** First run
  `python3 tools/overworld/test_spawn_refill_budget.py` and
  `python3 tools/overworld/test_spawn_destination_scan.py`. Then run
  `scripts/owctl scenario run population.spawn-work-budget --json` on the
  current ROM. Its fixed Route 30 path must keep the player moving during the
  scan. It must see real legacy Pool and explicit profile-mask work, at most16
  legacy candidate queries or8 explicit physical reads per completed update,
  at least 120 in-transit samples,
  zero repeated exact player positions during those samples, and zero late main
  loops through four post-spawn loops. One three-VBlank loop or one frozen
  in-transit position is a failure. The host checker's batched-query control
  must fail as intended.
- **Long-route engine stutter.** Check `scripts/owctl scenario list` and the
  current ledger for `world.unmounted.long-travel-cadence` readiness. Its route
  fixture, collector and independent cadence bounds must work before a pass
  can close the report. It uses the unmounted player with a live FOLLOWER Cyndaquil,
  distinct streaming cells, and an area boundary. Existing short cadence and
  failed-scan cases do not replace it.
- **Ordinary refill interval (TKT-0029).** The same unchanged-Continue
  `world.unmounted.spawn-zero-stutter` run must contain at least one
  actual ordinary constructor bound to its native COMMIT SUCCESS, followed
  by its first distinct ordinary attempt in the same current Field. The gap
  must include the decoded density delay and be at least60 Actor frames.
  The named `zero-stutter-minimum-post-success-refill-frames` proof row owns
  this claim. READY alone is not creation. Resumed finalizers and later failed
  terrain groups are not new batches. This uses native return receipts, not
  timer words.
- **Failed-series retry.** Run `scripts/owctl scenario run population.failed-series-retry --json`. It observes240 neutral Cherrygrove frames, one declared warp to Route29, then360 neutral frames. Require a native15-frame failed-series delay followed by a new natural attempt before60 Actor frames, and an actual constructor/COMMIT SUCCESS followed by the full decoded density wait. The existing actual-C refill check retains the four-failure backoff and RNG-order contract.
- **Natural water birth.** Run `scripts/owctl scenario run population.natural-water-spawn --json`. It observes600 neutral Route30 frames at(565,369), with no species, profile, party or population setup. Require a natural Surf constructor and the same full Wild handle settled at its own loaded water target with native height, no authored surface and no residual jump offset. This does not prove Fishing or replace the land-only Surf rejection scenario or either pacing gate.
- **Route30 concurrent Sentret and Throw (TKT-0067).** Run `scripts/owctl scenario run world.route30.sentret-throw-pacing --json`. This one prepared case waits16 neutral setup frames after the Route30 warp, then requires three actual current native Sentret before arming and the unchanged saved party2 Mankey. It repeats LEFT120/DOWN120/neutral16, one actual Bell spawn, and neutral348. The same600 native returns must include natural Cargo/HELD/outward Throw with all three original Sentret current, no late loop, no normal-input render stall and no raw/native/semantic loss. A refused third spawn, READY without creation, no Throw, or lost data is red. The existing raw TestJobs stream covers the asynchronous Bell wait without fabricated Actor samples. This does not replace D1 or the separate full Throw lifecycle test.
- **Saturated Route30 loop headroom (TKT-0076).** Run `scripts/owctl scenario run population.route30.saturated-headroom --json`. This one prepared case teleports to map34 (557,361) facing0, waits16 neutral setup frames, requests six native level5 Wild spawns (species16,16,60,60,163,167 (Rattata19 and Sentret161 are rejected by native finalize on test3591); a busy native spawn queue, a queued Entry lost to natural spawn work, or a startup rejection (skipped after four tries), is retained as a refusal plus8 neutral frames and asked again, at most40 times each), waits16 more neutral frames, binds the unchanged saved party2 Mankey, and arms the existing main-loop reader for768 returns. It leaves natural refill, the population cap, profiles and timers untouched. The measured walk is exactly twenty-four pairs of UP16 then DOWN16 and neutral16 with no run key; the Player must stay within about five tiles of the pond bank, since longer steps let the Wild actors despawn by distance on test3591. Pidgey16 replaces Rattata because Rattata and Sentret are grass-only species that cannot be prepared on the grass-less bank. Every credited loop must carry `waitArm9Ticks` (mandatory-wait return clock minus entry clock). Require zero late loops, at most2 native cycles/frame-sequence and2800950 ARM9 ticks per loop, zero render stalls, idle minimum at least30000, 1st percentile at least175000, 5th percentile at least275000, at least six active actors (saved Mankey plus five Wild) in at least ninety percent of loops (the all-seven share is informational), a Player step, and the Player settled on map34. The floors sit between the old-ROM pond-bank run (14k/150k/231k) and the accepted-mode fixed-ROM test3588 run (43k/204k/318k). Natural creation is informational. Setup tiles are an uncalibrated first choice; a refused spawn, `population-full`, or an unloaded tile is a setup failure, not a pass. Copied controls (late loop, low-idle loop, thin low tail, missing wait ticks, six actors, short window, wrong map, wrong saved Mankey) must each fail for their own reason. This does not replace `world.unmounted.spawn-zero-stutter`.
- **Proof.** Confirm actual observed frames and all iteration results in each S5 manifest.
- **Exact landing tile.** Read `scripts/owctl dev terrain --x <x> --z <z> --radius 0 --json` at the same actor's own native destination. Inspect loaded-block provenance, behavior and collision. This paused endpoint is a diagnostic, not completed-landing or tree/roof height proof. Add the missing native surface/height and terminal observations through shared devtools; never judge terrain from screenshots.
- **Canopy catalog.** Run `python3 tools/overworld/test_canopy_surface_catalog.py`, then use the current-ROM Canopy scenario when it is registered. A Canopy hit must report type4, surface ID `0xFFFE`, its own actor/profile identity, and a resolved support height exactly `0x41580` FX32 above the checked native ground. A behavior-6 tile or an unresolved catalog hit alone is not proof of a valid perch.

## Gotchas

- Encounter terrain and traversal permission are different contracts.
- Model `0xD0` is a headbutt interaction model. Do not treat its full land block as Canopy.
- Final map coordinates do not prove that each stream boundary loaded.
- Declaring a large frame budget does not prove that the emulator ran it.
- A population count alone does not prove that each actor spawned on valid terrain.
- The incremental legacy helper retains all 289 cursor positions and 240
  eligible tiles. That helper-only result does not cover the profile
  destination-mask scanner.
- Spawn-work proof becomes stale after spawn, population, behavior-profile,
  destination-mask, or generated-profile changes. Reopen D1 and rerun the cheap
  host checks before the short current-ROM gate. Host timing is diagnostic only.

- **Prepared Move entry arrival.** Run `scripts/owctl scenario run spawn.move-entry.arrival --json`. Rattata19 level4 receives a normal request(560,375) on Route30. Native PREPARE owns its actual offscreen origin and target; same-serial ADOPT binds the created full handle/PID. Retain each Pending/READY callback and dense acquire/travel samples, exact saved GUIDEs and shared START/END, then native target/height with zero offsets and cleared trip. The public spawn command retains native queue receipts but no dense queue poses. This finite prepared case does not prove quiet120-frame offscreen retirement, other lanes, or natural population choice.
