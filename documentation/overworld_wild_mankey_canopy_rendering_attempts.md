# Mankey Canopy Rendering And Layering Attempts

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- This is the do-not-repeat pile for making Mankey appear above canopy using map-object render knobs.
- Height, follower flags, draw callbacks, OAM/depth fields, proxies, and late map-object redraw did not solve the layer problem.
- Bubble/effect-owned rendering remains the most useful clue if this is revisited.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 2 | 2 | Chase Logic Using `object->fsys` |
| 3 | 3 | Publish Active `FieldSystem *` Globally And Add Scratch Init |
| 4 | 4 | Replace `MIi_CpuClearFast` With Direct Scratch Clears |
| 7 | 7 | Alias Movement `47` To Stock Movement `3` Descriptor |
| 8 | 8 | Make Stale Movement `47` No-Op And Spawn Fresh Objects With Stock Movement `3` |
| 9 | 9 | Disable Spawner Step Actions After Map-State Refresh |
| 10 | 10 | Disable The Entire Overworld-Wild Player-Step Hook |
| 11 | 11 | Load Overlay Entry But Do Not Call Overlay Step |
| 12 | 12 | Call Overlay Step But Return Immediately |
| 13 | 13 | Read-Only UpdateMapState Diagnostic |
| 14 | 14 | UpdateMapState Map Writes Without Clear |
| 15 | 15 | Read Spawn State Without Writing It |
| 19 | 19 | Re-enable Stale-Slot Cleanup Only |
| 20 | 20 | Re-enable Distance Despawn Only |
| 21 | 21 | Re-enable Touch-Battle Detection Only |
| 22 | 22 | Re-enable Refill And Spawn Only |
| 23 | 23 | Restore Ambient Cry With Stock Movement |
| 24 | 24 | Spawner-Driven Movement Param Tick |
| 25 | 25 | Spawner-Driven Coordinate Read And Direction Calculation |
| 29 | 29 | Spawner-Owned Movement Command Update And Clear |
| 30 | 30 | Obvious Spawner-Driven Tile Movement |
| 31 | 31 | Frame Task Movement Command Updates |
| 32 | 32 | Per-Slot Movement Ownership And Battle Reset |
| 33 | 33 | Range 8 And Idle Frame Chase |
| 34 | 34 | One-At-A-Time Overlap Untangle |
| 35 | 35 | Guard Idle Frame Context And Moving Battle Contact |
| 36 | 36 | Frame Task Battle Detection |
| 37 | 37 | Post-Movement Battle Settle Window |
| 42 | 42 | Proximity-Only Battle Settle |
| 43 | 43 | Cap High Speeds To Fluent Walk Command |
| 45 | 45 | Remove Redundant Speed 6 And Add Spot Emote |
| 46 | 46 | Short Independent Spot Range |
| 47 | 47 | Use Jump-Site Movement Command For Spot Emote |
| 48 | 48 | Manual PosVec Height Bob For Spot Emote |
| 49 | 49 | Use WaitJumpSite Movement Command |
| 50 | 50 | LockDir Jump2 Smoke Release Sequence |
| 53 | 53 | Three-Speed Scale And Speed-3 Double Hop |
| 54 | 54 | Hop Cry, Tired Cooldown, And Chill Wander |
| 62 | 62 | Use Water Droplet Tired Bubble |
| 63 | 63 | Behavior Profile Resolver |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
| 66 | 182 | Tree-Anchor Single Stock Jump Probe |
| 67 | 183 | Tree-Anchor Stock Jump2 Probe |
| 69 | 185 | Chained Jump2 Without Midpoint Tile Normalization |
| 70 | 186 | Chained Jump2 With Logical-Only Midpoint Commit |
| 75 | 191 | Production Canopy Long-Jump Carrier |
| 83 | 226 | One Row Above Archive Mankey Tree-Top Target |
| 84 | 227 | Restore Archive MinY Tree-Top Logic After Too-High Row |
| 85 | 228 | Sparse Archive Tree-Top Row Lift |
| 88 | 229 | Live Blocked-Row Tree-Top Confirmation |
| 89 | 224 | Mankey Tree-Top Late Map-Object Redraw Effect |
| 90 | 225 | Mankey Tree-Top Effect-Owned Marker Canary |
| 91 | 214 | Bias Forced Verifier Ahead Of Player |
| 92 | 242 | Charmander Canopy Locator Probe |
| 93 | 260 | Charmander Probe Fallback Marker |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 99 | 238 | Generic Headbutt Tree-Top Location Filter |
| 100 | 213 | Score Forced Verifier By Resolved Perch |
| 101 | 65 | A-Button Facing Interaction Starts Spawn Battle |
| 102 | 197 | Route 29 Top-Cap Coordinate Probe |
| 103 | 198 | Route 29 Upper Top-Cap Coordinate Probe |
| 104 | 199 | Actual Headbutt Anchor With Render-Only Tree-Top Offset |
| 105 | 200 | Exact Headbutt Tile Occupancy, No Graphic Offset |
| 106 | 201 | Guaranteed Forced Headbutt Mankey Spawn |
| 107 | 202 | Spawn On Row Above Headbutt Tree Footprint |
| 108 | 203 | Lower Tree-Top Test Tile And Preserve Forced Idle Visibility |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 110 | 224 | Mankey Tree-Top Stock Large-Pokemon Draw Callback |
| 111 | 225 | Mankey Tree-Top Stock Helper Draw Callback |
| 112 | 226 | Mankey Tree-Top Post-Draw Sprite Priority Probe |
| 113 | 227 | Mankey Tree-Top Live Sprite Depth Zero Probe |
| 114 | 228 | Mankey Tree-Top Synced Visual Proxy |
| 115 | 229 | Mankey Tree-Top BG Layer Identification Probe |
| 116 | 236 | Mankey Tree-Top Effect-Layer Bubble Probe |
| 117 | 237 | Cache Mankey Tree-Top Archive Predicate |
| 118 | 238 | Gate Mankey Bubble Probe On Final Tree-Top Landing |
| 119 | 239 | Align Mankey Tree-Top Settled Rows With Target Rows |
| 129 | 249 | Target Two Tiles Above Headbutt Archive Row |
| 130 | 250 | Follower-Sprite Tree-Top Proxy Probe |
| 131 | 251 | Prefer Unblocked Direct Mankey Tree-Top Directions |
| 132 | 252 | Generic Field Effect Probe For Tree-Top Mankey |
| 133 | 253 | Down-First Mankey Tree-Top Target Selection |
| 134 | 254 | Restore Archive MinY As Strict Tree-Top Row |
| 135 | 255 | Snap Final Canopy Landing After Partner Restore |
| 136 | 256 | Skip Final Mankey Tree-Top Partner Restore |
| 137 | 257 | Re-enable Tree-Top Anchored Effect Probe After Movement Fix |
| 138 | 258 | Late-Draw Mankey Through Field-Effect Render Callback |
| 139 | 234 | Direct Straight Headbutt Tile Target For Mankey |
| 141 | 233 | Split Mankey Tree Targets From Settled Perches |
| 142 | 230 | Mankey 2x6 Headbutt Tree Top-Row Targeting |
| 143 | 231 | Prefer Nearest Direct Mankey Tree-Top Jump |
| 144 | 232 | Include Exposed Archive Top Row For Mankey Tree Targets |
| 145 | 67 | Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram |
| 146 | 68 | Tune Onix Ram Start, Range, Crash State, And Feedback |
| 148 | 70 | Restore Normal Ram Movement And Make Alertness A Facing Line |
| 149 | 71 | Keep Normal Ram Walking But Borrow Site Visual Parameter |
| 151 | 73 | Run WaitJumpSite After Each Onix Ram Step |
| 152 | 74 | Direct Boulder Step Effect Helper During Normal Ram Movement |
| 161 | 83 | Try Paired HGSS Push Sound `SEQ_SE_GS_PUSH03` |
| 163 | 85 | Load Push Sound With `NNS_SND_ARC_LOAD_ALL` |
| 164 | 86 | Try Field Rock Sound `SEQ_SE_GS_IWAOTOSHI02` |
| 166 | 88 | Use Field Wall-Hit Sound And Shake The Crashed Overworld Object |
| 167 | 89 | Non-Locking Object Shake And `SEQ_SE_DP_GASHIN` Crash Thud |
| 168 | 90 | Non-Locking Object Shake And HGSS Gondola Wall-Hit Sound |
| 169 | 91 | Sound-Only `SEQ_SE_GS_IWA_TRAP` Crash Feedback |
| 170 | 92 | Sound-Only `SEQ_SE_GS_IWAOTOSHI01` Crash Feedback |
| 171 | 93 | Restore Decent Crash Sound And Shorten Speech-Only Alert |
| 172 | 94 | C-Side Ram Crash Object Wobble |
| 173 | 95 | Direct Camera Shake Work Driven By SysTask |
| 174 | 96 | Stronger Ram Crash Object Wobble And Shorter Speech Alert |
| 177 | 99 | Player Wall-Hit Ram Crash Sound |
| 178 | 100 | Ram Crash-Only Automatic Battle Trigger |
| 179 | 101 | Follower Object-ID Fallback For Ram Crash Battles |
| 180 | 102 | Fled Battle Sends Spawn To Tired State |
| 182 | 104 | Aggressive Ram Cardinal Alert Line |
| 184 | 106 | Aipom-Only Playful Chase Pass |
| 185 | 107 | Playful Previous-Tile Hard Guard |
| 186 | 108 | Direction-History Playful Backtrack Guard |
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
| 206 | 128 | Phantom Stalker Hidden Movement |
| 207 | 129 | Phantom Flicker And Follower Behind Targeting |
| 208 | 130 | Phantom Blink Behind Player Then Flicker Chase |
| 209 | 131 | Faster Phantom Destination Flicker And Battle Reveal |
| 210 | 132 | Deterministic Phantom Flicker Pulse |
| 211 | 133 | Refresh Phantom Sprite On Visible Flicker Phase |
| 212 | 134 | Phantom Flicker Apparition Object |
| 213 | 135 | Phantom Teleport Alert Build-Up |
| 214 | 136 | Active Phantom 60 Percent Flicker Loop |
| 215 | 137 | Active Phantom Real-Object Flicker |
| 216 | 138 | Recreate Phantom Object After Teleport |
| 217 | 139 | Origin/Destination Teleport Flicker And Face Player |
| 218 | 140 | Active Phantom Teleport-Step Movement |
| 219 | 141 | Front-Of-Player Phantom Teleport Movement |
| 220 | 142 | One-Second Pause After Active Phantom Teleport |
| 222 | 144 | Visible Teleport Pauses And Faster Alert Teleport |
| 223 | 145 | Restrict Directional Bump Battles To Phantom Stalkers |
| 226 | 148 | Phantom Chill Wander Teleportation |
| 229 | 151 | Materialize Visible Phantom Flicker For A-Button Battles |
| 230 | 152 | Disable Phantom Stalk Alert-State Teleport |
| 231 | 153 | Mankey Canopy Hopper Headbutt-Tree Profile |
| 232 | 154 | Canopy Hopper Attentive Ambush Target |
| 233 | 155 | Canopy Hopper Tired Return-To-Tree Case |
| 235 | 157 | Universal Canopy Hopper Return-To-Tree Priority |
| 240 | 162 | Custom Rendered Far Canopy Hop |
| 241 | 163 | Canopy Helper Object Far-Hop Visual |
| 242 | 164 | Helper Object Stock-Jump Segments |
| 243 | 165 | Real Object Stock-Jump Chain Without Segment Wait |
| 244 | 166 | Real Object Deferred Logical Commit Render-Hop |
| 245 | 167 | Horizontal WaitJump Command Probe |
| 246 | 168 | Strict Five-To-Seven Tile Canopy Hop Probe |
| 247 | 169 | Recreate Real Canopy Object After Each Segment |
| 248 | 170 | Canopy Hopper Always-Visible Invariant |
| 249 | 171 | Boundary-Only Canopy Visual Cleanup |
| 253 | 175 | Recreate Final Tree Landing Without Manual Tile Rewrite |
| 254 | 176 | Use One Manual Render Hop For Full Canopy Distance |
| 255 | 177 | Canopy Hopper Vanilla Movement-List Task |
| 257 | 179 | Direct Engine-Owned Long Canopy Jump |
| 258 | 180 | Clean Straight-Run Canopy Driver |
| 259 | 192 | Range-Gated Canopy Long-Jump Carrier |
| 261 | 194 | Forced Mankey Tree-Tile Occupancy Render Probe |
| 262 | 195 | Forced Mankey Canopy-Top Occupancy Render Probe |
| 263 | 196 | Normal-Path Canopy-Top Occupancy Probe |
| 264 | 216 | Remove Forced Mankey Canopy Tests And Restore Land Mankey |
| 268 | 220 | Mankey Tree-Top Render Height Lift |
| 269 | 221 | Mankey Tree-Top Priority Flag Probe |
| 270 | 222 | Mankey Failed Tree-Path Backoff And Target Grid |
| 271 | 223 | Mankey Tree-Top Draw-Mode Probe |
| 272 | 232 | Mankey Low Land Row Tree-Top Correction |
| 277 | 238 | Generic Headbutt Tree-Top Location Filter |

## Original Attempt Sections

### Attempt 2: Chase Logic Using `object->fsys`

Idea:

Use `LocalMapObject::fsys` to locate the player and compute chase/flee directions. Start movement with stock movement-command helpers.

Files/symbols:

- `src/overworld_wild_movement.c`
- `include/map_events_internal.h`
- `rom.ld`

Helper path:

- `MapObject_IsSingleMovementActive`
- `MapObject_UpdateMovementCommand`
- `MapObject_ClearSingleMovementActive`
- `MapObject_GetParam`
- `MapObject_SetParam`
- `MapObject_GetCurrentX`
- `MapObject_GetCurrentY`
- `GetPlayerXCoord`
- `GetPlayerYCoord`
- `MapObject_IsMovementDirectionBlocked`
- `MapObject_MovementCommandFromDirection`
- `MapObject_StartMovementCommand`
- `MapObject_SetSingleMovementActive`

Runtime result:

- Pokemon spawned and were stable.
- Pokemon did not move.

Learning:

- `object->fsys` is likely missing, stale, or not reliable for these special spawned objects.
- The no-movement result does not prove the movement-command helpers are safe, because the code probably returned before starting movement.

Do not repeat:

- Do not rely only on `LocalMapObject::fsys` for spawned wild Pokemon unless the struct field is independently verified at runtime.

### Attempt 3: Publish Active `FieldSystem *` Globally And Add Scratch Init

Idea:

Have the spawner publish the active `FieldSystem *` to boot-resident movement code, then initialize movement scratch state similarly to stock wander. Also add a facing fallback when blocked, so a ticking but blocked callback shows visible activity.

Files/symbols:

- `src/overworld_wild_movement.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/overworld_wild_movement.h`

Runtime result:

- Built as `test98.nds`.
- User reported a crash after taking a single step.

Learning:

- Giving the movement code a real `FieldSystem *` likely allowed the chase path to advance farther than Attempt 2.
- The crash could have been from scratch initialization, movement-state manipulation, blocked-direction checks, command start/update, or the newly reachable player/object coordinate path.

Do not repeat:

- Do not re-enable the full package of global `FieldSystem *` plus scratch init plus movement command helpers all at once.
- Reintroduce only one helper group at a time after the idle diagnostic result is known.

### Attempt 4: Replace `MIi_CpuClearFast` With Direct Scratch Clears

Idea:

Remove the external `MIi_CpuClearFast` call from custom movement init and clear `object->unkD8` with direct word stores.

Files/symbols:

- `src/overworld_wild_movement.c`

Verification:

- Built as `test99.nds`.
- Verified `OverworldWildCustomMovement_Init` no longer calls the external clear helper.
- Verified movement slot `47` still points at the custom descriptor.

Runtime result:

- User reported the crash happened before issuing a player movement command.

Learning:

- The external clear helper was not the only issue.
- Manual scratch clearing plus the rest of the active update/init path is still not safe.
- The crash may occur during object creation, init, early update, or a helper called before the player moves.

Do not repeat:

- Do not treat scratch clearing as solved until isolated.
- Do not retry manual scratch clear together with active movement polling and command helpers without a narrower test.

### Attempt 7: Alias Movement `47` To Stock Movement `3` Descriptor

Idea:

Keep spawned wild Pokemon using movement ID `47`, but patch movement table slot `47` to point at the existing stock movement `3` descriptor in ARM9 (`0x020FD170`) instead of the custom overlay 129 descriptor.

Why this is new:

- Earlier attempts pointed slot `47` at custom overlay 129 descriptors.
- This attempt tests whether save/map load is stable when slot `47` resolves to a known-good ARM9-resident descriptor.

Files/symbols:

- `armips/asm/overworld_wild_movement.s`

Expected verification:

- Built ROM should have ARM9 movement slot `47` at `0x020FD2B0` pointing at `0x020FD170`.
- Slot `47` descriptor words should match stock movement `3`.
- Custom overlay callbacks may still exist in overlay 129, but movement `47` should not reference them.

Verification:

- Built as `test102.nds`.
- Slot `3` at `0x020FD200` points at `0x020FD170`.
- Slot `47` at `0x020FD2B0` also points at `0x020FD170`.
- Slot `3` and slot `47` descriptor words both read `0x00000003 0x020613A1 0x020613F9 0x0205FCBD 0x0205FCC1`.

Runtime result:

- User reported the save loaded, then the game crashed after a single player step.

Learning:

- Aliasing movement `47` to stock movement `3` likely avoids the save-load crash.
- The step-time crash remains.
- A plausible cause is that existing saved movement-47 objects now run stock movement-3 update without having gone through stock movement-3 init.
- Another plausible cause is that using movement ID `47` for freshly created objects is unsafe in some non-descriptor engine path.

Do not repeat:

- Do not alias stale movement `47` directly to active stock movement `3` again unless the object's movement scratch/init state is also migrated.

### Attempt 8: Make Stale Movement `47` No-Op And Spawn Fresh Objects With Stock Movement `3`

Idea:

Split stale-object safety from fresh-spawn behavior:

- Patch movement table slot `47` to stock movement `0`'s no-op descriptor at `0x020FCEC8`.
- Create new overworld wild spawn objects with stock movement `3` instead of movement `47`.

Why this is new:

- Attempt 7 aliased movement `47` to active stock movement `3`, which may run uninitialized movement state on old saved movement-47 objects.
- This attempt keeps stale movement-47 objects inert while proving whether new stock movement-3 spawns can step safely on the same save.

Files/symbols:

- `armips/asm/overworld_wild_movement.s`
- `include/overworld_wild_movement.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- Built ROM should have movement slot `47` at `0x020FD2B0` pointing at stock no-op descriptor `0x020FCEC8`.
- New spawns should call `CreateSpecialFieldObjectWithParams` with movement `3`.

Verification:

- Built as `test103.nds`.
- Slot `0` at `0x020FD1F4` points at `0x020FCEC8`.
- Slot `3` at `0x020FD200` points at `0x020FD170`.
- Slot `47` at `0x020FD2B0` points at `0x020FCEC8`.
- Slot `47` descriptor words match stock no-op movement `0`: `0x00000000 0x0205FCB5 0x0205FCB9 0x0205FCBD 0x0205FCC1`.
- Source verification: `OverworldWildSpawns_CreateObject` passes `OW_WILD_MOVE_STOCK_WANDER`, currently movement `3`, to `CreateSpecialFieldObjectWithParams`.

Runtime result:

- User reported the game still crashes.

Learning:

- Stale movement `47` running stock movement `3` was not the only cause.
- Fresh spawns using stock movement `3` plus stale movement `47` idling is still not enough to survive the one-step test.
- The next likely culprit is the spawner's player-step pipeline, or something that runs independently after the player step.

Do not repeat:

- Do not keep changing only movement-slot aliasing for this crash unless the player-step pipeline is ruled out.

### Attempt 9: Disable Spawner Step Actions After Map-State Refresh

Idea:

Keep map-state refresh alive but skip every action after it in `OverworldWildSpawns_OverlayOnPlayerStep`:

- no stale-slot dropping
- no distance despawn
- no touch battle checks
- no ambient cry
- no refill/spawn attempt

Why this is new:

- Earlier attempts focused on movement descriptor wiring, callback behavior, and fresh object movement IDs.
- No earlier attempt isolated the spawner's player-step pipeline after a successful save load.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` should be `1`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should return `FALSE` immediately after `OverworldWildSpawns_UpdateMapState` succeeds.
- The rest of the step actions should remain compiled but unreachable behind the diagnostic switch.

Verification:

- Built as `test104.nds`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Disassembly of `OverworldWildSpawns_OverlayOnPlayerStep` shows it reaches `OverworldWildSpawns_UpdateMapState` behavior and then returns `FALSE`; calls to `OverworldWildSpawns_DropStaleSlots`, `OverworldWildSpawns_DespawnFarMons`, `OverworldWildSpawns_TryStartBattle`, `OverworldWildSpawns_TryPlayAmbientCry`, and `OverworldWildSpawns_TryRefill` are not present in the active step path.

Runtime result:

- User reported the game still crashes.

Learning:

- Disabling the overlay's downstream step actions did not stop the one-step crash.
- The crash is now narrowed to either the ARM9 `OverworldWildSpawns_OnPlayerStep` wrapper/overlay load/map-state refresh, or code running independently of that hook.

Do not repeat:

- Do not keep toggling individual overlay step actions until the outer wrapper hook has been ruled in or out.

### Attempt 10: Disable The Entire Overworld-Wild Player-Step Hook

Idea:

Return `FALSE` immediately from `OverworldWildSpawns_OnPlayerStep`, before `OverworldWildSpawns_GetOverlayEntry` can load the overlay and before `entry->onPlayerStep` can run.

Why this is new:

- Attempt 9 still loaded and called overlay 129, then returned after map-state refresh.
- No previous attempt disabled the ARM9 wrapper hook before overlay loading.

Files/symbols:

- `src/overworld_wild_spawns.c`

Expected verification:

- `OW_WILD_DISABLE_PLAYER_STEP_HOOK` should be `1`.
- `OverworldWildSpawns_OnPlayerStep` should return `FALSE` without calling `OverworldWildSpawns_GetOverlayEntry`.
- The build should keep movement slot `47` pointing at the stock no-op descriptor from Attempt 8.

Verification:

- Built as `test105.nds`.
- Disassembly of `OverworldWildSpawns_OnPlayerStep` is `movs r0, #0; bx lr`, so it returns `FALSE` before any overlay-load path.
- `PlayerStepEvent_RepelCounterDecrement` still calls `OverworldWildSpawns_OnPlayerStep`, but the call now always falls through to normal repel handling.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported that the game no longer crashes, but Pokemon no longer spawn.

Learning:

- The one-step crash is caused by the overworld-wild player-step hook path.
- The movement table aliasing and general walking engine are not sufficient to crash on their own in this test.
- Spawns stop because the hook is fully disabled, so this is only a narrowing checkpoint rather than a usable solution.

Do not repeat:

- Do not leave `OverworldWildSpawns_OnPlayerStep` fully disabled except as a diagnostic.
- Continue by bisecting inside the hook: overlay load first, then overlay map-state refresh.

### Attempt 11: Load Overlay Entry But Do Not Call Overlay Step

Idea:

Re-enable `OverworldWildSpawns_OnPlayerStep` enough to call `OverworldWildSpawns_GetOverlayEntry` and check `entry->onPlayerStep`, then return `FALSE` before calling the overlay step function.

Why this is new:

- Attempt 10 returned before overlay loading.
- Attempt 9 loaded and called the overlay step function, which still crashed.
- This attempt isolates overlay loading and entry lookup from overlay step execution.

Files/symbols:

- `src/overworld_wild_spawns.c`

Expected verification:

- `OW_WILD_DISABLE_PLAYER_STEP_HOOK` should be `0`.
- `OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY` should be `1`.
- `OverworldWildSpawns_OnPlayerStep` should call `OverworldWildSpawns_GetOverlayEntry`, validate `entry->onPlayerStep`, and return `FALSE` before `entry->onPlayerStep(fieldSystem, &sOverworldWildSpawnState)`.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test106.nds`.
- Disassembly of `OverworldWildSpawns_OnPlayerStep` calls `OverworldWildSpawns_GetOverlayEntry` and then returns `FALSE`.
- The compiler optimized away the `entry->onPlayerStep` validation because the diagnostic path returns before using the entry; this ROM isolates overlay load only, not entry-pointer reading.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash, and no Pokemon spawn.

Learning:

- Overlay loading alone is safe.
- Pokemon do not spawn because the ROM intentionally returns before calling `entry->onPlayerStep`.
- The next boundary is the overlay step function entry itself versus map-state refresh.

Do not repeat:

- Do not keep testing overlay load-only behavior; it has been ruled safe.

### Attempt 12: Call Overlay Step But Return Immediately

Idea:

Allow `OverworldWildSpawns_OnPlayerStep` to call `entry->onPlayerStep`, but make `OverworldWildSpawns_OverlayOnPlayerStep` return `FALSE` immediately before `OverworldWildSpawns_UpdateMapState`.

Why this is new:

- Attempt 11 loaded overlay 149 but did not call the overlay step function.
- Attempt 9 called the overlay step function and then ran map-state refresh before returning.
- This attempt isolates the overlay function call boundary from map-state refresh.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY` should be `1`.
- `OverworldWildSpawns_OnPlayerStep` should call `entry->onPlayerStep`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should return `FALSE` before `OverworldWildSpawns_UpdateMapState`.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test107.nds`.
- Disassembly of `OverworldWildSpawns_OnPlayerStep` shows it calls `OverworldWildSpawns_GetOverlayEntry`, validates the entry and `entry->onPlayerStep`, then calls through the overlay entry.
- Disassembly of `OverworldWildSpawns_OverlayOnPlayerStep` is `movs r0, #0; bx lr`, so it returns `FALSE` before `OverworldWildSpawns_UpdateMapState`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Overlay step entry itself is safe.
- The next suspect is the body of `OverworldWildSpawns_UpdateMapState`.

Do not repeat:

- Do not keep testing entry-only overlay calls; they have been ruled safe.

### Attempt 13: Read-Only UpdateMapState Diagnostic

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` call `OverworldWildSpawns_UpdateMapState`, but make `OverworldWildSpawns_UpdateMapState` only:

- read `fieldSystem->mapObjectMan`
- read `mapObjectMan->objects`
- store those observed pointers to volatile diagnostic globals so the reads are not optimized away
- run `OverworldWildSpawns_IsEnabledMap(fieldSystem)`
- return before clearing spawn state, writing map state, or publishing the movement field system

Why this is new:

- Attempt 12 returned before `OverworldWildSpawns_UpdateMapState`.
- Attempt 9 ran the full map-state refresh and crashed.
- This attempt separates read-only pointer/map checks from state-clearing side effects.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY` should be `1`.
- `OverworldWildSpawns_UpdateMapState` should return before `OverworldWildSpawns_Clear` and before `OverworldWildCustomMovement_SetFieldSystem`.
- Movement slot `47` should remain stock no-op.

Runtime result:

- Built as `test108.nds`.
- User reported no crash.

Learning:

- Calling `OverworldWildSpawns_UpdateMapState` is safe when it only performs read-only map-object-manager observation and enabled-map detection.
- The crash is likely caused by side effects after those reads, especially `OverworldWildSpawns_Clear(state, FALSE)` or state field writes.

Do not repeat:

- Do not keep testing read-only map-state diagnostics; they have been ruled safe.

### Attempt 14: UpdateMapState Map Writes Without Clear

Idea:

Let `OverworldWildSpawns_UpdateMapState` run past read-only checks and update only:

- `state->mapId`
- `state->mapObjectMan`
- `state->mapObjects`
- `OverworldWildCustomMovement_SetFieldSystem(fieldSystem)`, which is currently compiled as a no-op

Keep `OverworldWildSpawns_OverlayOnPlayerStep` returning immediately after update-map-state, so no spawn/refill/battle work can run. Skip `OverworldWildSpawns_Clear(state, FALSE)` on both enabled-map and disabled-map transitions.

Why this is new:

- Attempt 13 returned before any `OverworldWildSpawnState` writes.
- Attempt 9 ran full map-state refresh and crashed.
- This attempt tests map-state pointer/id mutation without the slot clear loop and without `OverworldWildSpawns_ResetAmbientCryCooldown`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` should be `1`.
- `OverworldWildSpawns_UpdateMapState` should write map state fields but should not call `OverworldWildSpawns_Clear`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should still return before downstream spawner work.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test109.nds`.
- Disassembly shows the active overlay step path writes `state->mapId`, `state->mapObjectMan`, and `state->mapObjects`, calls `OverworldWildCustomMovement_SetFieldSystem`, and returns before downstream spawner work.
- The active path does not call `OverworldWildSpawns_Clear`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported a crash.

Learning:

- State-free update-map-state reads were safe in `test108.nds`, but update-map-state with state comparison/writes crashes in `test109.nds`.
- The crash is not caused by `OverworldWildSpawns_Clear`, refill, battle checks, ambient cries, or custom movement callbacks in this build, because all of those were still unreachable.
- The next boundary is read-only `OverworldWildSpawnState` access versus mutating that state.

Do not repeat:

- Do not retest map-state writes bundled with `OverworldWildCustomMovement_SetFieldSystem`; split state reads, state writes, and the setter separately.

### Attempt 15: Read Spawn State Without Writing It

Idea:

Let `OverworldWildSpawns_UpdateMapState` run the same read-only field-system and map eligibility path as `test108.nds`, but also read these state fields into diagnostics:

- `state->mapId`
- `state->mapObjectMan`
- `state->mapObjects`

Return before any state write, before `OverworldWildSpawns_Clear`, and before `OverworldWildCustomMovement_SetFieldSystem`.

Why this is new:

- Attempt 13 did not touch `state`.
- Attempt 14 touched and wrote `state` fields, then crashed.
- This attempt isolates whether simply reading the ARM9/field-extension state pointer from overlay 149 is safe.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY` should be `1`.
- `OverworldWildSpawns_UpdateMapState` should read state fields into volatile globals.
- The active update path should not write `state`, should not call `OverworldWildSpawns_Clear`, and should not call `OverworldWildCustomMovement_SetFieldSystem`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should still return before downstream spawner work.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test110.nds`.
- Disassembly shows the compiler narrowed the active overlay step path to only read `state->mapId`, store it to the volatile diagnostic integer, and return `FALSE`.
- The active path does not write `state`, does not call `OverworldWildSpawns_Clear`, does not call `OverworldWildCustomMovement_SetFieldSystem`, and does not run downstream spawner work.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Adjusted meaning:

- This ROM is now an even narrower diagnostic than the source-level intent: it tests whether reading one scalar field, `state->mapId`, from the overlay is safe.
- It does not test state pointer fields, map eligibility, or the field-system pointer reads because those side effects optimized away.

Runtime result:

- User reported no crash.

Learning:

- Reading one scalar field, `state->mapId`, from overlay 149 is safe.
- The crash in `test109.nds` is not caused by simply passing or reading the `OverworldWildSpawnState *state` pointer.
- The next split should isolate the no-op movement field-system setter before blaming state writes.

Do not repeat:

- Do not repeat state-read-only probes unless they force additional specific fields to survive compiler optimization.

### Attempt 19: Re-enable Stale-Slot Cleanup Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run `OverworldWildSpawns_DropStaleSlots` after the now-stable map-state update, then immediately return `FALSE`.

Why this is new:

- Attempt 18/`test113.nds` returned before every downstream step action.
- Earlier crashy probes either stopped before stale-slot cleanup or bundled it with more downstream spawner logic.
- No previous build has isolated stale-slot validation and clearing after the `LONG_CALL` setter fix.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` should be `1`.
- The active overlay step path should run map-state update, run `OverworldWildSpawns_DropStaleSlots`, then return `FALSE`.
- The active overlay step path should not run distance despawn, touch battle, ambient cry, or refill/spawn.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test114.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` is `1`.
- Disassembly shows the active overlay step path runs map-state update, then the stale-slot validation/clear loop, then returns `FALSE`.
- Disassembly shows no distance-despawn, touch-battle, ambient-cry, or refill/spawn path after stale-slot cleanup in the active step path.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended stale-slot-only probe.
- Runtime result confirms stale-slot validation and clearing are stable.

Expand:

- Re-enable `OverworldWildSpawns_DespawnFarMons` only, while returning before touch battle, ambient cry, and refill/spawn.

### Attempt 20: Re-enable Distance Despawn Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run map-state update, stale-slot cleanup, and `OverworldWildSpawns_DespawnFarMons`, then immediately return `FALSE`.

Why this is new:

- Attempt 19/`test114.nds` returned before distance despawn.
- Earlier crashy probes bundled distance despawn with touch battle, ambient cry, and refill/spawn.
- No previous build has isolated distance despawn after the `LONG_CALL` setter fix and stable stale-slot cleanup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` should be `1`.
- The active overlay step path should run map-state update, stale-slot cleanup, distance despawn, then return `FALSE`.
- The active overlay step path should not run touch battle, ambient cry, or refill/spawn.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test115.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` is `1`.
- Disassembly shows the active overlay step path runs map-state update, stale-slot cleanup, distance despawn, then returns `FALSE`.
- Disassembly shows no touch-battle, ambient-cry, or refill/spawn path after distance despawn in the active step path.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended distance-despawn-only probe.
- Runtime result confirms distance despawn is stable in the current empty/no-spawn state.

Expand:

- Re-enable `OverworldWildSpawns_TryStartBattle` only, while returning before ambient cry and refill/spawn.

### Attempt 21: Re-enable Touch-Battle Detection Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run map-state update, stale-slot cleanup, distance despawn, and `OverworldWildSpawns_TryStartBattle`, then immediately return `FALSE` if no battle was started.

Why this is new:

- Attempt 20/`test115.nds` returned before touch-battle detection.
- Earlier crashy probes bundled touch-battle detection with ambient cry and refill/spawn.
- No previous build has isolated touch-battle detection after the `LONG_CALL` setter fix and stable stale/despawn paths.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` should be `1`.
- The active overlay step path should run map-state update, stale-slot cleanup, distance despawn, and touch-battle detection.
- If `OverworldWildSpawns_TryStartBattle` returns `TRUE`, the active path should still return `TRUE`.
- If no battle is started, the active path should return `FALSE` before ambient cry or refill/spawn.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test116.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` is `1`.
- Disassembly shows the active overlay step path runs map-state update, stale-slot cleanup, distance despawn, and touch-battle detection.
- Disassembly shows the battle-start path can set pending battle state, call `EventSet_Script`, and return `TRUE`.
- Disassembly shows the no-battle path returns `FALSE` before ambient cry or refill/spawn.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended touch-battle-only probe.
- Runtime result confirms touch-battle detection is stable in the current empty/no-spawn state.

Expand:

- Re-enable `OverworldWildSpawns_TryRefill` to spawn Pokemon, while skipping ambient cry for now.

### Attempt 22: Re-enable Refill And Spawn Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run map-state update, stale-slot cleanup, distance despawn, touch-battle detection, and refill/spawn. Skip ambient cry so this build specifically tests Pokemon object creation and spawn state.

Why this is new:

- Attempt 21/`test116.nds` returned before refill/spawn.
- Earlier crashy probes bundled refill/spawn with unresolved setter/state issues.
- No previous build has isolated refill/spawn after the `LONG_CALL` setter fix and stable stale/despawn/battle paths.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` should be `1`.
- The active overlay step path should run map-state update, stale-slot cleanup, distance despawn, touch-battle detection, and `OverworldWildSpawns_TryRefill`.
- The active overlay step path should not run `OverworldWildSpawns_TryPlayAmbientCry`.
- Fresh spawns should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test117.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` is `1`.
- Disassembly shows the active overlay step path reaches `OverworldWildSpawns_SpawnOne` from refill/spawn call sites.
- Source-level diagnostic gating keeps `OverworldWildSpawns_TryPlayAmbientCry` skipped for this build.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test117.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- Refill/spawn is stable again with stock movement `3` and ambient cry skipped.
- This rules out spawn position selection, encounter rolling, `CreateSpecialFieldObjectWithParams`, Pokemon render params, shiny setup, and post-create spawn state writes as immediate crash causes for this checkpoint.

Expand:

- Restore `OverworldWildSpawns_TryPlayAmbientCry` while keeping stock movement `3` spawns, so the full stock spawner pipeline is tested before custom movement work resumes.

### Attempt 23: Restore Ambient Cry With Stock Movement

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run the full stock spawner pipeline again: map-state update, stale-slot cleanup, distance despawn, touch-battle detection, ambient cry, and refill/spawn. Fresh spawns still use stock movement `3`; custom movement slot `47` remains no-op.

Why this is new:

- Attempt 22/`test117.nds` skipped ambient cry and did not crash.
- Earlier crashy probes bundled ambient cry with unresolved setter/state issues and custom movement uncertainty.
- No previous build has restored ambient cry after the `LONG_CALL` setter fix and stable stale/despawn/battle/refill paths.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` should be `0`.
- The active overlay step path should run `OverworldWildSpawns_TryPlayAmbientCry` before `OverworldWildSpawns_TryRefill`.
- Fresh spawns should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test118.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` is `0`.
- Disassembly shows the active overlay step path reaches `PlayCry` at `0x02006219`.
- Disassembly shows the active overlay step path still reaches `OverworldWildSpawns_SpawnOne` from refill/spawn call sites after the ambient-cry section.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test118.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- The full stock spawner pipeline is stable again: stale-slot cleanup, distance despawn, touch-battle detection, ambient cry, and refill/spawn all run with stock movement `3`.
- This rules out ambient cry as the current crash source and gives a clean baseline before custom movement probes resume.

