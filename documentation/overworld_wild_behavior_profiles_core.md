# Behavior Profile Core Semantics

> **Status: historical attempt collection.** It does not define the current
> resolver contract. Use
> [`documentation/overworld-system/architecture.md`](overworld-system/architecture.md)
> and [`CONTEXT.md`](../CONTEXT.md) for current terms and target ownership.

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Behavior hierarchy is default behavior -> behavior class override -> behavior variable override.
- Profile data owns chill, alert, attentive, tired, rest, speed, stamina, range, and jump capability.
- Shared targeting should account for moving player/follower trails when behavior intent depends on player position.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 45 | 45 | Remove Redundant Speed 6 And Add Spot Emote |
| 46 | 46 | Short Independent Spot Range |
| 47 | 47 | Use Jump-Site Movement Command For Spot Emote |
| 48 | 48 | Manual PosVec Height Bob For Spot Emote |
| 49 | 49 | Use WaitJumpSite Movement Command |
| 50 | 50 | LockDir Jump2 Smoke Release Sequence |
| 51 | 51 | LockDir JumpSite Smoke Release Sequence |
| 52 | 52 | Partner Pokemon JumpSite Wrapper |
| 53 | 53 | Three-Speed Scale And Speed-3 Double Hop |
| 54 | 54 | Hop Cry, Tired Cooldown, And Chill Wander |
| 55 | 55 | Tired WaitJumpSite Then Stat-Fell Sound |
| 56 | 56 | Tired Follower Emotion Bubble Helper |
| 57 | 57 | Direct Follower Bubble Effect Creator |
| 58 | 58 | Silent Direct Tired Bubble |
| 59 | 59 | Tired Bubble Id Probe Cycle |
| 60 | 60 | Skip Known Heart And Smiley Bubble Ids |
| 61 | 61 | Name Known Bubble Ids And Skip Angry |
| 62 | 62 | Use Water Droplet Tired Bubble |
| 63 | 63 | Behavior Profile Resolver |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
| 101 | 65 | A-Button Facing Interaction Starts Spawn Battle |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 145 | 67 | Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram |
| 180 | 102 | Fled Battle Sends Spawn To Tired State |
| 181 | 103 | Behavior-Gated Ledge Far Jump |
| 182 | 104 | Aggressive Ram Cardinal Alert Line |
| 183 | 105 | Rename Aggressive Chase Profile |
| 202 | 124 | Score Playful Ledge Jumps By Landing Tile |
| 203 | 125 | Include Moving Target Trail For Playful Scoring |
| 204 | 126 | Shared Moving Player Target For Movement Intent |
| 205 | 127 | Double Playful Movement Range |

## Original Attempt Sections

### Attempt 45: Remove Redundant Speed 6 And Add Spot Emote

Idea:

Remove the redundant logical speed `6`, because it was identical to speed `5` after high speeds were capped to the fastest confirmed safe walk command. Add a first spot-emote state so a spawned Pokemon starts chill, detects the player entering spot range, hops in place with a jump sound, waits briefly, and only then enters the active chase/flee movement path.

Why this is new:

- Attempt 39 added logical speed levels through `6`; Attempts 41 and 43 later made the high levels aliases to the same safe command family.
- No previous attempt has removed the duplicate highest speed level while preserving Pidgey's fastest tested behavior.
- No previous attempt has added per-slot spotted/emoting state or tried a same-tile map-object hop before chase/flee.
- This avoids the old risky paths: no custom movement descriptor is re-enabled, no coordinate writes are used, and the chase/flee walk command path remains the existing spawner-owned path.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test142.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified speed `6` was removed from `OverworldWildSpawns_GetMovementWalkCommandForSpeed`.
- Verified Pidgey now uses logical speed `5`, which still maps to the fastest confirmed safe walk command family through the speed `3` alias.
- Verified `OverworldWildSpawnState` now stores per-slot `movementSpotStates` and `movementEmoteTimers`.
- Verified a chill spawn only starts the spot emote when the player is within `OW_WILD_SPAWNER_SPOT_RANGE` and a chase/flee direction exists.
- Verified the emote path sets `BIT_JUMP_START`, plays `SEQ_SE_GS_UFO_JUMP`, waits `OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES`, then allows the existing spawner-owned chase/flee command path to run.

Runtime result:

- User requested making the spot/emote trigger range distinct from chase range and much shorter.

Learning:

- Spot range should be a separate behavior parameter from chase/leash range. A Pokemon can notice the player nearby, emote, and then use a larger chase/flee range after it becomes active.

### Attempt 46: Short Independent Spot Range

Idea:

Keep chase/leash range at `8`, but stop deriving `OW_WILD_SPAWNER_SPOT_RANGE` from `OW_WILD_SPAWNER_MOVEMENT_RANGE`. Set spot range to `3` so the hop/sound emote only triggers when the player is close, while the already-spotted Pokemon can still chase/flee over the larger movement range.

Why this is new:

- Attempt 45 added spotting, but defined `OW_WILD_SPAWNER_SPOT_RANGE` as an alias of `OW_WILD_SPAWNER_MOVEMENT_RANGE`.
- No previous attempt has made spot/emote distance shorter than the movement/chase range.
- This changes only the spot threshold; it does not touch the proven spawner-owned movement command path, emote state machine, jump flag, or sound call.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test143.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified `OW_WILD_SPAWNER_MOVEMENT_RANGE` remains `8`.
- Verified `OW_WILD_SPAWNER_SPOT_RANGE` is now a distinct literal `3`.
- Verified `OverworldWildSpawns_IsPlayerInSpotRange` still uses the spot range only for the chill-to-emote transition.

Runtime result:

- User reported the spot -> chase logic works, but neither the hop nor the sound happens.

Learning:

- The chill/emote/active state machine and short spot range are working.
- Setting `BIT_JUMP_START` on these spawned idle objects is not enough to produce a visible same-tile hop.
- `PlaySE(SEQ_SE_GS_UFO_JUMP)` from this spot-emote path did not produce an audible sound in runtime.
- Do not retry the same `BIT_JUMP_START` + `SEQ_SE_GS_UFO_JUMP` presentation path without new evidence.

### Attempt 47: Use Jump-Site Movement Command For Spot Emote

Idea:

Replace the raw `BIT_JUMP_START` spot presentation with an actual single movement command from the script movement table: `JumpUpSite`/`JumpDownSite`/`JumpLeftSite`/`JumpRightSite` (`0x30`-`0x33`). Drive that command through the already stable spawner-owned frame updater, then transition to chase/flee when the command finishes or the emote timer expires. Also swap the test sound from `SEQ_SE_GS_UFO_JUMP` to common `SEQ_SE_DP_KON` so the next test can distinguish "wrong sound asset" from "sound call path broken."

Why this is new:

- Attempt 45 and Attempt 46 used only `BIT_JUMP_START` plus `SEQ_SE_GS_UFO_JUMP`.
- Earlier movement attempts proved spawner-owned look/walk commands and frame-updated single movement are viable, but none used the script jump-site command family.
- This still avoids the risky custom descriptor path, coordinate writes, and slot-47 callback execution.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test144.nds` and copied to Delta.
- `git diff --check` passed before and after the build.
- Verified active spot emote code no longer sets or clears `BIT_JUMP_START`.
- Verified the emote now starts a direction-specific jump-site movement command from the `0x30`-`0x33` family with `MapObject_StartMovementCommand` and `MapObject_SetSingleMovementActive`.
- Verified `OverworldWildSpawns_TickSpotEmote` drives the emote command through `OverworldWildSpawns_UpdateSpawnerMovementCommand` and still falls through to active chase/flee if the emote timer expires.
- Verified the test sound is now `SEQ_SE_DP_KON`.

Runtime result:

- User reported no visible hop, but the `SEQ_SE_DP_KON` sound does play.

Learning:

- The spot-emote trigger and sound call are working.
- The `Jump*Site` command family either is not visibly animating these spawned idle objects or is completing/clearing before any visible render frame.
- Do not retry the same `0x30`-`0x33` jump-site command path without new evidence.

### Attempt 48: Manual PosVec Height Bob For Spot Emote

Idea:

Stop relying on the stock jump-site movement command for the spot hop. When the Pokemon spots the player, save `object->posVec[1]`, play the now-confirmed audible `SEQ_SE_DP_KON`, and manually apply a 20-frame up/down fixed-point height offset before restoring the original `posVec[1]` and entering chase/flee. This tests whether spawned Pokemon can be visually lifted without tile-coordinate writes or custom movement descriptor callbacks.

Why this is new:

- Attempts 45 and 46 used `BIT_JUMP_START`.
- Attempt 47 used `Jump*Site` movement commands and proved the sound path works, but the jump command is still not visibly animating.
- No previous attempt has directly applied a temporary same-tile `posVec[1]` render-height bob.
- This avoids tile `xCurr`/`yCurr` writes, movement descriptor reactivation, and movement command polling for the emote.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test145.nds` and copied to Delta.
- `git diff --check` passed before and after the build.
- Verified `OverworldWildSpawnState` now stores `movementEmoteBasePosY` per spawn slot.
- Verified `OverworldWildSpawns_TryStartSpotEmote` saves `object->posVec[1]`, starts a 20-frame emote timer, plays `SEQ_SE_DP_KON`, and does not start a stock jump movement command.
- Verified `OverworldWildSpawns_TickSpotEmote` applies a triangular fixed-point offset up to `OW_WILD_SPAWNER_SPOT_HOP_PEAK_PIXELS` and restores the original `posVec[1]` when the emote ends.
- Verified reset paths restore `posVec[1]` if a slot is cleared while still emoting.

Runtime result:

- User reported no visible hop.

Learning:

- Directly changing `object->posVec[1]` from the spawner overlay does not produce a visible hop for these spawned Pokemon.
- The renderer likely derives the visible object height from another movement/render state, or overwrites `posVec[1]` before draw.
- Do not retry manual `posVec[1]` bobbing without new evidence.

### Attempt 49: Use WaitJumpSite Movement Command

Idea:

Use the default script movement command `WaitJumpSite` (`0x65`) directly for the spot emote. The user pointed out Lyra/Ethan perform an excited hop near the start of the game, and the script macro table has a specific same-tile waiting jump command distinct from the previously tested directional `Jump*Site` commands. Start `0x65` as a single movement command, drive it through the stable frame updater, and keep the confirmed-audible `SEQ_SE_DP_KON` sound.

Why this is new:

