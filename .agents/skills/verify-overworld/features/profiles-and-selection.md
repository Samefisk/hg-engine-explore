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
- **Mounted override.** Run `scripts/owctl scenario run profile.resolve.follower-mounted-parity --json`. The forced Mounted layer has no field overrides and inherits the normal selected Pokémon profile, including Sprint timing and Waddle sway. Follower remains a separate override.
- **Live mounted Waddle.** Run `scripts/owctl scenario run mount.bellsprout-waddle-sway --json` for one S4 Bellsprout Walk. It checks the player and Pokémon poses after each completed frame and proves the authored non-Sprint sway has a mounted effect; it does not prove nonzero Walk pause.
- **Current follower.** Run `scripts/owctl scenario run mount.begin-current-follower --json`. The live subject identity, encounter generation, unique object identity, resolved species, and control release all pass.
- **Proof.** Read each returned manifest. A source-only resolver pass does not replace the current-follower S3 run.

## Gotchas

- A configured party species does not prove that its field object exists.
- Re-selecting the previous follower must not count as a new spawn.
- Mounted is a System profile application and controller projection, not a
  separate profile type or resolver role.
