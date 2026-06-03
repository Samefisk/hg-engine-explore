# Overworld Wild Movement Investigation

## Current Milestone

Movement type `47` is now patched from a null vanilla descriptor to a boot-resident descriptor in overlay 129. Overworld wild spawns use movement `47` instead of stock wander `3`.

The custom descriptor currently supports behavior selection through map object param `1`:

- `1`: chase the player
- `2`: flee from the player

The spawner currently passes chase behavior for all visible wild Pokemon. Param `0` is used as a small movement decision cooldown, and param `2` remains the shiny palette/render metadata used by the shiny overworld palette hook.

## Engine Path Used

The custom callback follows the same movement-command shape as stock movement:

- choose a direction
- reject blocked directions with `MapObject_IsMovementDirectionBlocked`
- convert direction to a normal walk command with `MapObject_MovementCommandFromDirection`
- start the command with `MapObject_StartMovementCommand`
- set the single-movement bit
- poll `MapObject_UpdateMovementCommand`
- clear the single-movement bit when the command finishes

This deliberately avoids direct coordinate writes. The engine still owns animation, collision, and movement completion.

## Verification So Far

The ROM build passed with `./docker-makerom.cmd`.

Binary sanity checks on the built ROM:

- ARM9 movement table slot `47` points at `gOverworldWildCustomMovementDescriptor`
- descriptor word `0` is `47`
- all callback pointers have the Thumb bit set

## First Runtime Tests

Use the current Delta build and check these in order:

1. Load into a normal spawn-compatible map, such as Route 29.
2. Confirm visible wild Pokemon spawn without freezing.
3. Confirm spawned Pokemon move toward the player one step at a time.
4. Stand adjacent to a spawned Pokemon and confirm it does not repeatedly try to step into the player tile.
5. Touch/battle a spawned Pokemon and confirm battle transition still works.
6. Watch a Pokemon near rocks, ledges, trees, water edges, and NPCs; blocked primary directions should either use the alternate axis or wait.
7. Check surf, fishing, and headbutt spawns separately, because the current behavior is global.

## Known Limits

This is not pathfinding yet. A chasing Pokemon can only choose the best direct axis, then the alternate axis. If both are blocked, it waits for the next decision.

There is no terrain-specific behavior yet. Land, surf, fishing, and headbutt spawns all use chase for this first active test.

There is no species/personality behavior yet. The dispatcher can support it later, but the current spawner only passes a simple behavior ID.

## Next Increment Ideas

- Set behavior by terrain pool, such as fish staying still or surf Pokemon chasing only in water.
- Set behavior by species personality group, such as aggressive chase, skittish flee, idle wander, or patrol.
- Add chase radius and disengage radius to avoid every spawn homing from far away.
- Add flee behavior to a small controlled test group before making it dynamic.
- Add a terrain compatibility check before choosing a step, if collision alone is not enough for surf/land separation.