- Attempts 45 and 46 used `BIT_JUMP_START`.
- Attempt 47 used directional `Jump*Site` commands (`0x30`-`0x33`).
- Attempt 48 used manual `posVec[1]` height changes.
- No previous attempt has tried `WaitJumpSite` (`0x65`), which is a separate default movement command listed in `armips/include/scriptmacros.s`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test146.nds` and copied to Delta.
- `git diff --check` passed before and after the build.
- Verified the failed manual `posVec[1]` bob state was removed from `OverworldWildSpawnState`.
- Verified active spot emote code starts `OW_WILD_SPAWNER_SPOT_EMOTE_COMMAND` / `WaitJumpSite` (`0x65`) directly with `MapObject_StartMovementCommand` and `MapObject_SetSingleMovementActive`.
- Verified `OverworldWildSpawns_TickSpotEmote` drives the command through `OverworldWildSpawns_UpdateSpawnerMovementCommand` and falls back to active chase/flee after `OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES`.
- Verified the sound remains `SEQ_SE_DP_KON`.

Runtime result:

- User reported this produced the ground "smoke" that appears to be part of the hop visual presentation, but the Pokemon still did not visibly hop or jump.

Learning:

- `WaitJumpSite` reaches the movement/FX layer and can trigger the landing/smoke presentation on spawned Pokemon.
- `WaitJumpSite` alone does not provide the visible vertical hop for these objects.
- The stock excited-hop sequence likely pairs `WaitJumpSite` with another movement command that applies the vertical object motion.
- Do not retry `0x65` by itself.

### Attempt 50: LockDir Jump2 Smoke Release Sequence

Idea:

Run a multi-command spot-emote sequence instead of a single command. Decode of compiled script movement pointers found stock movement lists that use `LockDir -> Jump*2 -> ReleaseDir` for hop-like moments. Since Attempt 49 proved `WaitJumpSite` can produce the ground smoke, this attempt sequences `LockDir` (`0x47`), direction-specific `Jump*2` (`0x38`-`0x3B`), `WaitJumpSite` (`0x65`), and `ReleaseDir` (`0x48`) before entering chase/flee.

Why this is new:

- Attempts 45 and 46 used `BIT_JUMP_START`.
- Attempt 47 used a single directional `Jump*Site` command (`0x30`-`0x33`).
- Attempt 48 used manual `posVec[1]` height changes.
- Attempt 49 used only `WaitJumpSite` (`0x65`).
- No previous attempt has run a stock-style multi-command emote sequence with `LockDir`, `Jump*2`, smoke, and `ReleaseDir`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test147.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified `OverworldWildSpawnState` now stores per-slot emote step and emote direction state.
- Verified the active spot-emote sequence starts `LockDir`, then direction-specific `Jump*2`, then `WaitJumpSite`, then `ReleaseDir`.
- Verified the emote sequence is advanced by `OverworldWildSpawns_UpdateSpawnerMovementCommand` instead of retrying direct object height edits or `BIT_JUMP_START`.
- Verified the sound remains `SEQ_SE_DP_KON`.

Runtime result:

- User reported the Pokemon now visibly hops, but the hop is not in place; it hops while moving toward the player.

Learning:

- The stock `Jump*2` command family produces the visible lift animation on spawned Pokemon.
- `Jump*2` also advances the object toward the player, so it cannot be used directly for a same-tile spot emote.
- The successful visibility likely comes from the stock jump movement command path, not from `WaitJumpSite` alone.
- Do not retry direction-specific `Jump*2` as the spot emote unless the tile movement is intentionally desired.

### Attempt 51: LockDir JumpSite Smoke Release Sequence

Idea:

Keep the multi-command spot-emote machinery from Attempt 50, because that finally produced a visible hop, but replace the moving `Jump*2` command family (`0x38`-`0x3B`) with the same-tile `Jump*Site` command family (`0x30`-`0x33`). The sequence becomes `LockDir` (`0x47`), direction-specific `Jump*Site` (`0x30`-`0x33`), `WaitJumpSite` (`0x65`), and `ReleaseDir` (`0x48`) before chase/flee starts.

Why this is new:

- Attempt 47 used a single `Jump*Site` command without a stock-style `LockDir`/`ReleaseDir` wrapper and did not produce a visible hop.
- Attempt 49 used only `WaitJumpSite` and produced smoke but no visible hop.
- Attempt 50 used the wrapper plus `Jump*2`, producing the visible hop but also moving the Pokemon.
- No previous attempt has combined `LockDir`, direction-specific same-tile `Jump*Site`, `WaitJumpSite`, and `ReleaseDir`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test148.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified active code uses `OW_WILD_SPAWNER_SPOT_EMOTE_JUMP_SITE_COMMAND` / `0x30` as the emote jump command family.
- Verified the sequence still starts with `LockDir`, advances through the same frame-updated single-movement command path, then runs `WaitJumpSite` and `ReleaseDir`.
- Verified this does not reintroduce `BIT_JUMP_START` or direct `posVec[1]` edits.

Runtime result:

- User reported this still does not visibly hop.

Learning:

- The `LockDir`/`ReleaseDir` wrapper does not make the same-tile `Jump*Site` command family visibly hop on spawned Pokemon.
- Attempt 50's visible lift remains specific to the moving `Jump*2` command family so far.
- The next solution should explore more shipped movement examples and avoid retrying `Jump*Site` unless a different stock sequence provides new evidence.

### Attempt 52: Partner Pokemon JumpSite Wrapper

Idea:

Use a movement sequence copied from shipped partner-Pokemon movement examples instead of human NPC examples. A compiled script scan of `build/a012` found four directional variants in script file `2_163` applied to `obj_partner_poke` (`253`): `0x49 -> Jump*Site -> Freeze -> 0x4A`. Since spawned overworld Pokemon are created through the follower/special-object style path, this is a closer match than the earlier `LockDir`/`ReleaseDir` NPC examples. The spot emote now runs `0x49`, direction-specific `Jump*Site` (`0x30`-`0x33`), `Freeze` (`0x3E`), and `0x4A`, then enters chase/flee.

Why this is new:

- Attempt 47 used a single `Jump*Site` command.
- Attempt 51 used `LockDir -> Jump*Site -> WaitJumpSite -> ReleaseDir`.
- No previous attempt has used the unnamed `0x49`/`0x4A` wrapper found around stock partner-Pokemon `Jump*Site` movement.
- This is based on compiled shipped script movement lists, not just command macro names.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test149.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified active code uses the partner-Pokemon wrapper command sequence `0x49 -> Jump*Site -> Freeze -> 0x4A`.
- Verified the shipped-script evidence came from decoded `apply_movement` lists in `build/a012`, including `obj_partner_poke` (`253`) directional variants in script file `2_163`.
- Verified this does not retry `BIT_JUMP_START`, direct `posVec[1]` edits, `WaitJumpSite` alone, `LockDir -> Jump*Site -> WaitJumpSite -> ReleaseDir`, or moving `Jump*2`.

Runtime result:

- User reported jumping now works.

Learning:

- The partner-Pokemon wrapper sequence is the first confirmed same-tile visible hop path for spawned overworld Pokemon.
- The likely critical pieces are the unnamed `0x49` setup command and `0x4A` restore command around `Jump*Site`, matching the shipped `obj_partner_poke` movement examples.
- Keep using this wrapper for spot-emote jumps unless a future test reveals a regression.

### Attempt 53: Three-Speed Scale And Speed-3 Double Hop

Idea:

Remove logical speed `4` and speed `5`, because both were aliases to the same safe stock movement command family as speed `3`. Keep speed `1`, speed `2`, and speed `3` only. Set Pidgey to speed `3`, and use the now-confirmed partner-Pokemon hop wrapper twice for speed-3 Pokemon when they spot the player. Lower-speed Pokemon still hop once.

Why this is new:

- Attempt 45 removed speed `6`, but kept speed `4` and `5` as aliases.
- No previous attempt has collapsed the scale to the three distinct safe walk command families.
- Attempt 52 found the working same-tile hop sequence, but only played it once for every speed.
- No previous attempt has tied the number of spot-emote jumps to movement speed.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test150.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified speed `4` and speed `5` command constants and switch cases were removed from active source.
- Verified Pidgey now uses logical speed `3`.
- Verified speed `3` maps to `OW_WILD_SPAWNER_MOVEMENT_SPEED_3_COMMAND` / stock command family `0x10`; speed `1` and speed `2` remain `0x08` and `0x0C`.
- Verified speed-3 spawns set `movementEmoteJumpsRemaining` to `2`, while lower speeds set it to `1`.
- Verified the hop sound now plays from the jump step itself, so a speed-3 double-hop plays the sound twice.

Runtime result:

- User reported "Nice!" and requested keeping the jump behavior while adding a hop cry, tired behavior, and chill wandering.

Learning:

- The three-speed scale and speed-3 double-hop are good enough to build on.
- Keep Pidgey at speed `3` for current testing.

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

### Attempt 55: Tired WaitJumpSite Then Stat-Fell Sound

Idea:

Change the tired presentation so tiredness does not immediately play the sound and snap back to chill. When a Pokemon completes enough active chase/flee steps, put that slot into a distinct tired state, start only the default `WaitJumpSite` movement command (`0x65`), and keep battle detection suppressed while that tired command is running. When `WaitJumpSite` finishes, play `SEQ_SE_GS_PARAMETER_DOWN` as the stat-fell sound, then return the Pokemon to chill with the existing no-spot cooldown and brief wander pause.

Why this is new:

- Attempt 49 used `WaitJumpSite` as a spot-hop attempt and proved it could trigger the ground/smoke presentation, but it was not used as a tired-only emote.
- Attempt 54 played the tired sound immediately when the Pokemon became tired and did not run a tired movement-command animation first.
- No previous attempt has added a distinct tired state between active chase/flee and chill.
- No previous attempt has delayed the stat-fell sound until after a tired presentation command completes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test152.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified tiredness now starts `OW_WILD_SPAWNER_TIRED_EMOTE_COMMAND` / `0x65` (`WaitJumpSite`) instead of immediately entering chill cooldown.
- Verified tired slots use the distinct `OW_WILD_SPAWNER_SPOT_STATE_TIRED` state while the command is running.
- Verified `OverworldWildSpawns_TickTiredEmote` advances the single movement command through the existing frame-updated command path.
- Verified the stat-fell sound is `SEQ_SE_GS_PARAMETER_DOWN` and plays from `OverworldWildSpawns_StartTiredCooldown` after the tired command finishes or times out.
- Verified battle detection returns false while a slot is in the tired state.

Runtime result:

- Superseded by user request to try a different sound and explore follower-style chat/emotion bubbles instead of another `WaitJumpSite` presentation.

Learning:

- `WaitJumpSite` remains useful as a fallback, but the next investigation should move away from movement-command emotes and toward the follower emotion-bubble helper.

### Attempt 56: Tired Follower Emotion Bubble Helper

Idea:

Use the vanilla follower emotion-bubble task helper directly on spawned Pokemon when they become tired. Reference tracing found that `ScrCmd_597` calls `ov01_02203AB4(fieldSystem, partnerPokeObj, 0)`, and the normal follower interaction path can also call the same helper with ids `0..13` through `ov02_0224FB54`. The helper creates an overlay effect above the target map object, guarded by overlay slot `0x12`, instead of starting a map-object movement command.

Wire tired spawns to call `ov01_02203AB4` with a named `OW_WILD_SPAWNER_TIRED_BUBBLE_ID` constant, currently `0` because that is the vanilla script-command path shown after follower cries in `scr_seq_0163`. Keep `WaitJumpSite` as a fallback if the field context is not current. Replace the delayed tired sound with `SEQ_SE_PL_BALLOON05` so this test also tries a different tired sound.

Why this is new:

- Attempt 49 and Attempt 55 used `WaitJumpSite` (`0x65`), which is a movement command.
- Attempt 52 used the partner hop command sequence `0x49 -> Jump*Site -> Freeze -> 0x4A`, which is also a movement-command path.
- No previous attempt has exposed or called `ov01_02203AB4`.
- No previous attempt has used the follower emotion-bubble overlay slot or a named bubble id for spawned wild Pokemon.
- No previous tired attempt has used `SEQ_SE_PL_BALLOON05`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built successfully with `./docker-makerom.cmd`.
- `git diff --check` passed before build.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test153.nds`.

