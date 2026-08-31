# Playful Aipom Behavior

> **Status: historical attempt collection.** Use it as evidence, not current
> design. Start at [`overworld-system/README.md`](overworld-system/README.md).

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Playful behavior evolved from approach/orbit into a scoring model around player and follower targets.
- Previous-tile and direction-history rules prevent obvious backtracking, but should not override target priority.
- Hop expression should be randomized and should not reset just because orbit is briefly lost.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 54 | 54 | Hop Cry, Tired Cooldown, And Chill Wander |
| 145 | 67 | Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram |
| 181 | 103 | Behavior-Gated Ledge Far Jump |
| 184 | 106 | Aipom-Only Playful Chase Pass |
| 185 | 107 | Playful Previous-Tile Hard Guard |
| 186 | 108 | Direction-History Playful Backtrack Guard |
| 187 | 109 | Triple Playful Stamina |
| 188 | 110 | Playful Attentive Speed Rhythm |
| 189 | 111 | Revert Playful Attentive Speed Rhythm |
| 190 | 112 | Playful Targets Player And Follower |
| 191 | 113 | Close All-Direction Alert Radius |
| 192 | 114 | Unified Playful Movement Scoring |
| 193 | 115 | Soft Playful Backtrack Penalty |
| 194 | 116 | Playful Target-Progress Scoring |
| 195 | 117 | Coherent Playful Target Selection |
| 196 | 118 | Explicit Playful Approach Priority |
| 197 | 119 | Eight-Way Orbit Neighbor Filter |
| 198 | 120 | Playful Orbit Hop Every Five Neighbor Steps |
| 199 | 121 | Penalize Playful Orbit Moves Away Instead of Rejecting |
| 200 | 122 | Randomized Playful Orbit Hop Expression |
| 201 | 123 | Pause Playful Hop Timer Outside Orbit |
| 202 | 124 | Score Playful Ledge Jumps By Landing Tile |
| 203 | 125 | Include Moving Target Trail For Playful Scoring |
| 204 | 126 | Shared Moving Player Target For Movement Intent |
| 205 | 127 | Double Playful Movement Range |
| 206 | 128 | Phantom Stalker Hidden Movement |
| 231 | 153 | Mankey Canopy Hopper Headbutt-Tree Profile |
| 238 | 160 | Seven-Tile Canopy Hop Target And No Bounce-Back |
| 239 | 161 | Canopy Hopper Far-Preferred Tree Selection |

## Original Attempt Sections

### Attempt 54: Hop Cry, Tired Cooldown, And Chill Wander

Idea:

Layer richer behavior on top of the now-confirmed spot-hop and chase/flee system without adding a new movement-command family. When a spot-emote jump command completes, play that spawn's actual cry via the same `PlayCry(species, form)` API already proven by ambient overworld cries. Count completed chase/flee walk commands while a spawn is in the active spotted state; after a few completed active steps, play a distinct tired sound, reset the spawn to chill, and start a per-slot spot cooldown so it cannot immediately spot or re-engage the player again. While chill, choose random directions and start the same proven spawner-owned walk commands so chill Pokemon wander instead of standing still.

Why this is new:

- Attempts 52 and 53 made the spot-hop visual work, but only played the generic hop sound from the jump step.
- Ambient cries already use `PlayCry`, but no previous attempt has tied a species/form cry to completion of a spot-hop jump command.
- Previous chase/flee attempts kept active Pokemon pursuing indefinitely until blocked, battled, or effectively leashed by map/object movement constraints.
- No previous attempt has counted completed active chase/flee steps and transitioned back to chill with a temporary no-spot cooldown.
- No previous attempt has suppressed the proximity battle retry during that tired no-spot cooldown.
- Earlier "stock wander masks behavior" attempts used stock movement ownership; this chill wander keeps ownership in the same spawner-driven command path that is currently stable.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test151.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the spot-emote path calls `PlayCry(state->spawns[slot].species, state->spawns[slot].form)` when the jump command finishes and the emote step advances to `FREEZE`.
- Verified completed spawner-owned movement commands call `OverworldWildSpawns_HandleFinishedMovementCommand`.
- Verified only the active spotted state increments `movementActiveSteps`; chill wander movement does not count toward tiredness.
- Verified active chase/flee transitions to tired after `OW_WILD_SPAWNER_TIRED_AFTER_STEPS` / `5` completed movement commands.
- Verified tired behavior plays `OW_WILD_SPAWNER_TIRED_EMOTE_SE`, returns the slot to chill, starts `movementSpotCooldowns[slot]`, and pauses wandering briefly.
- Verified proximity battle retry is suppressed while a chill slot still has a tired no-spot cooldown.
- Verified chill wandering uses random directions through the existing spawner-owned walk command path and skips occupied target tiles.

Runtime result:

- User reported that the playful behavior did not feel like it naturally fell back into approach behavior.
- The user also suggested that playful likely does not need two distinct chase branches.

Learning:

- The hard branch between "not adjacent, chase target tile" and "adjacent, seek adjacent/orbit tile" can make the behavior feel sticky instead of naturally unified.
- Next attempt should remove the explicit approach-vs-close split and use one scoring rule for all playful movement decisions.

### Attempt 67: Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram

Idea:

Revise the behavior profile table again:

- Rename `restRate` back to `restTime`.
- Add `normalSpeed` so chill wandering can use one speed while attentive behavior uses `maxSpeed`.
- Make stamina tile-based: one completed attentive movement command spends one stamina, regardless of speed.
- Update default/aggressive/skittish values to the new table.
- Add `Playful` behavior for Aipom: normal wandering at speed 2, excited double-hop alert, playful chase, near-player circling, and occasional happy double-hop emotes.
- Add Onix as aggressive with an Onix-specific ram attentive state: alertness 14 in a facing cone, lock the initial direction toward the player, keep moving straight until blocked, ramp speed every 3 completed tiles up to speed 3, then crash back to chill.
- Force land test spawns to alternate Onix and Aipom by slot while leaving saved shiny respawns untouched.

Why this is new:

