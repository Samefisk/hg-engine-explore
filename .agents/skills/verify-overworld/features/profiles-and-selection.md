# Profiles and follower selection

Profile and selection tests prove the resolved behavior data and that the
selected live follower is the actor used by mounted control.

## Sub-features

- `profile-order` proves ordered override composition.
- `condition-evaluation` proves the packaged condition service keeps the fixed
  conditional-profile activation and target rules.
- `profile-mounted-parity` proves the Mounted layer keeps the selected
  Pokémon's resolved fields while it has its own System-profile identity.
- `mount-current-follower` proves Select mounts the current highlighted follower.

## How to get to it (user POV)

- Open the follower selector with Y and choose a Pokemon.
- Press Select on the highlighted Pokemon to mount it.
- Edit a profile through the Overworld Workshop.

## Driving it with owctl

Preconditions:

- `scripts/owctl doctor` passes.
- The named behavior catalog and generated compatibility data agree.

- **Override order.** Run `scripts/owctl scenario run profile.resolve.override-order --json`. The portable resolver reports each layer once in source order.
- **Packaged resolver.** Run `scripts/owctl scenario run profile.resolve.packaged-rom-parity --json`.
  This short prepared service test compares all nine native cases with fresh
  Workshop results, including full bytes and ordered provenance. It has no
  actor subject. Its clock unit is native cycles containing resolver work,
  not completed game frames or movement soak. It does not prove live role callers.
- **Packaged conditions.** Run `scripts/owctl scenario run profile.condition.packaged-rom-evaluator --json`.
  This subjectless service test authenticates the ROM service and source blob,
  then evaluates seven fixed cases over one guarded owned copy. It proves
  overlap last-wins, application stacking, timed hold/cooldown/retrigger,
  player and actor targets, stale/fresh handles, and copied-input Wild/Follower
  parity. It does not prove either live role controller called the service.
- **Ambush player landing.** Run `scripts/owctl scenario run
  profile.ambush.player-tile-landing --json` on the current ROM. It prepares a
  Wild Weepinbell at Route 29 (583,406) and keeps the player at (585,408).
  The active Ambush condition must select PLAYER and current `apply-ambush`. The same
  actor must start a Hop to the exact player tile, render its complete path,
  commit once, finish, and return control. Continue neutral input until the
  same full actor clears equal-support overlap with a complete native shared
  one-tile exit and starts its next profile motion. Only after contact can
  normal Player knockback move the Player; it gives no actor-exit credit.
  The preserved old-ROM recording
  stops at (585,407), so this test must reject it. This case does not prove a
  battle starts or that every Ambush species works.
- **Mounted override.** Run `scripts/owctl scenario run profile.resolve.follower-mounted-parity --json`. The forced Mounted layer has no field overrides and inherits the normal selected Pokémon profile, including Sprint timing and Waddle sway. Follower remains a separate override.
- **Ram side and behind entry (TKT-0031).** Run
  `scripts/owctl scenario run profile.ram.until-crash --json` for side entry
  and the original full lifetime proof. Onix602402 must be centered and
  inactive with native Down1 facing; player607402 is beside it. Its exact first
  East Walk602402→603402 starts within one frame of activation. Normal Down16
  dodge keeps every prior speed, heading, complete movement, more-than96-frame
  charge, real Crash and100-frame cooldown check.
  Run `scripts/owctl scenario run profile.ram.behind-entry --json` for the
  second entry direction. Onix594404 faces Down1; player594399 is behind it.
  Require the same inactive native owner, exact North Walk594404→594403,
  normal Right16 dodge, complete committed movement, locked speed/heading,
  real Crash and100-frame cooldown. The known North lane stops at colliding
  y389, so the long side case alone owns the96-frame lifetime requirement.
  Native spawn commands get no idle entry credit. No facing, profile or timer
  writes are allowed. Source range/occlusion/rearm controls stay separate;
  source and copied data do not replace these current-ROM game runs.
- **Retired Notice Player cases (TKT-0040).** The Notice Player profile and
  application are removed. Do not run `profile.notice-player.routine-return`
  or `profile.notice.blocked-hop`. Keep the actual-C blocked Hop no-turn check
  and the other profiles' own notice/alert tests.

- **Follower Ram.** Run `scripts/owctl scenario run follower.ram-pokemon --json`.
  A current Onix follower captures the nearest visible Wild Snorlax through
  Ram condition49626. Normal line entry must start its first Walk toward that
  target, keep the charge heading, cause one real33-HP collision hit, and
  complete the same shared forced Jump3 with control returned. Player and
  party HP must remain unchanged. Locked Walk ignores ordinary previous-tile
  avoidance. Prepared positions do not prove natural population placement.

- **Live mounted Waddle.** Run `scripts/owctl scenario run mount.bellsprout-waddle-sway --json` for one S4 Bellsprout Walk. It checks the player and Pokémon poses after each completed frame and proves the authored non-Sprint sway has a mounted effect; it does not prove nonzero Walk pause.
- **Current follower.** Run `scripts/owctl scenario run mount.begin-current-follower --json`. The live subject identity, encounter generation, unique object identity, resolved species, and control release all pass.
- **Follower stop facing (TKT-0008).** Run `scripts/owctl scenario run walk.follower.stop-facing --json`.
  Prepare a level 10 Stantler follower at Route 29 (584,403), settle for 24
  frames, walk Right for 32 frames, then release input for 96 frames. The same
  full identity must finish a real Walk, commit its own target, and return
  control. It must keep its final Walk facing for at least 32 continuous idle
  frames. A native empty stop reply must carry no step or facing direction.
  Stock explicit FACE commands remain allowed. The preserved ROM3482 recording
  `recording-5e46d6345417` (SHA-256 `60662dbcfd955a36b0d3d93ceed17b9083ddb6f72ba3a706755f63ce69e7a270`)
  changes South to North at frame 903 without a move or commit; this same
  observer rejects its empty direction reply. The fixture does not prove
  natural follower creation or party selection.
- **Switch then mount.** Run `scripts/owctl scenario run mount.select-during-follower-switch --json`. From the saved Stantler follower, mount and dismount Stantler with two fresh Select presses. Y/R/Y then chooses party slot 2 Mankey. One Select during the queued switch must mount the new Mankey without a retry.
- **Proof.** Read each returned manifest. A source-only resolver pass does not replace the current-follower S3 run.

## Gotchas

- A configured party species does not prove that its field object exists.
- Re-selecting the previous follower must not count as a new spawn.
- Mounted is a System profile application and controller projection, not a
  separate profile type or resolver role.