Runtime result:

- User reported no balloon appeared above the tired Pokemon.

Learning:

- Directly calling `ov01_02203AB4(fieldSystem, spawnedObject, 0)` is not enough to show the follower-style emotion balloon on a spawned wild Pokemon.
- The next attempt should not simply retry the same helper call or bubble id. It should verify whether the helper has a missing prerequisite, whether another wrapper passes different object/effect data, or whether the spawned object needs a different overlay/emote path.

### Attempt 57: Direct Follower Bubble Effect Creator

Idea:

Bypass the script-task wrapper `ov01_02203AB4` and call the lower-level bubble effect creator `ov01_02203A48(spawnedObject, bubbleId)` directly when a spawned Pokemon becomes tired. Reference tracing shows `ov01_02203AB4` only allocates a tiny environment and queues a `TaskManager` task; that task later calls `ov01_02203A48`, which does the real overlay-slot `0x12` effect creation. Since the spawned-wild movement logic runs from spawner/frame tasks rather than a vanilla script command, this tests whether the wrapper's queued task path was the part that failed silently.

Why this is new:

- Attempt 56 called only `ov01_02203AB4(fieldSystem, spawnedObject, 0)`.
- No previous attempt has exposed or called `ov01_02203A48` directly.
- This keeps the same vanilla follower bubble resources and effect slot, so it isolates the entry point instead of changing the visual asset or retrying a movement-command emote.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built successfully with `./docker-makerom.cmd`.
- `git diff --check` passed before build.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test154.nds`.

Runtime result:

- User reported it worked: a balloon message appeared above the tired Pokemon's head. The icon was a heart, which does not fit the intended tired state, but confirms the follower bubble effect can attach to spawned wild Pokemon.

Learning:

- Direct `ov01_02203A48(spawnedObject, 0)` is the first confirmed visible follower-balloon path for spawned wild Pokemon.
- The failed part of Attempt 56 was likely the queued `TaskManager` wrapper path, not the overlay resource/effect itself.
- Bubble id `0` currently shows a heart, so future icon work should test other ids instead of changing the now-proven direct entry point.

### Attempt 58: Silent Direct Tired Bubble

Idea:

Keep the now-confirmed direct follower bubble creator from Attempt 57, but suppress sound while the tired balloon appears. Reference disassembly shows the bubble effect init plays `SEQ_SE_DP_DECIDE` internally, so call `StopSE(SEQ_SE_DP_DECIDE)` immediately after `ov01_02203A48`. Also gate the separate delayed tired cooldown sound behind `OW_WILD_SPAWNER_TIRED_PLAY_COOLDOWN_SE`, currently disabled, so tired balloon presentation can be tested silently.

Why this is new:

- Attempt 57 proved direct `ov01_02203A48` displays a balloon, but still allowed the vanilla bubble init sound and the later tired cooldown sound.
- No previous attempt has exposed or called `StopSE`.
- No previous tired-balloon attempt has explicitly separated the visual balloon from both the vanilla `SEQ_SE_DP_DECIDE` sound and our own delayed tired sound.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/sound.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built successfully with `./docker-makerom.cmd`.
- `git diff --check` passed before build.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test155.nds`.