- Attempt 66 implemented the first table semantics but still had `restRate`, no `normalSpeed`, and stamina spending based on speed.
- No previous attempt has separated chill movement speed from attentive max speed.
- No previous attempt has made stamina count completed tiles.
- No previous attempt has added a playful near-player circling behavior.
- No previous attempt has implemented a locked-direction ram behavior with crash handling.
- No previous attempt has forced Onix/Aipom spawns for behavior testing.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built once as `test164.nds`, then removed an unused alert-bubble helper and rebuilt.
- Final build copied as `test165.nds`.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test165.nds`.
- `git diff --check` passed before the final build and after the final build.
- Verified local `test.nds` exists at 176 MB.
- Verified the Delta folder contains `test165.nds`.
- Verified no stale `restRate` or `REST_RATE` references remain.
- Verified land test spawns are forced to Onix on even slots and Aipom on odd slots, while saved shiny respawns are not overridden.
- Verified the overlay compiles with the new profile shape, Aipom playful behavior, and Onix ram behavior.
- Onix ram currently approximates ground smoke/crash feedback with `BIT_JUMP_START` plus sound effects. A direct C-side camera-shake API was not identified in this pass.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 103: Behavior-Gated Ledge Far Jump

Idea:

Let spawned overworld Pokemon jump over one-tile ledges when their behavior profile allows it. Add a profile variable, `jumpLevel`, so default behavior can allow jumps while specific behavior classes or variable overrides can disable or restrict jumping later.

Implementation shape:

- Add `jumpLevel` to `OverworldWildBehaviorProfile`.
- Add `OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL` to the normal behavior override hierarchy.
- Default `jumpLevel` to `2`, meaning all current Pokemon profiles can jump both downhill and uphill.
- Define:
  - `0`: no ledge jump ability.
  - `1`: downhill ledges only.
  - `2`: downhill and uphill ledges.
- Detect HGSS one-tile ledge metatile behaviors `56..59`.
- Before issuing normal movement, check whether the adjacent tile is a ledge.
- If it is a ledge, check the tile after the ledge; if that landing tile is blocked, occupied, or out of bounds, treat the movement as blocked.
- If the ledge direction is allowed by `jumpLevel` and the landing tile is valid, issue the far-jump movement command family from base command `0x38`.
- Route normal wandering/chasing/fleeing/playful movement, untangle movement, and aggressive ram movement through the same ledge decision.
- For aggressive ram, a failed/disabled ledge jump is treated like a crash.

Why this is new:

- The movement log had no previous ledge-jump attempt.
- Previous jump work was alert/emote hopping in place, using the in-place jump command family.
- This approach uses the far-jump command family and a map collision/landing validation pass before movement starts.
- It avoids changing the fragile custom movement descriptor path; the spawner still owns movement decisions.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `jumpLevel`
- `OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL`
- `OW_WILD_BEHAVIOR_JUMP_LEVEL_NONE`
- `OW_WILD_BEHAVIOR_JUMP_LEVEL_DOWNHILL`
- `OW_WILD_BEHAVIOR_JUMP_LEVEL_BOTH`
- `OW_WILD_SPAWNER_MOVEMENT_LEDGE_JUMP_COMMAND`
- `OverworldWildSpawns_TryStartLedgeJumpCommand`
- `OverworldWildSpawns_IsValidLedgeLandingTile`
- `OverworldWildSpawns_StartMovementCommandForSlot`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test201.nds`.
- Verified `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` compiled with only the existing unused-diagnostic warnings.
- Verified `jumpLevel` defaults to `OW_WILD_BEHAVIOR_JUMP_LEVEL_BOTH`, so all current behavior profiles inherit bidirectional ledge jumping unless an override sets `OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL`.
- Verified ledge detection uses HGSS one-tile ledge behaviors `56..59`, and successful jumps issue the far-jump movement command family from base command `0x38`.
- Verified failed or disabled ledge jumps are treated as blocked movement, including the aggressive-ram path.
- Verified untangle movement no longer filters blocked directions before the ledge helper, so ledge jumps can still be considered there.
- Audited movement coverage after the user clarified this should work for all movement, including chase and flee:
  - active chase uses `OverworldWildSpawns_DiagnosticBuildDirections(dx, dy, directions)` and then calls `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - active flee negates `dx/dy`, builds directions the same way, and then calls `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - active playful movement builds playful directions and then calls `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - chill wander and untangle also call `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - aggressive ram has its own direct `OverworldWildSpawns_TryStartLedgeJumpCommand` call before its normal blocked check.
- Confirmed the older `src/overworld_wild_movement.c` custom chase/flee path still contains direct movement-command code, but `OW_WILD_CUSTOM_MOVEMENT_DIAGNOSTIC_IDLE` keeps that descriptor in no-op mode in the current build; the active behavior system is owned by `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.

Runtime result:

- Pending user test.

Learning:

- The implementation is build-clean and ready for runtime ledge testing.
- Landing validation currently checks map blockage and object occupancy, but not terrain/pool compatibility. If runtime testing shows Pokemon jumping onto inappropriate terrain, add a terrain compatibility check to `OverworldWildSpawns_IsValidLedgeLandingTile`.

### Attempt 106: Aipom-Only Playful Chase Pass

Idea:

Focus the test build on playful behavior by spawning only Aipom, reducing cry spam, and replacing the playful near-player random sidestep with a more deliberate adjacent-target chase.

Implementation shape:

- Force behavior test spawns to `SPECIES_AIPOM` instead of alternating Aipom and Onix.
- Suppress ambient overworld cries during this focused playful test pass.
- Play Pokemon cries only for alert-state hops; speech-only alerts and later non-alert hop experiments should not play cries.
- Disable the current playful chill/active random hop presentation for now, because the new attentive movement should be tested without hop noise.
- Track the tile a spawn leaves from when the spawner starts a movement command.
- While playful is active and adjacent to the player, choose directions that move toward a different cardinal-adjacent tile around the player, excluding the spawn's current tile and the tile it just came from.
- Let the existing shared movement starter try those directions in order, so blocked paths and ledge cases fall through to the next candidate.

Why this is new:

- Earlier playful attempts added random near-player side movement and occasional active hops.
- No previous attempt has made playful orbit around adjacent player tiles while avoiding immediate backtracking.
- No previous attempt has made cries alert-hop-only while suppressing ambient cry spam for a focused playful test.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before build.
- First build copied `test203.nds`, but exposed new avoidable warnings from zero-percent playful hop checks and disabled ambient cries.
- Cleaned the warning sources by compiling out disabled playful hop branches and compiling out the ambient cry player while `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` is enabled.
- Final build with `./docker-makerom.cmd` succeeded and copied the ROM to Delta as `test204.nds`.
- Verified behavior test spawns now force `SPECIES_AIPOM`.
- Verified ambient cries are disabled for this focused pass.
- Verified `movementEmotePlayCryOnHop` lets alert-hop emotes play cries, while speech-only alerts and manual/non-alert hop paths do not play cries.
- Verified playful active movement now calls the new `OverworldWildSpawns_BuildPlayfulDirections` with state, field system, and slot context.
- Verified playful movement stores the tile a spawn leaves from in `movementPreviousTileX/Y`, then excludes that tile while choosing next adjacent-target directions.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 107: Playful Previous-Tile Hard Guard

Idea:

Fix the playful "do not move to the tile it was previously on" rule, because Attempt 106 only filtered the previous tile inside the adjacent-player planner and stored that tile before the movement command actually completed.

Implementation shape:

- Add an explicit previous-tile validity flag next to `movementPreviousTileX/Y`.
- Keep recording the tile before command start, but refresh the remembered tile from the map object's `xPrev/yPrev` when a spawner-owned movement command finishes.
- Make playful active movement reject any one-tile step that targets the remembered previous tile at the shared command-start layer.
- Make playful ledge jumps reject landings that would return to the remembered previous tile.
- Replace the non-adjacent playful fallback with a four-direction chase sorter that excludes the remembered previous tile instead of falling back to ordinary chase directions.

Why this is new:

- Attempt 106 filtered previous tiles only inside the special adjacent-target planner.
- No previous attempt added a command-layer backtrack guard, refreshed previous-tile memory from completed movement state, or applied the filter to the non-adjacent playful chase fallback.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementPreviousTileLocked`
- `OverworldWildSpawns_RecordFinishedPreviousTile`
- `OverworldWildSpawns_IsPlayfulBacktrackStep`
- `OverworldWildSpawns_BuildPlayfulChaseDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test205.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:12 timestamp.
- Verified fresh spawns clear `movementPreviousTileLocked`.
- Verified completed spawner-owned movement refreshes previous-tile memory from `object->xPrev/yPrev`.
- Verified playful active movement has a command-layer guard for one-tile backtracks and ledge-jump landings.
- Verified non-adjacent playful chase now builds sorted four-direction candidates while excluding the remembered previous tile.

Runtime result:

- User reported Aipom still sometimes returns to the tile it was previously on.

Learning:

- The coordinate guard and `xPrev/yPrev` refresh are not reliable enough for this rule.
- The map object's previous-coordinate fields may not represent "the tile before the last spawner command" at the exact frame the custom frame task reads them.
- The next attempt should avoid relying only on previous-coordinate bookkeeping and should also block the opposite direction of the last completed playful movement command.

### Attempt 108: Direction-History Playful Backtrack Guard

Idea:

Make the playful no-backtracking rule independent of map-object previous-coordinate timing. If the last completed playful movement was one tile to the right, the next one-tile playful movement cannot be left, regardless of what `xPrev/yPrev` or current tile reads report on that frame.

Implementation shape:

- Add pending movement direction/distance fields and last-completed movement direction/distance fields to `OverworldWildSpawnState`.
- When a spawner-owned movement command starts, record its direction and movement distance as pending.
- When that movement command finishes, commit the pending direction/distance as the last completed movement and clear the pending fields.
- Stop refreshing previous-tile memory from `object->xPrev/yPrev`; keep the pre-command origin tile recorded at command start instead.
- Keep the existing coordinate guard, but also have `OverworldWildSpawns_IsPlayfulBacktrackStep` reject a movement when its direction is the exact opposite of the last completed movement and its distance matches.
- Mark normal walking commands as distance `1` and ledge jumps as distance `2`, so the reverse-direction rule remains distance-aware.

Why this is new:

- Attempt 106 used only pre-command coordinate storage.
- Attempt 107 added coordinate validity and a command-layer coordinate guard, but still depended partly on `object->xPrev/yPrev`.
- No previous attempt has tracked and committed spawner-owned movement direction/distance, or used an opposite-direction guard for playful backtracking.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementPendingDirections`
- `movementPendingDistances`
- `movementLastDirections`
- `movementLastDistances`
- `OverworldWildSpawns_RecordFinishedMovementHistory`
- `OverworldWildSpawns_AreOppositeDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test206.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:18 timestamp.
- Verified all `OverworldWildSpawns_StartMovementCommandForSlot` call sites now pass direction and movement distance.
- Verified normal walk commands are recorded as distance `1`, and ledge jumps are recorded as distance `2`.
- Verified finished movement commits pending direction/distance through `OverworldWildSpawns_RecordFinishedMovementHistory` instead of reading `object->xPrev/yPrev`.
- Verified `OverworldWildSpawns_IsPlayfulBacktrackStep` rejects same-distance opposite-direction movement in addition to the existing coordinate previous-tile guard.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 109: Triple Playful Stamina

Idea:

Make playful Pokemon stay in their attentive/chase behavior much longer before entering tired state.

Implementation shape:

- Change the playful behavior class stamina from `16` to `48`.
- Leave playful rest time, normal speed, max speed, alert state, and tired visual unchanged.
- Keep stamina tile-based: one completed attentive movement command still spends one stamina.

Why this is new:

- Previous attempts added the playful behavior and then refined its movement/backtracking logic.
- No previous attempt has retuned the playful stamina value after the Aipom-only focused test pass.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PLAYFUL`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test207.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:27 timestamp.
- Verified the playful behavior class now uses stamina `48`.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 110: Playful Attentive Speed Rhythm