Expand:

- Avoid re-pointing slot `47` to the overlay-resident descriptor because Attempts 5 and 6 already showed that crashes even with no-op callbacks.
- Start custom movement again from the stable spawner step loop by ticking `MapObject` params only.

### Attempt 24: Spawner-Driven Movement Param Tick

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Add a spawner-step diagnostic that iterates active spawned Pokemon and only reads/writes their movement cooldown param with `MapObject_GetParam` and `MapObject_SetParam`.

Why this is new:

- Attempts 5 and 6 tested slot-47 overlay callbacks and crashed even when callbacks were no-op.
- Earlier movement attempts bundled param access with coordinate reads, scratch writes, movement command helpers, or slot-47 descriptor wiring.
- No previous build has tested `MapObject_GetParam`/`MapObject_SetParam` on active spawned Pokemon from the stable overlay-149 spawner step path while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- The active overlay step path should call `OverworldWildSpawns_TickMovementParams` after touch-battle detection and before ambient cry/refill.
- `OverworldWildSpawns_TickMovementParams` should only call `MapObject_GetParam` and `MapObject_SetParam` for active spawned objects.
- The active movement probe should not use `object->fsys`, global `FieldSystem *`, coordinate reads, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test119.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- Disassembly shows the active overlay path contains `MapObject_GetParam` at `0x0205F2F5` and `MapObject_SetParam` at `0x0205F2D1`.
- Source verification shows `OverworldWildSpawns_TickMovementParams` only reads/writes `OW_WILD_MOVEMENT_PARAM_COOLDOWN` for active spawned objects.
- The new movement probe does not use `object->fsys`, global `FieldSystem *`, coordinate reads, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test119.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- `MapObject_GetParam` and `MapObject_SetParam` are safe to call on active spawned Pokemon from the stable overlay-149 spawner step path.
- This keeps the next probe focused on coordinate reads and direction calculation.

Expand:

- Add player/object coordinate reads and chase/flee direction calculation from the spawner step loop.
- Still avoid slot-47 callbacks, movement command helpers, blocked-direction checks, scratch writes, and single-movement flags.

### Attempt 25: Spawner-Driven Coordinate Read And Direction Calculation

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Extend the spawner-step movement diagnostic to read active spawned object coordinates, player coordinates, behavior param, compute chase/flee deltas, choose a preferred direction, and store the result into volatile diagnostics.

Why this is new:

- Attempt 24/`test119.nds` only tested spawner-driven movement param get/set and did not crash.
- Earlier movement attempts bundled coordinate reads with slot-47 descriptor callbacks, scratch writes, blocked-direction checks, and movement command helpers.
- No previous build has isolated coordinate reads and direction calculation from the stable overlay-149 spawner step path while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- The active overlay step path should still call `OverworldWildSpawns_TickMovementParams` after touch-battle detection and before ambient cry/refill.
- The movement probe should call `MapObject_GetCurrentX`, `MapObject_GetCurrentY`, `GetPlayerXCoord`, `GetPlayerYCoord`, and `MapObject_GetParam` for active spawned objects, then store calculated values in volatile diagnostics.
- The active movement probe should not use slot-47 callbacks, `object->fsys`, global movement `FieldSystem *`, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test120.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` is `1`.
- Source verification shows `OverworldWildSpawns_TickMovementParams` calls `MapObject_GetCurrentX`, `MapObject_GetCurrentY`, `GetPlayerXCoord`, `GetPlayerYCoord`, and `MapObject_GetParam`, then stores calculated values in volatile diagnostics.
- Disassembly target scan shows `MapObject_GetCurrentX` at `0x0205F915`, `MapObject_GetCurrentY` at `0x0205F935`, `GetPlayerXCoord` at `0x0205C67D`, `GetPlayerYCoord` at `0x0205C689`, `MapObject_GetParam` at `0x0205F2F5`, and `MapObject_SetParam` at `0x0205F2D1`.
- Disassembly target scan did not find `MapObject_StartMovementCommand` at `0x0206217D`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, or `MapObject_SetSingleMovementActive` at `0x0205F631` in the overlay object.
- Source verification shows the active spawner movement probe does not use slot-47 callbacks, `object->fsys`, global movement `FieldSystem *`, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test120.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- Position lookup and chase/flee direction calculation are safe for spawned Pokemon from the stable overlay-149 spawner step path.
- This keeps the next probe focused on non-walking movement-command setup.

Expand:

- Add a spawner-driven look command on cooldown reset.
- Still avoid walking commands, blocked-direction checks, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

### Attempt 29: Spawner-Owned Movement Command Update And Clear

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. When the spawner starts a walk command, mark the existing movement cooldown param as `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` (`-1`). On the next spawner tick for that object, call `MapObject_UpdateMovementCommand`; if it reports completion, call `MapObject_ClearSingleMovementActive` and restore the normal cooldown.

Why this is new:

- Attempt 28/`test123.nds` proved starting a gated spawner-driven walk command does not crash.
- Earlier update/clear attempts happened inside the slot-47 custom movement callback and were bundled with scratch writes, `object->fsys`, global movement `FieldSystem *`, or overlay movement descriptor concerns.
- No previous build has isolated `MapObject_UpdateMovementCommand` plus `MapObject_ClearSingleMovementActive` from the stable overlay-149 spawner step loop while keeping fresh spawns on stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND` should be `1`.
- The active probe should use `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` (`-1`) only after starting a spawner-driven walk command.
- The active probe should call `MapObject_UpdateMovementCommand` only when the cooldown param is in-progress.
- The active probe should call `MapObject_ClearSingleMovementActive` only if `MapObject_UpdateMovementCommand` returns complete.
- The active probe should still avoid scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawns should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- User reported no crash.
- User could not reliably tell whether movement was more directed or less random.

Learning:

- Spawner-owned `MapObject_UpdateMovementCommand` and `MapObject_ClearSingleMovementActive` are runtime-stable in the current player-step hook.
- The visual signal is still too subtle while fresh spawns use stock movement `3`.
- The next diagnostic should remove stock-wander interference and exaggerate command progression.

Verification:

- Built as `test124.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND` is enabled.
- Source verification shows `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` (`-1`) is assigned only after the spawner starts a walk command.
- Source verification shows `MapObject_UpdateMovementCommand` is called only when the cooldown param is in-progress.
- Source verification shows `MapObject_ClearSingleMovementActive` is called only if `MapObject_UpdateMovementCommand` returns complete.
- Disassembly target scan shows the newly added `MapObject_UpdateMovementCommand` at `0x02062429` and `MapObject_ClearSingleMovementActive` at `0x0205F63D`.
- Disassembly target scan still shows the prior movement setup targets: `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Source still avoids active custom movement scratch writes, `object->fsys`, and slot-47 callbacks; `OverworldWildCustomMovement_SetFieldSystem` remains no-op under the current idle diagnostic.
- Fresh spawns still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Copied to Delta as `test124.nds`.
- `git diff --check` passed.

Expand:

- Temporarily switch fresh spawns from stock movement `3` to stock idle movement `0` so only the spawner-owned command should move them.
- Set `OW_WILD_SPAWNER_MOVEMENT_PARAM_RESET` to `0` so a new command can be started as soon as the previous command finishes.
- Burst-poll the command up to a bounded number of iterations immediately after starting it so a successful command should visibly complete a tile step.

### Attempt 30: Obvious Spawner-Driven Tile Movement

Idea:

Make the movement result unmistakable for runtime testing. Fresh spawned Pokemon temporarily use stock idle movement `0` instead of stock wander `3`. After the spawner starts a walk command, it immediately burst-polls `MapObject_UpdateMovementCommand` up to 32 iterations and clears the single-movement flag if the command finishes. The cooldown reset is `0`, so a finished command can be followed by another command on the next player-step tick.

Why this is new:

- Attempt 29/`test124.nds` proved update/clear polling does not crash but was visually ambiguous.
- Previous no-op movement tests used slot `47` aliasing or disabled spawn paths; no previous build spawned Pokemon directly with movement `0` while driving their walk commands from the stable overlay-149 spawner step loop.
- No previous build has tried bounded burst-polling to force a started spawner command to visually complete for testing.

Files/symbols:

- `include/overworld_wild_movement.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_IDLE_OBJECT_MOVEMENT` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT` should resolve to `OW_WILD_MOVE_STOCK_IDLE`.
- Fresh spawns should pass movement `0` into `CreateSpecialFieldObjectWithParams`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_PARAM_RESET` should be `0`.
- `OverworldWildSpawns_UpdateSpawnerMovementCommand` should cap burst polling at `OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS` (`32`).
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`.
- Movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- User reported no crash.
- Pokemon rarely moved toward the player.
- When movement happened, it felt like an instant teleport to the adjacent tile rather than animated movement.

Learning:

- Switching fresh spawns to stock idle movement `0` and burst-polling the command does not crash.
- The burst-poll proves the command can complete a tile step, but completing all update iterations inside one player-step tick is not visually acceptable.
- The next direction should preserve spawner-owned commands but advance them over frames.

Verification:

- Built as `test125.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_IDLE_OBJECT_MOVEMENT` is enabled.
- `OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT` resolves to `OW_WILD_MOVE_STOCK_IDLE`.
- Fresh spawns pass `OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT` into `CreateSpecialFieldObjectWithParams`; source now defines `OW_WILD_MOVE_STOCK_IDLE` as movement `0`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` is enabled.
- `OW_WILD_SPAWNER_MOVEMENT_PARAM_RESET` is `0`.
- Source verification shows `OverworldWildSpawns_UpdateSpawnerMovementCommand` caps burst polling at `OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS` (`32`).
- Disassembly of `OverworldWildSpawns_UpdateSpawnerMovementCommand` shows the loop bound compare against `#32`, and target calls to `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_UpdateMovementCommand` at `0x02062429`, and `MapObject_ClearSingleMovementActive` at `0x0205F63D`.
- Disassembly target scan still shows the walk setup targets: `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Source still avoids slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`; references in `src/overworld_wild_movement.c` remain behind the idle diagnostic and are not part of the active overlay movement path.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Copied to Delta as `test125.nds`.
- `git diff --check` passed.

Expand:

- Disable burst polling.
- Keep fresh spawns on stock idle movement `0` to avoid stock wander masking the test.
- Create a short-lived `SysTask` when a spawner-owned command starts.
- Let the task call `MapObject_UpdateMovementCommand` once per frame and destroy itself when no in-progress commands remain.

### Attempt 31: Frame Task Movement Command Updates

Idea:

Keep fresh spawned Pokemon on stock idle movement `0`, but stop completing their walk command in the player-step hook. When the spawner starts a walk command, mark the object in-progress and create a frame-level `SysTask` if one is not already running. The task loops active spawned Pokemon, updates only objects with the in-progress marker, clears the single-movement flag when the command finishes, resets the cooldown, and destroys itself once no in-progress commands remain.

Why this is new:

- Attempt 30/`test125.nds` proved burst-polling can complete a tile step, but it visually teleports.
- Earlier update/clear attempts were either player-step based or inside slot-47 callbacks.
- No previous build has isolated a `CreateSysTask`-driven frame updater for spawner-owned wild Pokemon movement while keeping slot `47` no-op and fresh spawns on stock idle movement `0`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` should be `0`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK` should be `1`.
- The active path should call `CreateSysTask` when a spawner-owned movement command starts.
- The frame task should call `MapObject_UpdateMovementCommand` at most once per object per task tick.
- The frame task should call `MapObject_ClearSingleMovementActive` only when update reports completion.
- The frame task should call `DestroySysTask` after no active spawned Pokemon has `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS`.
- Map-context changes and battle start should stop the frame task.
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`.
- Movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- Built as `test126.nds`.
- User reported no crash.
- User reported the movement works.

Learning:

- Advancing the spawner-owned walk command through a frame-level `SysTask` fixes the instant-tile-snap behavior seen in `test125.nds`.
- The stable path is: keep slot `47` no-op, spawn Pokemon with stock idle movement `0`, start a spawner-owned walk command from the player-step hook, and update that command once per frame until complete.
- This confirms the previous bug was update timing, not the walk command helper itself.

Verification:

- `./docker-makerom.cmd` completed successfully.
- Copied to Delta as `test126.nds`.
- Source flags confirm `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` is `0` and `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK` is `1`.
- Source confirms fresh spawns still use `OW_WILD_MOVE_STOCK_IDLE`.
- Source confirms the active path creates `OverworldWildSpawns_FrameMovementTask` with `CreateSysTask`, stops it with `DestroySysTask`, and calls the stop path on battle start and map-context changes.
- Source confirms `OverworldWildSpawns_UpdateSpawnerMovementCommand` calls `MapObject_UpdateMovementCommand` and clears the single-movement flag only when update reports completion.
- Linked overlay target scan found `CreateSysTask` target `0x0200E321`, `DestroySysTask` target `0x0200E391`, `MapObject_UpdateMovementCommand` target `0x02062429`, and `MapObject_ClearSingleMovementActive` target `0x0205F63D`.
- Linked overlay target scan still contains the expected movement helper targets `0x02060BB9`, `0x0205F649`, `0x0206234D`, `0x0206217D`, and `0x0205F631`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `git diff --check` passed.

Expand:

- Keep the frame-task update timing from `test126.nds`.
- Stop using object param `0` as the spawner-owned cooldown/in-progress marker.
- Track movement cooldown and in-progress ownership per spawn slot.
- Clear/reset spawner-owned movement state when battle starts and when battle cleanup runs.
- Try a secondary chase/flee direction if the primary direction is blocked.

### Attempt 32: Per-Slot Movement Ownership And Battle Reset

Idea:

Keep the successful frame-task timing from `test126.nds`, but move movement ownership into `OverworldWildSpawnState`: each spawn slot has its own cooldown and a bit in an in-progress mask. The player-step hook starts commands per slot, and the frame task services every slot whose bit is set. Battle start and battle cleanup explicitly clear spawner-owned single-movement commands and reset movement cooldowns, so a battle cannot leave all Pokemon stuck in an in-progress state.

Why this is new:

- Attempt 31/`test126.nds` used a frame-level `SysTask`, but it still used object param `0` as the movement cooldown and in-progress marker.
- Earlier attempts did not test per-spawn-slot ownership in `OverworldWildSpawnState`.
- Earlier attempts did not reset all spawner-owned movement commands from both battle start and battle cleanup.
- Earlier spawner-driven movement only tried one preferred chase/flee direction before suppressing movement when blocked.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OverworldWildSpawnState` should contain per-slot movement cooldown storage and an in-progress mask.
- `OverworldWildSpawns_TickMovementParams` should use the per-slot state instead of reading object param `0` for cooldown/in-progress.
- `OverworldWildSpawns_FrameMovementTask` should loop every active bit in the in-progress mask, not only one object.
- Battle start and battle cleanup should call a movement reset path.
- The movement reset path should clear single-movement active only for currently active spawn objects.
- Direction selection should try both primary and secondary chase/flee axes before suppressing a walk.
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`.

Runtime result:

- Built as `test128.nds`.
- User reported this is a huge improvement.
- User reported the previous quirks are no longer issues:
  - multiple Pokemon movement limitation
  - no movement after battle
  - movement not always active outside those cases
- New quirk: Pokemon seem to stop chasing the player after a certain threshold is reached.

Learning:

- Per-slot movement ownership plus battle reset fixes the major follow-up problems from `test126.nds`.
- The new threshold quirk is likely the engine's map-object movement range doing its job: `OverworldWildSpawns_ApplyMovementRange` sets X/Y range to `2`, and `MapObject_IsMovementDirectionBlocked` likely treats a chase step outside that leash as blocked.
- The threshold therefore appears expected for the current implementation, but it is probably not the desired final chase behavior.
- The next direction should test a leash adjustment rather than reworking frame-task timing or per-slot ownership.

Verification:

- `./docker-makerom.cmd` completed successfully.
- Copied to Delta as `test128.nds`.
- Source confirms `OverworldWildSpawnState` has `movementCooldowns[OW_WILD_MAX_SPAWNS]` and `movementInProgressMask`.
- Source confirms `OverworldWildSpawns_TickMovementParams` uses `state->movementCooldowns[i]` and `OverworldWildSpawns_IsMovementSlotInProgress` instead of using object param `0` as cooldown/in-progress.
- Source confirms `OverworldWildSpawns_FrameMovementTask` loops all slots whose in-progress bit is set and increments `sOverworldWildMovementDiagnosticFrameTaskUpdatedObjects` per updated object.
- Source confirms battle start and battle cleanup both call `OverworldWildSpawns_ResetAllMovementCommands(state, TRUE)`.
- Source confirms map-context changes call `OverworldWildSpawns_ResetAllMovementCommands(state, FALSE)`.
- Source confirms `OverworldWildSpawns_DiagnosticBuildDirections` builds up to two chase/flee axes and `OverworldWildSpawns_TryStartSpawnerMovementCommand` tries each direction before suppressing movement.
- Source scan confirms the active overlay path no longer writes `OW_WILD_MOVEMENT_PARAM_COOLDOWN` with `MapObject_SetParam`, and the old `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` marker was removed from the source.
- Linked overlay target scan found `CreateSysTask` target `0x0200E321`, `DestroySysTask` target `0x0200E391`, `MapObject_UpdateMovementCommand` target `0x02062429`, and `MapObject_ClearSingleMovementActive` target `0x0205F63D`.
- Linked overlay target scan still contains expected movement helper targets `0x02060BB9`, `0x0205F649`, `0x0206234D`, `0x0206217D`, and `0x0205F631`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `git diff --check` passed.

Expand:

- Keep per-slot movement ownership and frame-task updates.
- Test whether increasing or removing `MapObject_SetXRange`/`MapObject_SetYRange` lets Pokemon keep chasing without reintroducing old movement issues.
- Alternatively, test recentering the movement leash after each successful spawner-owned step, if unlimited chase feels too chaotic.

### Attempt 33: Range 8 And Idle Frame Chase

Idea:

Keep the successful per-slot movement ownership from `test128.nds`, increase spawned Pokemon X/Y movement range from `2` to `8`, and make the frame task continue running while a compatible map context and active spawns exist. The task should still update in-progress commands, but when no command is in progress it should call the same spawner movement decision logic with the last valid `FieldSystem *`, allowing Pokemon to start new chase steps even when the player is not moving.

Why this is new:

- Attempt 31 used a frame task only to update commands that player-step had already started.
- Attempt 32 used per-slot ownership and battle reset, but movement decisions still came from the player-step hook.
- No previous build has tested a persistent active-spawn frame task that starts new chase commands while the player is idle.
- No previous build has tested widening the map-object X/Y range to `8`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OverworldWildSpawns_ApplyMovementRange` should set X/Y range to `8`.
- `OverworldWildSpawnState` should retain a movement `FieldSystem *` only while the current map context is active.
- `OverworldWildSpawns_EnsureFrameMovementTask` should accept/update the current `FieldSystem *`.
- `OverworldWildSpawns_FrameMovementTask` should validate the retained field system with `OverworldWildSpawns_IsEnabledMap` before making decisions.
- The frame task should call `OverworldWildSpawns_TickMovementParams` when active spawns exist, so new movement commands can start without player movement.
- Map-context changes and battle reset should clear the retained field system and stop the frame task.
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, and `object->fsys`.

Verification:

- Built as `test129.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_ApplyMovementRange` sets X/Y range to `8`.
- Verified `OverworldWildSpawnState` stores `movementFieldSystem`, clears it on movement reset, and refreshes it from player-step movement ticking.
- Verified `OverworldWildSpawns_EnsureFrameMovementTask` accepts the current `FieldSystem *`.
- Verified `OverworldWildSpawns_FrameMovementTask` stops if the retained field system is no longer an enabled map or if no active spawned objects remain.
- Verified the frame task calls `OverworldWildSpawns_TickMovementParams`, so movement decisions can be issued without a new player step.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.
- Verified active overlay code still avoids direct `object->fsys` and `object->unkD8` access; remaining references are in the dormant custom movement file.

Runtime result:

- User reported this is starting to look really good, with a minor issue where Pokemon that move at the same time can sometimes end on the same tile.

Learning:

- Range `8` and idle frame chase are viable enough to continue polishing.
- The next issue is not core movement timing; it is after-the-fact overlap cleanup for simultaneous successful moves.

### Attempt 34: One-At-A-Time Overlap Untangle

Idea:

Keep the successful range `8` and idle frame chase from `test129.nds`, but add a post-move untangle pass inside the spawner movement tick. When no spawner-owned command is in progress, scan active spawned Pokemon for duplicate current coordinates. If a pair overlaps, start one normal spawner-owned walk command for one of the pair into an adjacent unoccupied, unblocked tile, then return so only one untangle move is active at a time.

Why this is new:

- Previous attempts tested movement descriptors, safe command timing, per-slot ownership, battle reset, range, and idle chase.
- No previous attempt has scanned active spawned Pokemon for duplicate current coordinates.
- No previous attempt has used the proven spawner-owned walk command path specifically as an after-the-fact overlap resolver.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test130.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_TryUntangleOverlaps` runs before normal chase decisions inside `OverworldWildSpawns_TickMovementParams`.
- Verified the untangle pass only runs when `movementInProgressMask == 0`.
- Verified overlap detection compares current coordinates for active spawned Pokemon pairs.
- Verified untangle target validation rejects negative coordinates, currently occupied target tiles, and directions blocked by `MapObject_IsMovementDirectionBlocked`.
- Verified untangle movement reuses `OverworldWildSpawns_TryStartSpawnerMovementCommand`, so it stays on the proven spawner-owned command path.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.

Runtime result:

- User reported two issues:
  - route exits can slow down dramatically and sometimes freeze, and this was already present in the prior run
  - in `test130.nds`, battle engagement overshoots badly and starts fights before the player appears close to a spawned Pokemon

Learning:

- The route-exit problem likely predates the overlap untangle pass and points back to the persistent idle frame task added in Attempt 33.
- The battle overshoot could be caused by checking contact while a spawned Pokemon is still resolving a movement command.

### Attempt 35: Guard Idle Frame Context And Moving Battle Contact

Idea:

Keep range `8`, idle chase, and one-at-a-time untangling, but make the persistent frame task stop unless its retained `FieldSystem *` still matches the spawner's current map id, map-object manager, and object table. Also make `OverworldWildSpawns_IsTouchingPlayer` ignore a spawned Pokemon while that slot has a spawner-owned movement command in progress or while the object still has an engine single-movement command active.

Why this is new:

- Attempt 33 validated only `OverworldWildSpawns_IsEnabledMap(fieldSystem)` before using the retained `FieldSystem *`.
- Attempt 34 added overlap cleanup but did not add any stronger route-transition/lifetime guard.
- No previous attempt has suppressed battle detection while a spawned Pokemon is still moving.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test131.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_IsMovementFieldContextCurrent` checks enabled map, retained map id, retained map-object manager, and retained object table before the frame task keeps running.
- Verified `OverworldWildSpawns_FrameMovementTask` also requires a current active spawn via `OverworldWildSpawns_HasCurrentMovementSpawns`.
- Verified the frame task no longer updates a slot whose object is not current for the retained field context.
- Verified `OverworldWildSpawns_IsTouchingPlayer` returns false while the slot is in `movementInProgressMask` or the object reports `MapObject_IsSingleMovementActive`.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.

Runtime result:

- User reported the route-exit slowdown/freeze and contact timing still needed follow-up.

Learning:

- Stronger map-context guards remain useful, but route-transition and battle-timing behavior still needed follow-up.
- Keep suppressing contact while movement is active; use later battle timing attempts for the adjacency miss.

### Attempt 36: Frame Task Battle Detection

Idea:

Keep the player-step battle detector, but also call `OverworldWildSpawns_TryStartBattle` from `OverworldWildSpawns_FrameMovementTask` after all in-progress spawner movement commands have been updated. The frame-task call only runs when `movementInProgressMask == 0`, so battle detection happens after movement settles and before the next chase/untangle command can start. Add a `decrementBattleGrace` parameter so player-step checks still consume flee grace, while frame-task checks observe grace without burning it every frame.

Why this is new:

- Previous attempts proved `OverworldWildSpawns_TryStartBattle` on the player-step path.
- Previous attempts proved frame-task movement polling and idle chase.
- No previous attempt has scheduled the overworld-wild battle script from the frame-task path.
- No previous attempt has separated player-step flee-grace consumption from frame-task contact checks.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test132.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_FrameMovementTask` calls `OverworldWildSpawns_TryStartBattle(state, fieldSystem, FALSE)` only when `movementInProgressMask == 0`.
- Verified the frame-task battle check runs before `OverworldWildSpawns_TickMovementParams`, so it can schedule battle before starting another movement command.
- Verified the player-step path still calls `OverworldWildSpawns_TryStartBattle(state, fieldSystem, TRUE)`.
- Verified `battleGraceSteps` is decremented only when `decrementBattleGrace` is true.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.
- Linked overlay target scan still shows the expected movement helper targets and player coordinate helpers.

Runtime result:

- User reported no crash, and battle triggering works about 90% of the time.
- Remaining miss: when the player and spawned Pokemon move at the same time, they can end up adjacent without a battle starting.

Learning:

- Scheduling the battle script from the movement frame task is viable.
- The remaining issue appears to be a settle/timing race after simultaneous player and spawned-Pokemon movement, not a broad `EventSet_Script` or battle-start crash.

### Attempt 37: Post-Movement Battle Settle Window

Idea:

When a spawner-owned movement command finishes, start a short settle window before any new chase or untangle command can begin. During that window, retry the existing battle contact detector every frame without decrementing flee grace. This gives the engine a few frames to clear movement-active state and settle player/Pokemon coordinates after simultaneous movement, then starts the battle if they are adjacent.

Why this is new:

- Attempt 36 added one frame-task battle check after movement commands settled, but it did not hold off the next movement command for additional settle frames.
- Attempt 35 suppressed battle detection while movement was active, but it did not add a retry window after movement finished.
- No previous attempt has stored a per-state post-movement battle settle counter or blocked new spawner movement while that counter is active.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test134.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawnState` stores `movementBattleSettleFrames`.
- Verified `OverworldWildSpawns_FrameMovementTask` sets the settle counter only when `OverworldWildSpawns_UpdateSpawnerMovementCommand` reports a completed spawner-owned command.
- Verified `OverworldWildSpawns_TryHoldForBattleSettle` blocks new movement while the settle counter is active, and only decrements/retries `OverworldWildSpawns_TryStartBattle(state, fieldSystem, FALSE)` after `movementInProgressMask` reaches `0`.
- Verified `OverworldWildSpawns_TickMovementParams` returns early while the settle window is active, so no new chase/untangle command can start before the retry window resolves.
- Verified the player-step path returns `TRUE` if the settle retry starts a pending battle during movement ticking.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported the build seems more stable.

Learning:

- The post-movement settle window appears to improve the remaining simultaneous-movement battle timing issue.
- Per-species speed should not be implemented by slowing other species with larger decision cooldowns when the requested test is for Pidgey to be faster.

### Attempt 42: Proximity-Only Battle Settle

Idea:

Keep the six-frame post-movement battle-settle window, but only start that settle window when a finished movement ends near the player. Finished movement farther away from the player can immediately start the next spawner-owned movement command.

Why this is new:

- Attempt 37 added the global post-movement settle window after every completed movement command.
- Attempt 41 kept high logical speeds on the fastest stock walk command, making the global settle pause visibly jittery.
- No previous attempt has gated the settle window by proximity to the player.
- This avoids reducing the battle-settle duration globally, so the simultaneous player/Pokemon movement battle-retry case still has a buffer near contact.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test139.nds` and copied to Delta.
- `git diff --check` passed.
- Verified completed movement only starts `OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES` when a finished slot is within `OW_WILD_SPAWNER_BATTLE_SETTLE_RANGE` of the player.
- Verified movement that finishes farther from the player does not set the settle counter, allowing `OverworldWildSpawns_TickMovementParams` to start the next command immediately.

Runtime result:

- User corrected the assumption: this was not the cause of the jitter.

Learning:

- Proximity-gating the battle-settle window should not be treated as the smoothness fix.
- The active source for the next test restores the previous global settle behavior and instead changes the high-speed visual movement command mapping.

### Attempt 43: Cap High Speeds To Fluent Walk Command

Idea:

Keep Pidgey at logical speed `6`, but cap logical speeds `4`, `5`, and `6` to the 4-frame stock walk command family `0x10` instead of the 2-frame `0x14` family. The hypothesis is that `0x14` makes each tile step so short that the object appears to snap one tile and briefly stand still, while `0x10` should preserve a faster-than-Pidgey-speed-2 feel with more visible interpolation.

Why this is new:

- Attempt 40 showed `0x1C` does not move in this spawner path.
- Attempt 41 mapped high speeds to `0x14`, but runtime still felt jittery.
- Attempt 42 incorrectly tested the battle-settle timing; the user clarified that was not the cause.
- No previous attempt has kept Pidgey at logical speed `6` while capping the visual movement command to `0x10`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test140.nds` and copied to Delta.
- `git diff --check` passed.
- Verified Pidgey remains logical speed `6`.
- Verified logical speeds `4`, `5`, and `6` now map to `OW_WILD_SPAWNER_MOVEMENT_SPEED_3_COMMAND` / stock command family `0x10`.
- Verified the active source restored the previous global battle-settle behavior after Attempt 42 was corrected.

Runtime result:

- User clarified the core problem was not the high-speed command family. Movement feels jittery at all speeds because spawned Pokemon visibly stop and "think" between every tile instead of chaining movement like the player.

Learning:

- The visual-command cap does not address the main smoothness issue. The next solution should target command chaining and the pause between one-tile movement commands.

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

### Attempt 182: Tree-Anchor Single Stock Jump Probe

Idea:

Start from the successful Attempt 181 tree-anchor baseline and add back exactly one stock real-object jump command. This tests whether movement itself is safe when Mankey remains anchored to the normal headbutt-tree spawn path and route context-loss uses detach-only cleanup.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_VISIBILITY_BASELINE`.
- Add `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE`.
- Keep canopy Mankey on the original headbutt-tree spawn coordinate.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, or the direct internal long-jump starter.
- When the canopy behavior ticks, clear stale canopy target state, clear `BIT_VANISH`, pick one adjacent valid canopy/headbutt landing tile, and start a normal direction-specific `Jump*` command on the real object.
- If no adjacent valid canopy tile exists, idle visibly instead of forcing movement.
- Let the existing generic movement-finish handler settle the one-tile command; no pending far target is staged.

Why this is new:

- Attempt 181 proved idle tree anchoring is visible and route-safe, but did not move.
- Attempts 162, 163, 166, and 176 used raw render-position travel or helper objects; this does not.
- Attempts 177-180 used movement lists or direct internal long-jump ownership for far targets; this does not.
- Attempts 159, 161, 165, 167, and 168 tested stock movement as a far-hop carrier from older canopy/perch movement state; this revalidates one stock movement owner from the stable tree-anchor baseline.
- A sidecar explorer confirmed there is no proven stock 5-7 tile visible jump primitive in the repo; stock commands are still useful as short-jump safety probes, but the eventual long-hop solution should trace the full stock jump state contract rather than retrying `Jump*2`, movement lists, or raw `posVec` travel.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE`
- `OverworldWildSpawns_TryPickAdjacentCanopyStepTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test349.nds` and copied to Delta.
- Verified the single-jump probe leaves the tree-anchor spawn override active by preventing the older perch relocation while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE` is enabled.
- Verified the active canopy tick clears stale canopy target state, clears `BIT_VANISH`, and starts one normal real-object `Jump*` command only when an adjacent valid canopy/headbutt landing tile exists.
- Verified the probe does not stage a far pending target, start a movement-list task, use helper/recreate paths, call the direct internal long-jump starter, or run raw render-position interpolation.
- The edited overlay compiled; unused-helper warnings are expected because the legacy canopy helper/recreate/movement-list paths remain disconnected during this probe.

Runtime result:

- User reported:
  - Mankey stays visible.
  - Mankey does a visible short jump.
  - Leaving the route still avoids crash/freeze.

Learning:

- The stable tree-anchor baseline can safely run a normal stock real-object jump command.
- Route-transition stability holds when the active movement owner is the normal single-command path and context-loss uses detach-only cleanup.
- This gives a safe base for testing slightly longer stock jump variants without reintroducing helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec`, or the internal long-jump starter.
- User suggested the practical hop maximum may be 4 and hop distance may be related to movement speed. The movement command table shows explicit `Jump*` and `Jump*2` families, but no named 3/4/5/6/7 jump commands, so the next probe should test `Jump*2` from the same stable tree-anchor baseline before assuming a custom long-hop contract.

### Attempt 183: Tree-Anchor Stock Jump2 Probe

Idea:

Keep the successful Attempt 182 setup, but switch the active probe from one-tile `Jump*` to two-tile `Jump*2`. The user suggested the practical hop ceiling may be around 4 and hop distance may be tied to speed; this first verifies whether the stock two-tile jump family actually lands two tiles safely when started from the stable tree-anchor baseline.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE`.
- Keep canopy Mankey on the original headbutt-tree spawn coordinate by keeping the older perch relocation disabled while either tree-anchor probe is active.
- Generalize the one-step landing picker into `OverworldWildSpawns_TryPickStraightCanopyStepTarget`, taking a desired straight-line distance.
- Pick a straight two-tile valid canopy/headbutt landing target.
- Start a normal direction-specific `Jump*2` command on the real object through `OverworldWildSpawns_StartMovementCommandForSlot` with pending distance `2`.
- Do not stage a far pending target, use helper/recreate paths, start a movement-list task, call the internal long-jump starter, touch phantom cleanup, or run raw `posVec` interpolation.

Why this is new:

- Attempts 159, 161, 165, 167, and 168 tested stock jump families from the older canopy/perch movement path and did not establish route-safe tree-anchor movement.
- Attempt 182 proved one stock jump from the stable tree anchor is visible and route-safe.
- This is the first test of `Jump*2` from that stable tree-anchor baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE`
- `OverworldWildSpawns_TryPickStraightCanopyStepTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test350.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE` is enabled while the baseline and one-step probe flags are disabled.
- Verified the probe keeps the tree-anchor spawn override active by preventing the older perch relocation while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE` is enabled.
- Verified `OverworldWildSpawns_TryPickStraightCanopyStepTarget` picks a straight two-tile landing target and the active canopy tick starts a direction-specific stock `Jump*2` command with pending distance `2`.
- Verified the probe does not stage a far pending target, start a movement-list task, use helper/recreate paths, call the internal long-jump starter, touch phantom cleanup, or run raw `posVec` interpolation.
- The edited overlay compiled; unused-helper warnings are expected because the legacy canopy helper/recreate/movement-list paths remain disconnected during this probe.

Runtime result:

- User reported:
  - Mankey stays visible.
  - The hop visibly travels 2 tiles.
  - Leaving the route still avoids crash/freeze.

Learning:

- The stable tree-anchor baseline can safely run a stock real-object `Jump*2`.
- `Jump*2` is confirmed as a visible two-tile carrier in this context, contradicting the older failed canopy/perch results where the setup made the movement look like only 1-2 tile travel or became unstable.
- The next non-repeating probe is to chain two real-object `Jump*2` commands from the same tree-anchor baseline to test the user's possible practical 4-tile hop cap.

### Exploration Note: Directional Hop Accident

Prompt:

The user remembered that an earlier hop-in-place attempt accidentally did not lock the Pokemon in place, causing it to jump in the direction chosen by other behavior rules. Explore whether that accident points toward a canopy movement solution.

Relevant prior evidence:

- Attempt 50 used `LockDir -> Jump*2 -> WaitJumpSite -> ReleaseDir` for a spot emote. Runtime showed a visible hop, but the Pokemon moved toward the player instead of hopping in place.
- Attempt 51 replaced the moving `Jump*2` with `Jump*Site` under the same `LockDir`/`ReleaseDir` style wrapper. Runtime showed no visible hop.
- Attempt 52 used the follower/partner-style wrapper found in shipped scripts: `0x49 -> Jump*Site -> Freeze -> 0x4A`. Runtime finally showed a visible same-tile hop.
- Attempt 182 proved that a normal one-tile stock `Jump*` from the stable tree-anchor baseline is visible and route-safe.
- Attempt 183 is testing whether a normal two-tile stock `Jump*2` from the same stable tree-anchor baseline is visible and route-safe.

Interpretation:

- The old accident was likely not "hop-in-place almost worked"; it was evidence that moving jump commands (`Jump*` / `Jump*2`) correctly enter the visible airborne movement path when given a direction.
- The same-tile `Jump*Site` command only became visible after the follower/partner wrapper `0x49`/`0x4A`, which suggests that wrapper changes object presentation state, facing lock state, or follower-style jump prep/restore state.
- No prior attempt has combined the two useful ingredients from the stable tree-anchor baseline: `0x49`/`0x4A` partner wrapper plus a moving `Jump*` or `Jump*2` travel command.

Next non-repeating probe:

- Keep the stable tree-anchor setup from Attempts 181-183.
- Start a short moving canopy hop through a partner-style sequence: `0x49 -> direction-specific Jump*2 -> Freeze -> 0x4A`.
- Use only the real object and the existing frame-updated single-command path.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, or direct `MapObject_StartJumpMovementInternal`.
- If the wrapped `Jump*2` is visible and route-safe, test chaining two wrapped two-tile hops as the possible practical 4-tile hop cap.

### Attempt 185: Chained Jump2 Without Midpoint Tile Normalization

Idea:

Attempt 184 proves the two-segment stock `Jump*2` carrier can travel four tiles, but visibility is lost after the first two-tile segment. The current non-final segment handler rewrites object tile/init/prev state and X/Z render vectors with `OverworldWildSpawns_SetObjectTile` before the second segment. Test whether that midpoint normalization corrupts the stock jump/render state by skipping it only for the chained probe.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE`.
- Keep the same stable tree-anchor setup and the same staged four-tile cardinal target.
- Keep chaining stock direction-specific `Jump*2` commands through the existing pending-hop executor.
- On non-final segment completion, do not call `OverworldWildSpawns_SetObjectTile`; leave the stock movement command's landing state intact before the existing segment settle cooldown and second segment.
- Keep clearing `BIT_VANISH` at the canopy boundary.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 184 chained confirmed-safe stock `Jump*2` segments but still normalized the object at the midpoint.
- Earlier visibility attempts focused on helper objects, recreate/refresh, movement lists, raw render hopping, tree/perch selection, or direct internal long jumps.
- This is the first probe that isolates the midpoint `SetObjectTile` rewrite while keeping the otherwise successful four-tile stock chain.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test352.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE` is enabled while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE` is disabled.
- Verified the non-final canopy segment handler skips `OverworldWildSpawns_SetObjectTile` only for this probe.
- Verified the probe keeps the same stock direction-specific `Jump*2` segment chain and the same four-tile staged target from Attempt 184.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test352.nds`.
- Mankey only jumps two tiles at a time.

Learning:

- Fully skipping the midpoint tile normalization does not preserve the four-tile chained hop behavior from Attempt 184.
- The first segment likely still needs some logical midpoint commit before the second stock `Jump*2`.
- Since Attempt 184's full `SetObjectTile` midpoint commit preserved four-tile travel but broke visibility, the next probe should split logical tile commit from render-vector commit.

### Attempt 186: Chained Jump2 With Logical-Only Midpoint Commit

Idea:

Attempt 184 used full midpoint `OverworldWildSpawns_SetObjectTile` and preserved four-tile travel, but Mankey became invisible after the first two tiles. Attempt 185 skipped midpoint commit entirely and Mankey only jumped two tiles at a time. Test the middle path: commit only the logical tile/current/previous fields after the first segment, but leave the stock movement command's render vectors untouched.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE`.
- Add `OverworldWildSpawns_SetObjectLogicalTileOnly`, which updates `MapObject_SetCurrentX/Y`, `xInit/yInit`, and `xPrev/yPrev` but does not rewrite `posVec[0]` or `posVec[2]`.
- On non-final canopy segment completion, call the logical-only helper instead of full `OverworldWildSpawns_SetObjectTile`.
- Keep the same stable tree-anchor setup, staged four-tile cardinal target, segment settle cooldown, and stock direction-specific `Jump*2` chain.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 184 proved full midpoint tile/vector normalization preserves four-tile travel but breaks visibility.
- Attempt 185 proved no midpoint normalization preserves neither full travel nor the intended chain.
- No previous attempt has separated logical map-object tile commit from render-vector commit at the stock jump segment boundary.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE`
- `OverworldWildSpawns_SetObjectLogicalTileOnly`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test353.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE` is enabled while the full-midpoint and no-midpoint chained probes are disabled.
- Verified `OverworldWildSpawns_SetObjectLogicalTileOnly` commits current/init/previous tile fields but leaves `posVec[0]` and `posVec[2]` untouched.
- Verified the non-final canopy segment handler uses the logical-only helper for this probe.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test353.nds`.
- Mankey still only hops two tiles.
- In addition, Mankey gains no vertical height.

Learning:

- Logical-only midpoint commit does not preserve four-tile travel and also breaks the visible airborne presentation.
- The logical tile fields and render vectors are not separable enough to repair the stock `Jump*2` chain this way.
- Next probe should stop changing midpoint commit fields and instead test the untried shipped partner/follower wrapper around a moving `Jump*2` from the stable tree-anchor baseline.

### Attempt 191: Production Canopy Long-Jump Carrier

Idea:

Convert the successful Attempt 190 probe into a reusable movement carrier. The new helper should work for any cardinal tile distance that fits the internal jump frame budget, while the behavior/targeting layer remains free to choose normal ranges such as 5-7 tiles.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE`.
- Keep the successful partner-prepped internal-jump behavior active through production helpers, not through the probe block.
- Add `OverworldWildSpawns_GetCanopyLongJumpTiming` to derive frame count and arc step from distance.
- Keep the tested timing formula: `frameCount = distance * 8`, `arcStep = 0x1000 / frameCount`.
- Add `sOverworldWildCanopyLongJumpPrepActive[slot]` so finish/reset paths know whether the object has active partner-prepped presentation state.
- Rename the working starter to `OverworldWildSpawns_StartPreparedCanopyLongJumpCommand`.
- Make `OverworldWildSpawns_StartCanopyLongJumpCommand` derive direction and distance from a target tile, validate same-axis/cardinal movement, and delegate to the prepared helper.
- Let `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` attempt the prepared long-jump carrier for all cardinal pending canopy hops before falling back to legacy cleanup behavior.
- Restore `Freeze -> 0x4A` only when the per-slot prep flag is active.
- Clear the prep flag on normal finish and on movement reset; if a reset interrupts a still-active jump, clear the active movement first, then run restore if possible.

Why this is new:

- Attempt 190 proved the carrier but was hard-wired to the four-tile probe path.
- Earlier production helpers either lacked partner prep/restore or still used stock jump command sequences.
- This keeps the working primitive but removes the test-only distance assumption.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES`
- `sOverworldWildCanopyLongJumpPrepActive`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartPreparedCanopyLongJumpCommand`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_ResetSlotMovementCommand`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test358.nds` into the Delta ROM folder.
- Overlay compiled with the expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test358.nds` and reported that the behavior has "a lot of bugs" and that Mankey sometimes disappears and never reappears.

Learning:

- Generalizing the Attempt 190 carrier to any raw frame-budget distance was too broad.
- The production carrier should be constrained by the behavior's active tile range, not only by the internal jump frame budget.
- Short cleanup/return hops should not enter the partner-prepped long-jump path until they have their own proven presentation contract.

### Attempt 226: One Row Above Archive Mankey Tree-Top Target

Idea:

The user reported on `test421.nds` that Mankey is one tile too low on the canopy. Current code has a mismatch: `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW` still exists, but `OverworldWildSpawns_TryGetHeadbuttTreeTops` ignores it and uses `structuralTopY = minY`. Move the current strict `HEADBUTT_TREE_TOPS` target definition up one row by using `minY - 1`.

Why this is new:

- Attempt 249 used `minY - 2`, which later made some direct downward targets invisible.
- Attempt 254 restored raw `minY`, which made the movement target reachable but now lands one tile too low.
- Early `treeY - 1` attempts were from the old per-coordinate/forced-spawn model. This attempt changes the current strict-only archive resolver after the later down-first targeting, settled-tile latch, long-hop carrier, and no broad fallback fixes.
- This does not change rendering, field effects, proxy objects, movement carrier timing, or `OW_WILD_TILE_HEADBUTT` behavior.

Implementation shape:

- Change `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW` from `2` to `1`.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set `structuralTopY = minY - OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`.
- Reject negative resolved rows before adding the top-row target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test422.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User reported this made the game think the row above the real canopy was a tree-top tile.
- Screenshot showed Mankey standing one tile too high, with the marker bubble attached there.

Learning:

- `minY - 1` is not a valid `HEADBUTT_TREE_TOPS` definition in the current strict resolver.
- The `test421.nds` "Mankey is one tile too low" symptom should not be solved by changing logical tree-top targets.
- Restore raw archive `minY` for logical target/settled recognition and continue rendering work separately.

### Attempt 227: Restore Archive MinY Tree-Top Logic After Too-High Row

Idea:

Undo Attempt 226. The screenshot from `test422.nds` proves moving the strict tree-top row to `minY - 1` makes invalid upper tiles count as `HEADBUTT_TREE_TOPS`. Restore the logical target row to archive `minY` and keep the rendering/visibility problem separate from movement target selection.

Why this is new:

- Attempt 226 was the current strict-resolver middle-row test and failed.
- Attempt 254 previously made raw `minY` reachable; this attempt restores that rule after proving the one-row-up correction is wrong in the current build.
- This does not change rendering, field effects, proxy objects, movement carrier timing, settled-tile latching, or `OW_WILD_TILE_HEADBUTT` behavior.

Implementation shape:

- Set `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW` to `0`.
- Set `structuralTopY = minY` in `OverworldWildSpawns_TryGetHeadbuttTreeTops`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test424.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Restored raw archive `minY` as the logical `HEADBUTT_TREE_TOPS` row after the `minY - 1` probe made invalid upper canopy tiles count as tree tops.
- The visible one-tile-low/tree-obscured Mankey symptom should be investigated via render ordering or an overlay/effect-layer visual, not by shifting the accepted target row upward.

### Attempt 228: Sparse Archive Tree-Top Row Lift

Idea:

Fix the new screenshot where Mankey lands one row too low on a tree, without repeating the rejected global `minY - 1` shift from Attempt 226. Route 29 headbutt-tree data has mixed shapes: some trees contain a clean same-row adjacent two-tile pair, while sparse entries can have a single coordinate or only non-paired coordinates. Keep clean same-row pairs at raw archive `minY`, but let sparse entries derive their logical top row as `minY - 1`.

Why this is new:

- Attempt 226 moved every strict tree-top row to `minY - 1` and made image-2-style paired trees one tile too high.
- Attempt 227 restored raw `minY` globally, which fixed the too-high paired tree case but left the sparse/edge tree in image 1 one tile too low.
- This attempt changes the current archive resolver by tree-entry shape, not by a global row offset.
- It still does not use `OW_WILD_TILE_HEADBUTT` as a target definition and does not change map-object rendering, late-draw effects, proxy objects, movement carrier timing, or settled-state storage.

Implementation shape:

- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, detect actual adjacent coordinate pairs that share the same archive Y row.
- If any same-row pair exists, keep `structuralTopY = minY`.
- If no same-row pair exists, keep the existing X fallback but use `structuralTopY = minY - 1`.
- Leave paired image-2 trees on raw `minY` so the rejected one-row-too-high behavior is not reintroduced.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test425.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User reported `test431.nds` still places Mankey two tiles too far down on the top row of Route 29 trees.

Learning:

- For same-row two-coordinate entries, `minY` is not the visual top row. It is the lower/contact row of the 2x3 footprint, so the valid Mankey top row is `minY - 2`.
- Keep the multi-row case separate, because obstructed/overlapped 2x2 trees may already expose their top row as `minY`.

### Attempt 229: Live Blocked-Row Tree-Top Confirmation

Idea:

The user corrected the previous water/base-row assumption: the row under Mankey in the new screenshot is normal walking land, and Mankey is two tiles too low. Do not repeat the rejected global `minY - 2` attempt. Instead, keep the archive-derived row from Attempt 228 as the first proposal, then consult the live map: if the proposed tree-top row is still ordinary unblocked ground, lift the row upward until a blocked/canopy-like row is found, capped at two rows.

Why this is new:

- Attempt 249 set the strict row to `minY - 2` globally and later made some direct/downward targets disappear.
- Attempt 226 set the row to `minY - 1` globally and made paired trees one tile too high.
- Attempt 228 used only archive shape, which still allowed a normal walking-land row in the latest screenshot.
- This attempt makes row correction conditional on live map blocking, not on a fixed global offset or `OW_WILD_TILE_HEADBUTT`.

Implementation shape:

- Pass `FieldSystem *` into `OverworldWildSpawns_TryGetHeadbuttTreeTops`.
- After choosing the archive-derived row, test the two candidate top tiles with `IsMetatileBlockedAt`.
- If neither tile is blocked, lift the row upward, up to `OW_WILD_HEADBUTT_TREE_TOP_MAX_BLOCKED_ROW_LIFT` rows.
- Route both direct target picking and BFS target-grid marking through this field-aware resolver so they do not disagree.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_MAX_BLOCKED_ROW_LIFT`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test426.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 224: Mankey Tree-Top Late Map-Object Redraw Effect

Idea:

Create a custom field-effect descriptor whose lifetime is tied to a settled Mankey on a verified headbutt-tree top tile, then call `MapObject_GfxDraw` from that effect render callback. The hope was that field-effect render timing would submit the same Mankey sprite after the canopy layer.

Why this was new:

- Earlier attempts changed map-object height, priority bits, draw mode, follower flags, or proxy objects.
- This attempt used a real field-effect descriptor and effect lifetime, but kept the payload as the existing Mankey map-object draw.

Implementation shape:

- Added `OverworldWildFieldEffectDescriptor`.
- Added `OverworldWildMankeyTreeTopLateDrawEffectInit` / `Work`.
- Created/cleared the effect through `ov01_021F1620` / `ov01_021F1640` only while Mankey was settled on a cached tree-top tile.
- Render callback called `MapObject_GfxDraw(effectWork->object)`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `FieldEffect_GetInitData`
- `ov01_021F146C`
- `ov01_021F1620`
- `ov01_021F1640`

Verification:

- Built successfully before this log was repaired.
- Runtime checkpoint reported in thread summary as `test420.nds`.

Runtime result:

- User reported: "still not fixed".

Learning:

- Drawing the same `LocalMapObject` through a field-effect render callback is still the losing map-object renderer family.
- Do not retry effect-timed `MapObject_GfxDraw`, object height, follower flags, `unkA0`, priority bits, or proxy map objects without new renderer evidence.
- The next direction must use an effect-owned visual payload, not a redraw of the existing map object.

### Attempt 225: Mankey Tree-Top Effect-Owned Marker Canary

Idea:

Keep the successful field-effect lifetime/anchoring from Attempt 224, but remove the failed `MapObject_GfxDraw` payload. Instead, have the effect own a small timer and spawn a known-good speech-bubble marker over Mankey while the Mankey slot is settled on a verified tree-top tile. This tests effect anchoring, lifetime, and above-canopy visibility without touching movement or map-object render flags.

Why this is new:

- Attempt 224 used a field effect, but its payload was still `MapObject_GfxDraw`.
- Earlier bubble probes were separate periodic frame-task probes and could start before Mankey was actually settled on a tree-top tile.
- This attempt makes the marker a child of the tree-top effect's own validity path, so it should only appear while the exact Mankey slot/object/tile state is valid.

Implementation shape:

- Add `markerTimer` to `OverworldWildMankeyTreeTopLateDrawEffectWork`.
- Initialize the timer so the marker appears quickly after the effect is created.
- In the effect update callback, validate the Mankey slot/object/map/tile, then periodically call `OverworldWildSpawns_ShowBubble`.
- Remove the `MapObject_GfxDraw` call from the effect render callback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_ID`
- `OverworldWildSpawns_MankeyTreeTopLateDrawEffectUpdate`
- `OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md include/map_events_internal.h rom.ld` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test421.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

Learning:

- Pending.

Learning:

- Pending.

### Attempt 214: Bias Forced Verifier Ahead Of Player

Idea:

Attempt 213 still selected the same left-edge tree/perch. The scorer targeted a tile close to the player, but the forced spawn becomes eligible as soon as the player crosses the Route 29 threshold, so "close to player" still favors the old left-side tree. Bias the forced verifier toward a real Route 29 headbutt tree/perch ahead of the player, on the right side of the camera, so the capture can observe the hop instead of an edge object.

Why this is new:

- Attempt 210 changed pair ordering, not the camera-relative scoring target.
- Attempt 213 scored by resolved perch, but still aimed near the player.
- No previous attempt biases the forced Route 29 verifier toward an ahead/right camera-side perch.

Implementation plan:

- Add a real Route 29 headbutt coordinate from `armips/data/headbutt.s` (`594,389`) to the forced test pair list.
- Score fixed test perches toward `playerX + 6`, `playerY - 2` to prefer an ahead/right, top-screen-visible perch.
- Rebuild and capture a dense headless sequence.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test444.nds`.

### Attempt 242: Charmander Canopy Locator Probe

Runtime prompt:

- User reported the current tree-top/canopy locator still appears wrong and asked for a direct test spawner.

Learning:

- This is a diagnostic probe, not a behavior fix.
- Do not use normal wild spawn slots, normal spawn spacing, normal spawn count, or Mankey behavior to validate the locator.
- The probe should answer one question cleanly: which tile does the current canopy locator think is the closest valid canopy tile?

Implementation shape:

- Add a separate Charmander probe object ID range.
- Every 10 player steps, scan the current map's headbutt-tree top candidates through the shared locator and pick the closest candidate tile to the player.
- Spawn a stationary Charmander on that tile as a standalone map object.
- Ignore normal spawn spacing and normal spawn count.
- Reject only a tile that already has a Charmander probe object on it, so repeated steps fill additional closest candidates instead of stacking on one tile.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_CANOPY_CHARMANDER_PROBE_OBJECT_ID_START`
- `OverworldWildSpawns_TrySpawnCanopyCharmanderProbe`
- `OverworldWildSpawns_TryPickClosestCanopyCharmanderProbeTile`

Verification:

- Pending.

Runtime result from `test443.nds`:

- User reported no Charmander spawned.
- This means either the probe object path did not run/create an object, or the canopy locator returned zero candidates.

### Attempt 260: Charmander Probe Fallback Marker

Runtime prompt:

- The first Charmander canopy probe was silent when no canopy candidate existed.

Learning:

- A silent diagnostic is not good enough here: if the locator returns zero candidates, no Charmander appears and the result is ambiguous.
- The next probe must split "object spawning works" from "canopy locator works."

Implementation shape:

- Keep the normal success path: every 10 player steps, spawn Charmander on the closest candidate from `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`.
- If that locator returns no tile, spawn Charmander on a nearby normal land tile as a fallback marker.
- Continue to reject only tiles that already contain a Charmander probe, so repeated markers do not stack.
- If fallback Charmander appears, the locator is empty/broken. If no Charmander appears even with fallback, the probe tick/object creation path is broken.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TrySpawnCanopyCharmanderProbe`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test444.nds`.

### Attempt 261: Default Non-Phantom Reveal Guard

Runtime prompt:

- User reported the Charmander canopy probe can turn invisible.
- User clarified `BIT_VANISH` should not be something normal spawned Pokemon inherit or touch by default.
- `BIT_VANISH` should remain opt-in for phantom stalk movement only.

Learning:

- Previous phantom attempts showed repeated real-object `BIT_VANISH` toggling is fragile and should not leak into normal spawn behavior.
- The current phantom stalker implementation is the special case that intentionally uses vanish/flicker helper objects.
- Canopy hopper, Mankey, and diagnostic probe objects should be treated as normal visible map objects unless they are being deleted/despawned.

Implementation shape:

- Make `OverworldWildSpawns_CreateObject` clear `BIT_VANISH` immediately after any spawner-created object is allocated.
- Add a reusable non-phantom reveal guard that clears `BIT_VANISH` on all active normal spawn slots unless their resolved behavior profile is `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.
- Also clear `BIT_VANISH` on standalone Charmander canopy probe objects, since those are not tracked in normal spawn slots.
- Run the guard from the player-step path and the frame-movement task so stale vanish bits get corrected after both step-driven and frame-driven updates.
- Do not clear vanish on phantom flicker helper objects or active phantom stalk slots.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CreateObject`
- `OverworldWildSpawns_RevealNonPhantomObjects`
- `OverworldWildSpawns_SpawnSlotAllowsVanish`

Verification:

- First build failed because `LocalMapObject` uses `flags & MAPOBJECTFLAG_ACTIVE`, not an `active` field; corrected the probe-object scan.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before rebuild.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test445.nds`.

Runtime result from `test445.nds`:

- User reported Charmander is still invisible.

Learning:

- Clearing `BIT_VANISH` after creation is not enough for the Charmander probe.
- The special standalone Charmander probe object path itself is suspect.
- Do not keep the separate probe object ID/state lifecycle for this locator test.

### Attempt 238: Generic Headbutt Tree-Top Location Filter

Idea:

Make the settled headbutt tree-top location resolver reusable for future behavior profiles instead of keeping it named as Mankey-specific logic.

Why this is new:

- Earlier Mankey tree-top attempts focused on correcting the tile semantics and rendering. This pass does not change those semantics.
- The current goal is an internal API cleanup: future behaviors should be able to ask for valid headbutt tree-top locations without depending on Mankey names.

Implementation shape:

- Rename the footprint resolver to `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`.
- Rename the field/tile predicate to `OverworldWildSpawns_IsHeadbuttTreeTopLocation`.
- Rename the footprint-span constants from Mankey-specific names to `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_*`.
- Keep `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` as a thin wrapper for existing Mankey-specific call sites.
- Remove the older unused `OverworldWildSpawns_TryGetHeadbuttTreeTops` helper so there is one canonical generic tree-top location filter.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`
- `OverworldWildSpawns_IsHeadbuttTreeTopLocation`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_FOOTPRINT_HEIGHT_TILES`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_MAX_FOOTPRINT_Y_SPAN`

Verification:

- Pending.

Learning:

- Pending.

### Attempt 213: Score Forced Verifier By Resolved Perch

Idea:

Attempt 212 made the Route 29 test Mankey visible in early raw frames, but the actor is still at the left/bottom edge of the camera and the hop is not readable enough to verify. The fixed-pair verifier still chooses the first valid tree pair, then resolves that tree to a perch afterward. Instead, choose the forced test spawn by scoring the actual resolved perch relative to the player/camera.

Why this is new:

- Attempt 210 only reordered fixed tree pairs and still fell back to the old left-edge staging.
- Attempt 212 changed perch-side visibility preference, but did not change how fixed pairs are selected.
- No previous attempt scores forced Route 29 test candidates by the final resolved perch coordinate.

Implementation plan:

- In `OverworldWildSpawns_TryPickFixedRoute29CanopyTestSpawnPosition`, evaluate all fixed Route 29 pairs instead of returning the first valid one.
- Resolve each pair to a perch first, reject occupied/out-of-range perches, then score the perch toward a camera-centered tile near the player.
- Keep the one-tile vanilla `Jump*` movement-list carrier and the front/side perch preference.
- Rebuild and capture another dense headless sequence.

Verification:

- Pending.

Runtime result:

- Pending.

Learning:

- Pending.

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

### Attempt 197: Route 29 Top-Cap Coordinate Probe

Idea:

Keep the same stationary Mankey occupancy probe and normal render path from Attempt 196, but retarget the forced coordinate from `594,388` to `594,387`. This tests the visually higher top-cap row above the Route 29 headbutt anchors `(594,389)` / `(595,389)`.

Why this is new:

- Attempt 194 used the actual headbutt behavior tile `594,389`.
- Attempt 195/196 used `594,388`, which the user confirmed is the wrong visual tile class.
- This attempt changes only the forced coordinate to the likely top-cap row while keeping movement disabled and keeping the follower render bundle removed.

Implementation shape:

- Set `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y` to `387`.
- Keep `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X` at `594`.
- Keep the forced spawn idle/no-alert/no-attentive.
- Keep `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams` on the normal path, only clearing `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y`
- `OverworldWildSpawns_TryPickRoute29CanopyTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test364.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.

Runtime result:

- User reported this partially fixed the placement, but Mankey can still appear at the base/lower edge of the tree when that tile is closest to the walkable area.

Learning:

- `594,387` is closer to the desired canopy-top class than `594,388`, but it still reads as the walkable-adjacent lower canopy/base row.
- Do not treat the closest canopy tile above walkable ground as the desired tree-top perch. For this visual behavior, the target needs to be further inside/up on the canopy, not merely adjacent to the ground edge.

### Attempt 198: Route 29 Upper Top-Cap Coordinate Probe

Idea:

Keep the stationary Mankey occupancy probe and normal render path, but move one more tile upward from `594,387` to `594,386`. This tests whether the desired red-box tree-top tiles are the upper canopy cap rather than the walkable-adjacent lower edge.

Why this is new:

- Attempt 195/196 tested `594,388`, which was clearly too low/side-like.
- Attempt 197 tested `594,387`, which improved placement but still hit the lower base/edge row.
- This attempt changes only the forced coordinate to the next upper row while movement remains disabled and no follower render flags are reintroduced.

Implementation shape:

- Set `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y` to `386`.
- Keep `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X` at `594`.
- Keep the forced spawn idle/no-alert/no-attentive.
- Keep `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams` on the normal path, only clearing `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y`
- `OverworldWildSpawns_TryPickRoute29CanopyTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test365.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.

Runtime result:

- User reported this still did not place Mankey on the intended headbutt tree top.

Learning:

- Hardcoded Route 29 visual-coordinate guessing is not the right abstraction for this test.
- A future attempt should keep the logical object on a real headbutt-tree anchor from `ARC_HEADBUTT_TREES` and only adjust render placement, rather than pretending a nearby top-cap/base tile is the spawn tile.

### Attempt 199: Actual Headbutt Anchor With Render-Only Tree-Top Offset

Idea:

Stop relying on guessed Route 29 top/base coordinates. Pick a real headbutt tree tile directly from `ARC_HEADBUTT_TREES`, keep Mankey's logical object coordinates on that real tree anchor, and render it three tiles north through `posVec[2]` so it appears on top of the tree.

Why this is new:

- Attempts 194-198 moved the logical spawn coordinate between hardcoded Route 29 tiles.
- This attempt removes the hardcoded `594,386` style target and uses the actual headbutt-tree archive as the source of truth.
- It does not use the normal headbutt landing/perch spawner and does not call follower render flags.
- It keeps logical X/Y and render X/Z separate: collisions/state remain on the headbutt tree tile, while only the displayed Z position is offset upward.

Implementation shape:

- Replace the forced canopy-top coordinate constants with `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_RENDER_Y_OFFSET_TILES`.
- Add `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`, which iterates current-map headbutt tree archive entries, validates `OW_WILD_TILE_HEADBUTT`, and chooses a nearby actual tree anchor.
- Add `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual`, which keeps logical X/Y on the tree anchor, shifts `posVec[2]` by the visual offset, and clears `BIT_VANISH`.
- Refresh that visual every movement-frame tick for the forced stationary Mankey test so map-object updates cannot revert it after spawn.
- Replace stale active-spawn checks against hardcoded X/Y with "Mankey is on a current-map headbutt-tree tile."

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_RENDER_Y_OFFSET_TILES`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`
- `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual`
- `OverworldWildSpawns_IsObjectOnHeadbuttTree`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test366.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus old diagnostic globals.

Runtime result:

- User reported Mankey appeared to blink around.

Learning:

- Do not offset the rendered graphic separately from the actual headbutt-tree tile for this test.
- Do not retry render-only `posVec[2]` relocation or frame-refresh visual correction here; the user wants the actual object tile and displayed tile to be the same headbutt-tree tile.

### Attempt 200: Exact Headbutt Tile Occupancy, No Graphic Offset

Idea:

Keep the one useful part from Attempt 199: the forced test picks an actual current-map headbutt-tree tile from `ARC_HEADBUTT_TREES`. Remove the bad part: no render-only offset, no visual relocation, no frame refresh. The object's logical tile and displayed tile should both be exactly the chosen headbutt tree tile.

Why this is new:

- Attempts 194-198 moved hardcoded logical coordinates.
- Attempt 199 used the right source of truth for the logical tile, but added a render offset that made Mankey appear to blink around.
- This attempt keeps the archive-backed headbutt-tree spawn tile and explicitly synchronizes the object's X/Y and `posVec` back to that exact same tile.

Implementation shape:

- Remove the stale headbutt-tree top offset constant.
- Keep `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition` as the forced picker.
- Change `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual` to call `OverworldWildSpawns_SetObjectTile(object, position.startX, position.startY)` and clear `BIT_VANISH`.
- Do not adjust `posVec[2]` away from the actual tree tile.
- Do not refresh or move the graphic in the frame task.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test367.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus old diagnostic globals.

Runtime result:

- User reported no Pokemon spawned.

Learning:

- Exact-tile display is still the right visual direction, but the forced test cannot allow normal candidate filters or stale invisible slots to block the spawn entirely.
- A future attempt must guarantee that the forced test returns an archive coordinate whenever the map has headbutt-tree data, and must not rely on the normal headbutt encounter roll to produce the visible test Pokemon.

### Attempt 201: Guaranteed Forced Headbutt Mankey Spawn

Idea:

Fix the forced spawn path itself. Keep Mankey's logical/display tile exactly on the selected headbutt archive coordinate, but stop the forced test from failing because of normal spawner filters, invisible stale slots, or headbutt encounter-roll failures.

Why this is new:

- Attempt 200 used exact tile placement, but still allowed the forced picker to reject all candidates based on distance, nearby active spawns, and metatile behavior validation.
- Previous attempts still depended on the normal headbutt encounter roll before forcing the species to Mankey.
- This attempt makes the forced test deterministic: if the map has headbutt-tree archive entries, choose one, create Mankey, and clear stale invisible blockers.

Implementation shape:

- Remove distance, nearby-active-spawn, and metatile-behavior rejection from `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`.
- Keep scoring by distance so it prefers a nearby tree, but always accepts archive coordinates.
- Make invisible stale Mankey objects not count as an active forced test spawn, and clear them during forced-test refill preparation.
- Let forced-test refill cleanup run in any map context instead of only `MAP_R29`.
- In `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_OCCUPANCY_TEST`, create a fixed level 5 Mankey for headbutt terrain instead of requiring `OverworldWildSpawns_TryRollHeadbuttEncounter` to succeed.
- Keep `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual` exact: `OverworldWildSpawns_SetObjectTile(object, position.startX, position.startY)` and clear `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`
- `OverworldWildSpawns_HasActiveForcedCanopyHopperTestSpawn`
- `OverworldWildSpawns_PrepareForcedCanopyHopperTestRefill`
- `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_TEST_LEVEL`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test368.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus old diagnostic globals.

Runtime result:

- User rejected the interpretation: spawning on the headbutt/tree footprint contradicts the requested behavior.

Learning:

- The archive headbutt tile and the tree's own 2x2 footprint tiles are not valid Mankey spawn tiles for this test.
- The requested spawn tile is above that footprint, not on/inside it.
- Do not retry "spawn on archive tile" or "spawn on tree footprint" for this test.

### Attempt 202: Spawn On Row Above Headbutt Tree Footprint

Idea:

Treat each headbutt archive coordinate as part of the tree's 2x2 footprint, then spawn Mankey on the row immediately above that footprint. For the Route 29-style bottom-row headbutt coordinates, that means `spawnY = treeY - 2`; none of the tree footprint tiles themselves are valid.

Why this is new:

- Attempts 199-201 placed Mankey on the archive/headbutt coordinate or moved the rendered graphic from there.
- User clarified that the valid spawn tile is above the tree footprint, not any of the tree's four footprint tiles.
- This attempt changes the actual spawn tile before object creation; no render offset is involved.

Implementation shape:

- Add `OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES 2`.
- In `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`, compute `spawnX = treeX` and `spawnY = treeY - OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES`.
- Score candidates by distance to `spawnX/spawnY`.
- Set `position.startX/startY` and `position.headbuttPerchX/Y` to `spawnX/spawnY`.
- Keep `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual` exact: it sets the object tile to the chosen spawn tile and clears `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test369.nds` into the Delta ROM folder.
- Overlay compiled with the expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- User reported Mankey spawned one tile too high, then disappeared quickly.

Learning:

- This explicitly rejects the bad "tree footprint as spawn surface" model. The only valid test row is above the footprint.
- `spawnY = treeY - 2` overshoots by one tile for the current headbutt archive coordinate interpretation.
- Do not remove global distance despawn to solve this specific test; the user explicitly rejected that broad workaround.

### Attempt 203: Lower Tree-Top Test Tile And Preserve Forced Idle Visibility

Idea:

Move the forced Mankey test spawn one tile lower than Attempt 202 and keep it as an actual idle object. If the object temporarily has `BIT_VANISH`, reveal it instead of treating that as proof that the forced spawn is gone and deleting/refilling it.

Why this is new:

- Attempt 202 used `treeY - 2`, which user testing showed was one tile too high.
- Earlier attempts that moved graphics or used footprint tiles are still rejected.
- This attempt does not remove or bypass the normal distance despawn path.

Implementation shape:

- Replace `OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES 2` with `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_ROW_OFFSET_TILES 1`.
- In `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`, compute `spawnY = treeY - 1`.
- For the forced occupancy test only, stop treating `BIT_VANISH` on the active forced Mankey as a stale/deleted spawn during forced-refill checks; clear the bit and keep the object.
- Leave `OverworldWildSpawns_DespawnFarMons` unchanged.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_ROW_OFFSET_TILES`
- `OverworldWildSpawns_HasActiveForcedCanopyHopperTestSpawn`
- `OverworldWildSpawns_PrepareForcedCanopyHopperTestRefill`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test370.nds` into the Delta ROM folder.
- Overlay compiled with expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- Pending user test.
*** End of File

Learning:

- Pending.
Learning:

- Pending.


Learning:

- Pending.

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

### Attempt 224: Mankey Tree-Top Stock Large-Pokemon Draw Callback

Idea:

Do not repeat the failed height, follower-flag, `0x180` flag-only, or `unkA0` draw-mode probes. Instead, when spawned Mankey is settled on a verified headbutt-tree top tile, save its current `LocalMapObject::unkC8` draw callback and temporarily swap in the stock large-Pokemon draw callback from overlay 1 (`0x021F7811`). Restore the original callback when Mankey leaves the tree-top tile or the slot is cleaned up.

Why this is new:

- Attempt 223 changed `unkA0`, but left the draw callback unchanged. Disassembly suggests `unkA0` is only a sub-mode inside the same draw path.
- This attempt changes the actual map-object draw callback selected by callback descriptor index `17` (small Pokemon) to the already-existing descriptor index `16` large-Pokemon draw callback.
- It does not use a custom overlay callback, so it avoids the lifetime hazard of leaving a map object pointing at overlay 149 code during route/map transitions.
- It does not move the object, change object height, or reintroduce follower render flags.

Implementation shape:

- Replace the failed tree-top draw-mode save/restore state with per-slot draw-callback save/restore state.
- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK ((void (*)(LocalMapObject *))0x021F7811)`.
- In `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`, keep clearing `0x180`/`BIT_VANISH`, but set `object->unkC8` to the stock large-Pokemon draw callback while Mankey is on the verified tree-top tile.
- Restore the saved callback in `OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride` and clear saved callback state on spawn/slot cleanup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK`
- `sOverworldWildMankeyTreeTopDrawCallbacksSaved`
- `sOverworldWildMankeyTreeTopSavedDrawCallbacks`
- `OverworldWildSpawns_SaveMankeyTreeTopDrawCallback`
- `OverworldWildSpawns_RestoreMankeyTreeTopDrawCallback`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Verification:

- Checked the log first; stock draw-callback swapping had not been tried.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed before documenting the attempt.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test380.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Superseded before user test.

Learning:

- A read-only renderer explorer reported that the large-Pokemon callback path is likely just another size/model family and not a true "above priority canopy" path.
- Keep this build result as a checkpoint, but do not spend runtime testing time on `test380.nds` unless the newer helper callback probe fails to build.

### Attempt 225: Mankey Tree-Top Stock Helper Draw Callback

Idea:

Follow the renderer explorer's more precise recommendation: keep the same Mankey-only `unkC8` callback save/restore probe from Attempt 224, but use the stock helper/special-object draw callback `0x021F7919` instead of the stock large-Pokemon draw callback `0x021F7811`.

Why this is new:

- Attempt 224 used the existing large-Pokemon draw callback. It was built but superseded before runtime testing after the explorer identified `0x021F7919` as the more relevant helper/special-object candidate.
- No previous runtime attempt has swapped spawned Mankey to the stock helper/special-object draw callback while it is on the verified tree-top tile.
- This still avoids a custom overlay callback lifetime hazard and still does not touch object height, `posVec`, follower render flags, or `unkA0`.

Implementation shape:

- Change `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK` from `0x021F7811` to `0x021F7919`.
- Keep the existing per-slot original-callback save/restore, priority-bit clearing, and `BIT_VANISH` clearing from Attempt 224.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK`

Verification:

- Checked the log first; this exact helper callback swap had not been tried.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test381.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User reported that Mankey is still hidden by the headbutt-tree canopy on `test381.nds`.

Learning:

- Swapping to the stock helper/special-object draw callback still does not change the relevant canopy ordering.
- Combined with Attempt 224's large-Pokemon callback probe, stock `unkC8` callback swapping is very likely the wrong level of the renderer. Do not keep cycling stock draw callbacks as the primary solution.
- The next useful direction is a real Mankey-only post-draw sprite/OAM priority or depth probe, while avoiding the already-failed object-height, follower-flag, `0x180` flag-only, `unkA0`, and stock-callback-swap approaches.

### Attempt 226: Mankey Tree-Top Post-Draw Sprite Priority Probe

Idea:

Stop using stock callback replacement as the solution. Instead, use the normal small-Pokemon draw callback for Mankey, then apply a narrowly scoped cell/OAM priority override to the sprite resource only while the spawned Mankey is on a verified headbutt-tree top tile. This keeps the logical tile unchanged and targets the renderer ordering layer directly.

Why this is new:

- Attempts 224 and 225 changed which stock draw callback ran, but did not apply any post-draw mutation to the object sprite itself.
- Attempts 220, 194, 195, 221, and 223 already ruled out object height/`posVec`, follower render flags, priority-bit clearing alone, and `unkA0` draw-mode changes.
- A renderer explorer clarified that `sub_02023F04`/`sprite + 0xB6`/`sprite + 0xB8` is animation/cell-frame state, not BG priority. This attempt therefore avoids the earlier depth/frame-index guess.
- This attempt clears cell/OAM `attr2` priority bits (`0x0C00`) for the loaded sprite cell entries after the normal small-Pokemon draw path has run, so the sprite should draw above BG priority layers on subsequent frames.