Runtime result:

- User reported the balloon is still just a heart. Sound result was not reported.

Learning:

- Sound controls do not affect the icon choice; the icon is still determined by `OW_WILD_SPAWNER_TIRED_BUBBLE_ID`.
- The next attempt should keep the direct `ov01_02203A48` entry point and change the bubble id.

### Attempt 59: Tired Bubble Id Probe Cycle

Idea:

Keep the confirmed direct follower bubble creator and sound suppression from Attempts 57 and 58, but stop hardcoding bubble id `0`. Add a small probe cycle that starts at id `1`, advances through id `13`, then wraps back to `1`. This skips the confirmed heart icon at id `0` and lets runtime testing map the remaining follower balloon icons without requiring one ROM build per id.

Why this is new:

- Attempts 56, 57, and 58 all used bubble id `0`.
- Attempt 57 proved the direct creator works, but did not vary the id.
- Attempt 58 changed sound behavior only and confirmed the icon stayed heart.
- No previous attempt has cycled or otherwise probed alternate follower bubble ids.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test156.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test156.nds`.
- `git diff --check` passed after the build.
- Verified tired bubbles now call `OverworldWildSpawns_GetTiredBubbleId()` instead of hardcoding `0`.
- Verified the probe cycles through ids `1` through `13`, then wraps back to `1`, intentionally skipping the confirmed heart icon at id `0`.
- Verified `sOverworldWildMovementDiagnosticLookCommand` records the bubble id used for the tired balloon.

Runtime result:

- User reported the icon changed from the heart, but the next observed balloon was a smiley face.

Learning:

- The bubble id parameter is confirmed to affect the displayed icon.
- Bubble id `1` appears to be a smiley face, so the next tired-icon probe should continue through ids `2` through `13` rather than returning to id `0` or `1`.

### Attempt 60: Skip Known Heart And Smiley Bubble Ids

Idea:

Keep the confirmed direct follower bubble creator and id probe, but start the probe at id `2` instead of id `1`. This avoids making a fresh test session show the already-mapped smiley face first, while still cycling through the remaining unknown ids through `13`.

Why this is new:

- Attempt 57 confirmed id `0` shows a heart through the direct creator.
- Attempt 59 confirmed id `1` appears to be a smiley face and proved the id argument controls the icon.
- No previous attempt has skipped both known non-tired icons and started the probe at id `2`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test157.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test157.nds`.
- `git diff --check` passed before the build.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN` is now `2`, so fresh sessions skip the known heart id `0` and smiley id `1`.
- Verified the probe still wraps through `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MAX` / `13`.

Runtime result:

- User reported the next observed balloon was an angry face.

Learning:

- Bubble id `2` appears to be an angry face.
- Angry does not fit the intended tired state, so the probe should continue from id `3`.
- The known icon ids should be named in code as they are discovered so future behavior can use them directly.

### Attempt 61: Name Known Bubble Ids And Skip Angry

Idea:

Define the discovered follower bubble ids in source as reusable names: heart `0`, smile `1`, and angry `2`. Then move the active tired probe start to the first still-unknown id, `3`, while keeping the same direct `ov01_02203A48` creator and sound suppression.

Why this is new:

- Attempt 57 confirmed id `0` shows a heart.
- Attempt 59 confirmed id `1` appears to be a smiley face.
- Attempt 60 confirmed id `2` appears to be an angry face.
- No previous attempt has codified the discovered id map in source or started the probe at id `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test158.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test158.nds`.
- `git diff --check` passed before the build.
- Verified source now defines `OW_WILD_SPAWNER_BUBBLE_ID_HEART`, `OW_WILD_SPAWNER_BUBBLE_ID_SMILE`, and `OW_WILD_SPAWNER_BUBBLE_ID_ANGRY`.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN` now derives from `OW_WILD_SPAWNER_BUBBLE_ID_ANGRY + 1`, so fresh sessions start at id `3`.