Idea:

Test the feel of playful attentive movement with a repeating speed rhythm instead of one constant active speed.

Implementation shape:

- Add a playful-only attentive speed cycle: 3 completed attentive movement commands at speed `2`, followed by 6 completed attentive movement commands at speed `3`.
- Repeat the 9-step cycle while the Pokemon remains in the playful attentive state.
- Drive the cycle from `movementActiveSteps`, which is already the tile-based attentive stamina counter.
- Leave chill wandering, ram movement, stamina, rest time, and the no-backtracking guards unchanged.

Why this is new:

- Previous playful attempts used the behavior profile's `maxSpeed` during the whole attentive state.
- No previous attempt has alternated playful attentive movement speeds inside a repeated step-count cycle.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_ATTENTIVE_SPEED_2_STEPS`
- `OW_WILD_SPAWNER_PLAYFUL_ATTENTIVE_SPEED_3_STEPS`
- `OverworldWildSpawns_GetPlayfulAttentiveSpeed`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test208.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:33 timestamp.
- Verified the playful attentive speed cycle uses `movementActiveSteps % 9`.
- Verified phases `0` through `2` return speed `2`, and phases `3` through `8` return speed `3`.

Runtime result:

- User reported they did not like the feel and asked to revert it.

Learning:

- Alternating 3 speed-2 moves with 6 speed-3 moves did not feel good for playful attentive movement.
- Do not reintroduce this exact 3/6 speed rhythm without a new reason or a different feel target.

### Attempt 111: Revert Playful Attentive Speed Rhythm

Idea:

Remove Attempt 110's speed-rhythm experiment and return playful attentive movement to the profile's normal active speed.

Implementation shape:

- Remove the playful attentive speed-cycle constants.
- Remove `OverworldWildSpawns_GetPlayfulAttentiveSpeed`.
- Remove the playful-only active-speed branch from `OverworldWildSpawns_GetMovementWalkCommand`.
- Leave playful stamina `48`, no-backtracking guards, Aipom-only test spawns, and cry behavior unchanged.

Why this is new:

- This is an explicit revert of Attempt 110 after runtime feel testing, not another speed-rhythm variant.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test209.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:38 timestamp.
- Verified no active source symbols remain for `OW_WILD_SPAWNER_PLAYFUL_ATTENTIVE_SPEED_2_STEPS`, `OW_WILD_SPAWNER_PLAYFUL_ATTENTIVE_SPEED_3_STEPS`, or `OverworldWildSpawns_GetPlayfulAttentiveSpeed`.
- Verified `OverworldWildSpawns_GetMovementWalkCommand` again uses `profile.normalSpeed` while chill, ram speed for active ram movement, and `profile.maxSpeed` for other active movement including playful.

Runtime result:

- Pending user test of reverted feel.

Learning:

- Attempt 110 is now removed from active source. Keep the rejection recorded so future playful tuning does not repeat the exact 3/6 speed rhythm by accident.

### Attempt 112: Playful Targets Player And Follower

Idea:

Update playful attentive movement so Aipom treats both the player and the active follower Pokemon as chase targets. If it is not next to either target, it moves toward the closest target. If it is already cardinal-adjacent to either target, it continues trying to move to a valid tile adjacent to the player or follower, while still avoiding the immediate previous tile.

Implementation shape:

- Add a small playful target list with a maximum of two targets: player plus active follower.
- Resolve the follower using `fieldSystem->followMon.mapObject` first and the existing follower object-id fallback used by ram collision.
- Replace player-only playful scoring with closest-target scoring.
- Keep the current spawner-owned walk command path, ledge handling, movement speed, stamina, Aipom-only test spawn, and no-backtracking guard unchanged.

Why this is new:

- Previous playful movement attempts only optimized around the player's tile and the four tiles adjacent to the player.
- No previous attempt has included the follower Pokemon as a valid playful chase/adjacency target.
- This does not retry the rejected Attempt 110 speed rhythm or change the stable movement command execution path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildPlayfulTarget`
- `OverworldWildSpawns_BuildPlayfulTargets`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test210.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:43 timestamp.
- Verified the playful target resolver keeps the player as target `0`, adds an active follower as target `1`, and deduplicates matching coordinates.
- Verified playful movement scoring now rejects player/follower target tiles and scores both chase and adjacent-orbit directions against the closest target.
- Verified this change does not reintroduce the rejected Attempt 110 speed rhythm.

Runtime result:

- User reported that the playful behavior did not feel like it naturally fell back into approach behavior.
- The user also suggested that playful likely does not need two distinct chase branches.

Learning:

- The hard branch between "not adjacent, chase target tile" and "adjacent, seek adjacent/orbit tile" can make the behavior feel sticky instead of naturally unified.
- Next attempt should remove the explicit approach-vs-close split and use one scoring rule for all playful movement decisions.

### Attempt 113: Close All-Direction Alert Radius

Idea:

For behavior profiles using the normal `3`-tile facing alertness, also let the Pokemon spot the player within radius `1` in any direction. This keeps the longer alert range directional, but makes a very close player trigger alert even from behind or diagonally.

Implementation shape:

- Add `OW_WILD_SPAWNER_CLOSE_ALERT_RADIUS` with value `1`.
- Add `OverworldWildSpawns_IsPlayerInAlertRadius`, using a radius-1 all-direction check.
- Update `OverworldWildSpawns_IsPlayerInAlertLine` so non-ram profiles still use the facing line, but profiles whose resolved `alertness` is `OW_WILD_SPAWNER_SPOT_RANGE` also pass the close-radius check.
- Leave aggressive ram on its existing cardinal-line alertness path.
- Leave movement commands, speed, stamina, playful target selection, and battle triggers unchanged.

Why this is new:

- Attempt 70 changed normal alertness to a strict facing line.
- Attempt 104 made only aggressive ram alert in all cardinal directions.
- No previous attempt has combined normal facing-line alertness with a close-range all-direction fallback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CLOSE_ALERT_RADIUS`
- `OverworldWildSpawns_IsPlayerInAlertRadius`
- `OverworldWildSpawns_IsPlayerInAlertLine`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test211.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:46 timestamp.
- Verified `OverworldWildSpawns_IsPlayerInAlertLine` keeps aggressive ram on the cardinal-line path before applying the close-radius fallback.
- Verified non-ram profiles still use facing-line alertness, with radius `1` all-direction alerting only when resolved `profile.alertness == OW_WILD_SPAWNER_SPOT_RANGE`.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 114: Unified Playful Movement Scoring

Idea:

Remove the explicit playful approach/close split. Instead of checking whether Aipom is already adjacent to the player or follower, score every possible next tile with one rule: prefer the next tile that is closest to a valid tile adjacent to the player or follower, then use raw closeness to the player/follower as the tie-breaker.

Implementation shape:

- Remove `OverworldWildSpawns_IsCardinalAdjacentToAnyPlayfulTarget`.
- Remove `OverworldWildSpawns_BuildPlayfulChaseDirections`.
- Keep `OverworldWildSpawns_BuildPlayfulDirections` as the single playful direction builder for both approaching and staying close.
- Continue rejecting player/follower target tiles and the immediate previous tile.
- If no valid adjacent target tile can be scored, fall back to raw closest-target distance for that candidate direction.
- Leave movement command execution, ledge handling, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Attempt 112 added player/follower targets but kept two separate decision branches.
- No previous attempt has made playful approach and close movement use one unified scoring path.
- This does not retry the rejected Attempt 110 speed rhythm and does not change the stable spawner-owned movement-command path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_BuildPlayfulDirections`
- `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test212.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:11 timestamp.
- Verified active source no longer contains `OverworldWildSpawns_IsCardinalAdjacentToAnyPlayfulTarget` or `OverworldWildSpawns_BuildPlayfulChaseDirections`.
- Verified `OverworldWildSpawns_BuildPlayfulDirections` now always scores candidate directions through the same target-adjacent distance path, with raw closest-target distance as fallback/tie-break.

Runtime result:

- User reported that Aipom sometimes does not chase the player/follower and instead runs in circles.

Learning:

- The unified scorer made distance to a valid adjacent target tile primary, with raw player/follower distance only as a tie-breaker.
- That can make playful movement prefer orbit-like adjacent-tile scoring before it has actually closed distance to the player/follower.
- Do not conclude from this attempt alone that the hard previous-tile block is the blocker; later user feedback explicitly rejected softening that rule.

### Attempt 115: Soft Playful Backtrack Penalty

Idea:

Stop forbidding playful Pokemon from stepping back onto their previous tile during normal chase movement. Instead, make the previous tile slightly worse in the score so Aipom avoids it when another move is equally good, but can still turn back when that is the best way to keep chasing the player/follower.

Implementation shape:

- Add `OW_WILD_SPAWNER_PLAYFUL_TARGET_DISTANCE_SCORE_MULTIPLIER` with value `16` to name the existing primary distance weight.
- Add `OW_WILD_SPAWNER_PLAYFUL_PREVIOUS_TILE_SCORE_PENALTY` with value `4`.
- Remove the hard previous-tile rejection from `OverworldWildSpawns_BuildPlayfulDirections`.
- Remove previous-tile exclusion from `OverworldWildSpawns_IsPlayfulAdjacentTarget` so a previous tile can still count as a valid adjacent goal when it is actually the best target-adjacent spot.
- Add the previous-tile penalty after distance scoring.
- Remove the one-tile playful backtrack skip from `OverworldWildSpawns_TryStartSpawnerMovementCommand`, allowing the sorted direction list to decide.
- Leave the ledge-jump backtrack guard, blocked-direction checks, movement commands, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Earlier playful attempts hard-rejected immediate previous-tile movement to stop Aipom bouncing back and forth.
- Attempt 114 unified scoring, but still kept the hard previous-tile rejection.
- No previous attempt has made previous-tile avoidance a score penalty that loses to a genuinely better chase move.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_PREVIOUS_TILE_SCORE_PENALTY`
- `OverworldWildSpawns_BuildPlayfulDirections`
- `OverworldWildSpawns_TryStartSpawnerMovementCommand`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test213.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:18 timestamp.
- Verified `OverworldWildSpawns_BuildPlayfulDirections` no longer hard-rejects previous-tile candidates and instead adds `OW_WILD_SPAWNER_PLAYFUL_PREVIOUS_TILE_SCORE_PENALTY`.
- Verified normal one-tile movement through `OverworldWildSpawns_TryStartSpawnerMovementCommand` no longer skips playful backtrack directions before blocked-direction checks.

Runtime result:

- User corrected the premise before further runtime testing: going to the previous tile should remain a hard block, and previous-tile blocking is not the issue.

Learning:

- Avoid repeating the soft previous-tile penalty approach.
- Restore hard previous-tile rejection in both the playful direction builder and movement command start path.
- The next fix should target playful scoring itself, not the no-backtrack rule.

### Attempt 116: Playful Target-Progress Scoring

Idea:

Keep the hard previous-tile block, but stop the unified playful scorer from valuing orbit/adjacent-ring positioning above actual chase progress. Score candidate moves primarily by raw distance to the nearest player/follower target, use distance to a valid adjacent target tile as the secondary tie-breaker, and penalize candidate moves that fail to reduce raw target distance while Aipom is not yet adjacent.

Implementation shape:

- Remove `OW_WILD_SPAWNER_PLAYFUL_PREVIOUS_TILE_SCORE_PENALTY`.
- Add `OW_WILD_SPAWNER_PLAYFUL_NO_PROGRESS_SCORE_PENALTY` with value `64`.
- Restore hard one-tile playful backtrack rejection in `OverworldWildSpawns_TryStartSpawnerMovementCommand`.
- Restore previous-tile exclusion in `OverworldWildSpawns_IsPlayfulAdjacentTarget`.
- Restore hard previous-tile rejection in `OverworldWildSpawns_BuildPlayfulDirections`.
- Keep `OverworldWildSpawns_BuildPlayfulDirections` as one unified playful direction builder rather than reintroducing separate approach/near modes.
- Invert playful scoring priority from adjacent-ring distance first to raw nearest-target distance first:
  - primary: closest player/follower Manhattan distance
  - secondary: closest valid adjacent-target tile distance
  - extra penalty: no raw progress when current raw target distance is greater than 1