Implementation shape:

- Replace the tree-top stock-callback swap with a custom ARM9-resident wrapper that calls the normal small-Pokemon draw callback (`0x021F7895`), obtains the map-object sprite pointer from render data (`object + 0x108`), walks the loaded cell bank, and clears the priority bits from visible cell OAM entries.
- Keep the wrapper Mankey/tree-top gated and restore the original callback when the slot leaves the tree-top tile or is cleaned up.
- Leave the old Mankey/tree-top `0x180` and `BIT_VANISH` clearing in place because that was already part of the surrounding tree-top override, but do not rely on it as the primary solution.

Files/symbols:

- `include/overworld_wild_spawns.h`
- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_MankeyTreeTopDrawWrapper`
- `OW_WILD_MANKEY_TREE_TOP_CELL_PRIORITY_MASK`

Verification:

- Checked this log first and confirmed this is not a repeat of the failed object-height, follower-flag, `0x180` flag-only, `unkA0`, large-Pokemon callback, or helper callback attempts.
- `git diff --check -- include/overworld_wild_spawns.h src/overworld_wild_spawns.c src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test382.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User tested `test382.nds`:
  - Mankey still does not render above the headbutt-tree canopy.
  - Mankey stays visible and stable, but remains behind the tree.
  - Leaving the route still avoids crash/freeze.

Learning:

- Build confirmed the ARM9-resident wrapper and overlay callback install path compile/link cleanly.
- Loaded cell/OAM priority is not the renderer layer that controls this headbutt-tree canopy ordering, or the mutation is too early/resource-local to affect the final draw ordering.
- Since Mankey stays visible and route-stable, the remaining problem is specifically priority/layering, not spawn tile selection, invisibility cleanup, or route-transition ownership.
- Do not repeat object-side priority tweaks unless new renderer evidence identifies the actual final OAM/hardware slot or BG/object priority contract.

### Attempt 227: Mankey Tree-Top Live Sprite Depth Zero Probe

Idea:

Attempt 226 mutated the loaded cell/OAM resource and did not affect the canopy ordering. Disassembly of overlay 1 still shows the normal field-object draw variants call `sub_02023F04` with depth-like constants such as `0`, `0x800`, `0x1000`, and `0x2000`, and the current Mankey path was previously observed to keep reaching the `0x1000` family. Test a distinct, narrower live-sprite probe: while Mankey is on the verified tree-top tile, call the normal small-Pokemon draw callback, but force the live sprite depth/range value at `sprite + 0xB8` to `0` immediately before and after the normal draw.

Why this is new:

- Attempt 223 changed `LocalMapObject::unkA0` draw mode but did not directly set the live sprite depth value.
- Attempts 224 and 225 changed stock callback family but still let those callbacks choose their normal live sprite depth.
- Attempt 226 cleared loaded cell/OAM `attr2` priority bits in the cell bank, not the live sprite's `+0xB8` depth value.
- This does not retry object height, follower render flags, `0x180` flag-only clearing, stock callback cycling, or loaded cell-bank mutation.

Implementation shape:

- Keep the same Mankey/tree-top-gated ARM9-resident wrapper and original callback save/restore from Attempt 226.
- Replace the loaded cell-bank/OAM traversal with `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH ((void (*)(void *, u32))0x02023F1D)`.
- In `OverworldWildSpawns_MankeyTreeTopDrawWrapper`, obtain render data from `object + 0x108`, set primary/secondary live sprite depth to `0`, call the normal small-Pokemon draw callback (`0x021F7895`), then set depth to `0` again in case the callback rewrote it.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH`
- `OW_WILD_MANKEY_TREE_TOP_FRONT_DEPTH`
- `OverworldWildSpawns_SetMankeyTreeTopRenderDataDepth`
- `OverworldWildSpawns_MankeyTreeTopDrawWrapper`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test383.nds`.
- Compile warnings were limited to existing unused-parameter / unused-helper diagnostics in unrelated or long-running debug code.
- User tested `test383.nds`:
  - Mankey still does not render above the canopy.
  - Mankey stays visible after a few seconds, but remains behind the tree.
  - Leaving the route still avoids crash/freeze.

Learning:

- Build confirms the live sprite depth setter probe compiles, links, and packages cleanly.
- Setting the live sprite depth/range value before and after the normal draw callback does not beat the headbutt-tree canopy layer.
- Together with Attempt 226, object-side priority/cell/depth mutation appears exhausted unless new renderer evidence identifies a different final draw layer.

### Attempt 228: Mankey Tree-Top Synced Visual Proxy

Idea:

Attempts 223-227 exhausted the real object's draw-mode, draw-callback, loaded cell/OAM priority, and live sprite depth levers. Instead of mutating the real Mankey object again, keep the real object as the logical actor and create a separate Mankey-only visual proxy object while the real object is settled on a verified headbutt-tree top tile. The proxy uses its own ignored object-id range and is synced to the real object's visual position each update, but its logical anchor is the headbutt-tree/front coordinate.

Why this is new:

- It does not change the real object's `unkA0`, `unkC8`, height fields, `posVec`, loaded OAM/cell data, live sprite depth, or follower render flags.
- It does not retry the rejected render-offset-on-real-object approach from Attempt 199.
- It adapts the already route-safe phantom helper-object pattern, but gives Mankey its own proxy object-id range and cleanup path.
- If this proxy still renders behind the canopy, the next useful path is a map/compositor layer identification probe rather than more map-object priority work.

Implementation shape:

- Add `movementMankeyTreeTopProxyObjects[OW_WILD_MAX_SPAWNS]` to `OverworldWildSpawnState`.
- Add `OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START` and make spawn-position occupancy ignore this visual-only id range.
- When Mankey is on `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`, restore any old tree-top render override on the real object, clear `BIT_VANISH`, and ensure a proxy object at `(objectX, objectY + OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET)`.
- Sync the proxy's `posVec` and facing to the real object each update, while leaving the real object active and visible for this first test.
- Delete or detach the proxy through slot cleanup, movement reset, route-context detach, and canopy visual-boundary cleanup.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START`
- `movementMankeyTreeTopProxyObjects`
- `OverworldWildSpawns_EnsureMankeyTreeTopProxyObject`
- `OverworldWildSpawns_ClearMankeyTreeTopProxyObject`
- `OverworldWildSpawns_IsIgnoredVisualObjectId`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test384.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics, the existing unused `bsys` battle warning, and the now-unused old Mankey tree-top priority-save helpers because this proxy probe no longer activates the failed priority-wrapper path.
- User tested `test384.nds`:
  - Mankey appears above the canopy for only roughly 1-2 frames.
  - After that, Mankey is visible only behind the tree.
  - Leaving the route still avoids crash/freeze.
  - Duplicate/offset Mankey weirdness is visible.

Learning:

- Build confirms the proxy object-id range, proxy state pointer, sync path, cleanup path, and occupancy-ignore path compile/link cleanly.
- A map-object proxy can briefly escape on creation, but the normal field object renderer quickly reasserts the same canopy ordering.
- Do not pursue a constantly recreated map-object proxy as a real fix; it would likely be brittle and visually noisy.
- The next useful direction is a map/compositor layer identification probe or a non-map-object effect layer, not another map-object priority/proxy variation.

### Attempt 229: Mankey Tree-Top BG Layer Identification Probe

Idea:

Attempt 228 showed that even a separate map-object proxy falls back behind the canopy after the first frame or two. Since Attempts 223-228 now rule out the normal map-object render levers, identify which Engine A layer owns the headbutt-tree canopy. While Mankey is settled on a verified tree-top tile, temporarily cycle visible BG layer masks using `GX_EngineAToggleLayers` so runtime testing can tell whether disabling one layer removes the canopy while the Pokemon remains visible.

Why this is new:

- It does not change Mankey's map object, sprite callback, sprite data, OAM priority, depth/range state, height, `posVec`, follower flags, or proxy objects.
- It follows Erdos' renderer investigation: overlay 1 uses `GX_EngineAToggleLayers = 0x02022C60 | 1` around field compositor setup, so this probes map/compositor planes rather than the object renderer.
- It removes the failed synced proxy behavior from the active tree-top path before adding the new diagnostic.

Implementation shape:

- Add a tiny diagnostic state machine with phases for masks `2`, `4`, `8`, and a restore phase.
- When any active Mankey is on a verified tree-top tile, cycle every fixed number of frames:
  - phase 0: disable mask `2`, enable masks `4` and `8`
  - phase 1: disable mask `4`, enable masks `2` and `8`
  - phase 2: disable mask `8`, enable masks `2` and `4`
  - phase 3: enable all three masks
- When no active Mankey is on the tree-top tile, restore all masks and reset the diagnostic timer.
- Keep the real Mankey visible and delete any leftover proxy object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `GX_EngineAToggleLayers`
- `OverworldWildSpawns_UpdateMankeyTreeTopLayerProbe`
- `OverworldWildSpawns_AnyMankeyOnHeadbuttTreeTopTile`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- Removed active creation/sync of the failed Mankey tree-top proxy from the tree-top update path; any leftover proxy object is deleted when the real Mankey is updated.
- Added `GX_EngineAToggleLayers` layer cycling while any active Mankey is on a verified headbutt-tree top tile:
  - phase 0 disables mask `2`
  - phase 1 disables mask `4`
  - phase 2 disables mask `8`
  - phase 3 restores all three masks
- The probe advances from the frame task rather than player-step only, so the layer cycle should continue while the player stands still.
- Added restoration on context loss, spawner clear, and frame-task stop so the route should not inherit a disabled layer.
- `git diff --check` passed.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test385.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 236: Mankey Tree-Top Effect-Layer Bubble Probe

Idea:

Now that Mankey reaches the intended tree-top tiles, revisit the sprite layering issue where the Pokemon remains behind the tree canopy. Do not repeat object-height, follower flags, object priority bits, draw mode, stock draw-callback swaps, loaded cell priority, live sprite depth, or map-object proxy attempts. Instead, test a different render family: the follower/emote bubble effect layer. If a bubble attached to a tree-top Mankey draws above the canopy, then a future custom effect-layer visual for Mankey is a better path than continuing to mutate map-object rendering.

Why this is new:

- Attempts 223-228 exhausted normal map-object render levers and proxy objects.
- Attempt 229 added BG layer cycling, but it was only a diagnostic and can confuse visual testing now.
- This attempt uses the existing follower/emote bubble effect path (`ov01_02203A48`) from the spawned Mankey's tree-top anchor, which is a separate layer family from map-object sprites.

Implementation shape:

- Disable the old Mankey tree-top BG layer cycling by adding `OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED 0`; the restore function still keeps all layers enabled.
- Add `OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_FRAMES`.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe`, which periodically calls `OverworldWildSpawns_ShowBubble` with an exclamation bubble while an active Mankey is on a `HEADBUTT_TREE_TOPS` tile.
- Run the bubble probe from the frame movement task so it continues while the player stands still.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ID`
- `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe`
- `OverworldWildSpawns_ShowBubble`
- `ov01_02203A48`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test394.nds`.
- User confirmed the exclamation bubble is visible above the canopy while the real Mankey remains hidden behind the tree.
- The later follower-sprite proxy probe was also confirmed to remain behind the canopy.

Learning:

- The follower/emote bubble path (`ov01_02203A48`) is a proven above-canopy render family.
- The normal map-object family is still behind the canopy, including a separate following-sprite proxy object.
- Stop pursuing map-object render/proxy fixes for this tree-top layer issue; the next useful path is an overlay/effect-layer visual probe or clone.

### Attempt 237: Cache Mankey Tree-Top Archive Predicate

Idea:

The user reported Mankey has been incredibly laggy for several builds. Do not repeat Attempt 222's failed-path backoff, which only throttled no-path searches and removed archive checks from the BFS inner loop. The remaining repeated hotspot is the tree-top predicate itself: the Mankey chill branch, tree-top render update, and Attempt 236 bubble probe all ask whether the current Mankey tile is a `HEADBUTT_TREE_TOPS` tile. That predicate reloads/scans headbutt-tree archive data. Cache the result per slot/map/tile so the archive-backed predicate is only recomputed when that Mankey changes tile, map, or slot lifecycle.

Why this is new:

- Attempt 222 optimized failed path searches and target-grid lookup, but it did not cache the "am I currently on a tree-top tile" predicate.
- Attempt 236 added a per-frame bubble probe that also used that predicate, making the old repeated-check cost more visible.
- This does not change Mankey's path selection, target definition, hop timing, render flags, or layer behavior.

Implementation shape:

- Add per-slot static cache state for Mankey tree-top checks:
  - cached map id
  - cached x/y tile
  - cached boolean result
- Add `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached`.
- Route the runtime Mankey tree-top checks through the cached wrapper.
- Clear the cache on slot clear and spawn setup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildMankeyTreeTopCacheValid`
- `sOverworldWildMankeyTreeTopCacheResult`
- `sOverworldWildMankeyTreeTopCacheX`
- `sOverworldWildMankeyTreeTopCacheY`
- `sOverworldWildMankeyTreeTopCacheMapId`
- `OverworldWildSpawns_ClearMankeyTreeTopCache`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test395.nds`.
- User reported the exclamation bubble loop starts way before Mankey is actually on a tree.

Learning:

- Caching may still help performance, but the bubble probe was using the broad coordinate predicate as "perched" state.
- A coordinate matching `HEADBUTT_TREE_TOPS` is not enough to decide the layer probe should run; it needs a real completed final tree-hop/perched state.

### Attempt 238: Gate Mankey Bubble Probe On Final Tree-Top Landing

Idea:

Fix the premature exclamation bubble loop from `test395.nds`. Do not remove the layer probe or repeat object priority/render attempts. The problem is that the bubble probe uses the coordinate predicate directly, so any false-positive or pre-landing `HEADBUTT_TREE_TOPS` coordinate can start the bubble loop. Track whether the currently staged Mankey hop is expected to land on an actual final tree-top target, then only allow the bubble probe after that final hop has completed.

Why this is new:

- Attempt 236 added the bubble probe but keyed it directly off the tree-top coordinate predicate.
- Attempt 237 cached that predicate for performance but did not distinguish final tree-top landing from pre-tree/intermediate states.
- This attempt adds an explicit final-landing/perched gate for the bubble probe without changing the target definition, hop pathing, or render layer experiment.

Implementation shape:

- Add per-slot static flags:
  - `sOverworldWildMankeyTreeTopLandingExpected`
  - `sOverworldWildMankeyTreeTopSettled`
- Extend `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` to report whether its returned target is a final tree-top target or an intermediate path step.
- When Mankey stages a canopy hop, arm `sOverworldWildMankeyTreeTopLandingExpected` only for final tree-top targets.
- When the pending canopy hop finishes, set `sOverworldWildMankeyTreeTopSettled` only if that final target was expected.
- Make `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe` require `sOverworldWildMankeyTreeTopSettled`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildMankeyTreeTopLandingExpected`
- `sOverworldWildMankeyTreeTopSettled`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_FinishPendingCanopyHop`
- `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test396.nds`.
- Pending user runtime test.

Learning:

- Pending. Test specifically whether the exclamation loop no longer starts before Mankey reaches the tree and whether it still appears after final tree-top landing.

### Attempt 239: Align Mankey Tree-Top Settled Rows With Target Rows

Idea:

The user reported a Mankey behind the canopy that keeps moving back and forth even though it is on a visible tree-top tile. This is not the same as the premature bubble loop from Attempt 238. The target picker already allows both structural top rows and exposed top rows by calling `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., TRUE, ...)`, but the settled predicate still calls the same helper with `FALSE`. That means Mankey can legitimately target and land on an exposed tree-top row, then fail the idle settled check and immediately try to move again.

Why this is new:

- Attempt 235 defined the dedicated `HEADBUTT_TREE_TOPS` target set.
- Attempt 238 added a final-landing gate for the bubble probe but did not change which rows count as settled.
- No prior attempt aligned the settled predicate's row definition with the target picker's row definition.

Implementation shape:

- Change `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` to call `OverworldWildSpawns_TryGetHeadbuttTreeTops` with `includeExposedRows = TRUE`.
- This makes idle/perched detection match the Mankey target selection row set.
- The bubble probe remains guarded by `sOverworldWildMankeyTreeTopSettled`, so broad coordinate matches alone should still not restart the premature bubble loop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test397.nds`.
- Pending user runtime test.

Learning:

- Pending. Test specifically whether Mankey now stops moving once it reaches the visible/exposed tree-top tile shown in the screenshot.

### Attempt 249: Target Two Tiles Above Headbutt Archive Row

Idea:

The user clarified that the base at the tree is not a tree top; Mankey needs to land two tiles above it. Attempt 248 proved `minY` is a real tree-associated row, but runtime showed it is the wrong visual row. Keep the strict-only target system, but define Mankey's visual tree top as `minY - 2`.

Why this is new:

- Attempt 246-247 used `maxY - 5`, which targeted too high/wrong rows.
- Attempt 248 used `minY`, which runtime showed is the base/contact row.
- This attempt keeps the successful strict-only cleanup but changes the strict visual row to exactly two tiles above the archive row, matching the latest user correction.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW 2`.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set the strict row to `minY - OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`.
- Reject negative strict rows.
- Change `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` to call `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., FALSE, ...)`, so the base/contact row is not considered a settled tree-top tile.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test408.nds`.
- Build warnings were limited to the existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- User confirmed Mankey reaches the intended hidden tree-top position, and the exclamation bubble attached to that hidden Mankey is visible above the canopy.
- This proves the problem is not that Mankey is gone or on the wrong tile; it is specifically normal Pokemon map-object sprite ordering versus the canopy layer.
- The bubble is rendered through the follower/emote overlay effect path, so a true effect-layer visual remains the most promising long-term direction.

### Attempt 250: Follower-Sprite Tree-Top Proxy Probe

Idea:

Use the new bubble result to test one more renderer family before committing to a custom effect-layer clone. Do not repeat the old special-field proxy from Attempt 228, which was created with `CreateSpecialFieldObjectWithParams` and quickly fell behind the canopy. Instead, while the real Mankey remains the logical actor on the tree-top tile, create a visual-only proxy through the actual follower-sprite factory `CreateFollowingSpriteFieldObject` and keep it synced on the same tile.

Why this is new:

- Attempt 228 used a normal special field object proxy, not the follower-sprite factory.
- Attempts 194/195 mutated the real Mankey with follower-style flags and caused blinking/invisibility; this keeps the real actor untouched.
- Attempt 236 proved follower/emote overlay effects can draw above canopy, but it only rendered a bubble, not a Pokemon sprite.
- Dewey's read-only renderer investigation found no stock helper for arbitrary Pokemon sprites on the bubble layer, but confirmed the overlay/effect system is the likely layer family if this proxy still loses to the canopy.

Implementation shape:

- Add `OverworldWildSpawns_EnsureMankeyTreeTopProxyObject`, which creates a Mankey proxy with `CreateFollowingSpriteFieldObject` only while the real active Mankey is on a cached `HEADBUTT_TREE_TOPS` tile.
- Give the proxy the existing ignored visual object-id range so it does not block spawning or battle checks.
- Sync the proxy tile/facing to the real Mankey and clear `BIT_VANISH`.
- Delete the proxy when Mankey leaves the tree-top tile or the slot/context cleanup runs.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `CreateFollowingSpriteFieldObject`
- `OverworldWildSpawns_EnsureMankeyTreeTopProxyObject`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test409.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending. If this proxy is also behind the canopy, stop using map objects for this layer problem and move to a custom overlay/effect-layer visual clone based on `ov01_02203A48` / descriptor table `0x02209518`.

### Attempt 251: Prefer Unblocked Direct Mankey Tree-Top Directions

Idea:

Fix the case where Mankey appears to prefer a blocked upward direct tree-top candidate and never considers an obvious 3-tile downward jump. The direct tree-top picker currently returns before the BFS/path fallback and only ranks direct tree-top candidates by distance. Keep direct tree-top targeting, but add a first-step blocked tier: direct candidates whose immediate direction is not blocked beat direct candidates whose immediate direction is blocked, even if the blocked candidate was scanned first.

Why this is new:

- Attempts 247-249 changed which coordinates count as strict tree-top targets.
- Attempt 250 targeted tree-top rendering and did not change movement target priority.
- No previous attempt has ranked direct Mankey tree-top candidates by whether their immediate cardinal direction is blocked.
- This does not reintroduce `OW_WILD_TILE_HEADBUTT`, broad vertical bands, or exposed-row fallbacks.

Implementation shape:

- Pass the active Mankey object into `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`.
- For each same-axis direct tree-top candidate, derive its cardinal direction and check `MapObject_IsMovementDirectionBlocked(object, direction)`.
- Track `bestBlockedRank` across all scanned headbutt trees. Rank `0` unblocked candidates ahead of rank `1` blocked candidates; within the same rank, keep the existing nearest-distance selection and random tie-break.
- Keep blocked candidates as fallback if every direct tree-top option is blocked.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test411.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending user test. The screenshot case should now prefer the 3-tile downward jump when the upward direct candidate is blocked, while keeping blocked direct candidates as fallback only when no unblocked direct candidate exists.

### Attempt 252: Generic Field Effect Probe For Tree-Top Mankey

Idea:

Use the user-confirmed bubble result to stop map-object rendering work and test a broader effect family. The emotion bubble path is visible above canopy but can only display built-in icons. Before attempting a custom Mankey effect actor, call the generic anchored field-effect helper `ov01_021FFF5C(object, effectId)` from settled tree-top Mankey and cycle a small range of effect ids. If these effects render above canopy too, they provide a better template for a custom visual clone than more map-object mutations.

Why this is new:

- Attempts 223-228 and 250 exhausted real-object render levers and proxy map objects.
- Attempt 236 proved the follower/emote bubble effect layer is visible above canopy.
- Earlier Onix attempts used `ov01_021FFF5C` for ram step feedback, but not for settled Mankey tree-top layering.
- This does not retry `CreateFollowingSpriteFieldObject`, object height, draw mode, draw callbacks, OAM priority, live sprite depth, layer toggling, or emotion bubble icons as the final visual.

Implementation shape:

- Disable the Mankey tree-top bubble probe now that it has answered the layer question.
- Stop creating the Mankey tree-top proxy object while Mankey is on a verified tree-top tile; delete any stale proxy from that path.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopEffectProbe`, called from the frame movement task after the layer/bubble probe hooks.
- While a settled active Mankey is on a verified tree-top tile, call `ov01_021FFF5C(object, effectId)` every 90 frames and cycle effect ids `0..12`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED`
- `OverworldWildSpawns_UpdateMankeyTreeTopEffectProbe`
- `ov01_021FFF5C`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test412.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending user test. Test whether the cycling anchored effects appear above canopy, behind canopy, or not at all while Mankey remains on the tree-top tile.

### Attempt 253: Down-First Mankey Tree-Top Target Selection

Idea:

Fix the repeated case where Mankey is above a valid tree-top target but does not jump down three tiles. Attempt 251 still used `MapObject_IsMovementDirectionBlocked` to rank direct tree-top candidates, but final Mankey tree-top targets are intentionally allowed even when normal passability/blocking would reject the destination. That means the blocked helper can wrongly downgrade the exact downward tree-top jump we want.

Why this is new:

- Attempt 251 ranked direct targets by blocked/unblocked immediate direction.
- Earlier target attempts changed which tree-top coordinates are valid, but did not make downward direct jumps deterministic.
- This attempt removes normal blocked-direction ranking from final tree-top target choice and changes only Mankey's tree-top target ordering.
- This does not change the long-hop carrier, render layer probes, headbutt-tree-top coordinate definition, or `OW_WILD_TILE_HEADBUTT` handling.

Implementation shape:

- Disable the generic tree-top effect probe so this ROM tests movement only.
- Add `OverworldWildSpawns_GetMankeyTreeTopDirectionRank`: down is rank `0`, left/right rank `1`, up rank `2`.
- In `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`, stop calling `MapObject_IsMovementDirectionBlocked`.
- Direct targets now rank by shortest distance first; if distance ties, prefer down, then sideways, then up.
- In `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`, search fallback jump directions in down/left/right/up order instead of up/down/left/right.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_GetMankeyTreeTopDirectionRank`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test413.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending user test. The screenshot case should now choose the downward 3-tile tree-top jump instead of stalling or preferring an upward candidate.

### Attempt 254: Restore Archive MinY As Strict Tree-Top Row

Idea:

Fix the remaining refusal to jump three tiles down by restoring the strict `HEADBUTT_TREE_TOPS` row to archive `minY`. Current code had drifted back to `minY - OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`, which targets rows above the actual archive top-row pair. That can make the real 3-tile-down target invisible to both the direct picker and the fallback target grid.

Why this is new:

- Attempt 247 already established from Route 29 archive examples that obvious visual top-row pairs are stored at `minY`.
- Attempt 253 fixed target ordering, but did not notice the strict row had drifted back upward.
- This is not a new broad-row or exposed-row fallback; it restores the strict single-row target definition to the previously verified archive row.
- This does not reintroduce `OW_WILD_TILE_HEADBUTT`, exposed rows, broad bands, render probes, or proxy objects.

Implementation shape:

- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set `structuralTopY = minY`.
- Leave direct target selection down-first from Attempt 253.
- Leave settled/current-tile recognition strict-only.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test415.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- Pending user test. The direct 3-tile-down jump should now be recognized as an actual tree-top target instead of aiming above it.

### Attempt 255: Snap Final Canopy Landing After Partner Restore

Idea:

The user reported that `test415.nds` finally jumps onto the intended tree-top tile, but then Mankey is pushed one tile upward afterward. That means Attempt 254 fixed target selection, and the remaining bug likely happens after the hop lands. The active long-hop path wraps the internal jump with partner prep/restore commands, and final landing was checked before the restore command ran. If the restore nudges object state, the landed object can drift after the correct target was reached.

Why this is new:

- Attempt 254 changed only the strict tree-top row used for target selection.
- Earlier canopy landing attempts changed refresh/recreate behavior, intermediate segment handling, or target rows.
- This attempt does not change tree-top detection, pathing, direct down-first ordering, render probes, object recreation, or `OW_WILD_TILE_HEADBUTT`.
- It only normalizes the final landing tile after the partner restore wrapper has run.

Implementation shape:

- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, cache the staged canopy target before any cleanup can clear it.
- After the long-jump partner restore command runs, if this was the final landing, call `OverworldWildSpawns_SetObjectTile(object, targetX, targetY)`.
- Then run the existing canopy visual cleanup, `OverworldWildSpawns_FinishPendingCanopyHop`, and Mankey tree-top visual update.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test416.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- User reported `test416.nds` made Mankey vanish after every jump.
- Do not retry a full `OverworldWildSpawns_SetObjectTile(object, targetX, targetY)` final snap after partner restore for canopy hoppers. That repeats the historical heavy tile/vector reset visibility failure.

### Attempt 256: Skip Final Mankey Tree-Top Partner Restore

Idea:

Undo the harmful Attempt 255 final tile/vector snap. The new runtime clue says the snap made Mankey vanish, which matches older findings that heavy `SetObjectTile` normalization can corrupt canopy-hop visibility. The remaining one-tile-up shove still appears to happen after the correct landing, so test the direct post-landing culprit instead: keep the partner prep that makes the jump visible, but skip the partner restore command only when this is a final Mankey `HEADBUTT_TREE_TOPS` landing.

Why this is new:

- Attempt 255 tried to correct the post-landing position by forcing the full tile/vector state after restore; runtime says that breaks visibility.
- Attempts 187-190 established the partner prep/restore family is important for jump presentation, but did not test skipping only the final restore on a final tree-top landing.
- This does not change target selection, tree-top rows, direct down-first ordering, pathing, render probes, object recreation, or `OW_WILD_TILE_HEADBUTT`.
- This keeps the scope Mankey tree-top specific instead of changing all canopy hopper jumps.

Implementation shape:

- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, remove the Attempt 255 target snap.
- Add `skipFinalMankeyTreeTopRestore`, true only for a final landing where the active spawn is Mankey and `sOverworldWildMankeyTreeTopLandingExpected[slot]` is armed.
- Still run the existing final `Freeze` command, but skip `OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND` for that specific landing.
- Continue clearing the prep-active flag, boundary visual state, and final settled-state handling normally.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test417.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- Pending user test. If Mankey remains visible and no longer gets nudged upward, the final partner restore was the post-landing correction source. If the nudge remains, the next narrower test should also skip the final freeze command for Mankey tree-top arrivals.

### Attempt 257: Re-enable Tree-Top Anchored Effect Probe After Movement Fix

Idea:

Return to the canopy rendering problem now that `test417.nds` fixed the final Mankey tree-top movement/settling issue. The earlier rendering evidence says map-object rendering is the wrong layer, while the emotion bubble path is confirmed visible above the canopy. Attempt 252 implemented a generic anchored-effect probe with `ov01_021FFF5C`, but runtime testing moved back to movement fixes before this renderer question was answered. Re-enable that probe now that Mankey reliably lands and settles, and make it fire more frequently so the result is easier to observe.

Why this is new:

- This is not repeating a failed map-object render/proxy approach; those are already ruled out by Attempts 223-228 and 250.
- Attempt 252 built the generic effect probe, but its runtime result was still pending.
- Movement and final tree-top settling were unstable then; `test417.nds` now gives a cleaner canopy-render checkpoint.
- This still does not change target selection, tree-top rows, pathing, object recreation, follower flags, draw callbacks, OAM/cell priority, or live sprite depth.

Implementation shape:

- Set `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED` to `1`.
- Lower `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_FRAMES` from `90` to `45`.
- Keep the existing effect id cycle `0..12`.
- Keep bubble and BG layer probes disabled.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_FRAMES`
- `OverworldWildSpawns_UpdateMankeyTreeTopEffectProbe`
- `ov01_021FFF5C`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test419.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- User reported the canopy rendering is still not fixed.
- The generic anchored-effect probe did not become a usable Mankey visibility solution.
- Do not continue `ov01_021FFF5C` effect-id cycling for the Mankey canopy visual without new evidence. The confirmed useful path remains the follower/emote bubble effect family, not the trail/effect-id family.

### Attempt 258: Late-Draw Mankey Through Field-Effect Render Callback

Idea:

Stop changing the real Mankey map object's render fields. Attempts 223-228, 250, and 257 show map-object/proxy/trail-effect approaches do not solve the canopy priority problem. Instead, create a small persistent field-effect actor while Mankey is settled on a verified headbutt tree-top tile. The effect actor stores the real Mankey object as its anchor and calls `MapObject_GfxDraw` from the effect render callback. This tests whether drawing the same anchored Pokemon sprite from the confirmed above-canopy effect render family changes the layer outcome.

Why this is new:

- Attempts 223-228 changed map-object draw mode, callbacks, priority bits, live OAM/cell depth, or field-object proxies.
- Attempt 250 used a follower-sprite map-object proxy, which still belongs to the losing map-object family.
- Attempt 257 used stock `ov01_021FFF5C` effect ids, but did not draw the Pokemon sprite itself.
- This attempt creates a custom effect descriptor and moves the draw timing/layer family, while leaving the real Mankey object as the logic/battle/movement anchor.

Implementation shape:

- Add imports for the stock field-effect helpers:
  - `ov01_021F146C`
  - `ov01_021F1620`
  - `ov01_021F1640`
  - `FieldEffect_GetInitData`
- Add `OverworldWildFieldEffectDescriptor`.
- Add a Mankey-only late-draw effect work/init struct.
- Disable the old `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED` id-cycling probe.
- While a Mankey slot is settled on a cached tree-top tile, ensure one persistent late-draw effect exists for that slot.
- The effect self-destroys if the slot is no longer an active, current-map, settled Mankey tree-top object.
- For this first test, keep the real Mankey visible too; do not hide it until the effect-layer visual proves stable.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_EnsureMankeyTreeTopLateDrawEffect`
- `OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender`
- `MapObject_GfxDraw`
- `ov01_021F1620`

Runtime result:

- `git diff --check -- include/map_events_internal.h rom.ld src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test420.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- User reported the canopy rendering is still not fixed.
- Drawing `MapObject_GfxDraw` from a field-effect render callback is still not enough. The map-object renderer likely submits/sorts through the same losing sprite path even when called late.
- Do not retry effect-timed map-object drawing without new evidence. The next direction must be a true effect-owned sprite/resource payload, not `MapObject_GfxDraw`.

### Attempt 234: Direct Straight Headbutt Tile Target For Mankey

Idea:

The user reported that Mankey still will not jump down three tiles to a visually valid tree target. Attempts 230-233 all depended on interpreting the headbutt tree archive entry into one or more "top" rows. The repeated failure suggests the visually valid tree target may be better identified from the live map tile behavior than from the archive coordinates. Add a Mankey-only direct fallback: before archive-derived tree-top target selection, scan 3-8 tiles straight up/down/left/right from Mankey and choose the nearest actual `OW_WILD_TILE_HEADBUTT` tile.

Why this is new:

- Attempt 230 derived structural tree top rows from archive coordinates.
- Attempt 231 only changed direct candidate priority within that archive-derived set.
- Attempt 232 added exposed archive rows.
- Attempt 233 split targetable rows from settled rows and added X-edge ambiguity for sparse archive entries.
- This attempt bypasses archive interpretation for obvious straight-line jumps and uses the live metatile behavior at the candidate tile instead.

Implementation shape:

- Add `OverworldWildSpawns_TryPickMankeyStraightHeadbuttTileTarget`.
- The helper scans cardinal directions at distances `3..8`.
- A candidate is valid only if `GetMetatileBehaviorAt(fieldSystem, x, y) == OW_WILD_TILE_HEADBUTT` and no active spawn occupies that tile.
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` tries this direct live-tile fallback before scanning the headbutt tree archive.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryPickMankeyStraightHeadbuttTileTarget`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented, but the user correctly rejected the premise before runtime testing.
- The in-progress build still completed and copied to Delta as `test391.nds`; do not use that ROM to evaluate this feature.
- The code path was removed after the user clarified that `OW_WILD_TILE_HEADBUTT` is unrelated to this problem and must not define Mankey's tree-top targeting.

Learning:

- Do not use `OW_WILD_TILE_HEADBUTT` as a proxy for Mankey tree tops.
- Define a dedicated `HEADBUTT_TREE_TOPS` concept from headbutt tree data instead, so this behavior does not bleed into unrelated headbutt mechanics.

### Attempt 233: Split Mankey Tree Targets From Settled Perches

Idea:

The user reported Mankey standing on a visually invalid tile even though it can jump three tiles left or right to a correct tree-top tile. Attempt 232 broadened target rows by adding the exposed archive `minY` row, but `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` used the same broad rows. That can make Mankey think it is already perched on a valid tree-top tile and short-circuit before target-picking. Split the concepts: use exposed rows and ambiguous X edges for target selection, but use only structural rows for "already settled" recognition.

Why this is new:

- Attempt 230 added one strict 2x6 structural top row.
- Attempt 231 changed nearest direct target priority.
- Attempt 232 added the exposed archive `minY` row everywhere.
- This attempt does not add another Y offset. It separates targetable cells from settled-perch cells and adds X-edge ambiguity only for sparse/single-column tree entries.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_X_CANDIDATES`.
- Add an `includeExposedRows` argument to `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`.
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` now calls the row resolver with `includeExposedRows = FALSE`, so exposed/archive fallback rows no longer count as "already correctly perched."
- Add `OverworldWildSpawns_TryGetHeadbuttTreeTopLeftCandidates`, which keeps `minX` as the primary left edge and adds `minX - 1` only when a tree entry has a single distinct X column.
- Direct target selection and BFS target marking use exposed rows plus those X-edge candidates, so Mankey can still jump to nearby visible targets.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_X_CANDIDATES`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLeftCandidates`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test390.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 230: Mankey 2x6 Headbutt Tree Top-Row Targeting

Idea:

The user noticed each headbutt tree should be treated as a 2-tile-wide, 6-tile-high visual footprint. Previous Mankey tree-top attempts targeted one tile above archive headbutt coordinates, but the archive coordinates are only part of the tree footprint, often lower/interaction-obscured cells. Change Mankey's chill tree-hop state to derive each whole tree footprint from the archive entry and target only the two tiles on the top row of that 2x6 footprint.

Why this is new:

- Attempts 197-199 and 217-219 tried hardcoded Route 29 offsets or `treeY - 1` / `treeY - 2` style offsets from individual archive coordinates.
- This attempt treats one `treecoords` entry as one tree, not as several independent top candidates.
- It derives `topLeftX = min(valid coord x)` and `topY = max(valid coord y) - 5`, matching the newly identified 2x6 tree footprint.
- It does not retry forced Mankey spawning, render-height changes, follower render flags, proxy objects, draw-callback swaps, OAM priority, or live sprite depth.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_WIDTH_TILES 2` and `OW_WILD_HEADBUTT_TREE_HEIGHT_TILES 6`.
- Add `OverworldWildSpawns_TryGetHeadbuttTreeTopRow`, which resolves a whole `OverworldWildHeadbuttTree` archive entry into the two top-row target tiles.
- Update `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` to recognize those two top-row tiles.
- Update direct target selection and BFS target marking to process each tree entry once and mark both top-row cells.
- Keep the final target allowed even if normal map passability says the tree-top tile is blocked; only intermediate hops still require normal landing tiles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_WIDTH_TILES`
- `OW_WILD_HEADBUTT_TREE_HEIGHT_TILES`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopRow`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check` passed.
- A quick Route 29 source-data check maps example entries as intended:
  - `[(588,396), (588,397), (589,397)] -> (588,392)/(589,392)`
  - `[(612,395), (612,396), (613,395), (613,396)] -> (612,391)/(613,391)`
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test386.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 231: Prefer Nearest Direct Mankey Tree-Top Jump

Idea:

The user reported a Mankey standing three tiles from a valid tree-top target but not jumping to it. Attempt 230 changed which tiles count as valid tree-top targets, but the direct target picker still preferred the farthest aligned direct tree-top jump from older long-hop testing. For chill-state tree return, the nearest valid direct top-row jump should win before any farther candidate.

Why this is new:

- This does not change the 2x6 footprint resolver from Attempt 230.
- This does not retry earlier render, proxy, forced-spawn, or offset approaches.
- This only changes the direct candidate priority rule: nearest valid direct jump beats farther valid direct jumps.

Implementation shape:

- Initialize Mankey direct target `bestDistance` to `maxHop + 1`.
- In `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`, reject candidates farther than the current best and reset tie counting when a closer candidate is found.
- Keep random tie-breaking among equally near direct top-row targets.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check` passed.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test387.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 232: Include Exposed Archive Top Row For Mankey Tree Targets