Runtime result:

- User reported this build appeared to get a different icon each time, then mapped the remaining ids:
- `3`: Sad
- `4`: Mildly happy
- `5`: Angry and shaking head / disapproval
- `6`: Music note
- `7`: Question mark
- `8`: Exclamation mark
- `9`: Water droplet / sweat / nervousness
- `10`: Screaming in despair
- `11`: Poison
- `12`: Ellipsis
- `13`: Sleep

Learning:

- Attempt 61's apparent randomness was the intentional id cycle through ids `3` through `13`.
- The full follower bubble id range is now mapped.
- The water droplet at id `9` fits the tired state best.

### Attempt 62: Use Water Droplet Tired Bubble

Idea:

Turn off the tired bubble probe now that all ids are mapped. Define named constants for every discovered follower bubble id, set `OW_WILD_SPAWNER_TIRED_BUBBLE_ID` to `OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET`, and keep the direct `ov01_02203A48` creator plus sound suppression from the working bubble path.

Why this is new:

- Attempts 57 through 61 were discovery/probe builds.
- Attempt 61 mapped the remaining ids and identified water droplet id `9` as the best tired icon.
- No previous attempt has disabled the probe and used a stable water-droplet tired bubble.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test159.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test159.nds`.
- `git diff --check` passed before the build.
- Verified source defines named constants for all discovered follower bubble ids `0` through `13`.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE` is disabled.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID` is set to `OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET`.

Runtime result:

- User reported Mankey still blinks / becomes invisible when on trees.
- User clarified that the assumption "headbutt tree tiles themselves are unsafe render surfaces, so Mankey should use nearby landing/perch tiles instead" is wrong.

Learning:

- Boundary-only cleanup did not solve the tree-state blinking/invisibility.
- Do not pursue a tree-anchor rewrite that moves canopy hoppers to adjacent landing/perch tiles based on the rejected "tree tile render surface" assumption.
- Next attempt should preserve the design that Mankey is on the tree, and investigate the movement/object/render state transition that makes it blink while there.

### Attempt 63: Behavior Profile Resolver

Idea:

Replace the current scattered movement constants with a composable behavior profile. The profile contains `chill_State`, `alert_State`, `alertness`, `attentive_State`, `stamina`, `tired_State`, `rest_Time`, `max_speed`, and `range`. Resolve behavior in this order: default profile, optional behavior-class override, then species-specific override. Keep the default profile aligned with the current working behavior, move Pidgey's speed into the species override table, and keep tired Pokemon on the mapped water-droplet bubble.

Why this is new:

- Attempts 54 and 55 added tired/chill behavior directly through hardcoded counters and constants.
- Attempts 57 through 62 focused on tired bubble presentation and icon mapping.
- No previous attempt has introduced a data-driven behavior profile with default, behavior-class, and species-specific override layers.
- No previous attempt has made stamina spending depend on `max_speed`.
- No previous attempt has made movement range, alertness, rest time, attentive movement, chill behavior, and tired presentation resolve from one behavior contract.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test160.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test160.nds`.
- `git diff --check` passed before the build.
- Verified `OverworldWildBehaviorProfile` contains `chillState`, `alertState`, `alertness`, `attentiveState`, `stamina`, `tiredState`, `restTime`, `maxSpeed`, and `range`.
- Verified profile resolution merges default profile, behavior-class override, then species-specific override.
- Verified Pidgey's speed is now supplied by the species override table instead of a direct species switch in the movement-speed function.
- Verified movement range, alertness, attentive chase/flee/none decision, chill wandering, stamina spending, tired rest duration, and tired bubble id are read from the resolved profile.
- Verified completed attentive moves spend stamina equal to `maxSpeed`, capped at the profile's `stamina`.
- Verified cleared spawn slots reset their stored behavior class.

Runtime result:

- Superseded before user runtime testing.
- User clarified the intended hierarchy is `Default behavior -> Behavior class override -> Behavior variable override`, not `Default behavior -> Behavior class override -> species-specific override`.

Learning:

- Avoid repeating the Attempt 63 species-specific third layer. Species, broader groups, terrain/pool, level, shiny state, and other context should be used to select behavior classes or match behavior-variable overrides; the final layer itself is a generic variable override layer.

### Attempt 64: Separate Behavior Class Rules From Behavior Variable Overrides

Idea:

