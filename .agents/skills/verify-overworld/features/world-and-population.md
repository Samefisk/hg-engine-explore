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
- **Transition.** Run `scripts/owctl scenario run mount.transition-mid-motion --json`. The map and field epoch change while the one motion completes and releases control.
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
  scan. It must see real legacy Pool and explicit profile-mask work, at most one
  costly candidate query per completed update, at least 120 in-transit samples,
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