Idea:

The user reported another case where Mankey is three tiles from a valid tree target, this time directly downward, but still stands still. Since Attempt 231 made nearest direct targets win and the problem persisted, the likely issue is that the visible target row is not being marked as a target by the strict `maxY - 5` 2x6 resolver. Some headbutt tree entries are visually/structurally overlapped, so the full structural top may be hidden while the exposed top of the archive entry is the actual useful perch row. Add that exposed archive top row as a secondary target row.

Why this is new:

- This does not repeat the earlier `treeY - 1` or `treeY - 2` per-coordinate offset attempts.
- This still treats one `treecoords` entry as one tree.
- It keeps the 2x6 structural top from Attempt 230, but adds the entry's `minY` as a fallback target row when it differs.
- It does not touch render layers, proxy objects, movement command execution, forced spawning, or the nearest-direct priority from Attempt 231.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_ROW_CANDIDATES 2`.
- Replace the single-row resolver with `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`, returning:
  - structural row: `maxY - 5`
  - exposed row: `minY`, if different
- Update `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`, direct target picking, and BFS target marking to consider both rows.
- Keep both rows tied to the same archive-derived `topLeftX` and 2-tile width.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_CANDIDATES`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c include/overworld_wild_spawns_internal.h documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test389.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

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

### Attempt 68: Tune Onix Ram Start, Range, Crash State, And Feedback

Idea:

Refine the first Onix ram implementation after runtime feedback:

- Start Onix ram at speed 2 instead of speed 1.
- Give Onix an explicit movement range of 16 instead of inheriting the default range 8.
- Let Onix inherit the aggressive profile's water-droplet tired state and rest time, then enter tired state after a ram crash instead of returning directly to chill.
- Switch the ram step sound from `SEQ_SE_DP_DANSA` to the stronger boulder-like `SEQ_SE_DP_DANSA5`.
- Switch the crash sound from `SEQ_SE_DP_DODON` to `SEQ_SE_GS_DODON`.
- Move the `BIT_JUMP_START` ram-step feedback to after the ram walk command starts, so the walk-command setup is less likely to immediately overwrite the visual bit.

Why this is new:

- Attempt 67 introduced Onix ram but started at speed 1, left the object range at the default 8, disabled tired state through the Onix variable override, and set the jump bit before issuing the walk command.
- No previous attempt has made Onix ram enter the behavior tired state after crashing.
- No previous attempt has tested the `DANSA5`/`GS_DODON` sound pair for Onix ram feedback.
- The script macro layer exposes `ShakeOverworld` and `ShakeCamera`, but this attempt intentionally does not inject a field script from the movement frame task because that would add a larger timing risk than the requested profile/feedback tuning.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test166.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test166.nds`.
- `git diff --check` passed before the build.
- Verified Onix now overrides normal speed to `2`, max speed to `3`, range to `16`, and ram alertness to `14`.
- Verified Onix no longer overrides stamina, tired state, or rest time, so it inherits aggressive water-droplet tired behavior and rest timing.
- Verified the ram crash path clears ram direction/counters and calls `OverworldWildSpawns_StartTiredEmote` instead of setting the spot state directly to chill.
- Verified ram step feedback now uses `SEQ_SE_DP_DANSA5` and crash feedback now uses `SEQ_SE_GS_DODON`.

Runtime result:

- User reported no ground smoke, no thud, no screen shake, and no strength movement sound. The audible result sounded like the hop sound instead.

Learning:

- `BIT_JUMP_START` is likely the wrong primitive for Onix ram feedback. It can produce hop-like feedback, and moving it after the walk command did not make it behave like ground smoke or a crash effect.

### Attempt 70: Restore Normal Ram Movement And Make Alertness A Facing Line

Idea:

Recover Onix ram movement by undoing the failed site-walk substitution while keeping the new non-jump crash script available:

- Remove the Onix ram use of `Walk*FastSite` / `Walk*VeryFastSite`.
- Make Onix ram use the same normal speed-based walk command path that moved correctly before Attempt 69.
- Keep the `BIT_JUMP_START` removal from Attempt 69, because Attempt 68 made the feedback sound/feel like a hop.
- Keep common script `2075` for crash thud and screen shake so it can be tested once Onix moves again.
- Change alertness checks from a facing cone to a straight line in front of the Pokemon.
- The line check only succeeds when the player is on the same row/column, in the Pokemon's facing direction, and within `profile.alertness`.

Why this is new:

- Attempt 66 introduced facing-cone alertness.
- Attempts 67 and 68 used cone-based Onix ram alertness.
- Attempt 69 tested site-walk ram movement and failed at runtime.
- No previous attempt has used a strict straight-line alertness check for the behavior-profile system.
- This deliberately avoids retrying `BIT_JUMP_START` and avoids retrying site-walk ram movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test168.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test168.nds`.
- `git diff --check` passed before the build.
- Verified Onix ram movement no longer uses the failed `Walk*Site` movement command family.
- Verified ram movement now calls the normal speed-based walk command selector again.
- Verified alert checks now use `OverworldWildSpawns_IsPlayerInFacingLine`, requiring the player to be directly in front of the Pokemon within `profile.alertness`.
- Verified the script NARC still accepts the existing `scr_seq_0003_075_overworld_wild_ram_crash_feedback` common script.

Runtime result:

- User reported Onix moves again.
- Onix still plays a hop-like sound each step.
- Onix still does not produce ground smoke.

Learning:

- Restoring the normal walk command family recovered ram movement.
- `SEQ_SE_DP_DANSA5` is not a good Onix ram step sound; in runtime it reads like the hop sound.
- Normal walk commands alone do not produce the desired ground smoke.
- Reference decomp inspection shows normal walk and site-walk commands both set the lower movement-start bit, so retrying only `BIT_MOVE_START` would not be meaningfully new.
- Reference decomp inspection shows `Walk*Site` commands differ from normal walk commands by movement timing/type parameters, including a site visual parameter of `5` for `Walk*FastSite`.
- Attempt 69 already proved whole `Walk*Site` movement commands are unsafe for Onix ram, but no prior attempt has kept normal walking while borrowing only the site visual parameter.

### Attempt 71: Keep Normal Ram Walking But Borrow Site Visual Parameter

Idea:

Preserve the movement path that works, while changing only the feedback pieces:

- Change Onix ram step sound from `SEQ_SE_DP_DANSA5` to stock `SEQ_SE_DP_DANSA`, because the reference decomp shows the heavy field movement helpers play `SEQ_SE_DP_DANSA`.
- Add a local import for the movement visual parameter setter at `sub_0205F328`.
- After the first update frame of an active Onix ram step, override the movement visual parameter to `5`, matching the value used by `Walk*FastSite`.
- Re-set the lower movement-start bit after that override so the renderer has a fresh chance to consume the site-style visual parameter.
- Do not use `BIT_JUMP_START`, because Attempt 68 produced hop-like behavior.
- Do not replace ram walking with `Walk*Site` commands, because Attempt 69 made Onix stop moving.

Why this is new:

- Attempt 68 used the jump flag and failed.
- Attempt 69 used whole `Walk*Site` movement commands and failed.
- Attempt 70 restored normal ram walking but left feedback wrong.
- No previous attempt has combined normal walk commands with only the site visual parameter override.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test169.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test169.nds`.
- `git diff --check` passed before the build.
- Verified the overlay compiles after importing `sub_0205F328` at `0x0205F328`.
- Verified Onix ram step sound now uses `SEQ_SE_DP_DANSA` instead of `SEQ_SE_DP_DANSA5`.
- Verified active ram movement still starts from the normal speed-based walk command path, not the failed `Walk*Site` command family.
- Verified the site visual parameter override is latched once per ram step and only runs for active ram Pokemon with speed `2` or higher.

Runtime result:

- User reported no visible or audible improvement.
- Onix still uses the hop-like sound each step.
- Onix still does not produce ground smoke.

Learning:

- The site visual parameter override did not reach the desired visible effect.
- Changing the explicit sound from `SEQ_SE_DP_DANSA5` to `SEQ_SE_DP_DANSA` did not remove the hop-like sound in runtime.
- Do not continue trying to get Onix ram dust through whole `Walk*Site` commands, `BIT_JUMP_START`, or the post-init site visual parameter override without new evidence.
- The next direction should bypass movement-command feedback and call a stock field-effect helper directly.

### Attempt 73: Run WaitJumpSite After Each Onix Ram Step

Idea:

Use the command already proven to produce smoke, but isolate it from the ram walking command:

- Remove the failed direct `ov01_021FD640` call and import.
- Keep normal ram walking unchanged so Onix still moves.
- After an Onix ram walk command finishes at speed `2` or higher, count the ram step, update ram speed, then start a separate `WaitJumpSite` (`0x65`) single-movement command.
- Track `movementRamSmokeActive` per slot so the follow-up `WaitJumpSite` completion is not counted as another ram movement step.
- Do not add an explicit per-step sound yet; this attempt tests whether `WaitJumpSite` alone gives the desired smoke in the ram context.

Why this is new:

- Attempt 49 used `WaitJumpSite` as a spot emote and produced smoke, but did not use it in the Onix ram path.
- Attempt 68 used `BIT_JUMP_START` directly and failed.
- Attempt 69 used whole `Walk*Site` commands and failed.
- Attempt 71 used a site visual parameter override and failed.
- Attempt 72 called `ov01_021FD640` directly and failed.
- No previous attempt has inserted `WaitJumpSite` as a separate post-step Onix ram smoke command.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test171.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test171.nds`.
- `git diff --check` passed before the build.
- Verified the failed direct `ov01_021FD640` call and import are not active code.
- Verified the failed `sub_0205F328` site-visual override is not active code.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_SMOKE_COMMAND` is `0x65` (`WaitJumpSite`).
- Verified the ram path starts `WaitJumpSite` only after a ram walk command finishes at speed `2` or higher.
- Verified `movementRamSmokeActive` prevents the follow-up `WaitJumpSite` completion from being counted as another ram movement step.
- Verified no explicit per-step sound was added in this attempt, so this build isolates whether `WaitJumpSite` alone creates the ram smoke.

Runtime result:

- User reported that `WaitJumpSite` does not work for ram feedback because it stops Onix's movement each time the animation runs.

Learning:

- `WaitJumpSite` can produce a smoke-like presentation, but it is a movement command and takes over the same single-movement slot the ram step needs.
- Do not use post-step `WaitJumpSite` as Onix ram smoke; it creates a visible stop/start interruption.
- The next direction should keep normal ram movement active and layer the feedback as a side effect instead of as another movement command.

### Attempt 74: Direct Boulder Step Effect Helper During Normal Ram Movement

Idea:

Keep Onix on the normal ram walk commands that already move correctly, but layer a boulder-style side effect onto the start of each ram step:

- Remove the failed post-step `WaitJumpSite` ram command and its `movementRamSmokeActive` bookkeeping.
- Import `ov01_021FFF5C`, a stock overlay helper that attaches a small ground/step effect to a `LocalMapObject` without starting a movement command.
- When an active ram step starts at speed `2` or higher, call `ov01_021FFF5C(object, effectId)` from the current movement field context.
- Use ram speed clamped to `3` as the effect id for this test, because the helper's resource table has four valid effect slots and the stock movement-effect code uses small category ids.
- Play `SEQ_SE_DP_DANSA` at the same time, matching the sound emitted by the vanilla movement-command paths around `sub_02062958`/`sub_020632B0`.

Why this is new:

- Attempt 68 used `BIT_JUMP_START` and failed with hop-like feedback.
- Attempt 69 replaced ram movement with `Walk*Site` commands and made Onix stop moving.
- Attempt 71 borrowed only the site visual parameter through `sub_0205F328` and failed.
- Attempt 72 directly called `ov01_021FD640(object)` and failed.
- Attempt 73 used `WaitJumpSite` as a separate movement command and interrupted ram movement.
- No previous attempt has called `ov01_021FFF5C` directly from the Onix ram path while keeping the normal walk command active.

Files/symbols:

- `include/map_events_internal.h`
- `include/overworld_wild_spawns_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test172.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test172.nds`.
- `git diff --check` passed before the build.
- Verified the failed post-step `WaitJumpSite` ram follow-up path and `movementRamSmokeActive` bookkeeping are not active code.
- Verified `ov01_021FFF5C` is imported at `0x021FFF5C` and called from `OverworldWildSpawns_PlayRamStepFeedback`.
- Verified the direct effect call is guarded by the current movement field context and only runs for active ram Pokemon at speed `2` or higher.
- Verified Onix ram still starts the normal ram walk command before playing ram-step feedback, so this attempt keeps movement on the proven walking path.
- Verified per-step sound now uses `SEQ_SE_DP_DANSA`.

Runtime result:

- User reported a weird trail effect instead of smoke. Screenshot showed green/footprint-like trail marks following Onix's ram path.

Learning:

- `ov01_021FFF5C` successfully creates a side effect without stopping Onix, so the helper path itself is viable.
- Using ram speed as the effect id was wrong for the desired dust/smoke: speed `2`/`3` selects the later `0x66`/`0x67` effect resources, which present as a trail.
- Do not retry speed-derived effect ids with `ov01_021FFF5C` for Onix ram smoke.
- The stock movement-effect code maps command groups `0x0C-0x0F`, `0x10-0x13`, and `0x14-0x17` to effect ids `3`, `2`, and `1`, so fixed id `1` remains an untested direct-helper candidate.

### Attempt 83: Try Paired HGSS Push Sound `SEQ_SE_GS_PUSH03`

Idea:

Keep the successful Attempt 81 smoke path and change only the explicit ram step sound from the silent push candidate to its paired neighbor:

- Keep `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`.
- Change it from `SEQ_SE_GS_PUSH02` to `SEQ_SE_GS_PUSH03`.
- Leave the smoke effect, ram movement, and crash feedback unchanged.

Why this is new:

- Attempt 82 tested `SEQ_SE_GS_PUSH02` and it produced no audible sound.
- No previous Onix ram attempt has used `SEQ_SE_GS_PUSH03`.
- `SEQ_SE_GS_PUSH03` is the only other locally named HGSS `PUSH` sound, so testing it completes the named push pair before moving to rockfall/trap candidates like `IWAOTOSHI` or `IWA_TRAP`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_PUSH03`

Verification:

- `git diff --check` passed before the build.
- Built as `test181.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now uses `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`, defined as `SEQ_SE_GS_PUSH03`.

Runtime result:

- User reported no sound played.

Learning:

- `SEQ_SE_GS_PUSH03` is also not audible through the direct C `PlaySE` path in the current overworld context.
- SDAT inspection showed both push sounds are real SSEQ entries, not missing constants:
  - `SEQ_SE_GS_PUSH02`: bank `770`, player `3`, volume `100`, event data present.
  - `SEQ_SE_GS_PUSH03`: bank `770`, player `4`, volume `127`, event data present.
- Bank `770` uses wave archives `[700, 770]`; this suggests the silence may be because direct `PlaySE` does not load the extra bank/wave archive needed by these HGSS push sounds in the field context.

### Attempt 85: Load Push Sound With `NNS_SND_ARC_LOAD_ALL`

Idea:

Keep the successful Attempt 81 smoke path and current `SEQ_SE_GS_PUSH03` sound candidate, but use the extended sound-archive load path:

- Expose `GF_Snd_LoadSeqEx` in `include/sound.h`.
- Mark `GF_Snd_LoadSeqEx` as `LONG_CALL` in `src/sound.c` so overlay code can call it safely.
- Replace `GF_Snd_LoadSeq(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)` with `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)`.
- Then call `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Why this is new:

- Attempt 84 loaded only the sequence before playback and still produced no sound.
- `NNS_SND_ARC_LOAD_ALL` requests sequence, bank, and wave data, which targets the SDAT finding that `SEQ_SE_GS_PUSH03` uses bank `770` and wave archive `770`.
- No previous Onix ram attempt has used `GF_Snd_LoadSeqEx` or `NNS_SND_ARC_LOAD_ALL`.

Files/symbols:

- `include/sound.h`
- `src/sound.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_PUSH03`

Verification:

- `git diff --check` passed before the build.
- Built as `test183.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now calls `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)` before `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Runtime result:

- User reported no sound played.

Learning:

- Full sequence/bank/wave loading was not enough to make `SEQ_SE_GS_PUSH03` audible in this field context.
- The named `PUSH` pair has now failed through direct playback, sequence-only loading, and full archive loading.
- Avoid more `PUSH02` / `PUSH03` retries unless new evidence identifies a different required caller or player setup.

### Attempt 86: Try Field Rock Sound `SEQ_SE_GS_IWAOTOSHI02`

Idea:

Keep the successful Attempt 81 smoke path and the safer full sound-archive load path, but change the sound candidate away from the silent `PUSH` bank:

- Change `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE` from `SEQ_SE_GS_PUSH03` to `SEQ_SE_GS_IWAOTOSHI02`.
- Keep `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)`.
- Keep `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)` after the load call.

Why this is new:

- Attempts 82 through 85 only tested the named HGSS `PUSH` pair and loading variants for `PUSH03`.
- No previous Onix ram attempt has used `SEQ_SE_GS_IWAOTOSHI`, `SEQ_SE_GS_IWAOTOSHI01`, `SEQ_SE_GS_IWAOTOSHI02`, or `SEQ_SE_GS_IWA_TRAP`.
- SDAT inspection showed `SEQ_SE_GS_IWAOTOSHI02` uses the field rock bank `750` and field player `3`, while `SEQ_SE_GS_PUSH03` uses bank `770` and player `4`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_IWAOTOSHI02`
- Existing function `GF_Snd_LoadSeqEx`
- Existing constant `NNS_SND_ARC_LOAD_ALL`

Verification:

- `git diff --check` passed before the build.
- Built as `test184.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now uses `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`, defined as `SEQ_SE_GS_IWAOTOSHI02`.
- Verified the sound path still calls `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)` before `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Runtime result:

- User reported the Onix ram step sound works.

Learning:

- `SEQ_SE_GS_IWAOTOSHI02` is a usable Onix ram step sound in this field context when loaded with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)`.
- Keep the successful smoke path and this field rock sound for active ram steps.

### Attempt 88: Use Field Wall-Hit Sound And Shake The Crashed Overworld Object

Idea:

Replace the failed crash-feedback path with two signals that have not been tested on ram crashes:

- Change the crash thud from `SEQ_SE_GS_DODON` to `SEQ_SE_GS_TOUMEINAKABEHIT`.
- Keep the successful full sound-archive load path before playing the crash thud.
- Store the crashed spawned object's object ID in `VAR_SPECIAL_x8004` from C before scheduling the crash feedback script.
- Change the crash feedback script from `ShakeCamera` to `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`.
- Add `lockall` / `releaseall` around the crash feedback script so the object-shake command has a normal script envelope.

Why this is new:

- Attempt 87 fairly tested `SEQ_SE_GS_DODON` plus `ShakeCamera`; both failed at runtime.
- No previous Onix ram attempt has used `SEQ_SE_GS_TOUMEINAKABEHIT`, the named HGSS transparent-wall-hit sound.
- No previous Onix ram attempt has passed a spawned object ID into a script variable and used `ShakeOverworld` on that object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing script `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`
- Existing script variable `VAR_SPECIAL_x8004`
- Existing sound constant `SEQ_SE_GS_TOUMEINAKABEHIT`

Verification:

- `git diff --check` passed before the build.
- Built as `test186.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_TOUMEINAKABEHIT` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified `OverworldWildSpawns_PlayRamCrashFeedback` writes the crashed object's ID into `VAR_SPECIAL_x8004` before scheduling `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`.
- Verified the crash script now uses `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2` inside `lockall` / `releaseall`.

Runtime result:

- User reported the crash causes the player to freeze while other Pokemon still move.
- User also reported the sound plays, but it is not the desired thud.

Learning:

- `SEQ_SE_GS_TOUMEINAKABEHIT` is audible in this field context with the current C-side full-load sound path, but it has the wrong character for Onix crashing.
- `ShakeOverworld` with `lockall`, `wait`, and `releaseall` likely leaves player input locked or stuck in a script wait even though the movement frame task continues to move other spawned Pokemon.
- Do not retry a locked/waiting `ShakeOverworld` common script for ram crash feedback.

### Attempt 89: Non-Locking Object Shake And `SEQ_SE_DP_GASHIN` Crash Thud

Idea:

Keep the object-ID handoff from Attempt 88, but remove the script envelope that can freeze the player and try a different impact sound:

- Change the crash thud from `SEQ_SE_GS_TOUMEINAKABEHIT` to `SEQ_SE_DP_GASHIN`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep writing the crashed spawned object's object ID to `VAR_SPECIAL_x8004`.
- Change the crash script to call `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`, then end immediately.
- Remove `lockall`, `wait`, and `releaseall` from the crash script.

Why this is new:

- Attempt 88 proved the locked/waiting `ShakeOverworld` script can freeze the player and that `SEQ_SE_GS_TOUMEINAKABEHIT` is the wrong sound.
- No previous Onix ram attempt has tested `SEQ_SE_DP_GASHIN`.
- No previous Onix ram attempt has tested `ShakeOverworld` as a fire-and-finish script without locking player input or waiting on a script result.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing script `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`
- Existing script variable `VAR_SPECIAL_x8004`
- Existing sound constant `SEQ_SE_DP_GASHIN`

Verification:

- `git diff --check` passed before the build.
- Built as `test187.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_DP_GASHIN` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified the crash script still uses `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`, but now ends immediately without `lockall`, `wait`, or `releaseall`.

Runtime result:

- User reported no crash feedback or sound from this build.
- User also requested that future attempts do not lock out the player or other Pokemon.

Learning:

- Removing `lockall`, `wait`, and `releaseall` avoided the player-lock problem from Attempt 88.
- `SEQ_SE_DP_GASHIN` did not produce the desired audible crash sound in this field context.
- Keep future ram-crash feedback on non-locking/non-waiting paths.

### Attempt 90: Non-Locking Object Shake And HGSS Gondola Wall-Hit Sound

Idea:

Keep the non-locking crash script from Attempt 89 and try a field-bank HGSS impact sound:

- Change the crash thud from `SEQ_SE_DP_GASHIN` to `SEQ_SE_GS_GONDORA_KABEHIT`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep the `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2` script as a fire-and-finish script with no `lockall`, no `wait`, and no `releaseall`.

Why this is new:

- Attempt 89 tested the non-locking script shape with `SEQ_SE_DP_GASHIN`, which was not audible.
- No previous Onix ram attempt has used `SEQ_SE_GS_GONDORA_KABEHIT`.
- `SEQ_SE_GS_GONDORA_KABEHIT` uses the HGSS field sound family rather than the silent DP impact sound path, while still avoiding the already-wrong `SEQ_SE_GS_TOUMEINAKABEHIT`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_GONDORA_KABEHIT`

Verification:

- `git diff --check` passed before the build.
- Built as `test188.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_GONDORA_KABEHIT` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified the crash script remains non-locking: `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`, then `endstd` / `end`.

Runtime result:

- User reported the sound now plays and is acceptable, but should be more impactful.
- User reported no screen shake.
- User reported the player still locks afterward.

Learning:

- `SEQ_SE_GS_GONDORA_KABEHIT` is audible and usable as a fallback crash thud, but it is not quite impactful enough.
- Even a fire-and-finish common script with only `ShakeOverworld` can still leave the player locked after ram crash feedback.
- Treat crash feedback field-script scheduling as unsafe for now; remove `EventSet_Script` from ram crash feedback before further sound auditions.

### Attempt 91: Sound-Only `SEQ_SE_GS_IWA_TRAP` Crash Feedback

Idea:

Remove the crash feedback script path entirely and try a stronger rock-field sound:

- Change the crash thud from `SEQ_SE_GS_GONDORA_KABEHIT` to `SEQ_SE_GS_IWA_TRAP`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Stop writing a script object ID to `VAR_SPECIAL_x8004`.
- Stop calling `EventSet_Script` for `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`.
- Leave the crash common script uncalled for this checkpoint.

Why this is new:

- Attempts 88 through 90 all scheduled a field script for crash feedback and produced either player lock or no visible screen shake.
- No previous Onix ram attempt has used `SEQ_SE_GS_IWA_TRAP` as the ram crash sound.
- This is the first crash-feedback checkpoint that fully removes script scheduling from `OverworldWildSpawns_PlayRamCrashFeedback`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_IWA_TRAP`

Verification:

- `git diff --check` passed before the build.
- Built as `test189.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_IWA_TRAP` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified `OverworldWildSpawns_PlayRamCrashFeedback` only plays the C-side thud and no longer calls `EventSet_Script` or writes `VAR_SPECIAL_x8004`.

Runtime result:

- User reported this sound was worse.
- User also reported no shake.

Learning:

- `SEQ_SE_GS_IWA_TRAP` is not a good Onix ram crash sound; it is worse than `SEQ_SE_GS_GONDORA_KABEHIT`.
- The no-shake result is expected because this checkpoint intentionally removed script-based shake to avoid player lock.
- Keep crash feedback script scheduling disabled while auditioning additional sounds.

### Attempt 92: Sound-Only `SEQ_SE_GS_IWAOTOSHI01` Crash Feedback

Idea:

Keep the stable sound-only crash-feedback path and try a different field-rock impact:

- Change the crash thud from `SEQ_SE_GS_IWA_TRAP` to `SEQ_SE_GS_IWAOTOSHI01`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep crash feedback script scheduling disabled.

Why this is new:

- Attempt 91 tested sound-only crash feedback with `SEQ_SE_GS_IWA_TRAP`, which sounded worse.
- `SEQ_SE_GS_IWAOTOSHI02` works as the ram step sound, but `SEQ_SE_GS_IWAOTOSHI01` has not been tested as the ram crash sound.
- This keeps the no-script crash path that avoids the player-lock problem from Attempts 88 through 90.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_IWAOTOSHI01`

Verification:

- `git diff --check` passed before the build.
- Built as `test190.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_IWAOTOSHI01` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified crash feedback script scheduling remains disabled.

Runtime result:

- User reported this sound was worse.
- User reported no screen shake.

Learning:

- `SEQ_SE_GS_IWAOTOSHI01` is not a good Onix ram crash sound.
- The no-shake result is expected because crash feedback script scheduling remains disabled.
- Return to the previously acceptable `SEQ_SE_GS_GONDORA_KABEHIT` sound and keep screen shake out of the crash feedback path for now.

### Attempt 93: Restore Decent Crash Sound And Shorten Speech-Only Alert

Idea:

Keep the stable, non-locking crash feedback path and address the latest feel issues:

- Restore the ram crash sound from `SEQ_SE_GS_IWAOTOSHI01` to the previously acceptable `SEQ_SE_GS_GONDORA_KABEHIT`.
- Keep screen shake disabled; do not schedule any crash feedback field script.
- Add a separate speech-only alert timer so non-hop alerts such as aggressive_ram's mad speech bubble plus cry do not wait for the full jump-emote duration.
- Leave hop-alert timing unchanged to avoid regressing the working jump animation.

Why this is new:

- Attempt 90 used `SEQ_SE_GS_GONDORA_KABEHIT` together with a script-scheduled shake path, which still locked the player.
- Attempts 91 and 92 removed script scheduling while auditioning different crash sounds.
- No previous attempt has combined the stable sound-only feedback path with `SEQ_SE_GS_GONDORA_KABEHIT`.
- No previous attempt has split speech-only alert timing from hop alert timing.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE`
- `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test191.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE` now resolves to `SEQ_SE_GS_GONDORA_KABEHIT`.
- Verified crash feedback still only loads and plays the thud; the only remaining `EventSet_Script` call in the overlay is the battle-start path.
- Verified speech-only spot emotes now use `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES` / `24` frames instead of `OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP` / `64` frames.
- Verified hop-alert timing remains unchanged.

Runtime result:

- User reported there is still no screen shake.

Learning:

- The no-shake result is expected because Attempt 93 intentionally kept crash feedback sound-only.
- The user still wants visible shake feedback, so the next attempt should add visual crash feedback without reusing script-scheduled `ShakeCamera` or `ShakeOverworld`.

### Attempt 94: C-Side Ram Crash Object Wobble

Idea:

Add a visible, reversible crash wobble without scheduling a field script:

- Keep the crash thud as `SEQ_SE_GS_GONDORA_KABEHIT`.
- Keep `EventSet_Script` out of ram crash feedback.
- Store the crashed object's original `posVec[0]` and `posVec[2]`.
- For 18 frames, offset the crashed object diagonally by a small fixed-point amount from the existing movement frame task.
- Restore the original render position when the wobble ends or when the slot resets/clears.

Why this is new:

- Attempts 87 through 90 tested `ShakeCamera` or `ShakeOverworld` through a common script and produced no visible shake and/or player lock.
- Attempt 91 through Attempt 93 removed script scheduling entirely and were sound-only.
- Attempt 48 tried a vertical `posVec[1]` hop bob for alert presentation, but no previous attempt has tried a short post-crash X/Z wobble on the ram object itself.
- This does not call `EventSet_Script`, does not use `ShakeCamera`, and does not use `ShakeOverworld`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementRamCrashShakeTimers`
- `OverworldWildSpawns_StartRamCrashShake`
- `OverworldWildSpawns_TickRamCrashShake`

Verification:

- `git diff --check` passed before the build.
- Built as `test192.nds` and copied to Delta.
- Verified the crash thud remains `SEQ_SE_GS_GONDORA_KABEHIT`.
- Verified the ram crash path calls `OverworldWildSpawns_StartRamCrashShake` and still does not schedule a crash feedback field script.
- Verified `OverworldWildSpawns_FrameMovementTask` advances `OverworldWildSpawns_TickRamCrashShake`.
- Verified slot reset restores any active ram crash wobble before clearing the shake state.

Runtime result:

- User reported this did nothing visible and also clarified this was not the desired effect.
- The requested effect is an actual screen shake, not wobbling the crashed object or adding another non-screen visual.

Learning:

- Manual X/Z `posVec` wobble is not a useful substitute for screen shake.
- Remove this code and do not retry object-wobble crash feedback unless the requested effect changes.
- The next attempt should trace or call the underlying camera/screen shake routine directly instead of scheduling field scripts or offsetting the object.

### Attempt 95: Direct Camera Shake Work Driven By SysTask

Idea:

Trace the actual `ShakeCamera` script command instead of scheduling it again:

- Field script command `561` points to `0x02201A50` in overlay 1.
- That handler reads four script parameters and calls `0x02246714` in overlay 2 with `fieldSystem->taskman`.
- `0x02246714` creates a camera-shake work object through `0x02246744`, then schedules a `TaskManager` task at `0x02246798`.
- The task updates the shake via `0x0224663C`, restores via `0x0224662C`, and frees via `0x02246534`.

For this attempt, bypass both `EventSet_Script` and the `TaskManager_Call` wrapper:

- Add linker names for the lower-level camera-shake work functions.
- Create the same camera-shake work directly on Onix ram crash.
- Drive it from a small `SysTask`.
- Restore/free the shake work when it finishes or when movement/map context resets.
- Keep the existing `SEQ_SE_GS_GONDORA_KABEHIT` crash thud.

Why this is new:

- Attempts 87 through 90 scheduled common scripts using `ShakeCamera` or `ShakeOverworld`; they produced no visible shake and/or player lock.
- Attempt 94 offset the crashed object's render position, which the user correctly rejected as not a screen shake.
- No previous attempt has traced command `561` to the lower-level overlay-2 camera-shake work functions or driven those functions directly from a spawner-owned `SysTask`.
- This follows the successful follower-bubble lesson: bypass the vanilla task/script wrapper when the direct lower-level effect creator is available.

Files/symbols:

- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `FieldCamera_CreateShakeWork` / `0x02246744`
- `FieldCamera_UpdateShakeWork` / `0x0224663C`
- `FieldCamera_RestoreShakeWork` / `0x0224662C`
- `FieldCamera_FreeShakeWork` / `0x02246534`
- `OverworldWildSpawns_StartRamCrashScreenShake`
- `OverworldWildSpawns_RamCrashScreenShakeTask`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test193.nds` and copied to Delta.
- Verified the rejected Attempt 94 object-wobble state was removed from `OverworldWildSpawnState`.
- Verified the ram crash path no longer calls `OverworldWildSpawns_StartRamCrashShake` / `OverworldWildSpawns_TickRamCrashShake`.
- Verified `rom.ld` exposes the direct camera-shake work functions at `0x02246744`, `0x0224663C`, `0x0224662C`, and `0x02246534`.
- Verified `OverworldWildSpawns_PlayRamCrashFeedback` still plays the accepted `SEQ_SE_GS_GONDORA_KABEHIT` thud and now starts `OverworldWildSpawns_StartRamCrashScreenShake` only when the movement field context is current.
- Verified the only remaining `EventSet_Script` call in the overlay is the battle-start path, not ram crash feedback.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- User clarified that the screen-shake direction should be abandoned.
- User also clarified the object-wobble attempt did work, but was too subtle.

Learning:

- Retire the direct camera-shake work path for now.
- Reintroduce object wobble as the requested crash feedback, but make it much more obvious.
- Keep the crash feedback out of `EventSet_Script`, `ShakeCamera`, `ShakeOverworld`, and the direct camera-shake work functions.

### Attempt 96: Stronger Ram Crash Object Wobble And Shorter Speech Alert

Idea:

Return to the working Attempt 94 presentation, but tune it for visibility:

- Remove the direct camera-shake work symbols and task from Attempt 95.
- Re-add slot-owned ram crash wobble state.
- Store the crashed object's original `posVec[0]` and `posVec[2]`.
- Wobble the crashed object for 32 frames instead of 18 frames.
- Use a larger `3/8` tile fixed-point X/Z offset so the feedback is not barely visible.
- Restore the original render position when the wobble ends or when the slot/movement state resets.
- Shorten speech-only alert timing from 24 frames to 8 frames so aggressive_ram starts moving sooner after its mad bubble and cry.

Why this is new:

- Attempt 94 used object wobble, but the amplitude/duration were too subtle.
- Attempt 95 tried the direct camera-shake work path; the user asked to abandon screen shake.
- No previous attempt has tested the working object-wobble path with a deliberately stronger amplitude and the shorter speech-only alert state.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementRamCrashShakeTimers`
- `OverworldWildSpawns_StartRamCrashShake`
- `OverworldWildSpawns_TickRamCrashShake`
- `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test194.nds` and copied to Delta.
- Verified the direct camera-shake work symbols were removed from active code and `rom.ld`.
- Verified the ram crash path calls `OverworldWildSpawns_StartRamCrashShake` again.
- Verified `OverworldWildSpawns_FrameMovementTask` advances `OverworldWildSpawns_TickRamCrashShake`.
- Verified slot reset restores active ram crash wobble before clearing movement/spot state.
- Verified `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES` is now `8`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 99: Player Wall-Hit Ram Crash Sound

Idea:

Change the aggressive ram crash sound to the same sound family used when the player bumps into a wall:

- Change `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE` from `SEQ_SE_GS_GONDORA_KABEHIT` to `SEQ_SE_DP_WALL_HIT`.
- Keep the no-script crash feedback path, object wobble, no screen shake, and aggressive_ram tired-state flow unchanged.

Why this is new:

- Earlier crash-sound attempts tried `SEQ_SE_GS_DODON`, `SEQ_SE_GS_TOUMEINAKABEHIT`, `SEQ_SE_DP_GASHIN`, `SEQ_SE_GS_GONDORA_KABEHIT`, `SEQ_SE_GS_IWA_TRAP`, and `SEQ_SE_GS_IWAOTOSHI01`.
- `SEQ_SE_GS_TOUMEINAKABEHIT` was a transparent-wall-hit sound and was already proven audible but wrong for Onix crash feedback.
- `SEQ_SE_DP_WALL_HIT` is the direct player wall-bump sound constant, has not been used in this ram crash path before, and matches the user's requested sound more closely than the transparent-wall variant.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE`
- `SEQ_SE_DP_WALL_HIT`

Verification:

- `git diff --check` passed before the build.
- Built as `test197.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE` now resolves to `SEQ_SE_DP_WALL_HIT`.
- Verified the crash feedback path still uses `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 100: Ram Crash-Only Automatic Battle Trigger

Idea:

Make `aggressive_ram` stop using the generic automatic contact-battle detector. Ram should only self-start a battle when its straight-line attentive movement crashes into the player or the active follower Pokemon. The universal A-button facing interaction remains unchanged and can still start battles with any spawned Pokemon.

Implementation shape:

- Remove `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE` from the generic `OverworldWildSpawns_TryStartBattle` touch loop.
- Pass the active `FieldSystem *` into `OverworldWildSpawns_TryStartRamMovementCommand`.
- When ram movement is blocked, predict the tile in front of the ram from its current tile plus ram direction.
- If that blocked tile is the player tile or the active follower object's tile, call `OverworldWildSpawns_TryStartBattleForSlot`.
- If the blocked tile is anything else, keep the existing crash feedback and tired-state behavior without starting a battle.

Why this is new:

- Attempts 35 and 36 tuned generic contact timing after movement settled, but still treated ram as an automatic contact battle behavior.
- Attempt 65 added the universal A-button facing interaction, but did not change ram's automatic battle condition.
- Attempt 67 introduced Onix ram movement, but its battle behavior was still represented as `RAM_START_BATTLE` and later shared the generic touch detector.
- No previous attempt has made ram's automatic battle trigger depend on the ram crash target, and no previous attempt has included follower Pokemon as a ram crash battle target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryStartRamMovementCommand`
- `OverworldWildSpawns_TryStartBattleForRamCrash`
- `OverworldWildSpawns_TryStartBattle`
- `fieldSystem->followMon.mapObject`

Verification:

- `git diff --check` passed before the build.
- Built as `test198.nds` and copied to Delta.
- Verified `OverworldWildSpawns_TryStartBattle` now only includes `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_CHASE_START_BATTLE` in the generic automatic touch battle loop.
- Verified `OverworldWildSpawns_TryStartRamMovementCommand` receives the active `FieldSystem *`.
- Verified ram blocked-direction handling still calls `OverworldWildSpawns_EndRamCrash`, then calls `OverworldWildSpawns_TryStartBattleForRamCrash` only for the predicted blocked tile.
- Verified `OverworldWildSpawns_TryStartBattleForRamCrash` checks the predicted tile against the player tile and the active follower object's tile.
- Verified `OverworldWildSpawns_TryStartBattleFromAButton` remains unchanged, so the universal A-button interaction still starts battles.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- User reported the player crash trigger works, but crashing into the follower Pokemon does not start a battle.

Learning:

- The ram crash battle path and predicted player tile check are sound.
- The follower miss is likely in follower object lookup or follower active-state detection, not in `OverworldWildSpawns_TryStartBattleForSlot`.
- Do not rely only on `fieldSystem->followMon.active` for this ram crash target check without more evidence that it is valid in this context.

### Attempt 101: Follower Object-ID Fallback For Ram Crash Battles

Idea:

Keep the working player ram crash trigger from Attempt 100, but make follower detection less dependent on `fieldSystem->followMon.active`:

- Define the vanilla follower map-object id as `253`, matching `obj_partner_poke` / `Following` in `armips/include/scriptmacros.s`.
- First try `fieldSystem->followMon.mapObject`, but require only that the pointer belongs to the current map-object table, is active, and occupies the predicted crash tile.
- If that direct pointer check misses, scan the current map-object table for an active object with id `253` on the predicted crash tile.
- Keep the generic automatic touch battle loop ram-free, and keep the universal A-button interaction unchanged.

Why this is new:

- Attempt 100 required `fieldSystem->followMon.active` before accepting the follower object as a ram crash battle target.
- Runtime proved player crash battles work while follower crash battles do not, pointing specifically at follower lookup/active-state detection.
- Earlier attempts used follower APIs for shiny palette and speech bubbles, but no previous ram crash attempt has identified the follower by its vanilla object id.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_FOLLOWER_OBJECT_ID`
- `OverworldWildSpawns_IsRamCrashBattleTarget`
- `fieldSystem->followMon.mapObject`
- `LocalMapObject::id`

Verification:

- `git diff --check` passed before the build.
- Built as `test199.nds` and copied to Delta.
- Verified `OW_WILD_FOLLOWER_OBJECT_ID` is defined as `253`, matching `obj_partner_poke` / `Following` in `armips/include/scriptmacros.s`.
- Verified `OverworldWildSpawns_IsRamCrashBattleTarget` no longer depends on `fieldSystem->followMon.active`.
- Verified the direct follower pointer path still requires the follower object to be current, active, and on the predicted crash tile.
- Verified the fallback scans the current map-object table for an active object with id `253` on the predicted crash tile.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

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

### Attempt 129: Phantom Flicker And Follower Behind Targeting

Idea:

Make phantom stalkers flicker visible during some hidden movement steps so the player occasionally sees the Pokemon moving, and make the stalking target choose the closest tile behind either the player or the follower Pokemon instead of only behind the player.

Implementation shape:

- Add a per-slot `movementPhantomFlickerTimers` state array.
- When a hidden phantom starts a movement command, randomly open a short visibility window.
- Tick the flicker window from the frame movement task and restore `BIT_VANISH` when the window expires.
- Reset the flicker timer whenever a phantom reveals, despawns, respawns, or resets its movement state.
- Replace the player-only behind-target helper with a target builder that adds the tile behind the active player object, direct follower object, and fallback scanned follower object.
- Select the closest behind-target candidate from the ghost's current position and keep using the existing collision-safe movement command path.

Why this is new:

- Attempt 128 made phantoms fully invisible until the hidden-step counter finished.
- Attempt 128 targeted only the tile behind the player's facing direction.
- No previous attempt has exposed brief hidden-movement flicker windows or used the follower's facing to create phantom stalk targets.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `movementPhantomFlickerTimers`
- `OverworldWildSpawns_TryStartPhantomFlicker`
- `OverworldWildSpawns_UpdatePhantomFlicker`
- `OverworldWildSpawns_BuildPhantomBehindTargets`
- `OverworldWildSpawns_TryGetClosestPhantomBehindTarget`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test227.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test227.nds` both exist at 176 MB.
- Verified active source no longer references the player-only `OverworldWildSpawns_TryGetPlayerBehindTarget` helper.
- Verified hidden phantoms reset `movementPhantomFlickerTimers` on reveal, slot reset, and fresh spawn initialization.
- Verified the frame movement task ticks phantom flicker windows before updating in-progress movement commands.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 130: Phantom Blink Behind Player Then Flicker Chase

Idea:

Change phantom stalker attentive behavior from "walk toward a behind-target" to a clearer blink-and-chase pattern. When the ghost enters attentive state, it vanishes, teleports up to 5 tiles behind the player's current facing direction, then uses the same chase movement and contact-battle behavior as the aggressive chase attentive state while remaining in flicker mode.

Implementation shape:

- Replace `OW_WILD_SPAWNER_PHANTOM_STALK_HIDDEN_STEPS` with `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_DISTANCE`.
- Add a phantom teleport helper that tries 5 tiles behind the player first, then falls back to 4/3/2/1 if the farther tile is blocked or occupied.
- Validate teleport landing tiles with the existing map-object occupancy, metatile-blocked, surf, and headbutt-tile checks.
- Teleport with `MapObject_SetCurrentX/Y`, reset previous-tile and pending movement history, and update object init/previous/render tile state.
- Remove the old phantom behind-target direction builder; active phantom movement now keeps the default chase direction list already used by chase behavior.
- Keep `movementPhantomHidden` active through the whole attentive chase so movement commands can start random flicker windows.
- Treat active phantom contact with the player as battle-starting, like `agressiveChase`.
- Allow A-button battle targeting while a phantom is currently flickered visible, but still skip fully invisible phantoms.

Why this is new:

- Attempt 128 made the phantom walk invisibly toward a tile behind the player and then reveal after a fixed hidden-step count.
- Attempt 129 added flicker windows and follower-aware behind-target selection to that walking-behind-target approach.
- No previous attempt has teleported the phantom up to 5 tiles behind the player as the attentive-state entry action.
- No previous attempt has made phantom active movement reuse the chase attentive behavior while keeping flicker presentation.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_DISTANCE`
- `OverworldWildSpawns_TryGetPhantomTeleportTarget`
- `OverworldWildSpawns_TryTeleportPhantomBehindPlayer`
- `OverworldWildSpawns_MaybeStartPhantomStalkerVanish`
- `OverworldWildSpawns_TryStartBattle`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test228.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test228.nds` both exist at 176 MB.
- Verified active source defines `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_DISTANCE` as `5`.
- Verified the old phantom behind-target direction builder is removed from active source.
- Verified phantom active movement now keeps the default chase direction list, while active contact battle accepts both `CHASE_START_BATTLE` and `PHANTOM_STALK`.
- Verified hidden/flicker state no longer reveals after a fixed hidden-step count.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 131: Faster Phantom Destination Flicker And Battle Reveal

Idea:

Tune the phantom stalker presentation after the blink-and-chase pass. The first visible flicker should happen at the teleport destination before the ghost begins chasing, ordinary movement flickers should be shorter/faster, and a phantom should be fully visible before it starts a battle.

Implementation shape:

- Reduce `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_FRAMES` from `8` to `2` for faster normal movement flickers.
- Add `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES` as a separate short destination flash length.
- Add `OverworldWildSpawns_StartPhantomTeleportFlicker`.
- Call the teleport flicker helper after `MapObject_SetCurrentX/Y` and render-position updates, so the visible flash happens at the destination tile.
- Give the teleport flash a tiny movement cooldown before chase begins, preventing the first chase command from immediately overwriting the destination flicker.
- Explicitly call `OverworldWildSpawns_RevealPhantomStalker` from `OverworldWildSpawns_TryStartBattleForSlot` before pending battle setup.

Why this is new:

- Attempt 129 added random flicker windows only when hidden movement commands started.
- Attempt 130 teleported behind the player, but immediately hid after teleport and let the first chase command own the next flicker decision.
- No previous attempt has started a guaranteed flicker after the teleport destination is applied.
- No previous attempt has explicitly revealed phantoms at the central battle-start entry point.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES`
- `OverworldWildSpawns_StartPhantomTeleportFlicker`
- `OverworldWildSpawns_TryTeleportPhantomBehindPlayer`
- `OverworldWildSpawns_TryStartBattleForSlot`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test229.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test229.nds` both exist at 176 MB.
- Verified normal phantom flicker pulse length is now `2` frames.
- Verified teleport flicker uses `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES`.
- Verified teleport flicker starts after the map object's current/render position is updated to the destination.
- Verified the teleport path holds movement cooldown briefly so chase does not immediately overwrite the destination flicker.
- Verified `OverworldWildSpawns_TryStartBattleForSlot` reveals hidden phantoms before pending battle setup.

Runtime result:

- User reported that flicker was not working, and that it also did not appear to work in the previous iteration.

Learning:

- The short visible-window approach is not reliable enough visually, even with a guaranteed teleport-destination flash.
- Avoid treating "make the visible window shorter" as the fix; the problem needs a more explicit pulse/cadence or a different render toggle path.

### Attempt 132: Deterministic Phantom Flicker Pulse

Idea:

Replace the tiny one-shot visible windows with an explicit flicker pulse. A pulse starts visible, alternates visible/hidden every two frames, lasts long enough to see at the teleport destination, and also starts for every hidden movement command during the test build.

Implementation shape:

- Keep using `BIT_VANISH`, but stop interpreting `movementPhantomFlickerTimers` as "visible for all remaining frames".
- Add `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_PHASE_FRAMES` and `OverworldWildSpawns_ShouldShowPhantomFlicker`.
- Set normal hidden-movement pulses to `10` frames and teleport-destination pulses to `18` frames.
- Temporarily make the pulse chance `100%` so the behavior is testable and not dependent on random rolls.
- Call `OverworldWildSpawns_EnsureFrameMovementTask` when a normal or teleport pulse starts, so the visual timer is serviced even during cooldown or non-movement frames.

Why this is new:

- Attempt 129 used random visible windows during hidden movement.
- Attempt 131 made those visible windows shorter and added a guaranteed teleport-destination window.
- No previous attempt has alternated visible/hidden phases inside a single pulse or forced the frame task awake from pulse startup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_PHASE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES`
- `OverworldWildSpawns_ShouldShowPhantomFlicker`
- `OverworldWildSpawns_ApplyPhantomHiddenVisual`
- `OverworldWildSpawns_UpdatePhantomFlicker`
- `OverworldWildSpawns_TryStartPhantomFlicker`
- `OverworldWildSpawns_StartPhantomTeleportFlicker`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test230.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test230.nds` both exist at 176 MB.
- Verified normal hidden-movement pulses now last `10` frames and teleport-destination pulses last `18` frames.
- Verified `OverworldWildSpawns_ShouldShowPhantomFlicker` alternates visible/hidden phases every `2` frames.
- Verified both normal and teleport flicker pulse startup paths call `OverworldWildSpawns_EnsureFrameMovementTask`.

Runtime result:

- User reported the flicker still did not work.

Learning:

- Alternating `BIT_VANISH` in a deterministic pulse still does not produce a visible flicker in runtime.
- Do not keep cycling `BIT_VANISH` timing, odds, or phase lengths as the primary solution.
- The likely missing piece is that clearing the vanish bit during active movement does not force the spawned special/follower-style object's visible render resource back into the draw path.

### Attempt 133: Refresh Phantom Sprite On Visible Flicker Phase

Idea:

Keep the hidden phases on the existing `BIT_VANISH` path, but when a flicker phase becomes visible, explicitly refresh the object's current overworld sprite tag with `ChangeMapObjSprite` before clearing `BIT_VANISH`. This tests whether the failed flicker is not the timer itself, but the renderer/resource side failing to re-enter the visible draw path from a hidden moving object.

Implementation shape:

- Add `movementPhantomFlickerVisible` per spawn slot so the visible-phase refresh runs once per visible phase, not every frame.
- Add `OverworldWildSpawns_GetSpawnSpriteIdForSlot` to recover the correct species/form sprite tag from the saved spawn metadata.
- Add `OverworldWildSpawns_RefreshPhantomVisibleSprite`, which calls `ChangeMapObjSprite(object, spriteId)` for the current spawn sprite.
- Update `OverworldWildSpawns_ApplyPhantomHiddenVisual` so a visible flicker phase refreshes the sprite and then clears `BIT_VANISH`; hidden phases still set `BIT_VANISH`.
- Reset the new visible-phase bookkeeping when phantoms reveal, enter hidden state, start a pulse, reset movement, or spawn.
- Tighten universal A-button targeting so a hidden phantom is targetable only during a currently visible flicker phase.

Why this is new:

- Attempts 129 through 132 only changed the `BIT_VANISH` timer/chance/cadence and frame-task wakeup.
- Earlier shiny work used `ChangeMapObjSprite` only during spawn-time shiny palette setup, not as an in-motion visible-phase refresh.
- No previous attempt has combined `ChangeMapObjSprite` with each visible flicker phase while keeping hidden phases on `BIT_VANISH`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `movementPhantomFlickerVisible`
- `OverworldWildSpawns_GetSpawnSpriteIdForSlot`
- `OverworldWildSpawns_RefreshPhantomVisibleSprite`
- `OverworldWildSpawns_ApplyPhantomHiddenVisual`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test231.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test231.nds` both exist at 176 MB.
- Verified `movementPhantomFlickerVisible` is reset on reveal, hidden-state entry, pulse start, movement reset, and spawn initialization.
- Verified visible flicker phases call `ChangeMapObjSprite` once when entering the phase, then clear `BIT_VANISH`.
- Verified hidden phases still set `BIT_VANISH`.
- Verified A-button targeting now skips hidden phantoms unless the current flicker timer phase is visible.

Runtime result:

- User reported two failures:
  - Flicker still did not work.
  - Leaving a route where Pokemon had spawned crashed the game.

Learning:

- Refreshing the hidden object with `ChangeMapObjSprite` during visible flicker phases still did not produce the desired visible flicker.
- The same sprite-refresh path is unsafe during route cleanup: `OverworldWildSpawns_RevealPhantomStalker` ran from generic movement reset/map-transition paths and could call `ChangeMapObjSprite` on an object whose map/render context was being torn down.
- Do not call `ChangeMapObjSprite` from phantom reveal/reset/flicker cleanup paths. Keep heavy sprite reloads at normal object creation/spawn-time only.

### Attempt 134: Phantom Flicker Apparition Object

Idea:

Stop trying to make the hidden moving object itself visible. Keep the real phantom hidden with `BIT_VANISH`, and show a short-lived separate special-field-object apparition at the phantom's current position during visible flicker phases. This should avoid the failed "clear vanish on the same object" render path and avoid `ChangeMapObjSprite` during route cleanup.

Implementation shape:

- Replace `movementPhantomFlickerVisible` with `movementPhantomFlickerObjects`, a per-slot temporary apparition object pointer.
- Add `OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START` for apparition object IDs.
- Add `OverworldWildSpawns_ClearPhantomFlickerObject`, which only calls `DeleteMapObject` when the current field context is still valid; route teardown just clears the pointer.
- Add `OverworldWildSpawns_EnsurePhantomFlickerObject`, which creates a temporary special field object using the saved species/form/shiny metadata, syncs it to the real phantom's current position, and leaves the real phantom hidden.
- Add `OverworldWildSpawns_SyncPhantomFlickerObject` to keep the apparition aligned with the real phantom while it exists.
- Add `OverworldWildSpawns_HidePhantomFlickerObject` so the apparition can persist for a full flicker pulse and use `BIT_VANISH` only on the temporary apparition during hidden phases.
- Update `OverworldWildSpawns_ApplyPhantomHiddenVisual` so visible flicker phases ensure/sync the apparition, hidden phases hide the existing apparition, the pulse end deletes it, and the real phantom stays vanished either way.
- Move `movementFieldSystem` clearing to after per-slot movement reset so normal in-map resets can delete a live apparition, while route transitions still fail the current-field guard before deleting.
- Make tile-occupancy checks ignore apparition object IDs so the visual clone does not block movement or spawn placement.
- Remove the Attempt 133 visible-phase `ChangeMapObjSprite` refresh from reveal/reset/flicker paths.

Why this is new:

- Attempts 129 through 132 toggled `BIT_VANISH` on the real phantom.
- Attempt 133 tried reloading the real phantom sprite when the real object should become visible.
- No previous attempt has used a separate temporary map object as a visible flicker apparition while the real phantom remains hidden.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START`
- `movementPhantomFlickerObjects`
- `OverworldWildSpawns_ClearPhantomFlickerObject`
- `OverworldWildSpawns_EnsurePhantomFlickerObject`
- `OverworldWildSpawns_SyncPhantomFlickerObject`
- `OverworldWildSpawns_HidePhantomFlickerObject`
- `OverworldWildSpawns_IsPhantomFlickerObjectId`

Verification:

- `git diff --check` passed before and after build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test232.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test232.nds` both exist at 176 MB.
- Verified the old Attempt 133 source symbols `movementPhantomFlickerVisible`, `OverworldWildSpawns_GetSpawnSpriteIdForSlot`, and `OverworldWildSpawns_RefreshPhantomVisibleSprite` are gone from active source.
- Verified route cleanup no longer calls `ChangeMapObjSprite` from phantom reveal/reset/flicker cleanup paths.
- Verified the apparition object ID range is ignored by tile-occupancy checks.
- Verified a temporary apparition is kept alive across the whole flicker pulse instead of being recreated every visible phase.

Runtime result:

- User reported the flicker is now working, but the visible phases are a bit hard to follow.

Learning:

- The separate temporary apparition object solved the failed real-object `BIT_VANISH` flicker path.
- Expand the apparition approach; do not go back to toggling/reloading the real hidden object for flicker.
- The flicker cadence needs longer readable visible phases.

### Attempt 135: Phantom Teleport Alert Build-Up

Idea:

Keep the working apparition-object flicker from Attempt 134, but make it easier to read and move the teleport presentation into the alert state. When a phantom stalker spots the player, it now pauses with its alert bubble, enters a stand-still flicker charge that starts slowly and accelerates, teleports behind the player with a teleport sound, then briefly flickers at the arrival point before entering active stalking.

Implementation shape:

- Increase normal phantom flicker from `10` to `18` frames.
- Replace the old fixed `2`-frame alternating phase with `5` visible frames and `2` hidden frames for normal/arrival flicker.
- Add explicit phantom alert emote steps:
  - `OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PHANTOM_NOTICE`
  - `OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PHANTOM_CHARGE`
  - `OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PHANTOM_ARRIVE`
- Add a `24`-frame notice pause, a `96`-frame accelerating charge, and a `36`-frame arrival flicker.
- Route `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK` through `OverworldWildSpawns_TryStartPhantomTeleportAlert` instead of the generic speech-alert path.
- Use `SEQ_SE_DP_TELE` for the teleport sound, loaded through `GF_Snd_LoadSeqEx` immediately when the teleport succeeds.
- Keep the real phantom hidden during the charge/arrival phases and reuse the Attempt 134 apparition object for the visible flicker.

Why this is new:

- Attempt 134 proved the separate apparition object works, but kept the teleport as an immediate active-state transition.
- No previous attempt has moved phantom teleport timing into the alert/emote state.
- No previous attempt has used an accelerating flicker cadence or a notice/charge/arrival sequence.
- This does not retry the failed real-object `BIT_VANISH` flicker or the unsafe `ChangeMapObjSprite` visible refresh.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_VISIBLE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_HIDDEN_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_NOTICE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_CHARGE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_ARRIVE_FRAMES`
- `OverworldWildSpawns_ShouldShowPhantomFlickerForSlot`
- `OverworldWildSpawns_TryStartPhantomTeleportAlert`
- `OverworldWildSpawns_TickPhantomTeleportAlert`
- `OverworldWildSpawns_PlayPhantomTeleportSE`

Verification:

- `git diff --check` passed before and after build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test233.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test233.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled successfully.

Runtime result:

- User reported Gengar is not visible at all during its attentive state.

Learning:

- The alert build-up can finish with the real phantom still hidden and the finite apparition pulse expired.
- A finite arrival/movement-start pulse is not enough for active stalking; attentive state needs a continuous flicker loop.
- Keep the alert build-up, but make active phantom stalking continuously drive the apparition visibility instead of relying on one-shot pulses.

### Attempt 136: Active Phantom 60 Percent Flicker Loop

Idea:

Keep the Attempt 135 alert teleport presentation, but make the attentive/active phantom stalking state constantly flicker with a 60% visible ratio. The active stalker should never drop into permanent invisibility after the arrival pulse ends.

Implementation shape:

- Add active-state flicker constants:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_VISIBLE_FRAMES = 3`
  - `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_HIDDEN_FRAMES = 2`
  - `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_FLICKER_FRAMES = 5`
- Add `OverworldWildSpawns_IsActivePhantomStalker` to identify `OW_WILD_SPAWNER_SPOT_STATE_ACTIVE` phantoms using the phantom-stalk attentive state.
- Add `OverworldWildSpawns_EnsureActivePhantomFlickerTimer`, which restarts the 5-frame active flicker loop whenever the active phantom timer reaches zero.
- Update `OverworldWildSpawns_ShouldShowPhantomFlickerForSlot` so active phantom stalking uses the 3-visible/2-hidden cadence.
- Update `OverworldWildSpawns_UpdatePhantomFlicker` so active phantom stalking refreshes its loop timer before applying the apparition visual.
- Update `OverworldWildSpawns_TryStartPhantomFlicker` so movement starts in active phantom state restart the active 5-frame loop instead of starting a finite normal pulse.

Why this is new:

- Attempt 134 created the working apparition object.
- Attempt 135 moved teleport into the alert state but still let active visibility depend on finite pulses.
- No previous attempt has made active phantom stalking run a persistent 60/40 apparition loop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_VISIBLE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_HIDDEN_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_FLICKER_FRAMES`
- `OverworldWildSpawns_IsActivePhantomStalker`
- `OverworldWildSpawns_EnsureActivePhantomFlickerTimer`
- `OverworldWildSpawns_ShouldShowPhantomFlickerForSlot`
- `OverworldWildSpawns_UpdatePhantomFlicker`
- `OverworldWildSpawns_TryStartPhantomFlicker`

Verification:

- `git diff --check` passed before and after build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test234.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test234.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled successfully.

Runtime result:

- User reported Gengar is still completely invisible during attentive state.

Learning:

- A persistent 60/40 loop on the temporary apparition object is not enough during active stalking.
- The active stalking state still depends on the real object staying hidden after the teleport alert, and the apparition layer is not reliable as the active-state visible representation.
- Next attempt should make attentive stalking use the real map object again, while keeping the apparition object only for the teleport/hidden presentation.

### Attempt 137: Active Phantom Real-Object Flicker

Idea:

Keep the slow teleport build-up from Attempt 135 and the apparition object from Attempt 134 for hidden/teleport frames, but stop using the apparition as the active attentive-state representation. When the teleport alert finishes, reveal the real Gengar object, delete any temporary apparition, and drive a 3-visible/2-hidden flicker directly on the real object during attentive stalking.

Implementation shape:

- Add `OverworldWildSpawns_ShouldShowActivePhantomRealFlicker` so the active loop starts on a visible frame and then runs 3 visible frames followed by 2 hidden frames.
- Add `OverworldWildSpawns_StartActivePhantomRealFlicker`, called when the phantom teleport alert finishes:
  - delete the temporary apparition object;
  - clear `movementPhantomHidden`;
  - reset hidden-step state;
  - seed the active 5-frame flicker loop;
  - clear `BIT_VANISH` on the real object.
- Add `OverworldWildSpawns_UpdateActivePhantomRealFlicker`, serviced by the frame movement task before the hidden/apparition flicker path.
- Keep `OverworldWildSpawns_UpdatePhantomFlicker` for hidden teleport/arrival frames only.

Why this is new:

- Attempts 129-132 toggled `BIT_VANISH` while the phantom remained in the hidden path.
- Attempt 133 refreshed the sprite on the real object and caused unsafe route cleanup behavior.
- Attempts 134-136 used a separate apparition object for visible phantom frames.
- This attempt reveals the real object at the attentive-state boundary and flickers only that real object during active stalking, with no sprite refresh and no active apparition dependency.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ShouldShowActivePhantomRealFlicker`
- `OverworldWildSpawns_StartActivePhantomRealFlicker`
- `OverworldWildSpawns_UpdateActivePhantomRealFlicker`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`
- `OverworldWildSpawns_FrameMovementTask`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test235.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test235.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User reported Gengar is still completely invisible in attentive state after the teleport.

Learning:

- Revealing the old real object and flickering `BIT_VANISH` directly during active stalking still does not restore post-teleport visibility.
- The problem is likely not just a stale `BIT_VANISH` bit. The teleport path hand-writes render `posVec[0/2]` from tile coordinates, while stock object creation owns the correct map-object render setup.
- Do not keep trying to revive the same hidden/teleported object with `BIT_VANISH` timing.

### Attempt 138: Recreate Phantom Object After Teleport

Idea:

Stop trying to make the old hidden/teleported real object visible again. At the moment the teleport alert enters attentive state, create a fresh special field object at the teleported tile with the same species/form/shiny/render params, delete the old hidden object, swap the spawn slot pointer to the fresh object, and keep that fresh object visible for this test checkpoint.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_REAL_FLICKER = 0` for this checkpoint so active stalking does not immediately hide the fresh object again.
- Add `OverworldWildSpawns_RecreatePhantomObjectForActiveState`:
  - validate the current field/map-object context;
  - read the old object's current tile after teleport;
  - create a fresh special field object through `CreateSpecialFieldObjectWithParams`;
  - apply the spawn slot's species/form/shiny params;
  - apply the resolved behavior range;
  - delete the old real object;
  - store the replacement in `state->spawns[slot].object`.
- Call the recreate helper from `OverworldWildSpawns_FinishPhantomTeleportAlert` before starting the active visible state.
- Keep `OverworldWildSpawns_UpdateActivePhantomRealFlicker` as an active-state visibility service, but with active real flicker disabled it only clears `BIT_VANISH`.

Why this is new:

- Attempts 129-133 tried to revive or refresh the same hidden real object.
- Attempts 134-136 used a separate temporary apparition object while the real object stayed hidden.
- Attempt 137 revealed the old real object at active-state entry and flickered that same old object.
- No previous attempt has replaced the actual spawn object with a fresh stock-created object at the teleport destination before active stalking starts.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_REAL_FLICKER`
- `OverworldWildSpawns_RecreatePhantomObjectForActiveState`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`
- `OverworldWildSpawns_UpdateActivePhantomRealFlicker`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test236.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test236.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User moved on to teleport presentation tuning instead of reporting the post-teleport active invisibility as the current blocker.

Learning:

- Replacing the active phantom with a fresh stock-created object is a workable baseline for post-teleport visibility.
- The next problem is no longer just "make Gengar visible"; it is communicating the teleport clearly during the alert/charge before active stalking begins.

### Attempt 139: Origin/Destination Teleport Flicker And Face Player

Idea:

Make the teleport charge flicker between two visible positions instead of flickering between visible and invisible. When the phantom starts its teleport alert, turn the real object toward the player-facing direction already selected by alert detection. At charge start, record the origin tile and precompute the destination behind the player. During the charge/arrival, keep the real object hidden and alternate temporary apparition objects at the origin and destination tiles so the teleport reads as Gengar blinking between "here" and "there".

Implementation shape:

- Add per-slot teleport visual state:
  - `movementPhantomTeleportFlickerObjects`;
  - `movementPhantomTeleportOriginX/Y`;
  - `movementPhantomTeleportTargetX/Y`;
  - `movementPhantomTeleportHasTarget`.
- Add `OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START` so the destination apparition has its own object ID range, and update `OverworldWildSpawns_IsPhantomFlickerObjectId` so both apparition ranges are ignored by occupancy checks.
- Refactor apparition creation into `OverworldWildSpawns_EnsurePhantomFlickerObjectAtPosition`, then use it for:
  - the origin apparition;
  - the target apparition;
  - the existing one-position hidden flicker path.
- Add teleport target bookkeeping helpers:
  - `OverworldWildSpawns_ClearPhantomTeleportTarget`;
  - `OverworldWildSpawns_PreparePhantomTeleportTarget`.
- Update `OverworldWildSpawns_StartPhantomTeleportCharge` so it precomputes the teleport destination before the flicker begins.
- Update `OverworldWildSpawns_TryTeleportPhantomBehindPlayer` so it uses the precomputed target if still valid, or recalculates if something moved into the destination during the charge.
- Update `OverworldWildSpawns_ApplyPhantomHiddenVisual` to call `OverworldWildSpawns_ApplyPhantomTeleportPositionVisual` during phantom charge/arrival.
- Add `OverworldWildSpawns_SetObjectFacing` and call it from `OverworldWildSpawns_TryStartPhantomTeleportAlert` before the bubble appears.
- Reset the new teleport visual state on reveal, slot reset, and fresh spawn initialization.

Why this is new:

- Attempts 129-133 toggled visibility or refreshed the old real object.
- Attempts 134-136 used one temporary apparition object at the real object's current position.
- Attempt 137 tried real-object active flicker after teleport.
- Attempt 138 recreated the active object after teleport.
- No previous attempt alternated two visible temporary apparition objects at the origin and the destination during the teleport charge itself.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START`
- `OverworldWildSpawns_SetObjectFacing`
- `OverworldWildSpawns_ClearPhantomTeleportTarget`
- `OverworldWildSpawns_PreparePhantomTeleportTarget`
- `OverworldWildSpawns_EnsurePhantomFlickerObjectAtPosition`
- `OverworldWildSpawns_ApplyPhantomTeleportPositionVisual`
- `OverworldWildSpawns_StartPhantomTeleportCharge`
- `OverworldWildSpawns_TryTeleportPhantomBehindPlayer`
- `OverworldWildSpawns_TryStartPhantomTeleportAlert`

Verification:

- `git diff --check` passed before and after the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test237.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test237.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User reported the origin/destination flicker does not feel good for the standard teleport alert.
- User also reported that this visual idea does seem promising as a movement type where the phantom teleports instead of walking.

Learning:

- Do not keep the two-position origin/destination flicker on the standard alert teleport.
- The visual is worth reusing as active stalking locomotion, but it needs to be about twice as fast and isolated to attentive-state movement.

### Attempt 140: Active Phantom Teleport-Step Movement

Idea:

Revert the origin/destination flicker out of the standard phantom alert teleport, but reuse the same "old tile / new tile" presentation as the phantom stalker's active movement type. While active stalking, the behavior resolver still picks chase directions as before, but the phantom teleports one tile to the chosen valid destination instead of starting a stock walk command. The real object moves to the target immediately for behavior continuity, then stays hidden while temporary apparitions flicker between origin and destination for a short transition.

Implementation shape:

- Keep `OverworldWildSpawns_SetObjectFacing` from Attempt 139 so the standard alert still turns toward the player before the speech bubble.
- Stop precomputing the standard alert destination in `OverworldWildSpawns_StartPhantomTeleportCharge`.
- Restore `OverworldWildSpawns_TryTeleportPhantomBehindPlayer` to choosing its destination at the actual teleport moment and not setting the two-position visual target state.
- Gate `OverworldWildSpawns_ApplyPhantomTeleportPositionVisual` behind `OverworldWildSpawns_IsActivePhantomTeleportMove` so two-position flicker only runs during active attentive movement.
- Add active teleport movement timing:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_FRAMES`, half of the older teleport flicker window;
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_PHASE_FRAMES`, a short origin/target alternation phase.
- Add `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand`:
  - uses the existing active stalking direction list;
  - requires a valid, unoccupied target tile;
  - records origin/target;
  - moves the real object to target;
  - hides the real object;
  - starts the frame-task-owned teleport-step visual.
- Add `OverworldWildSpawns_TickPhantomTeleportMovementCommand` so the active movement slot completes after the visual timer and then runs the normal finished-movement handler for history, stamina, tired-state, and battle settle behavior.
- Update the frame task so active teleport-step visuals own their timer and are not also decremented by the generic phantom hidden-flicker updater.

Why this is new:

- Attempt 139 used origin/destination flicker only for the standard teleport alert/arrival presentation.
- Previous active stalking attempts used walking movement, active real-object visibility, or hidden apparition flicker, but did not replace active stalk movement with a frame-task-owned teleport step.
- This attempt keeps the standard teleport presentation reverted while moving the two-position effect into a separate locomotion path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_PHASE_FRAMES`
- `OverworldWildSpawns_SetObjectTile`
- `OverworldWildSpawns_IsActivePhantomTeleportMove`
- `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`
- `OverworldWildSpawns_FrameMovementTask`

Verification:

- `git diff --check` passed before and after the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test238.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test238.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User asked to change active stalking movement away from the one-tile chase teleport. The desired behavior is now to teleport toward the front of the player, with up to 5 tiles of movement per blink, and to avoid passive proximity battle starts.

Learning:

- The one-tile chase-direction teleport is not the intended fantasy for the stalking profile. Active stalking should treat "front of the player" as the locomotion goal, while keeping the standard alert teleport separate.

### Attempt 141: Front-Of-Player Phantom Teleport Movement

Idea:

Change active phantom stalking movement so it tries to teleport to the tile in front of the player instead of teleporting one tile along the existing chase direction list. Each attentive-state blink can move up to 5 tiles. If the exact front tile is farther than 5 tiles from the ghost, the ghost should blink up to 5 tiles toward that front target rather than stalling. Also remove phantom stalk from the automatic proximity battle path: it should battle only through the universal A-button interaction or by the player actively pressing into the occupied facing tile.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_DISTANCE` as the active blink distance limit.
- Add front-target helpers:
  - `OverworldWildSpawns_TryGetPhantomFrontTeleportTarget`;
  - `OverworldWildSpawns_TryUsePhantomFrontTeleportCandidate`;
  - `OverworldWildSpawns_ClampDeltaToStep`;
  - `OverworldWildSpawns_GetOppositeDirection`;
  - `OverworldWildSpawns_GetFacingTowardTile`.
- Make `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand` ignore the normal chase/flee direction list for phantom stalkers and instead:
  - prefer valid tiles on the ray in front of the player's current facing;
  - fall back to a clamped 5-tile blink toward the closest front tile;
  - record the movement distance and origin/target tiles for the existing active teleport visual;
  - face the ghost toward the player after the blink target is selected.
- Add `OverworldWildSpawns_TryStartBattleFromDirectionalBump`, which starts a battle when the player is pressing the D-pad direction matching their current facing and a spawned Pokemon occupies that facing tile.
- Keep `OverworldWildSpawns_TryStartBattleFromAButton` unchanged as the universal intentional interaction.
- Remove `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK` from the generic `OverworldWildSpawns_TryStartBattle` automatic touching loop, leaving only aggressive chase there.

Why this is new:

- Attempt 128 targeted behind-player stalking with ordinary movement.
- Attempt 130 teleported behind the player on alert and then reused chase/contact behavior.
- Attempt 140 made active stalking teleport one tile along the existing chase direction list.
- No previous attempt has made the active stalk locomotion explicitly target the front of the player, nor separated phantom battles into A-button/directional-bump interactions while removing passive phantom proximity battles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_DISTANCE`
- `OverworldWildSpawns_TryGetPhantomFrontTeleportTarget`
- `OverworldWildSpawns_TryUsePhantomFrontTeleportCandidate`
- `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand`
- `OverworldWildSpawns_TryStartBattleFromDirectionalBump`
- `OverworldWildSpawns_TryStartBattle`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test239.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test239.nds` both exist at 176 MB.
- `git diff --check` passed after updating the log.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User asked for a 1-second wait after each active teleport movement before the next phantom stalk movement can begin.

Learning:

- The front-of-player movement target still needs pacing: without an explicit post-teleport cooldown, the frame task can immediately enter another movement decision after the teleport visual finishes.

### Attempt 142: One-Second Pause After Active Phantom Teleport

Idea:

After an active phantom stalk teleport movement finishes, wait one second before allowing the next attentive teleport movement. The pause should apply after the teleport-step visual completes, not before or during the visual, and should not override tired-state transitions.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES` set to `60`.
- In `OverworldWildSpawns_TickPhantomTeleportMovementCommand`, after the active teleport clears its movement-in-progress bit and runs `OverworldWildSpawns_HandleFinishedMovementCommand`, set `state->movementCooldowns[slot]` to the new cooldown only if:
  - the spawn is still active;
  - the spot state is still `OW_WILD_SPAWNER_SPOT_STATE_ACTIVE`;
  - the resolved attentive state is still `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.

Why this is new:

- Earlier cooldown work controlled generic movement cadence, tired cooldowns, chill wandering pauses, and alert-arrival flicker timing.
- Attempt 131 briefly held movement after the alert teleport destination flicker, but that was before active chase and was part of the old behind-player alert presentation.
- No previous attempt has added a post-completion cooldown specifically after each active attentive-state phantom teleport movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test240.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User asked to add the same 1-second wait to the alert-arrival phase as well.

Learning:

- The post-active-teleport pause covers repeated active movement, but the first movement after the alert arrival still needs the same pacing pause so the arrival can breathe before stalking resumes.

### Attempt 144: Visible Teleport Pauses And Faster Alert Teleport

Idea:

Make the phantom visible during both 1-second teleport pauses, and make the alert-state teleport presentation twice as fast. The pause should no longer leave hidden/apparition/teleport target state active while the Pokemon is waiting.

Implementation shape:

- Halve alert teleport timing:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_CHARGE_FRAMES` from `96` to `48`;
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_ARRIVE_FRAMES` from `36` to `18`.
- Keep `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_NOTICE_FRAMES` unchanged so the alert bubble still has readable time before the teleport begins.
- Add `OverworldWildSpawns_StartPhantomVisibleCooldown`, which:
  - calls `OverworldWildSpawns_RevealPhantomStalker`;
  - clears hidden/flicker/teleport target state through the reveal path;
  - clears `BIT_VANISH` on the real object;
  - sets the 60-frame phantom cooldown;
  - keeps the frame task awake.
- Use the visible-cooldown helper after:
  - active phantom teleport movement finishes and the Pokemon remains in active phantom stalking;
  - phantom alert arrival finishes and the Pokemon enters active phantom stalking.
- Preserve the active teleport's reveal before post-movement state handling so tired-state transitions do not inherit a hidden real object.

Why this is new:

- Attempts 134-138 established that active visibility is reliable only after using the recreated real object and clearing hidden state, but did not connect that to the new cooldown pauses.
- Attempt 142 added a post-active-teleport cooldown but did not centralize visibility cleanup at pause start.
- Attempt 143 added an alert-arrival cooldown but did not force visibility during that wait.
- No previous attempt has paired the explicit 60-frame pause with a shared "make the real phantom visible now" helper.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_CHARGE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_ARRIVE_FRAMES`
- `OverworldWildSpawns_StartPhantomVisibleCooldown`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test242.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.
- Verified both `test.nds` and the Delta copy exist and are 176 MB.

Runtime result:

- User reported a regression: all spawned Pokemon now start battles when the player gets close/presses into them. That was not intended.

Learning:

- The likely culprit is the directional-bump battle helper added during phantom stalking work: `OverworldWildSpawns_TryStartBattleFromDirectionalBump` loops every active spawn, even though that interaction was meant for the phantom stalker profile only.

### Attempt 145: Restrict Directional Bump Battles To Phantom Stalkers

Idea:

Keep the universal A-button battle path for all spawned Pokemon, keep automatic contact battles for `agressiveChase`, but restrict directional bump battles to active phantom stalkers only. This should remove unintended "all Pokemon start battle when close/pressed into" behavior without losing the intentional Gengar-style "player runs into the ghost" interaction.

Implementation shape:

- In `OverworldWildSpawns_TryStartBattleFromDirectionalBump`, check each slot's behavior profile before allowing the battle:
  - `movementSpotStates[i]` must be `OW_WILD_SPAWNER_SPOT_STATE_ACTIVE`;
  - `profile.attentiveState` must be `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.
- Skip fully hidden phantom stalkers unless their flicker window is currently visible.
- Leave `OverworldWildSpawns_TryStartBattleFromAButton` unchanged, so pressing A on any visible spawned Pokemon still starts a battle.
- Leave `OverworldWildSpawns_TryStartBattle` unchanged, so only active `agressiveChase` Pokemon auto-start battles on contact.

Why this is new:

- Attempt 141 added directional bump battles while removing phantom stalkers from the generic proximity-battle loop, but the new directional-bump loop was accidentally broad and applied to every spawn.
- No previous attempt has profile-gated `OverworldWildSpawns_TryStartBattleFromDirectionalBump` back to the phantom stalker behavior that motivated it.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryStartBattleFromDirectionalBump`
- `OverworldWildSpawns_TryStartBattleFromAButton`
- `OverworldWildSpawns_TryStartBattle`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test243.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- No battle-trigger runtime result was reported yet. User reported a separate phantom-stalk issue: the visible-pause fix is working after the alert-state teleport, but not after attentive-state teleport movement.

Learning:

- The profile guard should still stand for directional bump battles, but attentive-state teleport visibility needs its own follow-up.
- Alert arrival works because `OverworldWildSpawns_FinishPhantomTeleportAlert` recreates the real object before starting the visible pause.
- Active attentive teleport still only revealed the same object that was hidden for the teleport visual, so it can fall back into the old unreliable "clear vanish on the just-hidden object" path.

### Attempt 148: Phantom Chill Wander Teleportation

Idea:

Make phantom stalkers use a new `wanderTeleportation` chill movement instead of ordinary walking. While chill/default, each movement decision should choose a random cardinal direction and a random landing distance from 3-6 tiles, use the same origin/target flicker teleport visual as attentive-state phantom movement, then recreate/reveal the real object and pause visibly for 1 second.

Implementation shape:

- Add `OW_WILD_BEHAVIOR_CHILL_STATE_WANDER_TELEPORT` and assign it to the phantom stalker behavior-class override.
- Add wander teleport distance constants:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MIN_DISTANCE = 3`;
  - `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MAX_DISTANCE = 6`.
- Add `movementPhantomVisiblePause[slot]` so the post-teleport pause is an explicit interaction window rather than inferred from a cooldown value.
- Generalize the phantom teleport visual runner so it works when the phantom stalker is either:
  - active/attentive; or
  - chill/default.
- Add `OverworldWildSpawns_TryGetPhantomWanderTeleportTarget`, which:
  - randomizes direction order;
  - randomizes distance order from 3-6;
  - accepts only valid, unoccupied, non-blocked, non-surf, non-headbutt landing tiles.
- Add `OverworldWildSpawns_TryStartPhantomWanderTeleportMovementCommand` and route chill `WANDER_TELEPORT` decisions through it.
- Keep active attentive phantom movement targeting the front of the player unchanged.
- On teleport completion, recreate the real phantom object and call `OverworldWildSpawns_StartPhantomVisibleCooldown` for both active and chill phantom teleport movement.
- Keep directional bump battles restricted to the explicit visible-pause flag.

Why this is new:

- Attempts 140-147 changed alert and attentive-state phantom teleport behavior, but chill/default phantom movement still used ordinary chill walking.
- Attempt 147 made visible pause explicit for battle gating, but did not use it as a chill movement cadence.
- No previous attempt has added a phantom-only chill movement mode that randomly teleports 3-6 tiles and then uses the same post-teleport visible pause.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_BEHAVIOR_CHILL_STATE_WANDER_TELEPORT`
- `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MIN_DISTANCE`
- `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MAX_DISTANCE`
- `movementPhantomVisiblePause`
- `OverworldWildSpawns_TryStartPhantomWanderTeleportMovementCommand`
- `OverworldWildSpawns_TryGetPhantomWanderTeleportTarget`

Verification:

- `git diff --check` passed.
- `./docker-makerom.cmd` produced a fresh `test.nds` at `2026-06-06 19:57`.
- The Docker wrapper did not return to the post-build copy helper after the ROM was created, so the stale wrapper session was closed and the repo helper was run directly.
- `./scripts/copy-test-nds-to-delta.sh` copied the ROM to Delta as `test246.nds`.

Runtime result:

- User reported that Gengar still simply wanders normally, so the chill/default `wanderTeleportation` behavior is not reaching runtime Gengar in `test246.nds`.

Learning:

- The phantom class override table contains `OW_WILD_BEHAVIOR_CHILL_STATE_WANDER_TELEPORT`, and Gengar is in `OW_WILD_BEHAVIOR_GROUP_GHOST`.
- The failure is more likely behavior-class resolution/caching on the active slot than the table definition itself.

### Attempt 151: Materialize Visible Phantom Flicker For A-Button Battles

Idea:

Allow A-button battles during visible Gengar flicker frames by converting the currently visible apparition tile into the real, stable Gengar object before queuing battle. This keeps A responsive without carrying hidden movement state, teleport targets, or helper objects into the black battle transition.

Implementation shape:

- Add `OverworldWildSpawns_TryGetPhantomBattleVisibleTile`.
  - Stable visible phantom: returns the real object's current tile.
  - Teleport-position flicker: returns the currently displayed origin or target tile.
  - Normal/alert flicker: returns the real object's tile only on visible flicker frames.
  - Hidden invisible frames remain non-interactable.
- Add `OverworldWildSpawns_IsPlayerFacingTile` so the A-button path can target a visible apparition tile directly.
- Add `OverworldWildSpawns_StabilizePhantomForBattleAtTile`.
  - Clears single movement/in-progress movement.
  - Deletes phantom flicker helper objects.
  - Moves the real object to the visible apparition tile.
  - Clears `BIT_VANISH`, hidden/flicker timers, teleport target state, and phantom alert emote state.
- Update `OverworldWildSpawns_TryStartBattleFromAButton`:
  - If a phantom visible tile is facing the player, stabilize it first, then call `OverworldWildSpawns_TryStartBattleForSlot`.
  - Keep hidden invisible frames ignored.
  - Keep normal non-phantom A-button battles unchanged.

Why this is new:

- Attempt 150 blocked unsafe phantom battle starts during flicker/teleport state.
- Earlier attempts revealed hidden phantoms before battle, but did not move the real object to the currently visible flicker tile or support A-button targeting of the apparition itself.
- No previous attempt has stabilized a visible phantom helper frame into the real object before battle setup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetPhantomBattleVisibleTile`
- `OverworldWildSpawns_IsPlayerFacingTile`
- `OverworldWildSpawns_StabilizePhantomForBattleAtTile`
- `OverworldWildSpawns_TryStartBattleFromAButton`

Verification:

- `git diff --check` passes.
- Clean rebuild was required after an earlier interrupted build removed generated headers; removed generated `build/` and `base/`, then rebuilt with `./docker-makerom.cmd`.
- Build succeeded and copied the ROM to Delta as `test250.nds`.

Runtime result:

- Pending user test on hardware/emulator.

Learning:

- Code/build side supports the intended stable A-button path: visible phantom frames are materialized into the real object before the battle script is queued, while invisible frames remain ignored.

### Attempt 152: Disable Phantom Stalk Alert-State Teleport

Idea:

Try Phantom Stalk without the alert-state teleport. Gengar should still spot the player and enter its attentive state, but the initial alert should be the normal speech-bubble beat instead of the slow flicker/teleport/arrival sequence.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_ALERT_TELEPORT_ENABLED`, currently set to `0`.
- When the toggle is off, do not route phantom stalkers through `OverworldWildSpawns_TryStartPhantomTeleportAlert`.
- Let phantom stalkers use the generic speech alert path, then enter active state through `OverworldWildSpawns_EnterActiveStateFromGenericAlert`.
- For phantom stalkers leaving a generic alert, call the same stable active-entry helper used after the old alert teleport: reveal/recreate the real object, start active-state real flicker handling, and apply the visible cooldown.
- Keep chill/attentive teleport movement unchanged.

Why this is new:

- Earlier phantom attempts refined the alert teleport, active teleport movement, flicker timing, and battle stability around teleport/flicker frames.
- No previous attempt has disabled only the alert-state teleport while preserving Phantom Stalk's teleport-style movement in chill/attentive states.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ALERT_TELEPORT_ENABLED`
- `OverworldWildSpawns_EnterActiveStateFromGenericAlert`
- `OverworldWildSpawns_TryStartSpotEmote`

Verification:

- `git diff --check` passed.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test251.nds`.
- After wrapping the disabled alert-teleport starter in `#if OW_WILD_SPAWNER_PHANTOM_STALK_ALERT_TELEPORT_ENABLED`, `./docker-makerom.cmd` built successfully again and copied the clean ROM to Delta as `test252.nds`.

Runtime result:

- Pending user test on `test252.nds`.

Learning:

- Build-side result is stable. This ROM isolates the feel of removing only Phantom Stalk's alert-state teleport while preserving later teleport movement.

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

### Attempt 154: Canopy Hopper Attentive Ambush Target

Idea:

Refine Mankey's `canopy_hopper` attentive state so it uses trees to approach the player, then jumps from a tree down onto the tile in front of the player when close enough.

Implementation shape:

- Keep chill-state canopy movement as random real-headbutt-tree hopping.
- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE`, currently 6 tiles.
- Split headbutt-tree target validation from target selection so both random and directed modes reuse the same safety checks.
- In attentive state:
  - read the player's current facing and compute the tile directly in front of the player
  - require that tile to be a valid non-headbutt, non-surf, unblocked, unoccupied landing tile
  - if Mankey is currently on a headbutt tree and that front tile is within ambush range, jump directly to that tile
  - otherwise choose a valid headbutt tree within profile range that reduces distance to the player-front tile
- When the direct ambush jump succeeds, force the profile's normal tired transition so Mankey pauses in front of the player instead of immediately jumping away.

Why this is new:

- Attempt 153 proved the new class/profile shape and archive-backed random tree hopping.
- No previous attempt made canopy hopping a directed two-phase behavior: tree chase toward a player-relative target, then ground ambush.
- This still avoids custom animated movement descriptors and keeps using the stable direct placement path from Attempt 153.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE`
- `OverworldWildSpawns_TryUseCloserHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTargetToward`
- `OverworldWildSpawns_TryGetCanopyHopperPlayerFrontTarget`
- `OverworldWildSpawns_TryPickCanopyHopperAttentiveTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test254.nds`.

Runtime result:

- Pending user test on `test254.nds`.

Learning:

- Build-side result is stable. Runtime should verify that attentive Mankey first tree-hops closer when the player-front tile is out of range, then jumps down to that tile and pauses tired when it can make the ambush jump.

### Attempt 155: Canopy Hopper Tired Return-To-Tree Case

Idea:

Make Mankey explicitly return to a headbutt tree after its attentive ambush makes it tired on the ground. It should not rely on random chill hopping to maybe choose a tree; it should have a dedicated recovery path back into the canopy.

Implementation shape:

- Keep the tired timer and tired bubble state generic.
- After tired finishes, Mankey already returns to chill state through the normal tired cooldown path.
- In chill-state canopy movement, detect whether the canopy hopper is currently standing on a headbutt tree.
- If it is not on a headbutt tree, choose the nearest valid real headbutt tree from the current map's `ARC_HEADBUTT_TREES` data.
- Reuse the same tree validity checks as the other canopy hopper modes:
  - real headbutt tree coordinate
  - not current tile
  - within profile range
  - within despawn distance
  - not occupied
  - has a valid nearby landing tile
- Only after Mankey is back on a tree does chill movement fall back to random tree-to-tree hopping.

Why this is new:

- Attempt 153 added random tree-to-tree hopping.
- Attempt 154 added attentive tree chase plus direct ambush onto the player-front ground tile and a tired pause there.
- No previous attempt added a ground-to-tree recovery case for canopy hoppers after tired state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseReturnHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test255.nds`.

Runtime result:

- Pending user test on `test255.nds`.

Learning:

- Build-side result is stable. Runtime should verify that Mankey returns from the ground ambush/tired pause to the nearest valid real headbutt tree before resuming random canopy movement.

### Attempt 157: Universal Canopy Hopper Return-To-Tree Priority

Idea:

Make Mankey's return-to-tree logic universal for the canopy hopper behavior. If Mankey is off a headbutt tree for any reason, its next canopy movement decision should return it to a tree before any chill, attentive, chase, or ambush behavior.

Implementation shape:

- Change the Mankey behavior-class rule from headbutt terrain only to any terrain.
- Remove the headbutt-terrain guard from `OverworldWildSpawns_TryStartHeadbuttTreeHop`; the behavior profile now decides whether this movement applies.
- At the start of canopy hopper target selection, before attentive ambush or random roaming, check whether the object is currently on a headbutt tree.
- If it is not on a tree, use `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget` immediately.
- Only when Mankey is already on a tree can it continue into active ambush targeting or chill random tree hopping.

Why this is new:

- Attempt 155 returned Mankey to a tree only from chill-state canopy movement.
- Attempt 156 made land test spawns become Mankey, which exposed that Mankey should not depend on headbutt terrain to get canopy behavior.
- No previous attempt made off-tree recovery the first priority across Mankey's canopy movement states and terrains.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildBehaviorClassRules`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`
- `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget`

Verification:

- Built as `test257.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the Mankey behavior-class rule now uses `OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN`.
- Verified `OverworldWildSpawns_TryStartHeadbuttTreeHop` no longer rejects non-headbutt-terrain spawns.
- Verified off-tree recovery via `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget` is selected before active ambush targeting or chill random tree hopping.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify that any canopy-hopper Mankey which ends up off a tree returns to a valid real headbutt tree before continuing chill, attentive, chase, ambush, or random tree-hop behavior.

### Attempt 162: Custom Rendered Far Canopy Hop

Idea:

Make canopy hopping visually travel more than one tile by moving the logical object to the far target, then rendering it offset back at the origin and interpolating its rendered X/Z position to the target over a short hop timer. This uses `posVec[0]` and `posVec[2]`, which are already proven visible by the ram crash object-wobble effect, instead of relying on stock `Jump*2` movement commands.

Implementation shape:

- Add per-slot canopy render-hop start/target X/Z, base Y, and timer state.
- When a pending canopy target starts, record the origin and target fixed-point positions.
- Set the object's logical tile to the far target immediately for behavior continuity.
- Override `posVec[0]`/`posVec[2]` back to the origin so the sprite starts visually where it stood.
- Each frame, interpolate the visible `posVec[0]`/`posVec[2]` toward the target for `24` frames.
- Apply a small Y arc during the timer as a best-effort hop lift, while keeping the important long-distance travel on the known-visible X/Z axes.
- Finish the pending canopy hop only after the custom render-hop timer reaches the far target.

Why this is new:

- Attempt 158 delayed direct placement but still blinked to the target.
- Attempt 159 chained stock visible jump commands and was limited to one visible tile per command.
- Attempt 160 allowed 7-tile targets but still used stock jump commands.
- Attempt 161 preferred far targets but still used stock jump commands.
- Earlier manual `posVec[1]` hopping failed, but this attempt is different because it uses `posVec[0]`/`posVec[2]`, which later ram crash work proved can visibly move spawned objects.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `movementCanopyRenderHopStartX/Z`
- `movementCanopyRenderHopTargetX/Z`
- `movementCanopyRenderHopTimers`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test263.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the touched overlay compiles with only older diagnostic unused warnings still present.
- Verified canopy travel no longer starts a stock `Jump*` / `Jump*2` movement command.
- Verified the frame task now ticks `OverworldWildSpawns_TickCanopyRenderHopMovementCommand` before generic stock movement updates.
- Verified reset paths restore a partially rendered canopy hop back to its logical target position before clearing movement state.

Runtime result:

- User reported Mankey still instantly teleports.

Learning:

- Moving the real object's logical tile to the destination and then overriding its `posVec[0]`/`posVec[2]` back to the origin does not produce a visible travel arc.
- The renderer or map-object update path appears to snap the real object to its logical destination strongly enough that large render offsets are not visible, even though small same-tile wobble offsets work.
- The next attempt should avoid showing the real object during travel and instead use a separate temporary visual object.

### Attempt 163: Canopy Helper Object Far-Hop Visual

Idea:

Hide the real Mankey at the far landing tile and use a temporary helper object as the visible travelling sprite. The helper starts at the origin, interpolates across the full route, then gets deleted when the real Mankey is revealed at the target. This should prevent the instant logical-target snap from being visible.

Implementation shape:

- Add a dedicated temporary object id range for canopy hop helper objects.
- Add per-slot `movementCanopyRenderHopObjects`.
- Exclude canopy helper ids from occupancy checks, the same way phantom helper ids are ignored.
- When a far canopy hop starts:
  - move the real object logically to the target;
  - set `BIT_VANISH` on the real object;
  - create a helper object at the origin with the same species/form/shiny render params;
  - animate the helper's `posVec[0]`/`posVec[2]` over the stored render-hop timer.
- On completion or reset:
  - delete the helper;
  - restore/reveal the real object at the target.

Why this is new:

- Attempt 162 manipulated the real object's render position after changing its logical tile.
- Phantom movement has used temporary helper objects, but no canopy attempt has used a helper object as the visible travelling sprite.
- This still avoids retrying stock `Jump*2` as a multi-tile travel command.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_CANOPY_RENDER_HOP_OBJECT_ID_START`
- `movementCanopyRenderHopObjects`
- `OverworldWildSpawns_ClearCanopyRenderHopObject`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test265.nds` and copied to Delta.
- `git diff --check` passed before the final build.
- Verified the helper-object path compiles after removing an accidental unused local from the unrelated phantom teleport function.
- Verified active code hides the real canopy hopper at the far target, creates a temporary visual helper at the origin, excludes helper ids from occupancy checks, interpolates the helper's `posVec[0]`/`posVec[2]`, then deletes the helper and reveals the real object at completion/reset.

Runtime result:

- User reported there is still no hopping.

Learning:

- A temporary helper object with manually interpolated `posVec[0]`/`posVec[2]` still does not produce a readable hop.
- This makes the failure less likely to be only "the real object's logical tile snaps its render position"; helper objects also appear to have their large manual render offsets snapped/ignored.
- Do not keep retrying raw large `posVec` travel arcs for canopy hopping without new evidence.
- The next attempt should use stock movement-command rendering on the helper object, because stock `Jump*Site` is already proven to render visible same-tile hops on spawned Pokemon and stock moving jumps are proven to render airborne motion.

### Attempt 164: Helper Object Stock-Jump Segments

Idea:

Keep the Attempt 163 hidden-real/helper-object split, but stop manually interpolating the helper's render position. Instead, make the helper object run stock `Jump*2` / `Jump*` movement commands toward the far canopy target. The real Mankey remains hidden at the final target for gameplay state, while the helper performs visible jump segments and is deleted once it reaches the target.

Implementation shape:

- Reuse `movementCanopyRenderHopObjects` as the visible helper object.
- When the helper starts, move the real object logically to the final target and hide it.
- Start a stock helper jump segment toward the final target:
  - prefer `Jump*2` if the remaining distance in that direction is at least two tiles;
  - use `Jump*` for the final one-tile segment.
- Drive `MapObject_UpdateMovementCommand` on the helper object from the frame task.
- When a segment finishes, either start the next helper jump immediately or reveal the real object/delete the helper if the target has been reached.

Why this is new:

- Attempt 159 chained stock jump commands on the real spawn object.
- Attempts 162 and 163 tried raw render-position interpolation.
- No previous attempt has combined the hidden-real/helper-object split with stock jump movement commands on the helper object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_StartNextCanopyHelperJumpSegment`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test267.nds` and copied to Delta.
- `git diff --check` passed before the final build.
- Verified the final build no longer emits the new signedness warning from `OverworldWildSpawns_IsAtCanopyRenderHopTarget`; remaining overlay warnings are older unused diagnostic symbols/functions.
- Verified `OverworldWildSpawns_TickCanopyRenderHopMovementCommand` now updates the helper object with `OverworldWildSpawns_UpdateSpawnerMovementCommand` instead of manual `posVec` interpolation.
- Verified segment selection prefers stock `Jump*2` for two-tile chunks and `Jump*` for one-tile cleanup, then reveals the real object at the final target when the helper reaches it.

Runtime result:

- User reported this still does not work, Mankey is often invisible, and hop time should scale with distance.

Learning:

- The hidden-real/helper-object split is not stable enough for canopy hopping.
- Helper stock jumps did not solve visibility; they made Mankey unreliable/invisible in runtime.
- Do not keep pursuing helper-object canopy travel unless a new reason appears to believe helper visibility ownership can be made stable.
- Hop timing should be derived from travel distance, not a fixed manual timer.

### Attempt 165: Real Object Stock-Jump Chain Without Segment Wait

Idea:

Back out of helper-object canopy travel and keep the real Mankey visible for the whole hop. Use stock moving jump commands on the real object again, but remove the old half-second wait between every segment. Long canopy targets should now take proportionally longer because Mankey performs more stock jump segments, while avoiding the invisible helper handoff.

Implementation shape:

- Do not move the real object directly to the final target before visual travel.
- Do not create or hide behind `movementCanopyRenderHopObjects`.
- When a pending canopy target is ready:
  - choose the larger remaining axis toward the target;
  - start `Jump*2` when at least two tiles remain on that axis;
  - start `Jump*` for the final one-tile cleanup.
- Let `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand` finish the full hop only when the real object reaches the stored target.
- If the real object has not reached the target, immediately queue the next segment with normal decision cooldown `0`, so no artificial pause is inserted between segments.

Why this is new:

- Attempt 159 chained stock jumps on the real object but intentionally waited half a second before each segment.
- Attempts 163 and 164 used helper objects and produced no hop/invisibility issues.
- No previous attempt has used the real-object stock jump chain without the per-segment staging wait after the first jump.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- Built as `test268.nds` and copied to Delta.
- `git diff --check` passed before and after the code change.
- Verified the active path in `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` no longer creates a helper object, moves the real object directly to the final target, or hides the real object with `BIT_VANISH`.
- Verified the active path clears any stale canopy render helper, keeps the real object visible, and starts stock real-object `Jump*2` / `Jump*` movement commands based on remaining distance.
- Verified `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand` keeps the pending target alive and immediately queues another real-object stock jump segment with cooldown `0` until Mankey reaches the final target.

Runtime result:

- User reported Mankey only jumps one tile.

Learning:

- This confirms the Attempt 161 learning: the stock `Jump*2` command family is not a multi-tile travel command for spawned Pokemon in this context.
- The real-object stock-chain path is better for visibility than the helper-object path, but it cannot create a readable far hop.
- Do not keep pursuing stock `Jump*` / `Jump*2` commands as the distance carrier for canopy hopping without new evidence.

### Attempt 166: Real Object Deferred Logical Commit Render-Hop

Idea:

Make the real Mankey perform one full-distance rendered hop without helper objects and without stock moving jump commands. Keep the logical object tile at the origin while the hop is in flight, animate the real object's X/Z render position toward the far target over a duration derived from hop distance, then commit the logical tile to the far target only when the animation lands.

Implementation shape:

- When the staged canopy target is ready:
  - record the real object's current fixed-point X/Z as the render-hop start;
  - record the target fixed-point X/Z and base Y;
  - set `movementCanopyRenderHopTimers[slot]` to a distance-scaled duration;
  - mark the movement slot in progress without starting a stock movement command.
- In the frame task, while the render-hop timer is active:
  - keep the real object visible;
  - interpolate `object->posVec[0]` and `object->posVec[2]` from origin to target;
  - add a best-effort vertical arc through `object->posVec[1]`;
  - only call `OverworldWildSpawns_SetObjectTile` at the final frame.
- Finish the pending canopy hop through the existing `OverworldWildSpawns_FinishPendingCanopyHop` path after landing.

Why this is new:

- Attempt 162 moved the logical object to the far target first, then tried to offset the rendered position back to the origin; runtime snapped/teleported.
- Attempts 163 and 164 used helper objects and produced invisibility.
- Attempts 159, 161, and 165 used stock `Jump*` / `Jump*2` commands and only moved one tile.
- No previous attempt has kept the real object's logical tile at the origin for the full custom X/Z render-hop and committed the logical target only on landing.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test269.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the overlay compiles; warnings shown during the build are the older unused diagnostic symbols/functions, not new canopy-hop compile failures.
- Verified the active canopy-hop starter no longer calls `MapObject_StartMovementCommand` / stock `Jump*` for distance travel.
- Verified the active canopy-hop starter records start X/Z, target X/Z, base Y, and a distance-scaled render-hop duration, then marks the slot in progress.
- Verified `OverworldWildSpawns_TickCanopyRenderHopMovementCommand` now interpolates the real object's `posVec[0]`/`posVec[2]` until the final frame, then commits the logical tile with `OverworldWildSpawns_SetObjectTile`.

Runtime result:

- User reported this failed: Mankey became invisible.

Learning:

- Moving the real object's X/Z render position far away from its logical tile makes Mankey disappear.
- This confirms that long-distance `posVec[0]`/`posVec[2]` travel is not safe for canopy hopping, even when the logical tile is committed only at landing.
- Do not keep pursuing real-object or helper-object raw X/Z render interpolation without new evidence.

### Attempt 167: Horizontal WaitJump Command Probe

Idea:

Test the less-used stock `WaitJumpLeft1/2` and `WaitJumpRight1/2` movement commands for canopy travel. These commands are distinct from the already-failed `JumpLeft2` / `JumpRight2` family and were not previously tried for Mankey. If `WaitJumpLeft2` / `WaitJumpRight2` are true two-tile waited jumps, they may provide a stable visible multi-tile horizontal hop without helper objects or manual render offsets.

Implementation shape:

- Revert the active canopy travel path away from manual X/Z render interpolation.
- Keep the real Mankey visible and use stock movement command ownership again.
- For horizontal canopy segments:
  - use `WaitJumpLeft2` / `WaitJumpRight2` when at least two horizontal tiles remain;
  - use `WaitJumpLeft1` / `WaitJumpRight1` for one horizontal tile.
- For vertical canopy segments, fall back to the previous stock `Jump*2` / `Jump*` family for now so the path remains functional even though vertical true far-hop remains unsolved.
- Continue chaining toward the staged far target with no artificial segment wait.

Why this is new:

- Attempts 159, 161, and 165 used `Jump*` / `Jump*2`, not the `WaitJumpLeft/Right` family.
- Attempts 162, 163, and 166 used raw render-position interpolation and produced teleport/no-hop/invisibility.
- Attempt 164 used helper objects with stock `Jump*` commands, not `WaitJumpLeft/Right`.
- No previous attempt has used `WaitJumpLeft1/2` or `WaitJumpRight1/2` as the active canopy travel command.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryGetCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Verified the active canopy starter no longer arms `movementCanopyRenderHopTimers[slot]` with a manual long-distance X/Z interpolation duration.
- Verified the active canopy starter clears stale render-hop state, keeps the real object visible with `MapObject_ClearBits(object, BIT_VANISH)`, and starts stock movement ownership through `OverworldWildSpawns_StartMovementCommandForSlot`.
- Verified horizontal segments use named `WaitJumpLeft1/2` and `WaitJumpRight1/2` constants (`0x5C`-`0x5F`), while vertical segments still fall back to the already-known `Jump*`/`Jump*2` family.
- Built as `test270.nds` and copied to Delta.

Runtime result:

- User reported Mankey still appears to only do one-tile jumps.

Learning:

- `WaitJumpLeft2` / `WaitJumpRight2` did not make the runtime feel like a readable multi-tile canopy hop.
- The next probe should remove one-tile target and command paths entirely so runtime testing can tell whether short targets or the stock movement command itself is the cause.

### Attempt 168: Strict Five-To-Seven Tile Canopy Hop Probe

Idea:

Disable short canopy hop choices for Mankey and only allow normal canopy tree-to-tree / attentive tree-chase targets whose Chebyshev distance is 5-7 tiles from the current tile. Also remove the explicit one-tile `WaitJumpLeft1` / `WaitJumpRight1` command path from active canopy travel, so a pending far target cannot deliberately issue a visible one-tile jump command as a segment.

Implementation shape:

- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES` with a value of `5`.
- Keep `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES` at `7`.
- Raise the attentive ambush range to `7`, and only allow direct player-front ambush jumps when the front tile is 5-7 tiles away.
- Pass the minimum distance into normal random tree-hop and attentive tree-chase candidate validation.
- Keep return-to-tree recovery exempt from the 5-tile minimum so off-tree Mankey can still get back onto a valid headbutt tree instead of getting stranded.
- Remove active use of the one-tile `WaitJumpLeft1` / `WaitJumpRight1` commands.
- If a previously staged odd-distance far target reaches a final one-tile remainder, silently land/finish the pending hop instead of starting another visible one-tile jump command.

Why this is new:

- Attempt 160 only raised the maximum target distance to 7 and still allowed short candidates.
- Attempt 161 preferred farther valid candidates, but still allowed short candidates if they were the best available or selected by context.
- Attempt 167 tested `WaitJumpLeft/Right1/2`, but still explicitly used one-tile wait-jump commands for one-tile remainders.
- No previous attempt has enforced a strict 5-tile minimum for normal canopy candidate selection while leaving return-to-tree recovery exempt.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`
- `OverworldWildSpawns_IsValidHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryGetCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Verified normal tree-hop and attentive tree-chase candidate validation now use a 5-tile minimum.
- Verified return-to-tree candidate validation still allows one-tile recovery movement.
- Verified direct player-front ambush requires `frontDistance >= OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`.
- Verified active canopy travel no longer references `OW_WILD_SPAWNER_CANOPY_HOPPER_WAIT_JUMP_LEFT_1_COMMAND` or `OW_WILD_SPAWNER_CANOPY_HOPPER_WAIT_JUMP_RIGHT_1_COMMAND`.
- Built as `test271.nds` and copied to Delta.

Runtime result:

- User reported Mankey sometimes becomes invisible.

Learning:

- Strict 5-7 tile candidate selection is not enough to make the current stock command carrier stable.
- Since helper-object travel and raw X/Z render offsets were already ruled out, the next probe should keep the real object as the gameplay object but refresh/recreate it after stock command completion so stale render state cannot persist between canopy segments.

### Attempt 169: Recreate Real Canopy Object After Each Segment

Idea:

Keep the Attempt 168 strict 5-7 tile target selection, but stabilize visibility by recreating the real spawned object at its current tile after each stock canopy movement segment finishes. This borrows the successful stabilization pattern from phantom stalking, where recreating the real object after hidden/teleport states restored visibility more reliably than clearing `BIT_VANISH` on the same object.

Implementation shape:

- Add `OverworldWildSpawns_RecreateSpawnObjectAtTile`, a generic real-spawn object refresh helper:
  - clears any active single-movement flag on the old object;
  - creates a new special field object at the requested tile;
  - reapplies object id, movement range, species/form/shiny render params, facing, tile position, and visible state;
  - updates `state->spawns[slot].object` to the replacement.
- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, recreate the real object at the segment landing tile before either finishing the pending canopy hop or scheduling the next segment.
- In the odd-distance final one-tile cleanup path, recreate the real object at the final target before finishing the pending hop.

Why this is new:

- Attempts 163 and 164 used a temporary helper object for canopy travel and produced invisibility; this attempt does not use a helper object as the visible traveller.
- Attempt 166 moved the real object's render position far from its logical tile and produced invisibility; this attempt does not manually interpolate X/Z render position.
- Attempt 167 and Attempt 168 kept the same real object through stock movement-command segments.
- Phantom attempts proved object recreation can restore stable visibility, but no canopy attempt has recreated the real Mankey after each completed stock movement segment.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test272.nds` and copied to Delta.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 170: Canopy Hopper Always-Visible Invariant

Idea:

Make `canopy_hopper` behavior explicitly never use hidden/flicker presentation state. Unless the object is being deleted/despawned, a canopy hopper should always clear `BIT_VANISH`, ignore stale phantom hidden flags, and clear stale helper/visual-hop state. Mankey should hop, not blink out.

Implementation shape:

- Add `OverworldWildSpawns_IsCanopyHopperProfile`.
- Add `OverworldWildSpawns_EnforceCanopyHopperVisibility`, which:
  - clears stale canopy render-hop helper objects without deleting the real Mankey if a stale pointer aliases it;
  - clears stale canopy render-hop timer/position state without clearing the pending canopy target;
  - clears stale phantom flicker helper objects and phantom teleport target state;
  - resets phantom hidden/flicker/visible-pause flags;
  - clears `BIT_VANISH` on the real canopy-hopper object;
  - normalizes the render position to the logical tile only when the object is not currently executing a movement command.
- Call the invariant from the normal movement tick, the frame-level movement task before phantom flicker handling, and after recreate-at-tile refresh.

Why this is new:

- Attempt 169 recreated the real object only after completed canopy movement segments.
- This attempt does not add another travel carrier or helper-object presentation path.
- This attempt adds an always-visible rule for the canopy profile itself, so stale phantom/helper state cannot keep hiding Mankey between movement decisions.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsCanopyHopperProfile`
- `OverworldWildSpawns_EnforceCanopyHopperVisibility`
- `OverworldWildSpawns_TickMovementParams`
- `OverworldWildSpawns_FrameMovementTask`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`

Verification:

- `git diff --check` passed before the build.
- Built as `test273.nds` and copied to Delta.

Runtime result:

- User reported Mankey is now much more often invisible.

Learning:

- The per-frame always-visible invariant is unsafe for canopy hoppers.
- Clearing helper/render/phantom state every update can interfere with stock movement-command ownership or render state and makes invisibility worse.
- Do not enforce canopy visibility by mutating visual state every frame.
- Back out the frame/tick enforcement path and only clean stale visual state at safe movement boundaries.

### Attempt 171: Boundary-Only Canopy Visual Cleanup

Idea:

Keep the useful part of Attempt 170, but remove the harmful part. Canopy hoppers should still clean stale hidden/helper state, but only at safe transition points: when a hop is staged, immediately before a stock movement command starts, and after the object is recreated at a landing tile. Do not touch render/helper state every frame while stock movement commands own the object.