Correct the resolver hierarchy to `Default behavior -> Behavior class override -> Behavior variable override`. Add one rule table for assigning behavior classes from spawn context, and a separate ordered rule table for variable overrides. A Pokemon can therefore be classified as `Skittish` by species/group/pool/etc. and still receive independent variable overrides like `max_speed = 1`.

Why this is new:

- Attempt 63 introduced the behavior profile contract, but its final layer was incorrectly species-specific.
- No previous attempt has separated behavior-class assignment from post-class variable overrides.
- No previous attempt has added broad group matching, such as baby Pokemon, as behavior input.
- The proposed hierarchy matches the user's corrected design: default values first, class changes second, and variable overrides last.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test161.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test161.nds`.
- `git diff --check` passed before the build.
- Verified `OverworldWildBehaviorClassRule` assigns behavior classes from spawn context separately from variable overrides.
- Verified `OverworldWildBehaviorVariableOverride` applies matched behavior variables after the default profile and behavior-class override.
- Verified the resolver now merges `default behavior -> behavior class override -> behavior variable override`.
- Verified baby Pokemon are grouped through `OW_WILD_BEHAVIOR_GROUP_BABY`, assigned `OW_WILD_BEHAVIOR_CLASS_SKITTISH`, and given a separate `maxSpeed` variable override.
- Verified Pidgey's test speed is still present, but now as a behavior-variable override rather than a species-specific resolver layer.

Runtime result:

- User reported:
  - Mankey still does not visibly travel; it blinks to trees or stands still invisible in trees.
  - Mankey is invisible.
  - Leaving the route still does not avoid the crash/freeze.

Learning:

- Clean straight-run target selection plus the internal jump starter did not solve the visibility problem.
- Removing movement-list fallback and phantom boundary cleanup was not enough; the object still becomes invisible around the tree/perch state.
- The next attempt should stop testing hop travel and isolate the spawn/anchor visibility state first.

### Attempt 65: A-Button Facing Interaction Starts Spawn Battle

Idea:

Add a deliberate A-button battle path for spawned overworld Pokemon. Keep the existing contact/settle detector for automatic battles, but add a frame-polled A-button check that finds the tile the player is facing and starts a battle if any active spawned Pokemon occupies that tile. This path should ignore the automatic contact filters such as tired cooldown, flee grace, and in-progress movement, because pressing A is an intentional interaction.

Why this is new:

- Attempts 35 through 38 focused on contact battle timing and settle retries after player/spawn movement.
- No previous attempt has used A-button input to start a spawned-Pokemon battle.
- No previous attempt has matched the player's facing tile against active spawned Pokemon as a battle trigger.
- No previous attempt has restarted the movement frame task after battle cleanup using the cleanup script's current `FieldSystem`.

Files/symbols:

- `include/overworld_wild_spawns.h`
- `include/overworld_wild_spawns_internal.h`
- `src/script_new_cmds.c`
- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test162.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test162.nds`.
- `git diff --check` passed before the build.
- Verified `OverworldWildSpawns_TryStartBattleForSlot` centralizes pending battle setup for both contact and A-button battle starts.
- Verified `OverworldWildSpawns_TryStartBattleFromAButton` polls a new A-button press, derives the player's facing tile from the player map object's `curFacing`, and starts battle for any active spawned Pokemon on that tile.
- Verified the A-button path does not call `OverworldWildSpawns_IsTouchingPlayer`, so tired cooldown, flee grace, and active movement-command filters do not block intentional A interactions.
- Verified battle cleanup now receives the script context's `FieldSystem` and restarts the movement frame task if active spawned Pokemon remain on the current map.

Runtime result:

- User reported Mankey is spawning on the wrong tree tiles. The screenshot shows the forced `594,388` point is on the side/shoulder canopy art below the desired flat top-cap tiles.

Learning:

- Removing the follower render bundle was still a separate, valid safety fix, but it did not answer the tile-class question because the test coordinate was visually wrong.
- Do not keep assuming `headbutt anchor Y - 1` is a tree-top/canopy-cap tile. The Route 29 headbutt archive shows this cluster has anchors at `(594,389)` and `(595,389)`, so the next non-repeating probe should move one more tile up to the likely top-cap row.

### Attempt 66: Implement Behavior Profile Table Semantics

Idea:

Make the behavior resolver match the requested profile table directly:

- Default: wander at max speed 1, show a question bubble when alert, then return to chill with no self-start battle.
- Aggressive: wander at max speed 2, hop plus angry speech when alert, chase the player, and start battle on contact while attentive.
- Skittish: wander at max speed 2, hop plus exclamation speech when alert, flee from the player, then show the water droplet tired bubble after stamina is spent.

Also rename `restTime` to `restRate`, keep Pidgey as an aggressive speed-3 variable override for testing, and make alertness use a facing cone inside radius 3 instead of radius-only spotting.

Why this is new:

- Attempt 63 created the general behavior profile contract, but left the older default chase/stamina values in place.
- Attempt 64 separated behavior-class rules from variable overrides, but did not implement the new default/aggressive/skittish table semantics.
- Attempt 65 added intentional A-button battle starts, but did not change which behavior profiles can start automatic battles.
- No previous attempt has made default Pokemon speech-only and A-button-only for battles while letting aggressive Pokemon self-start battles only during attentive chase.
- No previous attempt has required a facing cone for alertness.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test163.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test163.nds`.
- `git diff --check` passed before and after the build.
- Verified `OverworldWildBehaviorProfile` now uses `restRate` instead of `restTime`.
- Verified the default profile is speech-only (`PONDER`) with no attentive state, stamina, tired state, or automatic battle start.
- Verified the aggressive profile uses angry hop speech, chase-with-battle attentive state, stamina `12`, water droplet tired state, rest rate `1`, max speed `2`, and range `8`.
- Verified the skittish profile uses scared hop speech, flee attentive state, stamina `12`, water droplet tired state, rest rate `1`, max speed `2`, and range `8`.
- Verified Pidgey is assigned the aggressive class and then receives a max-speed `3` behavior-variable override.
- Verified alert checks use `OverworldWildSpawns_IsPlayerInFacingCone` with radius `3`.
- Verified contact battles require active aggressive attentive behavior; A-button facing interaction still starts a battle for any spawned Pokemon.