- Leave movement command execution, ledge handling, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Attempt 114 unified approach/near playful scoring but made adjacent-ring distance primary.
- Attempt 115 softened the previous-tile rule and was rejected by user feedback.
- No previous attempt has kept the hard no-backtrack rule while making raw target progress the primary playful scoring axis.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_NO_PROGRESS_SCORE_PENALTY`
- `OverworldWildSpawns_IsPlayfulAdjacentTarget`
- `OverworldWildSpawns_BuildPlayfulDirections`
- `OverworldWildSpawns_TryStartSpawnerMovementCommand`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test214.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:24 timestamp.
- Verified active source no longer contains `OW_WILD_SPAWNER_PLAYFUL_PREVIOUS_TILE_SCORE_PENALTY`.
- Verified `OverworldWildSpawns_TryStartSpawnerMovementCommand` again hard-skips one-tile playful backtracks before blocked-direction checks.
- Verified `OverworldWildSpawns_BuildPlayfulDirections` again hard-rejects previous-tile candidates and now scores raw closest target distance before adjacent-target distance.

Runtime result:

- User reported that the issue remains, but only after the Pokemon has already started orbiting the player; chase before that point works fine. When the player walks away after orbit starts, Aipom sometimes keeps circling instead of reacquiring chase.

Learning:

- Stronger raw-distance scoring alone is not enough.
- The bug is likely in the handoff from close/orbit behavior back into chase after the player/follower target positions separate.
- A new fix should focus on target coherence after orbiting, not on weakening the previous-tile hard block.

### Attempt 117: Coherent Playful Target Selection

Idea:

Stop scoring a single playful move against the player/follower target set as if it were one blended target. Pick one target for the current decision, then score both raw chase distance and adjacent/orbit distance against that same target. Keep the player as target `0`, and prefer the player when the player and follower distances are close, so Aipom is less likely to keep orbiting the follower/old nearby target when the player has just walked away.

Implementation shape:

- Add `OW_WILD_SPAWNER_PLAYFUL_PLAYER_PRIORITY_MARGIN` with value `1`.
- Add `OverworldWildSpawns_GetPlayfulTargetDistance`.
- Add `OverworldWildSpawns_SelectPlayfulTarget`.
- Update `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance` to optionally score adjacent tiles around only the selected target while still rejecting both player/follower occupied target tiles.
- Update `OverworldWildSpawns_BuildPlayfulDirections` so:
  - it selects one target before scoring candidate directions;
  - current target distance comes from that selected target;
  - candidate target distance comes from that same selected target;
  - adjacent/orbit tie-break distance also comes from that same selected target.
- Keep previous-tile hard rejection, movement command execution, ledge handling, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Attempt 112 added player/follower targets, but closest-target scoring could still switch between them.
- Attempt 114 unified playful scoring but allowed one candidate score to be influenced by multiple targets.
- Attempt 116 made raw target distance primary, but still let raw and adjacent distances be computed from the blended target set.
- No previous attempt has selected a single coherent player/follower target for each playful movement decision.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_PLAYER_PRIORITY_MARGIN`
- `OverworldWildSpawns_GetPlayfulTargetDistance`
- `OverworldWildSpawns_SelectPlayfulTarget`
- `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test215.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:34 timestamp.
- Verified active source defines `OW_WILD_SPAWNER_PLAYFUL_PLAYER_PRIORITY_MARGIN`.
- Verified active source contains `OverworldWildSpawns_SelectPlayfulTarget` and no longer contains the old blended `OverworldWildSpawns_GetClosestPlayfulTargetDistance` helper.
- Verified `OverworldWildSpawns_BuildPlayfulDirections` selects one target before scoring both raw target distance and adjacent-target distance.

Runtime result:

- User clarified the intended priority: if neither the player nor follower Pokemon is in a neighboring tile, getting next to the player/follower must be priority number 1.

Learning:

- Coherent target selection alone still leaves the priority rule too implicit.
- The next attempt should make "become adjacent to player/follower" a hard scoring phase before any orbit/adjacent-ring scoring is allowed.

### Attempt 118: Explicit Playful Approach Priority

Idea:

Make playful movement's first priority explicit: when Aipom is not cardinal-adjacent to either the player or follower Pokemon, score candidate moves only by whether they reduce raw distance to the closest target. Orbit/adjacent-ring scoring is only allowed after Aipom is already next to at least one valid target.

Implementation shape:

- Add `OverworldWildSpawns_GetClosestPlayfulAnyTargetDistance`.
- In `OverworldWildSpawns_BuildPlayfulDirections`, compute `currentAnyTargetDistance` before scoring moves.
- Treat `currentAnyTargetDistance == 1` as "already next to player/follower."
- If Aipom is not already next to player/follower:
  - score candidates by closest raw distance to any target;
  - add the no-progress penalty when a candidate does not reduce that raw distance;
  - skip the orbit/adjacent-ring scoring entirely for that candidate.
- If Aipom is already next to player/follower:
  - keep Attempt 117's coherent selected-target orbit scoring.
- Keep the hard previous-tile rejection, movement command execution, ledge handling, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Attempt 112 had an explicit approach/close split, but the user later pushed toward a unified feel and it still had sticky behavior.
- Attempt 114 unified scoring and made orbit-adjacent distance globally influential.
- Attempt 116 made raw distance stronger but did not disable orbit scoring before adjacency.
- Attempt 117 selected one coherent target but still scored approach/orbit in the same candidate path.
- No previous attempt has made "not adjacent to player/follower means approach-only scoring" the first priority while preserving the current hard no-backtrack rule.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_GetClosestPlayfulAnyTargetDistance`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test216.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:40 timestamp.
- Verified active source contains `OverworldWildSpawns_GetClosestPlayfulAnyTargetDistance`.
- Verified `OverworldWildSpawns_BuildPlayfulDirections` computes `currentAnyTargetDistance` and `isAdjacentToAnyTarget`.
- Verified the non-adjacent branch scores by closest raw distance to any target and skips the adjacent/orbit scoring path.

Runtime result:

- User agreed to make orbit mode hard-filter moves that increase distance from the player/follower. User also clarified that "next to" means both cardinal and diagonal neighboring tiles.

Learning:

- Attempt 118 made approach-vs-orbit priority explicit, but still used cardinal adjacency/Manhattan-ish distance semantics in key places.
- The next attempt should treat diagonal neighbors as "next to" and make orbit mode reject moves that leave the neighboring ring.

### Attempt 119: Eight-Way Orbit Neighbor Filter

Idea:

Make playful "next to" mean all 8 neighboring tiles around the player/follower, and make orbit movement hard-reject candidate moves that increase the closest player/follower neighbor distance. Once Aipom is next to a target, it may move around the target, but it may not move away from the player/follower ring and may not move to the previous tile.

Implementation shape:

- Replace `OverworldWildSpawns_IsCardinalAdjacentToTarget` with `OverworldWildSpawns_IsPlayfulNeighboringTarget`.
- Change `OverworldWildSpawns_GetPlayfulTargetDistance` to use Chebyshev/8-way distance instead of Manhattan distance.
- Expand the target-adjacent offset table in `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance` from 4 cardinal offsets to 8 neighboring offsets.
- Treat `currentAnyTargetDistance <= 1` as already next to the player/follower.
- In orbit mode, hard-reject candidate directions whose closest 8-way target distance is greater than the current closest 8-way target distance.
- Keep previous-tile hard rejection, target-tile rejection, movement command execution, ledge handling, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Earlier playful attempts treated adjacency as cardinal-only in the orbit target ring.
- Attempt 118 split approach/orbit priority but still treated `currentAnyTargetDistance == 1` as adjacency using the old distance helper.
- No previous attempt has defined playful adjacency as the full 8 neighboring tiles while hard-filtering orbit moves that increase 8-way distance from the player/follower.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsPlayfulNeighboringTarget`
- `OverworldWildSpawns_GetPlayfulTargetDistance`
- `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test217.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:52 timestamp.
- Verified active source contains `OverworldWildSpawns_IsPlayfulNeighboringTarget` and no longer contains `OverworldWildSpawns_IsCardinalAdjacentToTarget`.
- Verified active source uses an 8-entry target-neighbor offset table.
- Verified orbit mode hard-rejects candidates when `closestAnyTargetDistance > currentAnyTargetDistance`.

Runtime result:

- User requested a deterministic playful emote: every 5 movement steps while next to the player/follower, the Pokemon should hop.

Learning:

- The next attempt should add a separate neighbor-step counter instead of reusing attentive stamina, so playful orbit flavor does not shorten/extend tired-state timing.

### Attempt 120: Playful Orbit Hop Every Five Neighbor Steps

Idea:

When a playful Pokemon is already next to the player or follower Pokemon, count completed movement steps in that neighboring ring. On every fifth completed neighboring step, start a silent in-place hop emote, then resume the active playful state.

Implementation shape:

- Add `movementPlayfulNeighborSteps` to `OverworldWildSpawnState`.
- Add `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS` set to `5`.
- Compile `OverworldWildSpawns_TryStartManualHopEmote` even when random playful hop chances are `0`, while leaving those random hop paths disabled.
- Add `OverworldWildSpawns_IsPlayfulNeighboringAnyTarget` using the existing 8-way player/follower target list and Chebyshev distance.
- Add `OverworldWildSpawns_TryHandlePlayfulOrbitStep`, called after a spawner-owned movement command finishes in active playful state.
- Reset the new counter when the Pokemon is no longer next to a player/follower target, enters chill/tired/alert state, resets movement state, or respawns into a slot.
- Keep alert-state hop cries unchanged; the periodic orbit hop is silent and has no speech bubble.

Why this is new:

- Earlier playful hop work used random chill/active hop chance constants, both currently disabled.
- Previous playful movement attempts changed approach/orbit direction choice, adjacency semantics, and previous-tile filtering, but none added a deterministic "completed steps while adjacent" emote cadence.
- Reusing `movementActiveSteps` would repeat the stamina/tired-state mechanism and risk changing tired timing; this attempt adds a separate counter.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementPlayfulNeighborSteps`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS`
- `OverworldWildSpawns_IsPlayfulNeighboringAnyTarget`
- `OverworldWildSpawns_TryHandlePlayfulOrbitStep`
- `OverworldWildSpawns_TryStartManualHopEmote`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test218.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:01 timestamp.
- Verified active source contains `movementPlayfulNeighborSteps`, `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS`, and `OverworldWildSpawns_TryHandlePlayfulOrbitStep`.

Runtime result:

- User reported that the orbit-mode hard filter from Attempt 119 likely was not the right feel; moves that increase distance from the player/follower should be lowest priority rather than impossible.

Learning:

- Deterministic hops are separate from the orbit direction priority issue.
- The next attempt should preserve hard previous-tile and target-tile blocks, but make "move away from the player/follower ring" a low-priority fallback instead of a hard reject.

### Attempt 121: Penalize Playful Orbit Moves Away Instead of Rejecting

Idea:

Keep playful orbit's preference for staying next to the player/follower, but allow candidate moves that increase the closest 8-way distance as a last resort. This should reduce the chance of Aipom getting stuck or doing awkward local loops when every ideal orbit tile is blocked, while still making near-player/follower movement the dominant behavior.

Implementation shape:

- Add `OW_WILD_SPAWNER_PLAYFUL_MOVE_AWAY_SCORE_PENALTY`.
- In `OverworldWildSpawns_BuildPlayfulDirections`, remove the hard `continue` that rejected orbit candidates when `closestAnyTargetDistance > currentAnyTargetDistance`.
- Add the new move-away penalty to those candidates after the normal orbit score is computed.
- Keep target-tile rejection and previous-tile rejection as hard blocks.
- Keep approach-mode scoring, 8-way adjacency, deterministic five-step hop behavior, movement execution, stamina, ledges, and Aipom-only test spawning unchanged.

Why this is new:

- Attempt 119 made orbit mode hard-reject moves that increase 8-way target distance.
- Earlier playful scoring attempts allowed looser movement, but did not combine the current 8-way adjacency semantics with a specific "move away is allowed but lowest priority" orbit penalty.
- This is not a reversion to pre-119 behavior; it keeps the current neighbor model and only softens one rejection into scoring.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_MOVE_AWAY_SCORE_PENALTY`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test219.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:04 timestamp.
- Verified active source contains `OW_WILD_SPAWNER_PLAYFUL_MOVE_AWAY_SCORE_PENALTY` and scores move-away orbit candidates instead of rejecting them.

Runtime result:

- User requested more organic playful hop expression: exact every-five-step hops felt robotic, and hop sequences should sometimes double-hop and sometimes show one heart/smile bubble after the sequence.

Learning:

- The next attempt should keep the same adjacent-step hook point, but randomize cadence and presentation without changing alert-state cry behavior.

### Attempt 122: Randomized Playful Orbit Hop Expression

Idea:

Make playful adjacent hop emotes feel less robotic by randomizing when they happen, occasionally making the hop sequence a double hop, and sometimes showing one friendly speech bubble after the hop sequence.

Implementation shape:

- Replace exact `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS` timing with:
  - `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MIN_STEPS` = `4`;
  - `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MAX_STEPS` = `7`;
  - `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_CHANCE_PERCENT` = `45`.
- Add `OW_WILD_SPAWNER_PLAYFUL_ORBIT_DOUBLE_HOP_CHANCE_PERCENT` = `25`.
- Add `OW_WILD_SPAWNER_PLAYFUL_ORBIT_BUBBLE_CHANCE_PERCENT` = `45`.
- Add helper functions:
  - `OverworldWildSpawns_ShouldStartPlayfulOrbitHop`;
  - `OverworldWildSpawns_GetPlayfulOrbitJumpCount`;
  - `OverworldWildSpawns_GetPlayfulOrbitBubbleId`.
- Split `OverworldWildSpawns_TickSpotEmote` bubble display from cry playback so silent manual hops can still display bubbles.
- Keep `movementEmoteShowBubbleEachJump` false for playful orbit hops, so double-hop sequences display at most one bubble after the final hop.
- Keep alert-state hops playing cry; playful orbit hops remain silent.

Why this is new:

- Attempt 120 added exact five-step deterministic orbit hops with no bubble.
- Earlier random hop chance constants were for old chill/active random paths and are still disabled.
- No previous attempt has randomized the deterministic adjacent-step hook while adding sequence-level heart/smile bubble presentation.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MIN_STEPS`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MAX_STEPS`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_CHANCE_PERCENT`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_DOUBLE_HOP_CHANCE_PERCENT`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_BUBBLE_CHANCE_PERCENT`
- `OverworldWildSpawns_ShouldStartPlayfulOrbitHop`
- `OverworldWildSpawns_GetPlayfulOrbitJumpCount`
- `OverworldWildSpawns_GetPlayfulOrbitBubbleId`
- `OverworldWildSpawns_TickSpotEmote`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test220.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:13 timestamp.
- Verified active source contains the randomized orbit hop timing, double-hop chance, bubble chance, and sequence-level bubble helper.

Runtime result:

- User asked that the hop timing should not restart when Aipom loses orbiting/adjacent state.

Learning:

- The randomized hop timer still resets when Aipom temporarily leaves the neighboring ring, which can make orbit expression feel delayed after reacquiring the player/follower.
- The next attempt should pause the timer while out of orbit instead of clearing it, while still clearing it for invalid map context, state resets, tired state, alert starts, and respawns.

### Attempt 123: Pause Playful Hop Timer Outside Orbit

Idea:

When playful Aipom temporarily leaves the 8-way neighboring ring around the player/follower, preserve its current hop-timer progress instead of restarting from zero. The timer should only advance while actually orbiting/neighboring, but leaving and re-entering orbit should resume from the previous count.

Implementation shape:

- Split the guard in `OverworldWildSpawns_TryHandlePlayfulOrbitStep`.
- If the movement `FieldSystem *` is no longer current, still clear `movementPlayfulNeighborSteps`.
- If the Pokemon is merely not neighboring any playful target, return without incrementing or clearing `movementPlayfulNeighborSteps`.
- Keep counter reset after a hop sequence starts, and keep existing resets for full movement-state reset, tired state, alert start, chill handling, and respawn.
- Keep randomized 4-7 step timing, double-hop chance, heart/smile bubble chance, and silent orbit hops unchanged.

Why this is new:

- Attempt 120 reset the neighbor-step counter whenever the Pokemon was no longer next to a player/follower target.
- Attempt 122 randomized the hop timing but kept that reset behavior.
- No previous attempt has treated the adjacent-hop timer as paused while out of orbit.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryHandlePlayfulOrbitStep`
- `movementPlayfulNeighborSteps`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test221.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:22 timestamp.
- Verified active source clears the hop timer for invalid movement field context but preserves it when the Pokemon is merely not neighboring a playful target.

Runtime result:

- User reported the chase/orbit/rechase behavior is almost perfect, but Aipom sometimes loses direction completely, chases the wrong way, or spins the wrong way.
- User suspects ledge jumps may be involved, though it may also be another scoring/history issue.

Learning:

- The next focused change should inspect ledge interactions before changing the general orbit/chase priority rules again.
- A concrete mismatch exists: playful direction scoring evaluates the one-tile candidate, but the movement executor can turn that same direction into a two-tile ledge jump.

### Attempt 124: Score Playful Ledge Jumps By Landing Tile

Idea:

Make playful chase/orbit direction scoring evaluate the tile the Pokemon will actually reach. If a direction would trigger a ledge jump, score the two-tile landing position instead of the ledge tile one step away.

Implementation shape:

- Add `OverworldWildSpawns_TryGetPlayfulMovementDestination`.
- For normal movement, return the one-step destination.
- For ledge movement, check the behavior profile's `jumpLevel`, validate the landing tile with `OverworldWildSpawns_IsValidLedgeLandingTile`, and return the two-step landing destination.
- In `OverworldWildSpawns_BuildPlayfulDirections`, score candidate directions using this helper destination.
- Exclude invalid ledge jumps from the scored direction list.
- Keep the existing hard previous-tile rejection, target-tile rejection, 8-way target adjacency, orbit move-away penalty, randomized hop timing, and hop timer pause behavior unchanged.

Why this is new:

- Ledge jumping was added before, but the playful scorer still evaluated one-tile destinations.
- No previous attempt has aligned playful target scoring with the actual two-tile destination used by ledge jump execution.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryGetPlayfulMovementDestination`
- `OverworldWildSpawns_BuildPlayfulDirections`
- `OverworldWildSpawns_TryStartLedgeJumpCommand`
- `OverworldWildSpawns_IsValidLedgeLandingTile`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test222.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:32 timestamp.
- Verified active source contains `OverworldWildSpawns_TryGetPlayfulMovementDestination`, and `OverworldWildSpawns_BuildPlayfulDirections` now scores candidate moves through that helper destination.

