# Profiles and follower selection

Profile and selection tests prove the resolved behavior data and that the
selected live follower is the actor used by mounted control.

## Sub-features

- `profile-order` proves ordered override composition.
- `profile-mounted-parity` proves the mounted Owner lane uses follower resolution.
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
  This short prepared service test compares all seven native cases with fresh
  Workshop results, including full bytes and ordered provenance. It has no
  actor subject. Its clock unit is native cycles containing resolver work,
  not completed game frames or movement soak. It does not prove live role callers.
- **Mounted parity.** Run `scripts/owctl scenario run profile.resolve.follower-mounted-parity --json`. The resolved Owner lane and forced follower layer match.
- **Current follower.** Run `scripts/owctl scenario run mount.begin-current-follower --json`. The live subject identity, encounter generation, unique object identity, resolved species, and control release all pass.
- **Proof.** Read each returned manifest. A source-only resolver pass does not replace the current-follower S3 run.

## Gotchas

- A configured party species does not prove that its field object exists.
- Re-selecting the previous follower must not count as a new spawn.
- Mounted is a controller projection, not a separate profile type.