Runtime result:

- User reported Mankey is still hidden by the headbutt-tree canopy on `test379.nds`.

Learning:

- `LocalMapObject::unkA0` draw mode alone does not make spawned Mankey render above canopy-priority tiles.
- Follow-up disassembly showed both draw modes route through overlay 1's draw mode table and still apply the same `0x1000` sprite priority value.
- Avoid repeating the draw-mode-only probe. The next useful direction is a stock draw-callback/descriptor probe or a real sprite priority override.

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

### Attempt 102: Fled Battle Sends Spawn To Tired State

Idea:

When the player runs from a battle started by a spawned overworld Pokemon, keep that Pokemon spawned but put that slot into the behavior tired state. This makes the same Pokemon visibly recover instead of immediately returning to normal chase/spot behavior.

Implementation shape:

- Use the existing battle cleanup path because it still has `pendingSlot` and the final battle result.
- On `OverworldWildSpawns_BattleResultIsPlayerFlee`, keep the existing `OW_WILD_FLEE_GRACE_STEPS` protection.
- If the pending slot still has a current map object, set `movementFieldSystem` to the cleanup `FieldSystem *` and call `OverworldWildSpawns_StartTiredEmote`.
- Leave non-flee cleanup unchanged: defeated/caught/non-flee outcomes still clear the spawn slot.
- Give `StartTiredEmote` a fallback tired profile for Pokemon whose normal behavior has `tiredState = none`, so default/A-button-only Pokemon can still visibly become tired after the player runs.

Why this is new:

- Earlier flee cleanup only set `battleGraceSteps`, which prevented immediate re-battle but did not put the spawn into a tired/resting state.
- Attempts 53 through 62 built the tired-state presentation and cooldown system, but those transitions came from movement stamina, not from battle cleanup.
- The saved-shiny HP work preserved the same overworld Pokemon after running, but did not change its movement state after the run.
- No previous attempt has used `pendingSlot` during battle cleanup to transition the surviving spawn into tired state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_OverlayCleanupPendingBattle`
- `OverworldWildSpawns_StartTiredEmote`
- `OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd` and copied to Delta as `test200.nds`.
- Verified flee cleanup still keeps `OW_WILD_FLEE_GRACE_STEPS`.
- Verified flee cleanup calls `OverworldWildSpawns_StartTiredEmote` for the current `pendingSlot`.
- Verified default/no-tired-profile Pokemon fall back to a water-droplet tired state with `OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME`.
- Verified non-flee cleanup still clears the spawn slot.
- Build warnings were pre-existing unused-parameter/unused-symbol diagnostics in battle script, overlay diagnostics, and `OverworldWildSpawns_Clear`.

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

### Attempt 104: Aggressive Ram Cardinal Alert Line

Idea:

Let aggressive ram alertness work in every cardinal direction instead of only when the Pokemon is already facing the player. For ram profiles, if the player is directly north, south, east, or west within `profile.alertness`, the Pokemon should enter its alert state and lock the ram direction toward the player.

Implementation shape:

- Add `OverworldWildSpawns_IsPlayerInCardinalLine`, which succeeds when the player is on the same row or column within alertness.
- Add `OverworldWildSpawns_IsPlayerInAlertLine` as the behavior-aware alert gate.
- Keep non-ram behavior profiles on the existing `OverworldWildSpawns_IsPlayerInFacingLine` rule.
- Route `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE` through the new cardinal-line gate.
- Keep the existing `spotDirections[0]` direction assignment, so ram still starts in the cardinal direction toward the player.

Why this is new:

- Attempt 66 introduced a facing cone.
- Attempt 70 changed alertness to a strict facing line.
- No previous attempt made only aggressive ram use a four-direction cardinal alert line while preserving facing-line alertness for other profiles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsPlayerInCardinalLine`
- `OverworldWildSpawns_IsPlayerInAlertLine`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test202.nds`.
- Verified `OverworldWildSpawns_IsPlayerInAlertLine` keeps non-ram profiles on `OverworldWildSpawns_IsPlayerInFacingLine`.
- Verified `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE` uses `OverworldWildSpawns_IsPlayerInCardinalLine`, allowing same-row or same-column alerting in all four cardinal directions.
- Verified the alert start still passes `spotDirections[0]` into `OverworldWildSpawns_TryStartSpotEmote`, so aggressive ram locks its initial ram direction toward the player.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 105: Rename Aggressive Chase Profile

Idea:

Rename the normal chase/battle behavior profile from `aggressive` to `agressiveChase`, while keeping the separate aggressive-ram behavior name unchanged.

Implementation shape:

- Rename `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE` to `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE`.
- Keep the numeric behavior class value as `2`, so existing behavior-class table indexing remains unchanged.
- Update Pidgey's behavior-class rule to use `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE`.
- Leave `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM` unchanged.

Why this is new:

- Earlier attempts split `aggressive_ram` away from the normal aggressive chase behavior, but did not rename the normal chase behavior profile.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE`
- `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`

Verification:

- `git diff --check` passed.
- Verified active source now defines `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE` and uses it for Pidgey's behavior-class rule.
- Verified the separate `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM` symbol was not renamed.

Runtime result:

- Not applicable; symbol-only rename.

Learning:

- This is a naming-only cleanup; behavior class value `2` and runtime behavior remain unchanged.

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