Implementation shape:

- Replace `OverworldWildSpawns_EnforceCanopyHopperVisibility` with `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary`.
- Keep `OverworldWildSpawns_IsCanopyHopperProfile`.
- Remove the per-frame calls from:
  - `OverworldWildSpawns_TickMovementParams`;
  - `OverworldWildSpawns_FrameMovementTask`.
- Keep boundary cleanup calls in:
  - `OverworldWildSpawns_StageCanopyHopTarget`;
  - `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`;
  - `OverworldWildSpawns_RecreateSpawnObjectAtTile`.
- The boundary cleanup:
  - clears stale canopy render-hop helper/timer state only when the real object is not actively moving;
  - clears stale phantom hidden/flicker state;
  - clears `BIT_VANISH`;
  - does not normalize render position every frame.

Why this is new:

- Attempt 170 tried continuous per-frame enforcement and made invisibility worse.
- Attempt 171 keeps cleanup out of active movement frames and only runs at known transition boundaries.
- Earlier canopy attempts did not separate "always visible" cleanup into safe boundary-only moments.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsCanopyHopperProfile`
- `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`

Verification:

- `git diff --check` passed before the build.
- Built as `test274.nds` and copied to Delta.

Runtime result:

- User reported Mankey still blinks / becomes invisible when on trees.
- User clarified that headbutt trees can affect visibility somewhat, but they do not make Pokemon completely invisible; other Pokemon that spawn on trees without canopy-hopper behavior do not have this issue.
- User clarified that the assumption "headbutt tree tiles themselves are unsafe render surfaces, so Mankey should use nearby landing/perch tiles instead" is wrong.

Learning:

- Boundary-only cleanup did not solve the tree-state blinking/invisibility.
- Do not pursue a tree-anchor rewrite that moves canopy hoppers to adjacent landing/perch tiles based on the rejected "tree tile render surface" assumption.
- Preserve the design that Mankey is on the tree.
- The stronger suspect is now the canopy arrival path, especially deleting/recreating the moving Mankey object when it lands on a headbutt-tree tile.

### Attempt 175: Recreate Final Tree Landing Without Manual Tile Rewrite

Idea:

When a canopy hop reaches its final target on a headbutt tree, rebuild the spawned object the way ordinary headbutt spawns are created, but do not immediately call `OverworldWildSpawns_SetObjectTile` on the replacement. This tests whether the manual coordinate/vector rewrite is what makes tree-resting Mankey differ from normal visible tree spawns.

Implementation shape:

- Keep the Attempt 174 intermediate-segment behavior:
  - no delete/recreate during intermediate canopy segment landings;
  - normalize the landed tile;
  - clear `BIT_VANISH`;
  - wait a short settle delay before the next segment.
- Change final canopy landings so they can refresh on headbutt-tree tiles again.
- Add `OverworldWildSpawns_ShouldNormalizeCanopyRefreshAtTile`.
- Add a `normalizeTileAfterCreate` argument to `OverworldWildSpawns_RecreateSpawnObjectAtTile`.
- Pass `FALSE` for final headbutt-tree refreshes, letting `CreateSpecialFieldObjectWithParams` initialize the replacement position like a normal headbutt spawn.
- Pass `TRUE` for non-tree final refreshes, preserving the previous stabilization behavior there.

Why this is new:

- Attempt 169 recreated after every completed segment and always used `OverworldWildSpawns_SetObjectTile` on the replacement.
- Attempt 172 skipped refresh specifically on headbutt-tree arrivals.
- Attempt 173/174 also skipped final tree refreshes while focusing on intermediate segment handoff.
- Attempt 175 is the first test that recreates only the final tree landing while deliberately skipping the manual post-create tile rewrite for that replacement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`
- `OverworldWildSpawns_ShouldNormalizeCanopyRefreshAtTile`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built once as `test278.nds`; that build succeeded but exposed new unused-parameter warnings in the edited refresh predicate.
- Added explicit unused-parameter markers for the predicate split.
- Rebuilt as `test279.nds` and copied to Delta.
- The rebuild no longer emits the new `x`/`y` unused-parameter warnings. Existing unrelated project warnings remain.

Runtime result:

- User reported this did not fix the real symptom: after Mankey jumps more than two tiles, the first two tiles animate fine, then Mankey starts bugging out.

Learning:

- The final tree refresh path was not the primary issue for this report.
- The runtime clue points back to the boundary after the first two-tile stock jump segment.
- The existing canopy render-hop timer/state is currently only ticked/restored; it is not started anywhere, so long hops are still being implemented by chaining stock two-tile jump commands.
- The next attempt should avoid the repeated stock two-tile command boundary entirely and use one spawner-owned render hop from origin to final target.

### Attempt 176: Use One Manual Render Hop For Full Canopy Distance

Idea:

Stop chaining stock two-tile jump commands for Mankey canopy hops. The first stock two-tile segment works, but the handoff into the next segment is where the bug starts. Use the existing canopy render-hop state as the actual movement: lerp the real object's X/Z render position from the current tile to the final target over a distance-scaled arc, then commit the logical tile only at the end.

Implementation shape:

- Add a starter for the existing `movementCanopyRenderHop*` state.
- In `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, when the remaining distance is two or more tiles, start one full render hop to `movementCanopyHopTargetX/Y` instead of choosing a two-tile stock jump command.
- Preserve the one-tile final cleanup path.
- At render-hop completion:
  - commit the logical tile to the final target;
  - reuse the final refresh logic from Attempt 175, including skipping manual post-create tile normalization on headbutt-tree tiles;
  - finish the canopy hop normally.

Why this is new:

- Attempt 48 tried manual `posVec[1]` bobbing for a same-tile spot emote, but not full X/Z render movement for canopy travel.
- Attempts 159 and 173/174 changed timing around stock two-tile segment chaining, but still relied on multiple stock movement commands.
- Attempt 175 changed final tree refresh behavior, but still left long movement as chained two-tile stock commands.
- Attempt 176 is the first test that removes the segment-to-segment stock command boundary from Mankey's long canopy hop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_StartCanopyRenderHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test280.nds` and copied to Delta.
- The edited overlay compiled without new Attempt 176-specific warnings. Existing unrelated project warnings remain.

Runtime result:

- User reported this feels like an instant teleport instead of a hop.

Learning:

- Removing the stock two-tile command boundary avoids the exact chained-command implementation, but direct real-object `posVec` interpolation still does not communicate visible motion.
- This matches earlier evidence from Attempt 48 that direct render-position edits can be overwritten, ignored, or visually collapse into a snap for these objects.
- The next step needs deeper investigation of the movement-command/render contract rather than another narrow timing tweak.
- New investigation questions:
  - whether stock movement lists can safely sequence multiple jump commands on spawned Pokemon;
  - whether multi-tile jump commands or wrappers exist in shipped scripts;
  - which object fields the renderer actually uses for smooth movement and visibility.

## Proposed Next New Experiments

Only use this section after checking that the current idea has not already been tried above.

### Experiment A: Add Back `MapObject_SetParam` Only

Purpose:

Check whether custom movement init/update can safely touch params without field-system lookup, scratch writes, or movement commands.

Would add:

- Init: set cooldown param only.
- Update: decrement cooldown param only.

Would still avoid:

- `object->fsys`
- global `FieldSystem *`
- `object->unkD8`
- single-movement flags
- movement command helpers
- coordinate reads

### Experiment B: Add Back Player/Object Coordinate Reads Only

Purpose:

Check whether position lookup is safe before command movement is attempted.

Would add:

- global `FieldSystem *` setter
- player coordinate reads
- object coordinate reads

Would still avoid:

- movement command helpers
- blocked-direction helper
- scratch writes
- single-movement flags

### Experiment C: Add A Look Command Before Any Walk Command

Purpose:

Check whether starting a non-moving facing command is safer than a walk command.

Would add:

- `MapObject_MovementCommandFromDirection`
- `MapObject_StartMovementCommand`
- `MapObject_SetSingleMovementActive`
- `MapObject_UpdateMovementCommand`

Would still avoid:

- walking commands
- blocked-direction helper

### Experiment D: Compare Stock Movement Descriptor Init/Update Requirements

Purpose:

Understand whether movement descriptor word `0` or callback semantics require stock values more specific than current assumptions.

Would inspect:

- stock descriptor table around movement `3`, `47`, and neighboring slots
- stock init/update/finalize/cleanup functions near `0x020612b4` and `0x020613f8`
- how movement manager calls descriptor callbacks

Would avoid:

- new runtime changes until the descriptor contract is clearer

### Experiment E: Obstruction-Blocked Aggressive Ram Alertness

Purpose:

Make `aggressive_ram` alertness use line of sight instead of raw cardinal range. The ram should only spot and lock onto the player if every tile between the ram and the selected player target is unobstructed.

Would add:

- a ram-specific obstruction scan after `OverworldWildSpawns_IsPlayerInCardinalLine` succeeds
- a check for each intermediate tile between the ram and target
- blocked metatiles and occupied blocking objects interrupting alertness
- the existing cardinal-direction range and moving-player target smoothing from Attempt 126

Would still avoid:

- changing non-ram alertness
- changing ram attentive movement once alert has already started
- changing ram crash collision/battle logic
- changing spawn/despawn/tile-occupancy exact-coordinate behavior

### Attempt 177: Canopy Hopper Vanilla Movement-List Task

Idea:

Replace the manual full-hop render interpolation from Attempt 176 with the game's vanilla movement-list task runner. Instead of repeatedly starting single movement commands from the spawner, build one stock movement list for the full canopy hop and let the engine own command sequencing, previous/current tile updates, movement scratch state, and jump rendering.

Why this is new:

- Attempt 159 and later stock-command attempts restarted independent `Jump*` / `Jump*2` commands from the spawner.
- Attempts 162, 163, and 176 tried manual large `posVec` interpolation on real or helper objects.
- Attempt 164 used a helper object plus stock command restarts.
- No previous canopy attempt has called the vanilla lower-level movement-list task directly with `(command, count)` entries that persist for the whole hop.

Implementation plan:

- Expose the vanilla movement-list helpers at `0x02062214`, `0x02062260`, and `0x0206226C`.
- Store a per-slot `SysTask *` and fixed movement-list buffer in overworld wild spawn state.
- Build lists such as `LockDir -> JumpRight2 x N -> optional JumpRight -> ReleaseDir -> MovementEnd`.
- Poll the list task from the existing movement frame task and run the normal canopy landing/refresh/finish logic once the list task completes.
- Clean up the task on slot reset, slot deletion, map context loss, and battle cleanup paths so no stale task points at a deleted object.

Verification:

- `git diff --check` passed before the build.
- First build attempt compiled the overlay but overflowed the base ROM/data region by `119` bytes because the movement-list task pointer/list buffers were stored inside `OverworldWildSpawnState`.
- Moved the movement-list task pointers and list buffers to overlay-local static storage so the base spawn state size stays stable.
- Built successfully as `test281.nds` and copied to Delta.
- The edited overlay compiled with only older unused diagnostics still present.

Runtime result:

- User reported:
  - Mankey now visibly hops instead of instant teleporting, except for in trees.
  - It can travel only 1-2 tiles at a time and never exceeds that.
  - It does not stay visible on/near trees.
  - Route leaving no longer crashes/freezes.

Learning:

- The vanilla movement-list task is safer for route transitions than the earlier helper/manual render-hop attempts.
- The active builder did not actually match the planned `JumpRight2 x N` shape; it emitted one `Jump*` command per path tile and did not add `LockDir`/`ReleaseDir`.
- Final canopy landing still recreates the object, keeping one of the suspect visibility handoffs alive.
- Continue from the movement-list path, but make the list actually use two-tile jump runs and avoid final canopy object recreation.

### Attempt 179: Direct Engine-Owned Long Canopy Jump

Idea:

Stop treating `Jump*2` as a distance-two command. Disassembly and sidecar investigation show the stock jump wrappers use `MapObject_StartJumpMovementInternal` and that `Jump*` / `Jump*2` are timing variants around one-tile engine movement. For canopy hopper runs of at least 5 tiles, call the stock jump initializer directly with the normal one-tile delta but a longer frame count, so the engine owns the movement scratch, tile commits, and jump arc for one 5-7 tile straight run.

Implementation shape:

- Expose `MapObject_StartJumpMovementInternal` at `0x02062958 | 1`.
- Add the matching prototype to `include/map_events_internal.h`.
- Enable the previously disabled `OverworldWildSpawns_StartCanopyLongJumpCommand` path.
- Only use the direct internal jump when the first same-direction path run is at least `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`.
- Fall back to the vanilla movement-list task for shorter cleanup paths.
- Add one landing-boundary canopy visual cleanup after movement completion, without restoring the unsafe per-frame always-visible invariant from Attempt 170.

Why this is new:

- Attempts 159, 165, 167, 168, 177, and 178 used stock movement commands or movement lists as command sequences.
- Attempts 162, 163, 166, and 176 used manual or helper-object render interpolation.
- No previous attempt has called the stock internal jump initializer directly with a longer frame count for one engine-owned multi-tile run.

Files/symbols:

- `rom.ld`
- `include/map_events_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `MapObject_StartJumpMovementInternal`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test345.nds` and copied to Delta.
- The edited overlay compiled with only older unused diagnostics still present.

Runtime result:

- User reported:
  - Mankey never visibly travelled more than 1-2 tiles in one hop.
  - Mankey did not stay visible on/near trees after landing.
  - Leaving the route still did not avoid crashes/freezes.

Learning:

- Directly exposing `MapObject_StartJumpMovementInternal` was not enough because the active target picker could still choose a zig-zag path and the long-jump path only ran when the BFS path's first same-direction run was at least 5 tiles.
- The active path still kept legacy canopy movement-list fallback and canopy boundary cleanup still touched phantom hidden/flicker state, so this was not a clean canopy-only ownership model.
- Do not repeat Attempt 179 as "internal jump plus BFS first-run plus movement-list fallback plus phantom boundary cleanup."

### Attempt 180: Clean Straight-Run Canopy Driver

Idea:

Rebuild the active Mankey canopy movement path around one real object and one straight cardinal hop target. The new test should avoid the legacy systems that kept reappearing in failed canopy attempts: helper objects, object recreate/refresh, raw render-position interpolation, movement-list fallback, and phantom visibility cleanup.

Implementation shape:

- Add a direct straight-run target picker for canopy hoppers:
  - scan cardinal rays from the current tile;
  - prefer 5-7 tile landings;
  - require the landing tile to be a valid headbutt landing/perch tile;
  - avoid the previous landing, occupied tiles, and far-offscreen despawn targets.
- Use the direct internal jump starter only for same-axis target runs.
- Keep the normal internal one-tile jump delta and lengthen the frame count by run distance; disassembly shows the internal jump updater commits a tile whenever its accumulated delta reaches one tile, so scaling the delta would risk committing too many tiles too quickly.
- Remove the active movement-list fallback from canopy hopping while this test is active.
- Make canopy boundary cleanup canopy-only: clear `BIT_VANISH` on the real object and do not touch phantom flicker/hidden/helper state.
- On map-context reset, clear movement bookkeeping without revealing phantom objects or restoring ram wobble on stale map objects unless the caller explicitly requested current-object cleanup.

Why this is new:

- Attempt 179 used `MapObject_StartJumpMovementInternal`, but it depended on the BFS path's first run and still fell back to vanilla movement lists.
- Attempts 163-164 used helper objects; this does not.
- Attempts 166 and 176 used manual `posVec` travel; this does not.
- Attempts 169-175 used object recreate/refresh variations; this keeps the real object.
- Attempt 170 tried per-frame visibility enforcement; this only clears `BIT_VANISH` at controlled canopy boundaries and avoids phantom cleanup entirely.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryPickCanopyStraightRunTarget`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary`
- `OverworldWildSpawns_ResetSlotMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test346.nds` and copied to Delta.
- The edited overlay compiled. The build now warns that several legacy canopy helpers are unused (`OverworldWildSpawns_RecreateSpawnObjectAtTile`, `OverworldWildSpawns_StartCanopyMovementListTask`, and `OverworldWildSpawns_GetCanopyPathFirstRunLength`) because this attempt intentionally disconnects the old recreate/list/BFS-first-run paths from active Mankey movement.
- Verified active canopy target selection now asks `OverworldWildSpawns_TryPickCanopyStraightRunTarget` before the older tree-pair pickers for both chill wandering and attentive "toward target" movement.
- Verified active canopy movement no longer falls back to `OverworldWildSpawns_StartCanopyMovementListTask` when the clean straight jump cannot start.
- Verified canopy boundary cleanup no longer clears phantom hidden/flicker/helper state.
- Verified map-context loss in the frame task now clears movement bookkeeping through `OverworldWildSpawns_ResetAllMovementStateOnly` without touching stale map objects.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 192: Range-Gated Canopy Long-Jump Carrier

Idea:

Keep the successful partner-prepped internal long-jump carrier from Attempt 190/191, but stop treating it as a general-purpose jump primitive. The user reported that `test358.nds` had a lot of bugs and that Mankey sometimes disappeared and never reappeared. The likely regression is that Attempt 191 allowed the carrier to accept any distance up to the raw `255` frame budget and let `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` try that carrier before the older cleanup path.

Implementation shape:

- Set the active canopy hopper tile range to `3-8` tiles.
- Set the canopy ambush range to `8` so player-front ambushes can use the same maximum.
- Replace the raw frame-budget `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES` with behavior-gated `LONG_JUMP_MIN/MAX` aliases tied to the canopy hopper min/max constants.
- Make `OverworldWildSpawns_GetCanopyLongJumpTiming` reject distances below `3` or above `8`.
- Make `OverworldWildSpawns_StartCanopyLongJumpCommand` reject same-axis pending targets outside `3-8` before running partner prep.
- Make return-to-tree candidate selection use the same minimum `3` tile distance instead of allowing one-tile return hops.
- If a pending canopy target has a remaining distance of exactly `2`, clear the target, reveal the object, and cool down instead of entering the long-jump prep path or leaving an impossible short target staged.

Why this is new:

- Attempt 190 proved one partner-prepped four-tile internal jump.
- Attempt 191 generalized that carrier too broadly.
- Earlier visibility attempts either enforced visibility every frame, used helper/recreate handoffs, or cleaned phantom state. This attempt does not reintroduce those systems; it constrains the successful carrier to the behavior range and adds a narrow abort reveal for invalid short targets.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TryUseReturnHeadbuttTreeHopCandidate`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test359.nds` into the Delta ROM folder.
- Overlay compiled with the expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- User reported that Mankey now rarely decides to jump.

Learning:

- The 3-8 carrier range stayed safe enough to continue, but the behavior layer became too restrictive and could stage targets that the carrier later rejected.
- The old "visible perch" radius still made tree/perch state fuzzy, so Mankey could be considered on/near a tree without being on a concrete tree-adjacent perch.

### Attempt 194: Forced Mankey Tree-Tile Occupancy Render Probe

Idea:

The long-hop carrier now appears promising enough to pause movement work and isolate the next tree behavior question: can Mankey occupy the actual headbutt tree tile without being hidden by the canopy? This should not reuse the old perch-radius, helper-object, phantom hiding, or hop-state cleanup paths. For this test, spawn exactly one Mankey on a known Route 29 headbutt tree tile, do not move it, and try a small follower-style render flag bundle so it can potentially draw above the tree.

Why this is new:

- Attempt 193 removed the broad perch radius and improved movement target validation.
- Earlier canopy attempts focused on hopping, helper sprites, object recreation, visibility cleanup, or exact adjacent perches.
- This attempt does not move Mankey at all and does not stage a perch/hop target; it tests tree-tile occupancy and object render flags directly.

Implementation shape:

- Add `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_OCCUPANCY_TEST`.
- Broaden only the shared forced-canopy spawn/refill guards to compile for either the old movement test or the new tree-occupancy test.
- Force the Route 29 test spawn to `594,389`, the known headbutt tree tile, while ignoring player/follower occupancy and still rejecting duplicate active spawned Pokemon.
- Override Mankey headbutt behavior to idle/no-alert/no-attentive movement while this test is enabled.
- Skip the canopy-hopper perch relocation while this test is enabled.
- Apply a test-only follower-style render bundle to the forced Mankey object: set `0x2400`, clear `0x180`, call `MapObject_SetFlag29(TRUE)`, call `sub_02069DC8(TRUE)`, and clear `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_OCCUPANCY_TEST`
- `OW_WILD_SPAWNER_FORCE_CANOPY_TEST_SPAWN`
- `OverworldWildSpawns_TryPickRoute29CanopyTreeOccupancyTestSpawnPosition`
- `OverworldWildSpawns_ApplyCanopyTreeOccupancyTestRenderParams`

Verification:

- `git diff --check` passed before and after the log update.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test361.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this tree-occupancy probe.

Runtime result:

- User clarified before runtime testing that this targeted the wrong tile class. The desired probe is the tree-top/canopy-cap metatile visually above/overlapping the player and follower, not the actual headbutt behavior tile.

Learning:

- Do not treat "tree behavior" and "headbutt tree coordinate" as equivalent for the render-order test. The next test should target a canopy-top visual tile and should not require `GetMetatileBehaviorAt(...) == OW_WILD_TILE_HEADBUTT`.

### Attempt 195: Forced Mankey Canopy-Top Occupancy Render Probe

Idea:

Correct Attempt 194 by moving the isolated render probe from the known Route 29 headbutt behavior tile to the adjacent canopy-top visual tile. The user specifically wants to test the red-box style tree-top tiles that can visually obscure the player/follower, so this test should not reject the target just because it is not classified as `OW_WILD_TILE_HEADBUTT`.

Why this is new:

- Attempt 194 tested `594,389`, a known headbutt behavior coordinate, and required behavior `15`.
- This attempt tests `594,388`, one tile north of that headbutt pair, as a canopy-top visual tile.
- The movement remains disabled and the follower-style render flag bundle remains the same, so the only intentional variable is the target tile class.

Implementation shape:

- Rename the forced test coordinate constants to canopy-top terminology.
- Set the forced Route 29 Mankey test coordinate to `594,388`.
- Remove the `OW_WILD_TILE_HEADBUTT` metatile-behavior requirement from the forced position picker.
- Keep the forced spawn terrain as headbutt so encounter/species plumbing remains simple, but set `position.startX/startY` directly to the canopy-top tile.
- Keep movement, alertness, and attentive behavior disabled for this test.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y`
- `OverworldWildSpawns_TryPickRoute29CanopyTopOccupancyTestSpawnPosition`
- `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams`

Verification:

- `git diff --check` passed before and after the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test362.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.

Runtime result:

- User reported that Mankey appears to blink and disappear.

Learning:

- The corrected canopy-top coordinate is likely hitting the intended tile class, but the follower-style render bundle is unsafe here.
- This matches the prior shiny investigation warning that full follower render flags on wild special-field objects can make them invisible or unstable. The next probe should keep the object on the normal special-field path and not call the follower flag/toggle helpers for non-shiny canopy-top testing.

### Attempt 196: Normal-Path Canopy-Top Occupancy Probe

Idea:

Keep the forced Route 29 canopy-top coordinate from Attempt 195, but remove the follower-style render bundle that prior shiny work already identified as unsafe for wild special-field objects. For this probe, Mankey should still spawn on `594,388` with no movement, but its render setup should stay on the normal special-field path and only clear `BIT_VANISH`.

Why this is new:

- Attempt 194/195 used the follower-style bundle: set `0x2400`, clear `0x180`, `MapObject_SetFlag29(TRUE)`, `sub_02069DC8(TRUE)`, then clear `BIT_VANISH`.
- `documentation/overworld_shiny_sprite_investigation.md` explicitly says full follower render flags on overworld wild objects can make them invisible.
- This attempt removes those follower-path flags/toggles instead of adding more visibility enforcement.

Implementation shape:

- Keep `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X/Y` at `594,388`.
- Keep the forced spawn idle/no-alert/no-attentive.
- Change `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams` to only clear `BIT_VANISH`.
- Leave the standard `FollowPokeMapObjectSetParams(...)` call in `OverworldWildSpawns_ApplyPokemonRenderParams`, since that is the stable normal overworld wild sprite metadata path used by regular/shiny spawns.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams`
- `documentation/overworld_shiny_sprite_investigation.md`

Verification:

- `git diff --check` passed before and after the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test363.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.
- Sidecar render investigation independently confirmed that the follower bundle left follower-only bits on a normal special-field wild object and recommended this normal-path probe.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 216: Remove Forced Mankey Canopy Tests And Restore Land Mankey

Idea:

Stop the canopy/tree occupancy probe entirely. The current goal is not to keep debugging Mankey on or near trees; it is to remove the forced Mankey headbutt/tree spawn path and make Mankey a normal land-spawn test Pokemon again.

Why this is new:

- Attempts 194-196 intentionally forced Mankey onto headbutt/tree-top test coordinates and disabled movement to isolate render behavior.
- This attempt reverses that test harness instead of trying another tree visibility fix.
- The remaining generic canopy-hopper behavior code is left disconnected from Mankey, so Mankey should not enter the near-tree/on-tree behavior path.

Implementation shape:

- Remove the forced canopy/headbutt spawn macros and forced refill branch.
- Remove the forced Route 29 canopy/headbutt position pickers and render-parameter helpers.
- Remove the forced visible/readable canopy-hop candidate helpers and forced-test debug bubble guards.
- Remove the Mankey behavior-class rule that mapped headbutt Mankey into `OW_WILD_BEHAVIOR_CLASS_CANOPY_HOPPER`.
- Keep the behavior test species override land-only: land spawns become `SPECIES_MANKEY`, while headbutt terrain goes back to normal encounter rolling.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyBehaviorTestSpecies`
- `OW_WILD_SPAWNER_FORCE_BEHAVIOR_TEST_SPECIES`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed.
- `rg` found no remaining forced canopy test macros or helper names in `overworld_wild_spawns_overlay.c`.
- `SPECIES_MANKEY` only remains in the land-only behavior test override.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test371.nds` into the Delta ROM folder.

Runtime result:

- Pending user test.

Learning:

- The forced canopy-top/headbutt Mankey probe had grown into a separate test harness. Removing it cleanly is safer than continuing to patch around tree visibility while the immediate test goal is plain land-spawn Mankey.

### Attempt 220: Mankey Tree-Top Render Height Lift

Idea:

Mankey is now correctly landing on the headbutt-tree top tile, but the normal map tile priority draws the tree over the Pokemon. Try a narrow Mankey-only render-height state when it is settled on a headbutt-tree top tile: keep the actual logical X/Y tile unchanged, but set the object's height fields to render level `1` so the object may draw above the tree canopy.

Why this is new:

- Attempts 194/195 tried the full follower-style render bundle (`MapObject_SetFlag29`, `sub_02069DC8`, follower bits) and caused blinking/invisibility.
- Attempt 196 deliberately removed that follower bundle and kept the normal special-field render path.
- Attempt 48 tried manual `posVec[1]` height bobbing for same-tile hop presentation and did not visibly lift spawned Pokemon.
- This attempt does not retry follower render flags or `posVec[1]` alone. It sets `hInit`, `hPrev`, and `hCurr` together with `posVec[1]`, only for settled Mankey on the verified headbutt-tree top tile.

Implementation shape:

- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_RENDER_HEIGHT 1`.
- Add `OverworldWildSpawns_SetObjectHeight`.
- Make generic `OverworldWildSpawns_SetObjectTile` reset height to `0` so this state cannot leak into later movement.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopRenderState`, which sets render height `1` only if the active slot is Mankey and `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` is true.
- Apply the render state after final canopy-hop landing and while Mankey is idling on a tree-top tile.
- Clear height in the canopy visual-state boundary path before future movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_RENDER_HEIGHT`
- `OverworldWildSpawns_SetObjectHeight`
- `OverworldWildSpawns_UpdateMankeyTreeTopRenderState`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build and after documenting the build result.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test375.nds`.

Runtime result:

- User reported Mankey appeared lower/inside the ground rather than higher.
- The effect also happened during every jump, not only after landing on a headbutt-tree top tile.

Learning:

- The `hInit`/`hPrev`/`hCurr` + `posVec[1]` lever is not a tree-priority override for spawned Pokemon.
- Positive object height in this context can visually sink the Pokemon and can leak into jump presentation through shared tile/landing normalization.
- Avoid retrying object-height based canopy priority unless there is new renderer evidence.
- The next direction should be an object-ID-gated draw/priority probe rather than follower render flags or object-height edits.

### Attempt 221: Mankey Tree-Top Priority Flag Probe

Idea:

Remove Attempt 220's height mutation entirely. Isolate the `0x180` map-object flag pair that was previously only tested as part of the unsafe follower render bundle. When a spawned Mankey is settled on a verified headbutt-tree top tile, save its current `flags & 0x180`, clear only those bits plus `BIT_VANISH`, and restore the saved bits when the canopy movement boundary or slot cleanup says it is no longer in that settled tree-top state.

Why this is new:

- Attempt 220 mutated object height fields and `posVec[1]`, which visually sank Mankey and affected jumps.
- Attempts 194/195 cleared `0x180`, but bundled that with `0x2400`, `MapObject_SetFlag29(TRUE)`, and `sub_02069DC8(TRUE)`, causing blinking/invisibility.
- Attempt 196 removed that whole follower-style bundle; it did not isolate `0x180`.
- This attempt does not use follower flags, does not touch object height, does not install a draw callback, and does not move the sprite or logical tile.

Implementation shape:

- Replace the failed render-height constant with `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS 0x00000180`.
- Add per-slot saved-bit storage: `sOverworldWildMankeyTreeTopPriorityBitsSaved` and `sOverworldWildMankeyTreeTopPrioritySavedBits`.
- Add `OverworldWildSpawns_SaveMankeyTreeTopPriorityBits` and `OverworldWildSpawns_RestoreMankeyTreeTopPriorityBits`.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`, which only runs the flag probe when the active slot is Mankey and `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` is true.
- Restore the saved bits in `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary` and clear saved state in `OverworldWildSpawns_ClearSlot`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS`
- `sOverworldWildMankeyTreeTopPriorityBitsSaved`
- `sOverworldWildMankeyTreeTopPrioritySavedBits`
- `OverworldWildSpawns_SaveMankeyTreeTopPriorityBits`
- `OverworldWildSpawns_RestoreMankeyTreeTopPriorityBits`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the final build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test377.nds`.
- Build warnings were limited to the existing unused helpers/diagnostic symbols on this movement branch plus the existing unused `bsys` battle parameter warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 222: Mankey Failed Tree-Path Backoff And Target Grid

Idea:

Investigate the user report that Mankey sometimes lags the game, possibly because it repeatedly tries and fails to path to a jump/tree target. The frame movement task intentionally ticks while the player is idle, so do not remove the frame task. Instead, make repeated failed Mankey tree-top searches cheaper and less frequent.

Why this is new:

- Attempts 217-221 focused on Mankey tree-top destination selection, hop presentation, and tree rendering/priority.
- No previous recorded attempt added a Mankey-only no-path backoff.
- No previous recorded attempt precomputed the local tree-top target set for the Mankey path search.
- This avoids changing the canopy movement behavior itself and only targets the suspected lag hotspot.

Implementation shape:

- Added per-slot Mankey path-failure state to remember the tile where a path failed.
- Repeated no-path failures from the same tile now back off from 60 to 120 to 180 to 240 frames.
- Moving to a different tile, finding a target, landing on a valid tree-top tile, context cleanup, slot reset, and respawn all clear the path-failure state.
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` now builds a local grid of valid headbutt-tree top targets while it is already scanning the headbutt-tree archive.
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep` now checks that target grid in O(1) instead of calling `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` inside the BFS inner loop.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_BASE_COOLDOWN_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_MAX_COOLDOWN_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_MAX_COUNT`
- `movementMankeyPathFailureX`
- `movementMankeyPathFailureY`
- `movementMankeyPathFailureCounts`
- `sOverworldWildMankeyHeadbuttTreeTopTargets`
- `OverworldWildSpawns_RecordMankeyPathFailure`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- Checked the log first; no prior attempt had tried this exact performance fix.
- A read-only subagent investigation independently identified repeated failed Mankey path searches as a plausible hotspot, especially archive scans inside the BFS inner loop.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c include/overworld_wild_spawns_internal.h documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test378.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- The lag hypothesis is plausible from code inspection: the frame task can retry Mankey tree-top pathing while Mankey remains active, and failed searches previously reused only the short chill cooldown.
- The path search no longer performs archive-backed tree-top checks in its inner loop.

### Attempt 223: Mankey Tree-Top Draw-Mode Probe

Idea:

The user reported Mankey is still visually hidden by the headbutt-tree canopy after landing on the intended tree-top tile. Do not repeat the failed render-height lift, follower render bundle, render offset, or isolated `0x180` flag-only probe. Instead, use a narrow draw-mode probe: when an active Mankey is settled on a verified tree-top tile, save its current `LocalMapObject::unkA0` draw mode, set draw mode `1`, and restore the saved mode when it leaves the tree-top state or the slot is cleaned up.

Why this is new:

- Attempt 220 changed object height fields and `posVec[1]`, making Mankey appear lower/inside the ground.
- Attempts 194/195 used the unsafe follower-style render bundle and caused blinking/invisibility.
- Attempt 221 only cleared the `0x180` map-object priority bits and did not solve the user's screenshot issue.
- This attempt targets draw mode (`unkA0`), which overlay 1's map-object draw path uses to choose between real draw callbacks, without replacing the draw callback or touching object height.

Implementation shape:

- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_MODE 1`.
- Add per-slot saved draw-mode state:
  - `sOverworldWildMankeyTreeTopDrawModesSaved`
  - `sOverworldWildMankeyTreeTopSavedDrawModes`
- Add save/restore helpers for tree-top draw mode.
- Extend the existing Mankey tree-top render override so it saves priority bits and draw mode, clears the old `0x180` bits and `BIT_VANISH`, then sets `object->unkA0 = 1`.
- Restore both draw mode and priority bits when Mankey leaves the tree-top tile, when canopy visual state is cleared, and before slot cleanup releases/deletes the object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_MODE`
- `sOverworldWildMankeyTreeTopDrawModesSaved`
- `sOverworldWildMankeyTreeTopSavedDrawModes`
- `OverworldWildSpawns_SaveMankeyTreeTopDrawMode`
- `OverworldWildSpawns_RestoreMankeyTreeTopDrawMode`
- `OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Verification:

- Checked the log first; draw mode `unkA0` override had not been tried.
- Two read-only explorer agents investigated renderer/headbutt behavior. Their findings supported avoiding height/follower flags and targeting the draw path/draw mode or a future object-ID-gated draw callback.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c include/overworld_wild_spawns_internal.h documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test379.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 232: Mankey Low Land Row Tree-Top Correction

Idea:

Fix the specific case where Mankey settles two tiles too low under the canopy/base edge. Do not touch the shared headbutt-tree top detector, because the previous broad row-lift work made already-working Mankey tree cases stop moving. Instead, normalize only Mankey's tree-top target rows through one Mankey-specific helper: if the candidate already has a headbutt/contact anchor two rows below it, leave it alone; otherwise, if the candidate row is passable, lift it two rows.

Why this is new:

- Earlier attempts changed shared headbutt-tree top detection or tried broad direct-row lifting.
- The user reported the broad/shared approach reintroduced old failures where Mankeys stopped moving.
- This attempt is Mankey-only and applies the same narrow target correction to all three Mankey consumers: settled check, direct target picker, and path target grid.
- This uses the headbutt metatile only as a two-rows-below anchor guard, not as the destination set, and does not alter spawn logic, hop execution, rendering, or generic canopy hopper behavior.

Implementation shape:

- Replace the broad direct row-lift constant with `OW_WILD_HEADBUTT_TREE_TOP_LOW_LAND_ROW_LIFT`.
- Add `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY`.
- In that helper, keep candidates whose `candidateY + 2` tile is `OW_WILD_TILE_HEADBUTT`.
- Otherwise, lift passable candidate rows by two tiles.
- Use that helper in:
  - `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
  - `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
  - `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- Remove the direct-picker loop that generated multiple lifted rows from one archive target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_LOW_LAND_ROW_LIFT`
- `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY`

Verification:

- Checked the attempt log before editing.
- A read-only explorer confirmed the safest choke point is `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY`, and recommended avoiding `TryGetHeadbuttTreeTops`, movement carrier code, render/proxy/layer hacks, and broad row offsets.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed after the code edit.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test430.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 238: Generic Headbutt Tree-Top Location Filter

Idea:

Make the settled headbutt tree-top location resolver reusable for future behavior profiles instead of keeping it named as Mankey-specific logic.

Why this is new:

- Earlier Mankey tree-top attempts focused on correcting the tile semantics and rendering. This pass does not change those semantics.
- The current goal is an internal API cleanup: future behaviors should be able to ask for valid headbutt tree-top locations without depending on Mankey names.

Implementation shape:

- Rename the footprint resolver to `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`.
- Rename the field/tile predicate to `OverworldWildSpawns_IsHeadbuttTreeTopLocation`.
- Rename the footprint-span constants from Mankey-specific names to `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_*`.
- Keep `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` as a thin wrapper for existing Mankey-specific call sites.
- Remove the older unused `OverworldWildSpawns_TryGetHeadbuttTreeTops` helper so there is one canonical generic tree-top location filter.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`
- `OverworldWildSpawns_IsHeadbuttTreeTopLocation`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_FOOTPRINT_HEIGHT_TILES`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_MAX_FOOTPRINT_Y_SPAN`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test437.nds`.