Runtime result:

- User found another clue: when the player runs and then stops, Aipom can act weird as if the player/follower position was not updated coherently.
- This suggests the remaining wrong-direction/spin issue may be caused by target coordinates changing mid-movement, not only by ledge destination scoring.

Learning:

- The next focused test should keep the movement executor unchanged and make playful target selection more tolerant of in-flight player/follower map-object positions.

### Attempt 125: Include Moving Target Trail For Playful Scoring

Idea:

When the player or follower Pokemon is actively moving, playful movement should treat that target as occupying a tiny two-tile trail: its current tile plus its previous tile. This should make Aipom less likely to snap to the wrong side when the player runs and stops, or when the follower is still catching up.

Implementation shape:

- Increase `OW_WILD_SPAWNER_PLAYFUL_TARGET_MAX` from `2` to `6`.
- Add `OverworldWildSpawns_TryAddPlayfulMapObjectTargets`.
- For a player/follower map object, always add `MapObject_GetCurrentX/Y`.
- If that target object reports `MapObject_IsSingleMovementActive`, also add `object->xPrev/yPrev` when it is valid and differs from the current tile.
- Resolve the player through `fieldSystem->playerAvatar->mapObject` when possible, falling back to `GetPlayerXCoord/YCoord`.
- Resolve follower targets through both the direct `fieldSystem->followMon.mapObject` path and the follower object-id fallback, using the same current-plus-previous trail helper.
- Keep the playful movement command executor, ledge landing scorer, hard previous-tile block, target-tile block, orbit penalties, speed, stamina, and hop logic unchanged.

Why this is new:

- Attempt 112 added player/follower target selection, but only with one current tile per target.
- Attempt 124 aligned ledge scoring with the actual ledge landing tile, but did not change player/follower target freshness.
- Earlier attempts found spawned Pokemon `xPrev/yPrev` unreliable for their own no-backtrack bookkeeping, but no attempt has used player/follower `xPrev/yPrev` only while those target objects are actively moving.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_TARGET_MAX`
- `OverworldWildSpawns_TryAddPlayfulMapObjectTargets`
- `OverworldWildSpawns_BuildPlayfulTargets`
- `MapObject_IsSingleMovementActive`
- `LocalMapObject::xPrev`
- `LocalMapObject::yPrev`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test223.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:41 timestamp.
- Verified active source contains `OverworldWildSpawns_TryAddPlayfulMapObjectTargets`, the playful target cap is `6`, and `OverworldWildSpawns_BuildPlayfulTargets` now adds current-plus-previous target tiles for moving player/follower map objects.

Runtime result:

- User agreed the moving player/follower trail probably should be default handling for other behavior/state logic that relies on calculating the player's position.

Learning:

- Attempt 125 only helped playful scoring. The next change should promote the moving-target trail helper to shared movement intent, while keeping exact tile checks for battles, spawn placement, and despawn distance.

### Attempt 126: Shared Moving Player Target For Movement Intent

Idea:

Use the current-plus-previous moving-player target trail as the default player-position source for movement intent. Behaviors that choose alert/chase/flee/ram/untangle directions should target the closest coherent moving-player tile instead of always reading only `GetPlayerXCoord/YCoord`.

Implementation shape:

- Rename the target-add helpers from playful-specific names to shared movement-target names:
  - `OverworldWildSpawns_TryAddMovementTarget`;
  - `OverworldWildSpawns_TryAddMovementMapObjectTargets`.
- Add `OverworldWildSpawns_BuildPlayerMovementTargets`.
- Add `OverworldWildSpawns_TrySelectClosestMovementTarget`.
- Add `OverworldWildSpawns_TryGetClosestPlayerMovementTarget`.
- Keep playful using the same helper for player targets, then add follower targets on top of it.
- Update untangle movement to move away from the closest moving-player target.
- Update the per-slot movement tick so alert detection, chase direction, flee direction, and ram's alert-start direction use the closest moving-player target.
- Leave exact-coordinate systems unchanged for now:
  - spawn placement;
  - despawn distance;
  - tile occupancy;
  - touch battle;
  - A-button battle;
  - ram crash battle collision.

Why this is new:

- Attempt 125 applied the moving-target trail only inside playful player/follower target scoring.
- No previous attempt has made this the shared source for player-position-based movement intent.
- Earlier coordinate experiments only proved player/object coordinate reads were stable; they did not smooth moving-player coordinates or define exact-vs-smoothed usage boundaries.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryAddMovementTarget`
- `OverworldWildSpawns_TryAddMovementMapObjectTargets`
- `OverworldWildSpawns_BuildPlayerMovementTargets`
- `OverworldWildSpawns_TrySelectClosestMovementTarget`
- `OverworldWildSpawns_TryGetClosestPlayerMovementTarget`
- `OverworldWildSpawns_BuildUntangleDirections`
- `OverworldWildSpawns_TickMovementParams`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test224.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:52 timestamp.
- Verified active source contains the shared moving-player target helper path, playful now uses `OverworldWildSpawns_BuildPlayerMovementTargets`, and untangle plus the per-slot movement tick call `OverworldWildSpawns_TryGetClosestPlayerMovementTarget`.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 127: Double Playful Movement Range

Idea:

Let Playful Pokemon roam/chase/orbit within twice the normal movement leash, so Aipom can keep its playful behavior active over a larger local area.

Implementation shape:

- Add `OW_WILD_SPAWNER_PLAYFUL_RANGE` as `OW_WILD_SPAWNER_MOVEMENT_RANGE * 2`.
- Give the Playful behavior class an explicit `OW_WILD_BEHAVIOR_OVERRIDE_RANGE`.
- Set Playful's profile range to `OW_WILD_SPAWNER_PLAYFUL_RANGE`.
- Leave Playful alertness, stamina, speed, target scoring, ledge handling, orbit hops, and battle rules unchanged.

Why this is new:

- Earlier attempts widened the shared movement range from `2` to `8`.
- Onix/aggressive_ram later received its own explicit range override.
- No previous attempt has given Playful an explicit doubled range override.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PLAYFUL_RANGE`
- `OW_WILD_BEHAVIOR_CLASS_PLAYFUL`
- `OW_WILD_BEHAVIOR_OVERRIDE_RANGE`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test225.nds`.
- Verified active source defines `OW_WILD_SPAWNER_PLAYFUL_RANGE` as twice `OW_WILD_SPAWNER_MOVEMENT_RANGE`.
- Verified the Playful behavior class now sets `OW_WILD_BEHAVIOR_OVERRIDE_RANGE` and uses `OW_WILD_SPAWNER_PLAYFUL_RANGE`.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 128: Phantom Stalker Hidden Movement

Idea:

Add a ghost behavior that spots the player, shows a short ellipsis alert, disappears, takes several normal movement steps while invisible, then reappears while continuing to stalk behind the player. This should make Gengar feel like it is moving unseen rather than simply walking at the player.

Implementation shape:

- Add `phantomStalker` as a behavior class for ghost-group Pokemon.
- Add `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.
- Add `OW_WILD_BEHAVIOR_ALERT_STATE_SPEECH_ELLIPSIS`.
- Add per-slot hidden state:
  - `movementPhantomHidden`;
  - `movementPhantomHiddenSteps`.
- Use `MapObject_SetBits(object, BIT_VANISH)` to hide the Pokemon after the alert cue.
- Use `MapObject_ClearBits(object, BIT_VANISH)` to reveal it after `OW_WILD_SPAWNER_PHANTOM_STALK_HIDDEN_STEPS` completed movement steps.
- Build phantom stalking directions toward the tile behind the player's current facing.
- Keep movement command execution on the existing collision-safe spawner command path.
- Reveal hidden phantoms on reset, tired/rest transition, blocked hidden movement, and before A-button battles can target them.
- Force behavior test spawns to Gengar for this focused test build.

Why this is new:

- Earlier attempts used `BIT_VANISH` only as a render fix for shiny overworld Pokemon, not as timed behavior presentation.
- Earlier movement attempts tested visible chase/flee/playful/ram movement, but none made a Pokemon move invisibly for several completed steps and then reappear.
- Earlier player-position smoothing helped chase intent, but no previous attempt targeted the tile behind the player's current facing.
- This deliberately avoids true phasing/collision bypass for the first ghost pass.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_BEHAVIOR_CLASS_PHANTOM_STALKER`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`
- `OW_WILD_BEHAVIOR_ALERT_STATE_SPEECH_ELLIPSIS`
- `OW_WILD_SPAWNER_PHANTOM_STALK_HIDDEN_STEPS`
- `OverworldWildSpawns_MaybeStartPhantomStalkerVanish`
- `OverworldWildSpawns_RevealPhantomStalker`
- `OverworldWildSpawns_BuildPhantomStalkerDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test226.nds`.
- Verified active source defines the phantom stalker class, attentive state, ellipsis alert state, hidden-step state arrays, and forced Gengar test spawn.
- Verified hidden phantoms use `BIT_VANISH`, reveal after completed hidden movement steps, reveal on reset/tired transition, and are skipped by the universal A-button battle path while hidden.
- Verified phantom movement direction scoring targets the tile behind the player's current facing and still uses the existing spawner movement command path.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 153: Mankey Canopy Hopper Headbutt-Tree Profile

Idea:

Create a complete behavior profile for Mankey where headbutt-tree spawns jump from one headbutt tree to another, rather than using ordinary wander/chase movement.

Implementation shape:

- Add a new `canopy_hopper` behavior class.
- Match `SPECIES_MANKEY` only when it spawns from `OW_WILD_SPAWN_TERRAIN_HEADBUTT`.
- Give the profile:
  - chill state: headbutt tree hop
  - alert state: angry hop
  - alertness: standard 3-facing-player range plus the existing close-radius fallback
  - attentive state: headbutt tree hop
  - stamina/rest: 8 hops, water-droplet tired state, 4 rest units
  - speed/range: normal speed 2, max speed 3, range 16
  - jump level: both, so variable overrides can still disable ledge jumping later if needed
- Add archive-backed current-map headbutt tree target selection.
- Only hop to real headbutt-tree coordinates from `ARC_HEADBUTT_TREES`.
- Reject the current tree, occupied trees, trees with no valid adjacent landing tile, trees outside profile range, and trees beyond despawn distance.
- For testing, force headbutt-terrain behavior-test encounters to Mankey while leaving land behavior-test encounters as Gengar.

Why this is new:

- Previous movement attempts used normal walk commands, ledge jumps, ram movement, playful orbiting, and phantom teleporting.
- No previous attempt has reused the headbutt tree archive as a behavior target graph.
- This avoids another fragile custom animated movement-command experiment by first proving the tree-to-tree behavior layer with direct tile placement and hop feedback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_BEHAVIOR_CLASS_CANOPY_HOPPER`
- `OW_WILD_BEHAVIOR_CHILL_STATE_HEADBUTT_TREE_HOP`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_HEADBUTT_TREE_HOP`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`
- `OverworldWildSpawns_ApplyBehaviorTestSpecies`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test253.nds`.

Runtime result:

- Pending user test on `test253.nds`.

Learning:

- Build-side result is stable. Runtime should verify that headbutt Mankey spawns hop between nearby real headbutt trees and that the direct tree hop does not trigger route-transition or battle-start instability.

### Attempt 160: Seven-Tile Canopy Hop Target And No Bounce-Back

Idea:

Make Mankey's canopy hop read as a larger movement choice for feel testing. Allow a single canopy target selection up to 7 tiles away, but keep the known-safe stock visible jump commands for the actual motion. Also prevent the next tree-hop target from immediately being the previous full-hop origin, so Mankey does not bounce back and forth between two trees.

Implementation shape:

- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES` with a test value of `7`.
- Store the full-hop origin when a canopy target is staged.
- After the final jump segment reaches the staged target, mark the staged origin as the next avoided tree target.
- Random and directed tree-hop pickers first reject the avoided origin, then fall back to allowing it only if no other valid candidate exists.
- Return-to-tree recovery ignores the avoided origin so off-tree Mankey cannot get stuck when the previous tree is the only valid recovery target.
- Keep the initial half-second pre-hop read, but continue internal 1- or 2-tile stock jump segments immediately so one staged decision can feel like a longer hop sequence.

Why this is new:

- Attempt 159 chained visible stock jump commands, but still used the older target range and intentionally waited between every segment.
- Earlier no-backtracking work was for Playful Aipom one-tile chase/orbit movement, not canopy hopper tree target selection.
- No previous canopy attempt has stored the previous full-hop origin and used it as an avoided next tree target with a safety fallback.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES`
- `movementCanopyHopOriginX/Y`
- `movementCanopyHopAvoidX/Y`
- `OverworldWildSpawns_IsValidHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_FinishPendingCanopyHop`

Verification:

- Built as `test261.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the touched overlay compiles with only older diagnostic unused warnings still present.
- Verified random and directed canopy tree-hop target selection now reject the previous full-hop origin on the first pass, then fall back if no other valid tree exists.
- Verified return-to-tree recovery ignores the avoided origin so off-tree Mankey still has a recovery path.

Runtime result:

- User reported Mankey still only jumps 1 tile and should want to jump far.

Learning:

- Raising the maximum hop distance alone is not enough; the picker still treats near and far valid trees equally, so nearby trees can dominate the visible behavior.
- The next attempt should change target scoring so canopy hoppers actively prefer far tree targets.

### Attempt 161: Canopy Hopper Far-Preferred Tree Selection

Idea:

Make Mankey actively want far canopy hops. Keep the 7-tile maximum from Attempt 160, but change target selection so chill/random canopy movement chooses among the farthest valid tree candidates, and directed canopy movement chooses among the farthest valid candidates that still make progress toward the desired target.

Implementation shape:

- Add a best-distance accumulator to random headbutt-tree target selection.
- When a farther valid random tree is found, reset the reservoir and pick among only that farthest-distance group.
- Add a best-distance accumulator to directed headbutt-tree target selection.
- Keep directed candidates progress-gated, but prefer larger hop distance before using desired-target distance as a tie-break.
- Preserve the Attempt 160 avoid-origin first pass and fallback pass.
- Leave return-to-tree recovery shortest-path based, since that path is about getting Mankey unstuck rather than style.

Why this is new:

- Attempt 160 only raised the maximum target distance and added previous-origin avoidance.
- No previous canopy attempt has scored tree targets by farthest hop distance.
- Playful no-backtracking and chase scoring attempts do not apply here because canopy movement uses archive-backed headbutt tree candidates, not one-tile movement directions.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseRandomHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryUseCloserHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTarget`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTargetToward`

Verification:

- Built as `test262.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the touched overlay compiles with only older diagnostic unused warnings still present.
- Verified chill/random tree-hop selection now tracks the largest candidate distance and resets the reservoir when a farther valid tree is found.
- Verified directed tree-hop selection still rejects candidates that do not improve desired-target distance, but now prefers larger hop distance before desired-distance tie-breaks.

Runtime result:

- User reported Mankey still never hops more than one tile.

Learning:

- Far-preferred target selection works on paper, but the visible motion still uses stock jump command behavior from Attempt 159.
- The stock `Jump*2` command family is not a multi-tile travel command for spawned Pokemon in this context; it visibly advances only one tile.
- The next attempt needs to stop relying on stock jump commands for the travel distance.
