# Aggressive Ram Onix Behavior

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Onix ram is its own behavior profile, not the normal aggressive chase profile.
- Normal walk commands are the safe carrier; site-walk and WaitJumpSite paths interfered with movement.
- Crash feedback should avoid script-driven locks; battle should trigger only on ram crash into player/follower or universal A interaction.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 1 | 1 | Patch Movement Slot `47` To A Custom Descriptor |
| 2 | 2 | Chase Logic Using `object->fsys` |
| 3 | 3 | Publish Active `FieldSystem *` Globally And Add Scratch Init |
| 4 | 4 | Replace `MIi_CpuClearFast` With Direct Scratch Clears |
| 5 | 5 | Diagnostic Idle Callback |
| 6 | 6 | Use Stock Step Descriptor Class `3` |
| 7 | 7 | Alias Movement `47` To Stock Movement `3` Descriptor |
| 8 | 8 | Make Stale Movement `47` No-Op And Spawn Fresh Objects With Stock Movement `3` |
| 9 | 9 | Disable Spawner Step Actions After Map-State Refresh |
| 10 | 10 | Disable The Entire Overworld-Wild Player-Step Hook |
| 11 | 11 | Load Overlay Entry But Do Not Call Overlay Step |
| 12 | 12 | Call Overlay Step But Return Immediately |
| 13 | 13 | Read-Only UpdateMapState Diagnostic |
| 14 | 14 | UpdateMapState Map Writes Without Clear |
| 15 | 15 | Read Spawn State Without Writing It |
| 16 | 16 | Call No-Op Movement Setter Without State Writes |
| 17 | 17 | Mark Movement Setter As LONG_CALL |
| 18 | 18 | Re-enable Map-State Writes After LONG_CALL Fix |
| 19 | 19 | Re-enable Stale-Slot Cleanup Only |
| 20 | 20 | Re-enable Distance Despawn Only |
| 21 | 21 | Re-enable Touch-Battle Detection Only |
| 22 | 22 | Re-enable Refill And Spawn Only |
| 23 | 23 | Restore Ambient Cry With Stock Movement |
| 24 | 24 | Spawner-Driven Movement Param Tick |
| 25 | 25 | Spawner-Driven Coordinate Read And Direction Calculation |
| 26 | 26 | Spawner-Driven Look Command |
| 27 | 27 | Spawner-Driven Blocked Direction Check |
| 28 | 28 | Spawner-Driven Walk Command |
| 29 | 29 | Spawner-Owned Movement Command Update And Clear |
| 30 | 30 | Obvious Spawner-Driven Tile Movement |
| 31 | 31 | Frame Task Movement Command Updates |
| 32 | 32 | Per-Slot Movement Ownership And Battle Reset |
| 33 | 33 | Range 8 And Idle Frame Chase |
| 34 | 34 | One-At-A-Time Overlap Untangle |
| 35 | 35 | Guard Idle Frame Context And Moving Battle Contact |
| 36 | 36 | Frame Task Battle Detection |
| 37 | 37 | Post-Movement Battle Settle Window |
| 38 | 38 | Pidgey Fast Movement Command |
| 39 | 39 | Movement Speed Levels 1-6 |
| 40 | 40 | Pidgey Speed 6 Test |
| 41 | 41 | Alias High Logical Speeds To Fastest Stock Walk |
| 42 | 42 | Proximity-Only Battle Settle |
| 43 | 43 | Cap High Speeds To Fluent Walk Command |
| 44 | 44 | Non-Blocking Battle Retry Between Chained Commands |
| 45 | 45 | Remove Redundant Speed 6 And Add Spot Emote |
| 47 | 47 | Use Jump-Site Movement Command For Spot Emote |
| 48 | 48 | Manual PosVec Height Bob For Spot Emote |
| 49 | 49 | Use WaitJumpSite Movement Command |
| 51 | 51 | LockDir JumpSite Smoke Release Sequence |
| 55 | 55 | Tired WaitJumpSite Then Stat-Fell Sound |
| 57 | 57 | Direct Follower Bubble Effect Creator |
| 59 | 59 | Tired Bubble Id Probe Cycle |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
| 65 | 181 | Tree-Anchor Visibility Baseline |
| 66 | 182 | Tree-Anchor Single Stock Jump Probe |
| 67 | 183 | Tree-Anchor Stock Jump2 Probe |
| 68 | 184 | Tree-Anchor Chained Jump2 Four-Tile Probe |
| 72 | 188 | Partner-Wrapped Chained Jump2 Four-Tile Probe |
| 74 | 190 | Partner-Prepped Single Internal Four-Tile Jump |
| 75 | 191 | Production Canopy Long-Jump Carrier |
| 90 | 225 | Mankey Tree-Top Effect-Owned Marker Canary |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 100 | 213 | Score Forced Verifier By Resolved Perch |
| 101 | 65 | A-Button Facing Interaction Starts Spawn Battle |
| 102 | 197 | Route 29 Top-Cap Coordinate Probe |
| 103 | 198 | Route 29 Upper Top-Cap Coordinate Probe |
| 104 | 199 | Actual Headbutt Anchor With Render-Only Tree-Top Offset |
| 105 | 200 | Exact Headbutt Tile Occupancy, No Graphic Offset |
| 112 | 226 | Mankey Tree-Top Post-Draw Sprite Priority Probe |
| 113 | 227 | Mankey Tree-Top Live Sprite Depth Zero Probe |
| 114 | 228 | Mankey Tree-Top Synced Visual Proxy |
| 115 | 229 | Mankey Tree-Top BG Layer Identification Probe |
| 116 | 236 | Mankey Tree-Top Effect-Layer Bubble Probe |
| 117 | 237 | Cache Mankey Tree-Top Archive Predicate |
| 120 | 240 | Strict Top-Row Mankey Target Set With Broad X Candidates |
| 121 | 241 | Pair-Derived Mankey Tree-Top X Footprints |
| 122 | 242 | Exposed Mankey Tree-Top Rows With Pair-Derived X |
| 123 | 243 | Full Mankey Tree-Top Vertical Band |
| 124 | 244 | Direct Cardinal Mankey Tree-Band Target |
| 125 | 245 | Coordinate-Latched Mankey Tree-Top Settlement |
| 126 | 246 | Prioritize Strict Structural Mankey Tree Tops |
| 127 | 247 | Strict-Only Mankey Tree-Top Final Targets |
| 129 | 249 | Target Two Tiles Above Headbutt Archive Row |
| 130 | 250 | Follower-Sprite Tree-Top Proxy Probe |
| 131 | 251 | Prefer Unblocked Direct Mankey Tree-Top Directions |
| 132 | 252 | Generic Field Effect Probe For Tree-Top Mankey |
| 133 | 253 | Down-First Mankey Tree-Top Target Selection |
| 137 | 257 | Re-enable Tree-Top Anchored Effect Probe After Movement Fix |
| 140 | 235 | Dedicated HEADBUTT_TREE_TOPS Archive Target Set |
| 141 | 233 | Split Mankey Tree Targets From Settled Perches |
| 142 | 230 | Mankey 2x6 Headbutt Tree Top-Row Targeting |
| 143 | 231 | Prefer Nearest Direct Mankey Tree-Top Jump |
| 144 | 232 | Include Exposed Archive Top Row For Mankey Tree Targets |
| 145 | 67 | Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram |
| 146 | 68 | Tune Onix Ram Start, Range, Crash State, And Feedback |
| 147 | 69 | Use Site Walk Commands And Scripted Crash Feedback For Onix Ram |
| 148 | 70 | Restore Normal Ram Movement And Make Alertness A Facing Line |
| 149 | 71 | Keep Normal Ram Walking But Borrow Site Visual Parameter |
| 150 | 72 | Direct Stock Ground-Dust Effect Without Step Sound |
| 151 | 73 | Run WaitJumpSite After Each Onix Ram Step |
| 152 | 74 | Direct Boulder Step Effect Helper During Normal Ram Movement |
| 153 | 75 | Fixed Run-Style Boulder Effect Id |
| 154 | 76 | Direct WaitJumpSite Smoke Launcher During Ram Movement |
| 155 | 77 | Try Adjacent Overlay Effect Constructor `ov01_02200040` |
| 156 | 78 | Try Map-Object Anchored Effect Helper `ov01_02200730` |
| 157 | 79 | Try Short-Lived Map-Object Effect Helper `ov01_021FF74C` |
| 158 | 80 | Try Alternate Stock Ground Effect Helper `ov01_021FD684` |
| 159 | 81 | Add WaitJumpSite Flag Context Around `ov01_022000DC` |
| 160 | 82 | Use HGSS Push Sound For Onix Ram Steps |
| 161 | 83 | Try Paired HGSS Push Sound `SEQ_SE_GS_PUSH03` |
| 162 | 84 | Load Push Sequence Before Playing It |
| 163 | 85 | Load Push Sound With `NNS_SND_ARC_LOAD_ALL` |
| 164 | 86 | Try Field Rock Sound `SEQ_SE_GS_IWAOTOSHI02` |
| 165 | 87 | Promote `aggressive_ram` Behavior And Strengthen Crash Feedback |
| 166 | 88 | Use Field Wall-Hit Sound And Shake The Crashed Overworld Object |
| 167 | 89 | Non-Locking Object Shake And `SEQ_SE_DP_GASHIN` Crash Thud |
| 168 | 90 | Non-Locking Object Shake And HGSS Gondola Wall-Hit Sound |
| 169 | 91 | Sound-Only `SEQ_SE_GS_IWA_TRAP` Crash Feedback |
| 170 | 92 | Sound-Only `SEQ_SE_GS_IWAOTOSHI01` Crash Feedback |
| 171 | 93 | Restore Decent Crash Sound And Shorten Speech-Only Alert |
| 172 | 94 | C-Side Ram Crash Object Wobble |
| 173 | 95 | Direct Camera Shake Work Driven By SysTask |
| 174 | 96 | Stronger Ram Crash Object Wobble And Shorter Speech Alert |
| 175 | 97 | Aggressive Ram Rest-Only Tired State |
| 176 | 98 | Restore Smaller Ram Crash Wobble Offset |
| 177 | 99 | Player Wall-Hit Ram Crash Sound |
| 178 | 100 | Ram Crash-Only Automatic Battle Trigger |
| 179 | 101 | Follower Object-ID Fallback For Ram Crash Battles |
| 180 | 102 | Fled Battle Sends Spawn To Tired State |
| 181 | 103 | Behavior-Gated Ledge Far Jump |
| 182 | 104 | Aggressive Ram Cardinal Alert Line |
| 183 | 105 | Rename Aggressive Chase Profile |
| 184 | 106 | Aipom-Only Playful Chase Pass |
| 185 | 107 | Playful Previous-Tile Hard Guard |
| 186 | 108 | Direction-History Playful Backtrack Guard |
| 188 | 110 | Playful Attentive Speed Rhythm |
| 189 | 111 | Revert Playful Attentive Speed Rhythm |
| 190 | 112 | Playful Targets Player And Follower |
| 191 | 113 | Close All-Direction Alert Radius |
| 204 | 126 | Shared Moving Player Target For Movement Intent |
| 205 | 127 | Double Playful Movement Range |
| 206 | 128 | Phantom Stalker Hidden Movement |
| 207 | 129 | Phantom Flicker And Follower Behind Targeting |
| 209 | 131 | Faster Phantom Destination Flicker And Battle Reveal |
| 210 | 132 | Deterministic Phantom Flicker Pulse |
| 211 | 133 | Refresh Phantom Sprite On Visible Flicker Phase |
| 213 | 135 | Phantom Teleport Alert Build-Up |
| 214 | 136 | Active Phantom 60 Percent Flicker Loop |
| 215 | 137 | Active Phantom Real-Object Flicker |
| 216 | 138 | Recreate Phantom Object After Teleport |
| 218 | 140 | Active Phantom Teleport-Step Movement |
| 219 | 141 | Front-Of-Player Phantom Teleport Movement |
| 220 | 142 | One-Second Pause After Active Phantom Teleport |
| 221 | 143 | One-Second Pause After Phantom Alert Arrival |
| 222 | 144 | Visible Teleport Pauses And Faster Alert Teleport |
| 224 | 146 | Recreate Real Phantom After Attentive Teleport |
| 225 | 147 | Limit Phantom Bump Battles To Visible Pause |
| 228 | 150 | Stable Phantom Battle Entry Gate |
| 229 | 151 | Materialize Visible Phantom Flicker For A-Button Battles |
| 230 | 152 | Disable Phantom Stalk Alert-State Teleport |
| 231 | 153 | Mankey Canopy Hopper Headbutt-Tree Profile |
| 236 | 158 | Canopy Hopper Pre-Hop Wait |
| 240 | 162 | Custom Rendered Far Canopy Hop |
| 241 | 163 | Canopy Helper Object Far-Hop Visual |
| 242 | 164 | Helper Object Stock-Jump Segments |
| 244 | 166 | Real Object Deferred Logical Commit Render-Hop |
| 247 | 169 | Recreate Real Canopy Object After Each Segment |
| 248 | 170 | Canopy Hopper Always-Visible Invariant |
| 249 | 171 | Boundary-Only Canopy Visual Cleanup |
| 251 | 173 | Keep Same Object Across Intermediate Canopy Landings |
| 252 | 174 | Settle Intermediate Canopy Segment Handoff |
| 253 | 175 | Recreate Final Tree Landing Without Manual Tile Rewrite |
| 254 | 176 | Use One Manual Render Hop For Full Canopy Distance |
| 255 | 177 | Canopy Hopper Vanilla Movement-List Task |
| 256 | 178 | Canopy Movement Lists Use Jump2 Runs And No Final Recreate |
| 257 | 179 | Direct Engine-Owned Long Canopy Jump |
| 258 | 180 | Clean Straight-Run Canopy Driver |
| 259 | 192 | Range-Gated Canopy Long-Jump Carrier |
| 260 | 193 | Exact Headbutt Perches And Pre-Stage Carrier Validation |
| 261 | 194 | Forced Mankey Tree-Tile Occupancy Render Probe |
| 262 | 195 | Forced Mankey Canopy-Top Occupancy Render Probe |
| 263 | 196 | Normal-Path Canopy-Top Occupancy Probe |
| 264 | 216 | Remove Forced Mankey Canopy Tests And Restore Land Mankey |
| 267 | 219 | Mankey Lands On Headbutt Tree Top Row |
| 269 | 221 | Mankey Tree-Top Priority Flag Probe |
| 270 | 222 | Mankey Failed Tree-Path Backoff And Target Grid |

## Original Attempt Sections

### Attempt 1: Patch Movement Slot `47` To A Custom Descriptor

Idea:

Use vanilla movement slot `47`, which appeared to be unused/null, and point it at `gOverworldWildCustomMovementDescriptor` in overlay 129.

Files/symbols:

- `armips/asm/overworld_wild_movement.s`
- `armips/global.s`
- `scripts/generate_armips_symbols.py`
- `src/overworld_wild_movement.c`
- `include/overworld_wild_movement.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Verification:

- Built ROM successfully.
- Verified ARM9 word at `0x020FD2B0` points at `gOverworldWildCustomMovementDescriptor`.
- Verified descriptor word `0` is `47`.
- Verified callback pointers have Thumb bits set.

Runtime result:

- Spawned Pokemon appeared and did not crash.
- Pokemon did not visibly move.

Learning:

- Basic slot patching and descriptor installation are probably viable.
- A custom descriptor can exist without immediately crashing.
- Movement failure was likely inside callback logic or context lookup, not the table patch alone.

Do not repeat:

- Do not re-investigate whether the slot can be patched unless `test100.nds` proves descriptor wiring is actually unstable.

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

### Attempt 5: Diagnostic Idle Callback

Idea:

Keep movement slot `47` and the descriptor installed, but make every custom callback no-op. This isolates descriptor/spawn wiring from movement logic.

Files/symbols:

- `src/overworld_wild_movement.c`
- `documentation/overworld_wild_movement_investigation.md`

Verification:

- Built as `test100.nds`.
- Verified descriptor callback pointers are valid Thumb pointers.
- Verified all custom callbacks compile to `bx lr`.

Runtime result:

- User reported the game still crashes when the save is loaded.

Learning:

- Because all callbacks compiled to `bx lr`, the crash is not caused by chase logic, movement-command helpers, coordinate reads, scratch clearing, or custom callback bodies.
- The remaining suspects are descriptor shape/metadata, descriptor storage/load timing, movement `47` object creation semantics, or the engine's handling of a previously null descriptor becoming non-null.

Next decision:

- Try a descriptor metadata-only change before reintroducing any helper logic.

### Attempt 6: Use Stock Step Descriptor Class `3`

Idea:

Keep movement slot `47` patched and keep every custom callback no-op, but change descriptor word `0` from `47` to stock class `3`, matching stock wander-like descriptors.

Why this is new:

- Earlier attempts tested slot `47`, active callbacks, scratch clearing, and no-op callbacks.
- None isolated only the descriptor metadata word while leaving callbacks no-op.

Files/symbols:

- `src/overworld_wild_movement.c`

Expected verification:

- Built ROM should still have ARM9 slot `47` pointing at `gOverworldWildCustomMovementDescriptor`.
- Descriptor word `0` should be `0x00000003`.
- Callback pointers should still be valid Thumb pointers.
- No-op callbacks should still compile to `bx lr`.

Verification:

- Built as `test101.nds`.
- ARM9 movement slot `47` at `0x020FD2B0` points at `0x023DF740`.
- Descriptor words are `0x00000003 0x023D97ED 0x023D97EF 0x023D97F1 0x023D97F3`.
- All callback pointers have Thumb bits set.
- All custom callbacks still compile to `bx lr`.

Runtime result:

- User reported the game still crashes.

Learning:

- Matching stock descriptor class `3` did not fix save-load crash.
- The descriptor's metadata word was not the only issue.
- Because the callbacks were still no-op, the strongest remaining suspect is the movement table entry pointing at overlay 129 rather than an ARM9-resident descriptor.

Do not repeat:

- Do not keep testing overlay 129 no-op/custom descriptors for slot `47` unless there is new evidence that overlay 129 is guaranteed loaded before the movement table is dereferenced.

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

### Attempt 16: Call No-Op Movement Setter Without State Writes

Idea:

Let `OverworldWildSpawns_UpdateMapState` call `OverworldWildCustomMovement_SetFieldSystem(fieldSystem)` while still returning before any `OverworldWildSpawnState` writes, before `OverworldWildSpawns_Clear`, and before downstream spawner work.

Why this is new:

- Attempt 14 bundled state writes with the movement setter call and crashed.
- Attempt 15 read `state->mapId` without writing state or calling the movement setter and did not crash.
- This attempt isolates whether the cross-call from overlay 149 to the currently no-op ARM9 movement setter is safe.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_movement.c` for verification that `OverworldWildCustomMovement_SetFieldSystem` still compiles to `bx lr`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` should be `1`.
- The active update path should call `OverworldWildCustomMovement_SetFieldSystem(fieldSystem)`.
- The active update path should not write `state`, should not call `OverworldWildSpawns_Clear`, and should not run downstream spawner work.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test111.nds`.
- Disassembly shows the active overlay step path calls `__OverworldWildCustomMovement_SetFieldSystem_from_thumb`, then returns `FALSE`.
- Disassembly of `OverworldWildCustomMovement_SetFieldSystem` is still `bx lr`.
- The active overlay path does not write `state`, does not call `OverworldWildSpawns_Clear`, and does not run downstream spawner work.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported a crash.

Learning:

- The direct overlay-to-ARM9 setter call is unsafe as currently generated.
- This is probably not movement logic: `OverworldWildCustomMovement_SetFieldSystem` still compiles to `bx lr`.
- The likely bug is call generation/interworking: overlay 149's veneer switches to ARM state and branches to the Thumb function address without preserving the Thumb bit.

Do not repeat:

- Do not call `OverworldWildCustomMovement_SetFieldSystem` from overlay code through a plain, non-`LONG_CALL` declaration.

### Attempt 17: Mark Movement Setter As LONG_CALL

Idea:

Change `OverworldWildCustomMovement_SetFieldSystem` to a proper `LONG_CALL` declaration/definition, matching the repo's normal cross-region function declarations, while keeping the same setter-only diagnostic active.

Why this is new:

- Attempt 16 proved the plain generated veneer crashes.
- No previous attempt changed the setter's calling convention or verified the generated interworking veneer.

Files/symbols:

- `include/overworld_wild_movement.h`
- `src/overworld_wild_movement.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OverworldWildCustomMovement_SetFieldSystem` should be declared and defined with `LONG_CALL`.
- The active overlay step path should still only call the setter and return `FALSE`.
- Disassembly should no longer show a veneer that switches to ARM state and branches to `0x023D97F4` without the Thumb bit.
- The setter itself should still compile to `bx lr`.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test112.nds`.
- `OverworldWildCustomMovement_SetFieldSystem` is declared and defined with `LONG_CALL`.
- Disassembly shows the active overlay step path loads `0x023D97F5` and jumps via `bx r3`, so the Thumb bit is preserved.
- Disassembly of `OverworldWildCustomMovement_SetFieldSystem` is still `bx lr`.
- The active overlay path still only calls the setter and returns `FALSE`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence supports the interworking hypothesis from Attempt 16.
- Runtime result confirms the corrected setter-only path is stable.
- The next retest can bring back map-state writes because the prior state-write crash included the broken setter call.

Expand:

- Re-enable map-state writes with `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` disabled, while keeping `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` enabled.

### Attempt 18: Re-enable Map-State Writes After LONG_CALL Fix

Idea:

Let `OverworldWildSpawns_UpdateMapState` perform its normal `state->mapId`, `state->mapObjectMan`, and `state->mapObjects` writes using the corrected `LONG_CALL` setter path, but keep the overlay step diagnostic returning before spawn/despawn/battle work.

Why this is new:

- Attempt 14/`test109.nds` wrote state and crashed, but that build still included the broken plain setter call.
- Attempt 17/`test112.nds` proved the corrected setter-only call is stable.
- No previous build has tested state writes with the corrected Thumb-safe setter call.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` should remain `1`.
- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` should remain `1`.
- The active overlay step path should call `OverworldWildSpawns_UpdateMapState`, then return `FALSE` before stale-slot dropping, despawn checks, touch battle, ambient cry, or refill/spawn.
- The active update path should write map-state fields when map context changes, call `OverworldWildCustomMovement_SetFieldSystem` through the Thumb-safe long-call path, and avoid `OverworldWildSpawns_Clear`.

Verification:

- Built as `test113.nds`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` is `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` remains `1`.
- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` remains `1`.
- Disassembly shows the active overlay step path writes `state->mapId`, `state->mapObjectMan`, and `state->mapObjects` when the map context changes.
- Disassembly shows the setter call still uses the Thumb-safe `0x023D97F5` target via `bx r3`.
- Disassembly shows the active overlay step returns `FALSE` before stale-slot dropping, distance despawn, touch battle, ambient cry, or refill/spawn.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended state-write-only probe.
- Runtime result confirms map-state writes are stable with the corrected setter path.

Expand:

- Re-enable `OverworldWildSpawns_DropStaleSlots` only, while returning before distance despawn, touch battle, ambient cry, and refill/spawn.

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

### Attempt 26: Spawner-Driven Look Command

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Extend the spawner-step movement diagnostic so that, when the cooldown resets and the preferred direction is valid, it issues a non-walking look command toward the chase/flee direction.

Why this is new:

- Attempt 25/`test120.nds` only tested coordinate reads and direction calculation and did not crash.
- Earlier command-helper attempts ran through slot-47 callbacks and bundled command setup with walking, blocked-direction checks, command update/clear, scratch writes, `object->fsys`, or global movement `FieldSystem *`.
- No previous build has isolated a non-walking `MapObject_MovementCommandFromDirection` plus `MapObject_StartMovementCommand` plus `MapObject_SetSingleMovementActive` path from the stable overlay-149 spawner step loop while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` should be `1`.
- The active probe should call `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive` only after a cooldown reset and a valid direction.
- The active probe should still avoid walking commands, `MapObject_IsMovementDirectionBlocked`, `MapObject_UpdateMovementCommand`, `MapObject_ClearSingleMovementActive`, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test121.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` is `1`.
- Source verification shows the active probe only issues the look command after cooldown reset and a non-`NONE` preferred direction.
- Source verification shows the active probe calls `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive`.
- Disassembly target scan shows `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Disassembly target scan did not find `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_UpdateMovementCommand` at `0x02062429`, or `MapObject_ClearSingleMovementActive` at `0x0205F63D` in the overlay object.
- Source verification shows the active probe still avoids walking commands, blocked-direction checks, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test121.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.
- Visual confirmation was not practical because stock wander masks occasional facing changes.

Learning:

- Spawner-driven `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive` are runtime-stable for a non-walking look command.
- Because stock wander remains active, this proves command setup safety but not visible behavior.

Expand:

- Add a spawner-driven `MapObject_IsMovementDirectionBlocked` check on the same cooldown tick.
- Still avoid walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

### Attempt 27: Spawner-Driven Blocked Direction Check

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Before issuing the already-stable spawner-driven look command, call `MapObject_IsMovementDirectionBlocked` for the preferred chase/flee direction and store the result in volatile diagnostics. Do not use the blocked result to walk yet.

Why this is new:

- Attempt 26/`test121.nds` tested non-walking command setup and did not crash.
- Earlier movement attempts bundled blocked-direction checks with slot-47 callbacks, walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, or global movement `FieldSystem *`.
- No previous build has isolated `MapObject_IsMovementDirectionBlocked` from the stable overlay-149 spawner step loop while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK` should be `1`.
- The active probe should call `MapObject_IsMovementDirectionBlocked` only after a cooldown reset and a valid preferred direction.
- The active probe should still avoid walking commands, `MapObject_UpdateMovementCommand`, `MapObject_ClearSingleMovementActive`, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test122.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK` is `1`.
- Source verification shows the active probe calls `MapObject_IsMovementDirectionBlocked` only after cooldown reset and a non-`NONE` preferred direction.
- Disassembly target scan shows `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`.
- Disassembly target scan still shows the previously safe look-command setup targets: `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Disassembly target scan did not find `MapObject_UpdateMovementCommand` at `0x02062429` or `MapObject_ClearSingleMovementActive` at `0x0205F63D` in the overlay object.
- Source verification shows the active probe still avoids walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test122.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- Spawner-driven `MapObject_IsMovementDirectionBlocked` is runtime-stable for active spawned Pokemon when called after cooldown reset and a valid preferred direction.
- This clears the blocked-direction helper for a real walk-command probe.

Expand:

- Change the command base from non-walking look `0x00` to walking `0x08`.
- Gate the walk command on `!MapObject_IsMovementDirectionBlocked`.
- Still avoid movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

### Attempt 28: Spawner-Driven Walk Command

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. On cooldown reset, compute the preferred chase/flee direction, check that it is not blocked, and start a walk command using `MapObject_MovementCommandFromDirection(direction, 0x08)`, followed by `MapObject_StartMovementCommand` and `MapObject_SetSingleMovementActive`.

Why this is new:

- Attempt 26/`test121.nds` proved non-walking command setup does not crash.
- Attempt 27/`test122.nds` proved the blocked-direction helper does not crash.
- Earlier walk attempts bundled walking with slot-47 callbacks, movement-command update/clear calls, scratch writes, `object->fsys`, or global movement `FieldSystem *`.
- No previous build has isolated a gated walk command from the stable overlay-149 spawner step loop while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND` should be `1`.
- The active probe should call `MapObject_IsMovementDirectionBlocked`, then only start a walk command when the direction is not blocked and no single movement is already active.
- The active probe should use `OW_WILD_SPAWNER_MOVEMENT_WALK_UP_COMMAND` (`0x08`) as the command base.
- The active probe should still avoid `MapObject_UpdateMovementCommand`, `MapObject_ClearSingleMovementActive`, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- User reported no crash.

Learning:

- Starting a real walk command from the stable overlay-149 spawner step loop is runtime-stable when gated by `MapObject_IsMovementDirectionBlocked`.
- This does not prove the movement is visually controlled yet, because fresh spawns still use stock movement `3`, which has its own command state machine.

Verification:

- Built as `test123.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK`, `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ`, `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND`, `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK`, and `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND` are all enabled.
- Source verification shows the active probe starts a walk command only after cooldown reset, valid preferred direction, `!MapObject_IsMovementDirectionBlocked`, and `!MapObject_IsSingleMovementActive`.
- Source verification shows the command base is `OW_WILD_SPAWNER_MOVEMENT_WALK_UP_COMMAND` (`0x08`).
- Disassembly target scan shows `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Disassembly target scan did not find `MapObject_UpdateMovementCommand` at `0x02062429` or `MapObject_ClearSingleMovementActive` at `0x0205F63D` in the active overlay object.
- Source still avoids scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawns still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Copied to Delta as `test123.nds`.
- `git diff --check` passed.

Expand:

- Add spawner-owned command update/clear polling after a spawner-started command.
- Keep fresh spawns on stock movement `3` for this probe.
- Still avoid scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

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

### Attempt 38: Pidgey Fast Movement Command

Idea:

Keep the existing global movement decision cooldown at `0`, and make Pidgey faster by changing only its movement command family from normal stock walk `0x08` to stock fast walk `0x0C`. Sentret and every other species stay on the current `0x08` baseline.

Why this is new:

- Earlier attempts changed global movement cadence and command ownership, but did not select movement command speed per species.
- A partial cooldown-only idea would have made Sentret slower rather than Pidgey faster; that was rejected before building and is not the active solution.
- Local ARM9 disassembly shows the `0x08` direction family uses a 16-frame movement setup, while the `0x0C` direction family uses an 8-frame movement setup, so this tests a stock faster movement command instead of direct coordinate writes or burst-poll teleporting.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test135.nds` and copied to Delta.
- `git diff --check` passed.
- Verified source uses `OW_WILD_SPAWNER_MOVEMENT_FAST_WALK_UP_COMMAND 0x0C` only when `spawn->species == SPECIES_PIDGEY`.
- Verified Sentret has no species-specific slowdown path and remains on the default `OW_WILD_SPAWNER_MOVEMENT_WALK_UP_COMMAND 0x08`.
- Verified local ARM9 command table entries for `0x08` and `0x0C` are valid stock movement command families.

Runtime result:

- User clarified that Pidgey should become faster, not that Sentret should become slower.
- This led into generalizing movement speed levels instead of using a one-off species-only fast path.

Learning:

- Per-species speed should use faster stock movement command families rather than slowing baseline Pokemon down.
- The speed concept should become a behavior/profile parameter, which is expanded in the next attempt.

### Attempt 39: Movement Speed Levels 1-6

Idea:

Replace the one-off Pidgey fast-walk special case with an explicit overworld-wild movement speed scale. Sentret stays at speed `1`, Pidgey stays at speed `2`, and speeds `3`, `4`, `5`, and `6` are available for future species tuning by mapping them to stock movement command families.

Why this is new:

- Attempt 38 proved only a hardcoded Pidgey `0x0C` command path against the default `0x08` command path.
- No previous attempt exposed a reusable per-species speed parameter or reserved speed levels above `2`.
- This still uses stock movement command families rather than the previously crash-prone custom movement descriptor path, burst updates, or direct coordinate changes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test136.nds` and copied to Delta.
- `git diff --check` passed.
- Verified Sentret maps to speed `1`, Pidgey maps to speed `2`, and every other species defaults to speed `1`.
- Verified speed levels `3`, `4`, `5`, and `6` are selectable through the same speed-to-command helper for future species tuning.
- Local ARM9 movement command table already shows valid stock direction families for speed levels `1` through `6`: `0x08`, `0x0C`, `0x10`, `0x14`, `0x18`, and `0x1C`.

Runtime result:

- User reported this did nothing visible and also clarified this was not the desired effect.
- The requested effect is an actual screen shake, not wobbling the crashed object or adding another non-screen visual.

Learning:

- Manual X/Z `posVec` wobble is not a useful substitute for screen shake.
- Remove this code and do not retry object-wobble crash feedback unless the requested effect changes.
- The next attempt should trace or call the underlying camera/screen shake routine directly instead of scheduling field scripts or offsetting the object.

### Attempt 40: Pidgey Speed 6 Test

Idea:

Keep the new speed-level abstraction from Attempt 39, but set only Pidgey to speed `6` while Sentret remains speed `1`. This creates an obvious runtime test for the highest currently exposed speed level.

Why this is new:

- Attempt 39 added speed levels `1` through `6`, but only built Pidgey at speed `2`.
- No previous built ROM has tested Pidgey using speed `6` / stock command family `0x1C`.
- This still changes only the per-species speed parameter, not movement timing, battle detection, custom descriptors, or coordinate writes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test137.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OW_WILD_SPAWNER_PIDGEY_MOVEMENT_SPEED` is `6`, while `OW_WILD_SPAWNER_SENTRET_MOVEMENT_SPEED` remains `1`.
- Verified speed `6` maps through `OverworldWildSpawns_GetMovementWalkCommandForSpeed` to stock command family `0x1C`.

Runtime result:

- User reported Pidgey does not move and just stands still.

Learning:

- Stock command family `0x1C` is not usable as a spawner-owned walk command in this context, even though it exists in the local movement command table.
- The earlier verification was too broad: table presence does not prove a command family uses the same walk update path as `0x08`, `0x0C`, `0x10`, or `0x14`.

### Attempt 41: Alias High Logical Speeds To Fastest Stock Walk

Idea:

Keep Pidgey at logical speed `6`, but map speed levels `5` and `6` to the fastest stock walk command family `0x14` instead of the non-walking `0x18` / `0x1C` command families.

Why this is new:

- Attempt 40 directly tested speed `6` mapped to `0x1C`, and runtime showed Pidgey standing still.
- No previous attempt has kept the speed `1` through `6` parameter scale while aliasing unsupported high speed levels back to the fastest confirmed stock walk command.
- This avoids returning to burst-polling, custom movement descriptors, coordinate writes, or global timing changes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test138.nds` and copied to Delta.
- `git diff --check` passed.
- Verified Pidgey remains logical speed `6`.
- Verified speed `5` and speed `6` now map to `OW_WILD_SPAWNER_MOVEMENT_SPEED_4_COMMAND` / stock command family `0x14`.
- Local disassembly shows `0x08`, `0x0C`, `0x10`, and `0x14` share the stock walk update path, while `0x18` and `0x1C` switch to a different update path.

Runtime result:

- User reported movement looks jittery: one step, pause, one step, pause.

Learning:

- The high-speed command path still felt stop-start with speed `6` mapped to `0x14`.
- The first guess that this was caused by the global battle-settle pause was later corrected by the user and should not be treated as proven.

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

### Attempt 44: Non-Blocking Battle Retry Between Chained Commands

Idea:

Keep the post-movement battle retry check from Attempt 37, but stop using the retry counter as a movement hold. When a spawner-owned movement command finishes, perform a contact retry if no movement is currently active. If that retry does not start a battle, immediately continue into untangle/chase command selection so the next tile command can be queued without a visible "thinking" pause.

Why this is new:

- Attempt 37 explicitly blocked new movement while `movementBattleSettleFrames` was active.
- Attempt 42 only tried gating that same blocking settle window by proximity, and the user corrected that this did not address the real jitter.
- No previous attempt has made the battle retry non-blocking while still retaining the retry path before the next command can be issued.
- This targets the all-speeds stop-and-think behavior instead of changing walk command families or per-species speed values.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test141.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified `OverworldWildSpawns_TryBattleSettleRetry` only returns `TRUE` when `OverworldWildSpawns_TryStartBattle(state, fieldSystem, FALSE)` actually schedules a battle.
- Verified a failed retry now decrements `movementBattleSettleFrames` and returns `FALSE`, allowing `OverworldWildSpawns_TickMovementParams` to continue into untangle/chase command selection.
- Verified the frame task still sets `movementBattleSettleFrames` after a completed spawner-owned movement command, so the contact retry path still runs before the next command can be issued.

Runtime result:

- User reported it works, and the current fastest movement is plenty fast for testing.

Learning:

- The non-blocking retry fixed the visible stop-and-think pause between tile commands enough to keep building on this path.
- Current safe speed command families are still limited: speed `1` maps to `0x08`, speed `2` maps to `0x0C`, and speed `3` maps to `0x10`. Logical speeds above that were aliases rather than new motion speeds.

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

### Attempt 181: Tree-Anchor Visibility Baseline

Idea:

Pause canopy hopping entirely and put canopy Mankey back on the actual headbutt-tree coordinate used by ordinary headbutt spawns. Other headbutt spawns are visible on that coordinate, while the canopy path had been relocating Mankey to an adjacent perch and then running custom hop ownership. This test isolates whether the invisibility is caused by the perch/custom movement path rather than by the headbutt tree coordinate itself.

Implementation shape:

- Add a tree-anchor baseline switch for canopy hoppers.
- When spawning a canopy hopper from the headbutt pool, keep `position.startX/startY` as the tree coordinate instead of replacing it with `position.headbuttPerchX/Y`.
- Make `OverworldWildSpawns_TryStartHeadbuttTreeHop` return without starting movement while the baseline switch is active.
- Clear `BIT_VANISH` and set a normal cooldown so an idle Mankey remains visible and the frame task has no active canopy jump/list/internal movement to clean up on route transitions.
- Add a detach-only route context-loss reset that zeros custom movement bookkeeping and static canopy task pointers without calling `MapObject_*`, deleting helpers, or asking stale movement-list tasks to clean up.

Why this is new:

- Attempt 170 tried an always-visible invariant while movement was still active; this disables canopy movement instead.
- Attempts 177-180 all still attempted movement via movement lists or the internal jump starter; this does not.
- Earlier tree/perch attempts changed final landing refresh behavior; this tests stock-style initial tree anchoring before any canopy movement begins.
- This follows the user's observation that other Pokemon spawned on headbutt trees do not become fully invisible.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_VISIBILITY_BASELINE`
- `OverworldWildSpawns_DetachAllMovementStateOnContextLoss`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`
- `OverworldWildSpawns_SpawnOne`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test348.nds` and copied to Delta.
- Verified the active baseline switch keeps canopy Mankey at the original headbutt-tree spawn coordinate instead of relocating it to the perch coordinate.
- Verified `OverworldWildSpawns_TryStartHeadbuttTreeHop` exits before starting canopy movement while the baseline switch is active, clearing `BIT_VANISH` and setting a normal cooldown only.
- Verified route context-loss now uses `OverworldWildSpawns_DetachAllMovementStateOnContextLoss`, which zeros custom bookkeeping and static canopy task pointers without calling `MapObject_*`, deleting helpers, or cleaning up stale movement-list tasks.
- The edited overlay compiled; unused-helper warnings are expected in this baseline because the active canopy movement paths are intentionally disconnected.

Runtime result:

- User reported:
  - Mankey is visible while idle on/at headbutt trees.
  - Leaving the route does not freeze or crash.
  - Hop distance/movement feel was not tested because hopping is intentionally disabled in this baseline.

Learning:

- The headbutt-tree anchor itself is not what makes canopy Mankey invisible.
- The route-transition crash/freeze is tied to active canopy movement cleanup/state ownership, not to an idle Mankey on a tree.
- The next movement attempt should start from this stable tree-anchor baseline and add one movement owner back at a time.

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

### Attempt 184: Tree-Anchor Chained Jump2 Four-Tile Probe

Idea:

Attempt 183 proved plain stock `Jump*2` is a visible and route-safe two-tile carrier from the stable tree-anchor baseline. Before adding the partner/follower wrapper as another variable, test the user's possible 4-tile hop cap by chaining two plain real-object `Jump*2` commands toward one staged four-tile target.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE`.
- Keep canopy Mankey on the original headbutt-tree spawn coordinate by keeping the older perch relocation disabled while any tree-anchor probe is active.
- Reuse `OverworldWildSpawns_TryPickStraightCanopyStepTarget`, now validating intermediate two-tile landing points before accepting a four-tile target.
- Stage a normal pending canopy target four tiles away in one cardinal direction.
- While the chained probe is active, `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` starts a direction-specific stock `Jump*2` for each two-tile segment until the staged target is reached.
- Keep using the real object and the existing frame-updated single-command path.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 178 used movement lists with jump runs from the older canopy path.
- Attempt 179 and 180 used direct internal long-jump ownership or older far-hop state.
- Attempt 183 proved one plain tree-anchor `Jump*2` is safe; this is the first test of chaining two such confirmed-safe segments from the same stable baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE`
- `OverworldWildSpawns_TryPickStraightCanopyStepTarget`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test351.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE` is enabled while the baseline, one-step, and single `Jump*2` probe flags are disabled.
- Verified the four-tile target is only accepted after validating the final tile and the intermediate two-tile landing point.
- Verified the pending-hop executor uses stock direction-specific `Jump*2` segments until the staged target is reached.
- Verified this attempt does not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test351.nds`.
- Mankey stays visible until the first stock `Jump*2` segment completes.
- After the first two tiles of the four-tile hop, Mankey loses visibility and never regains it.
- The hop does cover four tiles.
- Leaving the route still avoids crash/freeze.

Learning:

- Chaining stock `Jump*2` commands proves the route-safe engine-owned path can cover a four-tile target.
- The failure is not target distance or route-leave cleanup.
- The failure appears at the segment handoff after the first two-tile stock jump completes, before or during the second stock segment.
- Next probes should focus on the midpoint finish/normalization/handoff state, not on tree-anchor spawn visibility or target selection.

### Attempt 188: Partner-Wrapped Chained Jump2 Four-Tile Probe

Idea:

Attempt 187 proved the partner/follower wrapper restores vertical height and visibility for a moving two-tile `Jump*2`. Earlier four-tile attempts failed at the manual midpoint handoff. Test whether two full wrapped `Jump*2` segments inside one engine-owned movement list can travel four tiles while preserving the wrapper's visual contract, with no manual midpoint normalization.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE`.
- Keep the stable tree-anchor setup.
- Pick a straight four-tile canopy target with `OverworldWildSpawns_TryPickStraightCanopyStepTarget`, including intermediate two-tile landing validation.
- Stage that four-tile target as the pending canopy target.
- Parameterize `OverworldWildSpawns_StartWrappedCanopyJump2Probe` with a segment count.
- Emit two full wrapped movement segments in one movement list: `0x49 -> Jump*2 -> Freeze -> 0x4A -> 0x49 -> Jump*2 -> Freeze -> 0x4A -> MovementEnd`.
- Do not use helper objects, object recreate/refresh, phantom cleanup, raw `posVec` interpolation, manual midpoint tile/vector normalization, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 184 chained plain `Jump*2` segments but needed a manual midpoint commit and lost visibility.
- Attempts 185-186 changed the midpoint commit, but lost full travel and/or vertical height.
- Attempt 187 used the partner wrapper but only for one two-tile segment.
- No previous attempt has chained two partner-wrapped moving `Jump*2` segments inside one engine-owned movement list from the stable tree-anchor baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE`
- `OverworldWildSpawns_StartWrappedCanopyJump2Probe`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test355.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE` is enabled while the single wrapped probe is disabled.
- Verified `OverworldWildSpawns_StartWrappedCanopyJump2Probe` accepts a segment count and emits two full wrapped `Jump*2` sequences when the chained probe is active.
- Verified the chained wrapped probe stages a four-tile pending target and uses the existing canopy movement-task finish path.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test355.nds`.
- Mankey jumps two tiles twice in sequence.
- It does not feel like a single full four-tile jump.

Learning:

- Two complete partner-wrapped movement segments preserve travel and visual presentation, but they also make the hop read as two distinct jumps.
- The break is now caused by the repeated wrapper/freeze/restore sequence, not by manual midpoint tile/vector normalization.
- Next probe should keep one partner wrapper open around both `Jump*2` commands to test whether removing the mid-sequence restore/prep/freeze makes the action feel continuous.

### Attempt 190: Partner-Prepped Single Internal Four-Tile Jump

Idea:

Attempt 189 confirmed two stock `Jump*2` commands always read as two arcs, even inside one partner wrapper. Try one actual engine jump state instead: run the same partner prep that made wrapped jumps visible, start one direct internal jump with the stock `Jump*2` parameters scaled to a four-tile duration, then run the partner restore on landing.

Implementation shape:

- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE`.
- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE`.
- Keep the stable tree-anchor setup and straight four-tile target from Attempts 188-189.
- Before the jump, run `0x49` as an immediate real-object movement command so the object receives the same presentation prep used by follower-style hops.
- Do not emit any stock `Jump*2` commands.
- Start one direct internal jump on the real object via `MapObject_StartMovementCommandInternal` plus `MapObject_StartJumpMovementInternal`.
- Use the stock jump scale from disassembly, stretched to four tiles: `deltaFx32 = 0x2000`, `frameCount = 32`, `jumpType = 3`, `arcTableId = 0`, `arcStep = 0x80`.
- When the internal jump finishes, run `Freeze -> 0x4A` as immediate real-object movement commands before normal canopy finish.
- Do not use helper objects, object recreate/refresh, phantom cleanup, raw `posVec` interpolation, movement-list tasks, manual midpoint normalization, or repeated `Jump*2` commands.

Why this is new:

- Attempts 179-180 used direct internal long jumps before the partner prep/restore visibility contract was discovered.
- Attempts 187-189 used partner prep/restore with stock `Jump*2`, but never with one direct internal four-tile jump state.
- No previous attempt has combined the successful tree-anchor baseline, partner prep/restore, and one scaled direct internal jump call.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE`
- `OverworldWildSpawns_RunImmediateCanopyMovementCommand`
- `OverworldWildSpawns_StartPartnerPreppedCanopyInternalJumpProbe`
- `MapObject_StartJumpMovementInternal`

Verification:

- `git diff --check` passed before build.
- First build failed because `OverworldWildSpawns_TryPickStraightCanopyStepTarget` was still guarded only by the older stock-jump probes; this confirmed the new probe was not yet enabling the shared straight-target helper.
- Added `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE` to the straight-target helper guard and the forced headbutt-perch suppression guard.
- Rebuilt successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test357.nds` into the Delta ROM folder.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE` is active while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE` is disabled.
- Overlay compiled with the expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test357.nds` and reported: "it works!!!!!!"
- The partner-prepped single internal jump gives the desired full long-hop feel instead of two chained two-tile arcs.

Learning:

- The working carrier is one direct internal jump state, not repeated stock `Jump*2` commands.
- The tested four-tile values are `frameCount = distance * 8` and `arcStep = 0x1000 / frameCount`, which gives `32` frames and `0x80` arc step at four tiles.
- The partner prep/restore commands are required for stable presentation; the old unwrapped direct internal path should not be used for canopy long jumps.
- Production work should remove the probe gate and expose this as a distance-scaled helper for any cardinal jump within the frame budget.

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

### Attempt 240: Strict Top-Row Mankey Target Set With Broad X Candidates

Idea:

The user reported that Mankey is still not getting to a tree-top tile on `test397.nds`. Do not repeat the rejected `OW_WILD_TILE_HEADBUTT` shortcut from Attempt 234. Do not simply repeat Attempt 230 either: Attempt 230 used the strict 2x6 structural top row but still used a narrow primary X footprint. Attempt 235 fixed the X ambiguity by deriving possible 2-tile top-left candidates from every archive coord, but it also kept the exposed/archive `minY` row as an active target. This attempt keeps Attempt 235's broader X candidates while removing the exposed row from active Mankey top targeting and settling.

Why this is new:

- Attempt 230 targeted only the structural row, but did not have the later broad `coordX` / `coordX - 1` top-left candidate set.
- Attempt 235 introduced broad X candidates, but still allowed the extra exposed/archive row.
- Attempt 239 aligned settling with the broad target set, but that can still let tree-body/exposed rows count as good enough.
- This attempt defines active `HEADBUTT_TREE_TOPS` as the strict structural top row of the 2x6 tree footprint, with the broad X ambiguity retained.

Implementation shape:

- Keep `OverworldWildSpawns_TryGetHeadbuttTreeTops` and its broad top-left candidate generation.
- Change all active Mankey uses of that helper to pass `includeExposedRows = FALSE`:
  - current-tile settled predicate
  - direct top target picker
  - BFS target grid marker
- Leave `OW_WILD_TILE_HEADBUTT` unused for this targeting path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test398.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported that Mankey did not move on `test398.nds`.
- The screenshot showed an exclamation bubble over a Mankey on/near the path, which suggests the strict-row predicate can still falsely classify ground/path tiles as already valid tree-top tiles.
- The remaining suspect is the broad X candidate set from Attempt 235: treating every archive coord as both possible left and right side can make one tree entry cover too many neighboring X tiles.

### Attempt 241: Pair-Derived Mankey Tree-Top X Footprints

Idea:

Fix the `test398.nds` no-movement regression without using the rejected `OW_WILD_TILE_HEADBUTT` shortcut. Attempt 240 made the row strict, but the screenshot still showed a bubble on a non-tree-top Mankey, so the X footprint is likely too broad. Replace the broad "every coordX and coordX - 1" candidate set with pair-derived 2-wide footprints: if a headbutt tree archive entry contains adjacent X columns, use that adjacent pair as the tree's left edge. Only fall back to `minX` and `minX - 1` when the archive entry has no adjacent X pair.

Why this is new:

- Attempt 230 used only `minX`, which was too narrow for some trees.
- Attempt 235 added every `coordX` and `coordX - 1`, which can over-expand a tree into nearby path/ground tiles.
- Attempt 240 kept that broad X set while making rows strict, which produced no movement because Mankey could already be falsely considered settled.
- This attempt uses archive geometry to find actual 2-wide X pairs instead of either one narrow edge or every possible edge.

Implementation shape:

- Keep the dedicated `HEADBUTT_TREE_TOPS` system and strict top-row targeting from Attempt 240.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, collect distinct X columns from the tree entry.
- Add top-left candidates only from adjacent X pairs when present.
- Use `minX` and `minX - 1` only as a sparse-entry fallback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test399.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported that the highlighted visible canopy-top row is not treated as tree-top on `test399.nds`.
- Pair-derived X footprints appear to have fixed one axis of the false-positive problem, but the strict structural Y row is too narrow for the visible top-cap tiles.
- The next attempt should keep pair-derived X but re-enable exposed rows; this is not the same as Attempt 235/239 because those still used broad X candidates.

### Attempt 242: Exposed Mankey Tree-Top Rows With Pair-Derived X

Idea:

The user reported that the highlighted visible canopy-top row is not treated as a tree-top tile on `test399.nds`. Do not go back to the rejected `OW_WILD_TILE_HEADBUTT` path. Also do not repeat Attempt 235/239 exactly: those included exposed rows but used the over-broad "every coordX and coordX - 1" X set. Keep Attempt 241's safer pair-derived X footprint, then re-enable exposed rows for current-tile settling, direct target picking, and BFS target marking.

Why this is new:

- Attempt 235 used exposed rows with broad X candidates and could over-expand into nearby non-tree tiles.
- Attempt 239 aligned settling with the broad exposed target set and still inherited that X problem.
- Attempt 241 narrowed X footprints but kept rows strict, causing visible top-cap rows to be missed.
- This attempt combines exposed visible rows with narrowed pair-derived X footprints.

Implementation shape:

- Leave `OverworldWildSpawns_TryGetHeadbuttTreeTops` pair-derived X logic intact.
- Change the active Mankey tree-top calls back to `includeExposedRows = TRUE`:
  - current-tile settled predicate
  - direct top target picker
  - BFS target grid marker
- Continue leaving `OW_WILD_TILE_HEADBUTT` unused for this targeting path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test400.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported that Mankey still does not jump three tiles down to the visible tree-top tile on `test400.nds`.
- Re-enabling only the exposed endpoint row was still too narrow.
- The resolver only stored two Y rows, so it could miss visible canopy rows between the structural top row and archive exposed row.

### Attempt 243: Full Mankey Tree-Top Vertical Band

Idea:

Fix the repeated failure where Mankey will not jump three tiles down to a visible tree-top tile. Do not use `OW_WILD_TILE_HEADBUTT`, and do not return to the broad-X false positive from Attempt 235. Keep the pair-derived X footprint from Attempt 241, but stop representing the tree top as only one or two Y rows. Treat every row from the structural 2x6 top through the archive exposed row as part of `HEADBUTT_TREE_TOPS`.

Why this is new:

- Attempt 242 re-enabled the exposed endpoint row, but the highlighted visible tree-top tile can still sit between the structural row and that endpoint.
- Previous attempts kept `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS` at `2`, so the resolver could not represent a vertical band.
- This attempt keeps the narrowed X footprint and expands only the Y representation.

Implementation shape:

- Change `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS` from `2` to `OW_WILD_HEADBUTT_TREE_HEIGHT_TILES`.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, when exposed rows are requested, add every row from `structuralTopY + 1` through `minY`, capped by the tree height.
- Keep current-tile settling, direct target picking, and BFS target marking on the same shared `HEADBUTT_TREE_TOPS` result.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test401.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported this is still not fixed on `test401.nds`; Mankey still does not jump three tiles down to a tree-top tile.
- Broadening the shared vertical row band is not enough by itself.
- The failure now points at direct target selection or post-landing settled handling rather than only target-row membership.

### Attempt 244: Direct Cardinal Mankey Tree-Band Target

Idea:

Stop relying only on enumerated tree-top tiles to eventually include the visible target. Add a direct, explicit cardinal resolver for the user's repeated case: if a Mankey has a tile 3-8 tiles straight up/down/left/right that falls inside any archive-derived headbutt-tree top band, pick that tile as the final tree target. Keep this separate from `OW_WILD_TILE_HEADBUTT`; it still uses dedicated headbutt-tree archive geometry. Also make final tree-top landing state authoritative so a target chosen by this direct resolver does not immediately get rejected by the stricter current-tile predicate after landing.

Why this is new:

- Attempts 240-243 changed which rows/Xs counted in the shared `HEADBUTT_TREE_TOPS` set.
- No previous attempt added a direct cardinal scan from the current Mankey tile to a broad archive-derived tree-top band.
- No previous attempt made `sOverworldWildMankeyTreeTopSettled` authoritative for the idle/stop path.

Implementation shape:

- Add `OverworldWildSpawns_IsMankeyBroadHeadbuttTreeTopBandCandidate`.
- Add `OverworldWildSpawns_TryUseDirectMankeyHeadbuttTreeTopBandCandidate`, scanning distances `3..8` in each cardinal direction.
- Run the direct resolver before the older precise target enumerator in `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`.
- In the Mankey chill branch, if `sOverworldWildMankeyTreeTopSettled[slot]` is already set, idle immediately instead of requiring the current tile to pass the stricter predicate again.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyBroadHeadbuttTreeTopBandCandidate`
- `OverworldWildSpawns_TryUseDirectMankeyHeadbuttTreeTopBandCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `sOverworldWildMankeyTreeTopSettled`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test402.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported this still does not work on `test402.nds`: Mankey can clearly jump three tiles right to a tree-top tile but stands still.
- The direct cardinal target may still be skipped because Mankey can be classified as already settled/on a tree-top before target selection runs.
- Attempt 244's coordinate-less authoritative settled flag is unsafe because it can idle a slot without proving the current tile is the completed landing tile.

### Attempt 245: Coordinate-Latched Mankey Tree-Top Settlement

Idea:

Fix the `test402.nds` stand-still case without returning to `OW_WILD_TILE_HEADBUTT` and without broadening the target detector again. Stop treating the current tile detector as a reason for Mankey to idle. Mankey should only stop in its chill state after it has completed a canopy tree-top hop, and only while it remains on the exact tile where that hop landed.

Why this is new:

- Attempt 244 made `sOverworldWildMankeyTreeTopSettled[slot]` authoritative, but it was coordinate-less and could freeze any later tile for that slot.
- Attempts 240-243 changed the shared tree-top geometry; this attempt changes the movement state gate instead.
- This does not use `OW_WILD_TILE_HEADBUTT` and does not add another broader tree-top row/footprint heuristic.

Implementation shape:

- Add `sOverworldWildMankeyTreeTopSettledX/Y` alongside `sOverworldWildMankeyTreeTopSettled`.
- When `OverworldWildSpawns_FinishPendingCanopyHop` completes an expected Mankey tree-top landing, store the exact current tile as the settled tile.
- In `OverworldWildSpawns_TryStartHeadbuttTreeHop`, clear stale settled state if the object is no longer on that stored tile.
- Remove the Mankey chill-state early return that idled solely because `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached` returned true.
- Clear stale landing-expected state in `OverworldWildSpawns_ClearCanopyHopTarget`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildMankeyTreeTopSettledX`
- `sOverworldWildMankeyTreeTopSettledY`
- `OverworldWildSpawns_ClearCanopyHopTarget`
- `OverworldWildSpawns_FinishPendingCanopyHop`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test403.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported Mankey still misses the mark on `test403.nds`: it moves, but lands beside/near the tree rather than on the intended tree-top tile.
- Coordinate-latched settling fixed the likely idle/stale-state issue, but did not fix final target choice.
- The broad fallback band is now suspect because it accepts rows through `minY` and can choose side/body tiles when they are closer than the strict visual top row.

### Attempt 246: Prioritize Strict Structural Mankey Tree Tops

Idea:

Fix the `test403.nds` "missing the mark" result by making direct Mankey tree-top selection prefer the strict structural top row first. Keep the broad row band only as a fallback. This uses `topY = maxY - (OW_WILD_HEADBUTT_TREE_HEIGHT_TILES - 1)` with pair-derived 2-wide X footprints, matching the 2-wide/6-high headbutt-tree model, while preserving the previous fallback for awkward sparse archive entries.

Why this is new:

- Attempts 240-241 tried strict structural rows while Mankey could still stop early from current-tile misclassification.
- Attempt 245 removed the current-tile early stop and coordinate-latched true completed landings.
- Attempt 244's broad direct band moved/selected targets but can land on side/body tiles because it accepts every row up to `minY`.
- This attempt does not use `OW_WILD_TILE_HEADBUTT` and does not broaden the target set.

Implementation shape:

- Add `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`.
- First pass through the headbutt-tree archive:
  - mark existing fallback target grid,
  - try direct cardinal jumps only to strict structural top-row candidates from `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., FALSE, ...)`,
  - return immediately if any strict direct candidate exists.
- Second pass keeps the previous broad direct/exposed-row candidate fallback.
- A read-only explorer confirmed `maxY - 5` is the most plausible strict top-row formula for sparse `treecoords`, with adjacent X pairs as the best X footprint.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test404.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported `test404.nds` was still bugged, with Mankey landing beside/near the canopy instead of on the intended tree top.
- The strict candidate ran first, but the old broad fallback could still win after strict direct selection failed, so the build was still mixing incompatible target definitions.
- Next attempt should stop allowing broad/exposed-row candidates as final Mankey tree-top targets.

### Attempt 247: Strict-Only Mankey Tree-Top Final Targets

Idea:

The `test404.nds` result shows that prioritizing strict structural tree tops is not enough while the broad band fallback is still allowed to produce final targets. For this test, make Mankey tree-top targeting strict-only: direct jumps and BFS target grids both use `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., FALSE, ...)`, and the previous broad band/exposed-row final fallback is not called.

Why this is new:

- Attempts 240-241 used strict structural rows before the coordinate-latched landing fix from Attempt 245, so Mankey could still stop early from current-tile misclassification.
- Attempt 246 prioritized strict structural rows but still kept the broad final fallback, which the latest screenshot suggests was still selecting near-tree/body/side tiles.
- This attempt does not use `OW_WILD_TILE_HEADBUTT`, does not use exposed rows, and does not use the broad direct band as a final target source.

Implementation shape:

- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget` now marks only strict structural top rows in the BFS target grid.
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` no longer calls `OverworldWildSpawns_TryUseDirectMankeyHeadbuttTreeTopBandCandidate` or the exposed-row candidate fallback.
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep` now reports whether the selected first path step is itself a final target, so a direct BFS step onto a tree top can latch as settled.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before and after the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test405.nds`.
- Build warnings were limited to the existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning; the newly unused broad Mankey fallback helpers are expected because this attempt intentionally stops calling that fallback.

Learning:

- User reported `test405.nds` still has the same bug: Mankey stands above/near a visible tree top with the failure bubble and does not take the obvious hop.
- Strict-only final targets helped remove the broad fallback, but the strict top-row formula itself still appears wrong.
- Inspecting `armips/data/headbutt.s` for Route 29 shows entries like `treecoords 646, 385, 647, 385`, which look like the actual top-row pair the user expects Mankey to target. The `maxY - 5` formula would target row `380` for that tree, far above the visible top row and explaining why a 3-tile downward hop is not recognized.

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

### Attempt 235: Dedicated HEADBUTT_TREE_TOPS Archive Target Set

Idea:

The user clarified that `OW_WILD_TILE_HEADBUTT` is unrelated to this Mankey tree-top problem and must not be used as the target definition. Define a dedicated `HEADBUTT_TREE_TOPS` concept from headbutt tree archive data. The important correction is X handling: for a 2-tile-wide tree top, each archive coord X may represent either the left or right tile of that visual two-tile top, so derive possible top-left X candidates from both `coordX` and `coordX - 1`.

Why this is new:

- Attempts 230-233 still assumed one primary left edge from `minX`, with at most one special `minX - 1` fallback for single-column entries.
- Attempt 234 used live `OW_WILD_TILE_HEADBUTT` behavior and was rejected.
- This attempt keeps Mankey tree tops separate from metatile behavior and broadens only the dedicated `HEADBUTT_TREE_TOPS` archive-derived target set.

Implementation shape:

- Add `OverworldWildHeadbuttTreeTops`, containing top rows and top-left X candidates.
- Add `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS` and `OW_WILD_HEADBUTT_TREE_TOPS_MAX_LEFTS`.
- Replace the old row/X helpers with `OverworldWildSpawns_TryGetHeadbuttTreeTops`.
- For every valid coord in one tree entry, add top-left candidates `coordX` and `coordX - 1`.
- Keep the row candidates from prior work:
  - structural row: `maxY - 5`
  - exposed row: `minY`, only when target-picking/path-marking asks for exposed rows
- Update settled recognition, direct candidate picking, and BFS target marking to consume `OverworldWildHeadbuttTreeTops`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS`
- `OW_WILD_HEADBUTT_TREE_TOPS_MAX_LEFTS`
- `OverworldWildHeadbuttTreeTops`
- `OverworldWildSpawns_AddHeadbuttTreeTopLeftCandidate`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- Route 29 source-data spot check shows wider dedicated top X sets without using metatile behavior:
  - entry `[(638,389), (639,389), (639,388)]` now yields rows `[384,388]` and top Xs `[637,638,639,640]`
  - entry `[(630,395), (631,395), (630,394)]` now yields rows `[390,394]` and top Xs `[629,630,631,632]`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test392.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

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

### Attempt 69: Use Site Walk Commands And Scripted Crash Feedback For Onix Ram

Idea:

Replace the failed jump-bit feedback path with two different built-in systems:

- Use `Walk*FastSite` / `Walk*VeryFastSite` movement commands for Onix ram movement at speed 2 or higher, while leaving normal walking commands intact for other Pokemon behavior.
- Remove `BIT_JUMP_START` from Onix ram step and crash handling entirely, because Attempt 68 produced hop-like feedback instead of smoke/thud.
- Add common script `2075` / `scr_seq_0003_075_overworld_wild_ram_crash_feedback` for Onix ram crashes.
- On ram crash, schedule the common script from the movement field context when available.
- The crash script plays `SEQ_SE_GS_DODON`, runs `ShakeCamera 3, 3, 4, 2`, waits briefly, then ends.
- Keep the C-side crash sound fallback if there is no current movement field context.

Why this is new:

- Attempts 67 and 68 approximated Onix ground/crash feedback with `BIT_JUMP_START`; this attempt removes that bit from the ram path.
- No previous attempt has used `Walk*Site` movement commands for Onix ram movement.
- No previous attempt has added a dedicated common script for ram crash sound and screen shake.
- No previous attempt has scheduled a non-battle overworld wild common script from the movement frame task for feedback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/config.h`
- `armips/include/scriptmacros.s`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test167.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test167.nds`.
- `git diff --check` passed before the build.
- Verified the overlay compiles after removing `BIT_JUMP_START` from the Onix ram step and crash paths.
- Verified the script NARC rebuild accepts the new `scr_seq_0003_075_overworld_wild_ram_crash_feedback` common script.
- Verified Onix ram speed 2 and 3 movement now choose `Walk*FastSite` / `Walk*VeryFastSite` command families instead of the normal walk command families.

Runtime result:

- User reported Onix no longer moves.

Learning:

- The `Walk*FastSite` / `Walk*VeryFastSite` command families are not safe replacements for Onix ram movement on these spawned Pokemon.
- Do not use the `Walk*Site` command family for the active ram step path unless a future isolated test proves how to make it move.
- The dedicated crash common script has not been fairly tested yet, because Onix did not reach its moving/crashing state.

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

### Attempt 72: Direct Stock Ground-Dust Effect Without Step Sound

Idea:

Stop trying to trigger Onix ram dust through movement command flags:

- Remove the failed Attempt 71 site visual override and `sub_0205F328` import.
- Stop playing an explicit sound on every Onix ram step, because both tested `DANSA5` and `DANSA` read as hop-like in runtime.
- Import `ov01_021FD640`, a stock field-effect helper used by map-object movement effect logic for ground/step presentation.
- Call `ov01_021FD640(object)` directly when an Onix ram step starts at speed `2` or higher.
- Keep the normal walk command family that still makes Onix move.

Why this is new:

- Attempt 68 used `BIT_JUMP_START` and failed.
- Attempt 69 used whole `Walk*Site` commands and failed.
- Attempt 71 tried borrowing only the site visual parameter and failed.
- No previous attempt has directly called `ov01_021FD640` from the Onix ram step path.
- No previous Onix ram feedback attempt has removed the explicit per-step sound to isolate visual dust from audio.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test170.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test170.nds`.
- `git diff --check` passed before the build.
- Verified the overlay compiles and links after importing `ov01_021FD640` at `0x021FD640`.
- Verified `OverworldWildSpawns_PlayRamStepFeedback` calls `ov01_021FD640(object)` only for active ram Pokemon at speed `2` or higher.
- Verified the Onix ram path no longer plays an explicit per-step `PlaySE`.
- Verified the failed Attempt 71 `sub_0205F328` site-visual override was removed from active code.

Runtime result:

- User reported no sound and no smoke effect.

Learning:

- Removing the explicit per-step sound did remove sound.
- Directly calling `ov01_021FD640(object)` did not create visible smoke for spawned Onix ram movement.
- Do not retry direct `ov01_021FD640` as the Onix ram dust solution without new evidence.
- The known smoke-producing primitive remains `WaitJumpSite` (`0x65`) from Attempt 49.

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

### Attempt 75: Fixed Run-Style Boulder Effect Id

Idea:

Keep the successful nonblocking direct helper from Attempt 74, but stop deriving the effect id from ram speed:

- Replace the speed-clamped `ov01_021FFF5C` effect id with a fixed `OW_WILD_SPAWNER_ONIX_RAM_STEP_EFFECT_ID`.
- Set the fixed id to `1`, because vanilla movement-effect logic maps the `Run*` command group (`0x14-0x17`) to effect id `1`.
- Keep normal Onix ram walking unchanged.
- Keep the per-step `SEQ_SE_DP_DANSA` sound unchanged for this visual-only probe.

Why this is new:

- Attempt 74 called `ov01_021FFF5C` with speed-derived ids `2`/`3` and produced trail marks.
- Attempts 68-73 did not call `ov01_021FFF5C` with a fixed id.
- No previous attempt has tested fixed id `1`, the remaining stock movement-effect id that is used by the `Run*` command group.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test173.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test173.nds`.
- `git diff --check` passed before the build.
- Verified active ram step feedback calls `ov01_021FFF5C(object, OW_WILD_SPAWNER_ONIX_RAM_STEP_EFFECT_ID)`.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_STEP_EFFECT_ID` is fixed to `1`, not derived from ram speed.
- Verified normal Onix ram walking still starts before ram-step feedback plays.
- Verified the failed post-step `WaitJumpSite` ram follow-up path remains absent from active code.

Runtime result:

- User reported this produced a different-color trail, not smoke. Screenshot showed pale/grey trail marks following Onix's ram path.

Learning:

- Fixed id `1` is also a trail resource in practice.
- The `ov01_021FFF5C` helper appears to be the wrong visual family for Onix ram dust/smoke, even though it does not interrupt movement.
- Do not continue cycling `ov01_021FFF5C` ids for this effect without new evidence.
- `WaitJumpSite` command `101` calls `ov01_022000DC` before it starts the vertical/facing-vector wait animation, so the smoke-producing part can be separated from the movement-stopping part.

### Attempt 76: Direct WaitJumpSite Smoke Launcher During Ram Movement

Idea:

Keep Onix on the proven normal ram walk command, but borrow only the visual launcher from `WaitJumpSite`:

- Import `ov01_022000DC`, the helper called by `MapObjectMovementCmd101_Step0` (`WaitJumpSite`) before that command animates the object vertically.
- Replace the `ov01_021FFF5C` trail-family call with `ov01_022000DC(object)`.
- Do not start movement command `101`, do not set `movementRamSmokeActive`, and do not add any post-step movement command.
- Keep the per-step `SEQ_SE_DP_DANSA` sound unchanged for this first direct smoke-launcher test.

Why this is new:

- Attempt 73 started the full `WaitJumpSite` movement command after each ram step and interrupted Onix movement.
- Attempts 74 and 75 called `ov01_021FFF5C` and produced trail resources.
- No previous attempt has called `ov01_022000DC` directly from the ram path while keeping normal ram movement active.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the blocked build attempts.
- Verified active ram step feedback calls `ov01_022000DC(object)` instead of `ov01_021FFF5C`.
- Verified `ov01_022000DC` is imported at `0x022000DC`.
- Verified the failed post-step `WaitJumpSite` ram follow-up path remains absent from active code.
- Built as `test174.nds` and copied to Delta after Docker recovered.

Runtime result:

- User reported this still produced only a trail. Screenshot showed pale footprint-like decals along Onix's path, matching the same visual family as Attempts 74 and 75 rather than a short dust/smoke puff.

Learning:

- Direct `ov01_022000DC` is not the separated smoke-only primitive after all. It behaves like another decal/trail effect when called independently.
- Do not keep pursuing `ov01_021FFF5C`/`ov01_022000DC` for Onix ram dust without new evidence.

### Attempt 77: Try Adjacent Overlay Effect Constructor `ov01_02200040`

Idea:

Keep Onix on the proven normal ram walk command, but switch ram step feedback to the adjacent standalone overlay effect constructor at `0x02200040`:

- Import `ov01_02200040(LocalMapObject *mapObject)`.
- Replace the direct `ov01_022000DC(object)` call with `ov01_02200040(object)`.
- Keep the normal ram movement command active and do not start any `WaitJumpSite` or post-step movement command.
- Keep the explicit `SEQ_SE_DP_DANSA` ram step sound for this first visual probe.

Why this is new:

- Attempts 74 and 75 used `ov01_021FFF5C` and produced trail/decal resources.
- Attempt 76 used `ov01_022000DC` and also produced trail/decal resources.
- Attempt 73 used the full `WaitJumpSite` movement command and interrupted movement.
- No previous attempt has called the standalone constructor at `0x02200040`.
- Disassembly shows `0x02200040` initializes a different effect resource set (`9/10/11`) and descriptor table `0x022092A8`, while `0x022000DC` uses descriptor `0x02209294`.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test175.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_02200040(object)`.
- Verified `ov01_02200040` is imported at `0x02200040`.
- Verified active code no longer calls `ov01_022000DC(object)` for ram step feedback.

Runtime result:

- User reported the game freezes when Onix tries to move.

Learning:

- `ov01_02200040` is not safe to call with a `LocalMapObject *`. Disassembly shows it passes raw `r0` directly into `ov01_021F1430` and then uses that stored pointer as an effect/resource system, so the imported prototype was likely wrong.
- Do not call adjacent constructors that expect an effect-system pointer with a map object just because they are near the known map-object helpers.

### Attempt 78: Try Map-Object Anchored Effect Helper `ov01_02200730`

Idea:

Back away from the unsafe `ov01_02200040` constructor and try a different one-shot helper that visibly treats its input as a `LocalMapObject`:

- Import `ov01_02200730(LocalMapObject *mapObject)`.
- Replace the freeze-prone `ov01_02200040(object)` ram step call with `ov01_02200730(object)`.
- Keep the normal ram walk command active and do not start `WaitJumpSite` or any post-step movement command.
- Keep `SEQ_SE_DP_DANSA` for this probe so the visual change is isolated from the rest of the ram behavior.

Why this is new:

- Attempts 74 and 75 used `ov01_021FFF5C` and produced trail/decal resources.
- Attempt 76 used `ov01_022000DC` and also produced trail/decal resources.
- Attempt 77 used `ov01_02200040` and froze because it likely expects an effect-system pointer, not a map object.
- No previous attempt has called `ov01_02200730`.
- Disassembly shows `ov01_02200730` derives the effect context from the map object via `ov01_021F146C`, reads map-object data with ARM9 helpers, and launches descriptor table `0x02209308`, so this is a new map-object anchored effect path rather than another unsafe constructor call.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test176.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_02200730(object)`.
- Verified `ov01_02200730` is imported at `0x02200730`.
- Verified the unsafe `ov01_02200040` import was removed from active code.

Runtime result:

- User reported Onix now has a bright red outline / targeting square when it moves.
- Screenshot showed the rectangle attached around Onix rather than a ground dust/smoke effect.

Learning:

- `ov01_02200730` is a selection/target-outline style visual, not the strength boulder dust/smoke family.
- Do not use descriptor table `0x02209308` for ram step feedback.

### Attempt 79: Try Short-Lived Map-Object Effect Helper `ov01_021FF74C`

Idea:

Replace the red-outline helper with another map-object anchored effect helper:

- Import `ov01_021FF74C(LocalMapObject *mapObject)`.
- Replace `ov01_02200730(object)` in the ram step feedback path with `ov01_021FF74C(object)`.
- Keep the normal ram walk command active and do not start `WaitJumpSite` or any post-step movement command.
- Keep `SEQ_SE_DP_DANSA` for this probe so the visual change is isolated.

Why this is new:

- No previous attempt in this log has called `ov01_021FF74C`.
- Attempts 74 and 75 used `ov01_021FFF5C` and produced trail/decal resources.
- Attempt 76 used `ov01_022000DC` and also produced trail/decal resources.
- Attempt 77 used `ov01_02200040` and froze because it likely expects an effect-system pointer, not a map object.
- Attempt 78 used `ov01_02200730` and produced a red target/outline effect.
- Disassembly shows `ov01_021FF74C` derives context from the map object and launches a different descriptor table, `0x022091EC`, so this is not a repeat of the trail helpers or the red-outline helper.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test177.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_021FF74C(object)`.
- Verified `ov01_021FF74C` is imported at `0x021FF74C`.
- Verified `ov01_02200730` was removed from active code imports/call sites.

Runtime result:

- User reported nothing visible happened.

Learning:

- `ov01_021FF74C` is not useful for Onix ram step feedback in this context.
- It is safe enough to call, but either its effect is invisible/subtle here or it is not a ground-smoke presentation.

### Attempt 80: Try Alternate Stock Ground Effect Helper `ov01_021FD684`

Idea:

Try the neighboring helper to the failed direct stock ground-dust effect:

- Import `ov01_021FD684(LocalMapObject *mapObject)`.
- Replace `ov01_021FF74C(object)` in the ram step feedback path with `ov01_021FD684(object)`.
- Keep the normal ram walk command active and do not start `WaitJumpSite` or any post-step movement command.
- Keep `SEQ_SE_DP_DANSA` for this probe so only the visual helper changes.

Why this is new:

- Attempt 72 called `ov01_021FD640(object)` directly and did not create visible smoke.
- No previous attempt in this log has called `ov01_021FD684`.
- Disassembly shows `ov01_021FD684` uses the same safe `LocalMapObject *` setup pattern as `ov01_021FD640`, but launches descriptor table `0x02208EC8` with a different launch argument instead of descriptor table `0x02208EA0`.
- This is not a repeat of the trail-family helpers (`ov01_021FFF5C` / `ov01_022000DC`), the unsafe constructor (`ov01_02200040`), the red-outline helper (`ov01_02200730`), or the no-visible-effect helper (`ov01_021FF74C`).

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test178.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_021FD684(object)`.
- Verified `ov01_021FD684` is imported at `0x021FD684`.

Runtime result:

- User reported nothing was visible.

Learning:

- `ov01_021FD684` is safe enough to call in this context, but it does not create visible Onix ram step feedback.
- Do not use `ov01_021FD684` as the active ram smoke path unless new evidence shows it needs extra setup.

### Attempt 81: Add WaitJumpSite Flag Context Around `ov01_022000DC`

Idea:

Try the effect helper that `WaitJumpSite` calls again, but with the map-object flag context that stock `WaitJumpSite` applies:

- Keep Onix ram using the normal walk command.
- Before `ov01_022000DC(object)`, set map-object bits `0x00010004`.
- After the helper, clear map-object bit `0x00100000`.
- Do not start the `WaitJumpSite` movement command and do not advance the movement command state from the feedback path.
- Keep `SEQ_SE_DP_DANSA` for this probe so the visual setup is isolated.

Why this is new:

- Attempt 73 used full post-step `WaitJumpSite` and got smoke-like feedback, but it interrupted Onix ram movement.
- Attempt 76 called `ov01_022000DC(object)` directly and produced a trail/decal rather than smoke.
- No previous attempt has called `ov01_022000DC(object)` while applying only the stock `WaitJumpSite` set/clear bit context and leaving the current ram walk command active.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing symbols `MapObject_SetBits`, `MapObject_ClearBits`, and `ov01_022000DC`

Verification:

- `git diff --check` passed before the build.
- Built as `test179.nds` and copied to Delta.
- Verified active ram step feedback sets `0x00010004`, calls `ov01_022000DC(object)`, then clears `0x00100000`.
- Verified `MapObject_SetBits`, `MapObject_ClearBits`, and `ov01_022000DC` are already imported.

Runtime result:

- User reported the smoke effect is in.

Learning:

- Applying the stock `WaitJumpSite` map-object flag context around `ov01_022000DC(object)` creates the desired Onix ram smoke without interrupting ram movement.
- The active visual path should keep this `MapObject_SetBits` / `ov01_022000DC` / `MapObject_ClearBits` structure while sound is tuned separately.

### Attempt 82: Use HGSS Push Sound For Onix Ram Steps

Idea:

Keep the successful Attempt 81 smoke path and change only the explicit ram step sound:

- Add `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`.
- Set it to `SEQ_SE_GS_PUSH02`, one of the HGSS `PUSH` sound effects near the field/rock sound constants.
- Replace the per-step `PlaySE(SEQ_SE_DP_DANSA)` call with `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Why this is new:

- Attempts 68, 71, and later visual probes used `SEQ_SE_DP_DANSA5` or `SEQ_SE_DP_DANSA`, and the runtime result sounded hop-like/wrong.
- No previous Onix ram attempt has used either `SEQ_SE_GS_PUSH02` or `SEQ_SE_GS_PUSH03`.
- The local sound table names `PUSH02` / `PUSH03` make this a better candidate for the strength-boulder push sound than cycling more `DANSA` variants.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_PUSH02`

Verification:

- `git diff --check` passed before the build.
- Built as `test180.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now uses `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`, defined as `SEQ_SE_GS_PUSH02`.

Runtime result:

- User reported no sound played.

Learning:

- `SEQ_SE_GS_PUSH02` is not a usable Onix ram step sound through this direct C `PlaySE` path, at least in the current overworld context.
- Keep the successful smoke path intact and continue sound probes separately.

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

### Attempt 84: Load Push Sequence Before Playing It

Idea:

Keep the successful Attempt 81 smoke path and keep the current `SEQ_SE_GS_PUSH03` sound candidate, but explicitly load the sequence before playing it:

- Call `GF_Snd_LoadSeq(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.
- Then call `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.
- Leave ram movement, smoke, and crash feedback unchanged.

Why this is new:

- Attempts 82 and 83 only called `PlaySE` directly for `SEQ_SE_GS_PUSH02` and `SEQ_SE_GS_PUSH03`.
- SDAT inspection shows those push sounds exist but use bank `770` and wave archive `770`, unlike known direct-play field/global sounds such as `SEQ_SE_DP_KON` / `SEQ_SE_DP_DANSA`, which use bank `700`.
- No previous Onix ram attempt has explicitly loaded the selected step sound sequence before playing it.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing function `GF_Snd_LoadSeq`
- Existing sound constant `SEQ_SE_GS_PUSH03`

Verification:

- `git diff --check` passed before the build.
- Built as `test182.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now calls `GF_Snd_LoadSeq(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)` before `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Runtime result:

- User reported no sound played.

Learning:

- `GF_Snd_LoadSeq` alone is not enough to make `SEQ_SE_GS_PUSH03` audible in this field context.
- This supports the idea that the missing piece is bank/wave loading rather than the SSEQ itself.

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

### Attempt 87: Promote `aggressive_ram` Behavior And Strengthen Crash Feedback

Idea:

Make ram a first-class behavior profile instead of an Onix-specific variable patch, and make crash presentation explicit:

- Add `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`.
- Add a non-hop angry alert state, `OW_WILD_BEHAVIOR_ALERT_STATE_SPEECH_ANGRY`.
- Move Onix from `AGGRESSIVE` plus variable overrides to the new `AGGRESSIVE_RAM` behavior class.
- Put the ram alertness, ram attentive state, stamina, tired state, rest time, normal speed, max speed, and range directly in the behavior class override.
- Make `AGGRESSIVE_RAM` alert with only the angry speech bubble and the Pokemon cry, not a hop.
- Play the crash thud from C with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep the common crash script for camera shake, and make it stronger/more visible.

Why this is new:

- Earlier Onix ram builds used `AGGRESSIVE` behavior with a species-specific variable override for ram values.
- No previous attempt has introduced `AGGRESSIVE_RAM` as a behavior class.
- Attempt 69 added a crash script with sound and a light camera shake, but it did not use the newer full archive load path for the crash thud and did not promote ram into the behavior hierarchy.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing script `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`
- Existing sound constant `SEQ_SE_GS_DODON`

Verification:

- `git diff --check` passed before the build.
- Built as `test185.nds` and copied to Delta.
- Verified Pidgey still maps to `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE`.
- Verified Onix maps to `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`.
- Verified `AGGRESSIVE_RAM` profile owns ram alertness, ram attentive state, stamina, tired state, rest time, normal speed, max speed, and range.
- Verified the non-hop angry speech alert shows the angry bubble and plays the Pokemon cry.
- Verified crash feedback loads `SEQ_SE_GS_DODON` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified the crash script now only handles the stronger `ShakeCamera 5, 4, 8, 2` presentation.

Runtime result:

- User reported no crash sound or shake.

Learning:

- `SEQ_SE_GS_DODON` is still silent in this field context even when loaded with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)`.
- The common script's `ShakeCamera 5, 4, 8, 2` path did not produce visible crash feedback.
- Avoid retrying `SEQ_SE_GS_DODON` or `ShakeCamera` for Onix ram crashes unless new evidence shows a missing caller/context requirement.

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

### Attempt 97: Aggressive Ram Rest-Only Tired State

Idea:

Keep aggressive_ram's tired/rest timing, but remove its tired visual cue:

- Add a `NO_VISUAL` tired state distinct from `NONE`.
- Set the aggressive_ram behavior profile's tired state to `NO_VISUAL`.
- Let `StartTiredEmote` still put the slot into `OW_WILD_SPAWNER_SPOT_STATE_TIRED` and start the rest timer.
- If the tired state is `NO_VISUAL`, skip the water-droplet bubble and fallback tired animation, then let `TickTiredEmote` count down normally.

Why this is new:

- Setting tired state to `NONE` would skip the tired/rest phase, which is not what the user asked for.
- Earlier tired-state attempts focused on finding the right bubble/icon, and aggressive_ram previously used the water-droplet tired visual.
- No previous attempt has created a rest-only tired state that preserves cooldown/rest behavior while intentionally showing no visual cue.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_BEHAVIOR_TIRED_STATE_NO_VISUAL`
- `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`
- `OverworldWildSpawns_StartTiredEmote`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test195.nds` and copied to Delta.
- Verified `OW_WILD_BEHAVIOR_TIRED_STATE_NO_VISUAL` is distinct from `OW_WILD_BEHAVIOR_TIRED_STATE_NONE`.
- Verified aggressive_ram now uses `OW_WILD_BEHAVIOR_TIRED_STATE_NO_VISUAL` instead of `OW_WILD_BEHAVIOR_TIRED_STATE_WATER_DROPLET`.
- Verified `OverworldWildSpawns_StartTiredEmote` still sets `OW_WILD_SPAWNER_SPOT_STATE_TIRED` and starts the rest timer before skipping the visual presentation for `NO_VISUAL`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 98: Restore Smaller Ram Crash Wobble Offset

Idea:

Keep the restored object-wobble feedback, but return its offset to the earlier subtle value:

- Keep the 32-frame wobble duration from Attempt 96.
- Change `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FX32_AMPLITUDE` from `3/8` tile to `1/8` tile.
- Leave the ram crash thud, tired-state flow, and no-screen-shake decision unchanged.

Why this is new:

- Attempt 96 deliberately boosted the offset to `3/8` tile after the old wobble seemed too subtle.
- The user now specifically asked to return only the offset to the previous version.
- No new screen-shake path is involved.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FX32_AMPLITUDE`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test196.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FX32_AMPLITUDE` is now `OW_WILD_SPAWNER_FX32_ONE / 8`.
- Verified `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FRAMES` remains `32`.
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

### Attempt 143: One-Second Pause After Phantom Alert Arrival

Idea:

Use the same 60-frame pause after the phantom alert teleport arrival finishes and the Pokemon enters active stalking. This should make the arrival read before the first attentive teleport movement begins.

Implementation shape:

- Reuse `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`.
- In `OverworldWildSpawns_FinishPhantomTeleportAlert`, replace the immediate `OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN` reset with the 60-frame phantom teleport cooldown.
- This applies whenever the phantom alert resolves into active stalking, including the normal arrival path and the fallback path where the alert teleport cannot find a destination.

Why this is new:

- Attempt 131 had a short movement hold after a now-reworked destination flicker.
- Attempt 142 added the explicit 60-frame pause after each active attentive-state teleport movement.
- No previous attempt has applied the same explicit 60-frame pacing pause at the current `OverworldWildSpawns_FinishPhantomTeleportAlert` transition.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`
- `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test241.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User reported the phantom is invisible during the new pause and asked to make it visible. User also asked for the alert-state teleport to be twice as fast.

Learning:

- The 60-frame pause is useful for pacing, but it must explicitly force the phantom into a visible state at pause start. Simply delaying the next movement decision is not enough if hidden/teleport visual state is still active.

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

### Attempt 146: Recreate Real Phantom After Attentive Teleport

Idea:

Use the proven alert-arrival handoff for active attentive teleport movement too: when an active phantom teleport finishes, recreate the real Pokemon object at the teleport destination before running finished-movement state handling and before starting the 1-second visible cooldown.

Implementation shape:

- In `OverworldWildSpawns_TickPhantomTeleportMovementCommand`, when the active teleport visual timer reaches zero:
  - call `OverworldWildSpawns_RecreatePhantomObjectForActiveState(state, slot, object)`;
  - then clear the movement-in-progress bit;
  - then run `OverworldWildSpawns_HandleFinishedMovementCommand`;
  - then, if the Pokemon remains an active phantom stalker, start `OverworldWildSpawns_StartPhantomVisibleCooldown`.
- This mirrors the successful alert-arrival path where `OverworldWildSpawns_FinishPhantomTeleportAlert` recreates the real object before the visible pause.
- It also means tired-state transitions after the final stamina-spending teleport see a fresh visible object rather than the object that was just hidden for teleport movement.

Why this is new:

- Attempt 138 recreated the real phantom only when the alert teleport entered attentive state.
- Attempt 144 shared the visible cooldown helper between alert-arrival and active-teleport pauses, but the active-teleport path still only cleared `BIT_VANISH` on the same hidden object.
- No previous attempt has recreated the real object after each active attentive-state teleport movement before starting the post-teleport pause.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`
- `OverworldWildSpawns_RecreatePhantomObjectForActiveState`
- `OverworldWildSpawns_StartPhantomVisibleCooldown`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test244.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User requested a behavior update: bumping into a phantom stalker should only start battle during the visible pause, not during other visible flicker/teleport frames.

Learning:

- The visible pause should be treated as a specific interaction window, distinct from alert-charge flicker, alert-arrival flicker, and active teleport position flicker.

### Attempt 147: Limit Phantom Bump Battles To Visible Pause

Idea:

Make directional bump battles for phantom stalkers trigger only during the explicit post-teleport visible pause created by `OverworldWildSpawns_StartPhantomVisibleCooldown`. Visible flicker frames during alert/arrival/active teleport should communicate movement, but should not be battle-start windows.

Implementation shape:

- Add `OverworldWildSpawns_IsPhantomVisiblePause`, which requires:
  - the slot is an active phantom stalker;
  - `movementPhantomHidden[slot]` is false;
  - no spawner-owned movement command is in progress;
  - `movementCooldowns[slot]` is nonzero;
  - `movementCooldowns[slot]` is within `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`.
- Update `OverworldWildSpawns_TryStartBattleFromDirectionalBump` to use only this helper.
- Remove the previous hidden/flicker-visible exception from directional bump battles, so flicker visibility no longer implies bump-battle eligibility.
- Leave the universal A-button path unchanged.

Why this is new:

- Attempt 141 added directional bump battles for phantom stalking.
- Attempt 145 restricted directional bump battles to active phantom stalkers, but still allowed them during visible flicker frames.
- Attempt 146 made attentive teleport pauses visible, but did not narrow the battle window.
- No previous attempt has treated the post-teleport visible cooldown as the only directional bump battle window.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsPhantomVisiblePause`
- `OverworldWildSpawns_TryStartBattleFromDirectionalBump`
- `OverworldWildSpawns_StartPhantomVisibleCooldown`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test245.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User requested the phantom stalker's normal/chill movement become `wanderTeleportation`: each chill step should teleport a random distance from 3-6 tiles using the same flicker movement as attentive-state teleport, followed by a 1-second visible pause.

Learning:

- The explicit visible-pause window is now useful beyond battle gating: chill phantom teleport movement can share the same pause contract.

### Attempt 150: Stable Phantom Battle Entry Gate

Idea:

Do not let a phantom stalker battle start while Gengar is in a teleport/flicker/hidden/intermediate alert state. The older battle-start fix only revealed hidden phantoms before queuing battle; it did not reject battles that were initiated during unsafe phantom movement frames, especially through the universal A-button path.

Implementation shape:

- Add `OverworldWildSpawns_IsSlotStableForBattle`.
- For non-phantom Pokemon, keep existing battle behavior.
- For phantom stalkers, require all of the following before battle can be scheduled:
  - the real object is not hidden;
  - no phantom flicker timer is active;
  - no phantom teleport target is active;
  - no spawner-owned movement command is in progress;
  - the real object has no active single movement command;
  - the slot is not in a phantom alert/charge/arrival emote step.
- Add `OverworldWildSpawns_PrepareSlotForBattle`, which reveals the stable phantom and clears any remaining phantom helper objects before pending battle setup.
- Harden `Script_QueueOverworldWildBattle` so if `OverworldWildSpawns_PopPendingBattle` fails, it jumps to a small `releaseall/end` script instead of falling through to the Rattata fallback battle.

Why this is new:

- Attempt 134 revealed hidden phantoms before battle setup, but did not block battle during unstable teleport/flicker states.
- Attempt 147 limited directional-bump battles to the visible pause, but the universal A-button path could still attempt phantom battles while flicker frames were visible or movement state was active.
- No previous attempt has centralized a phantom-specific "stable real object only" gate before queuing the battle script.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/script_new_cmds.c`
- `OverworldWildSpawns_IsSlotStableForBattle`
- `OverworldWildSpawns_PrepareSlotForBattle`
- `Script_QueueOverworldWildBattle`

Verification:

- `git diff --check` passed.
- `./docker-makerom.cmd` produced a fresh `test.nds` at `2026-06-07 12:11`.
- The Docker wrapper did not return to the post-build copy helper after the ROM was created, so the stale wrapper session was closed and the repo helper was run directly.
- `./scripts/copy-test-nds-to-delta.sh` copied the ROM to Delta as `test249.nds`.

Runtime result:

- User clarified that A-button interaction should still work during visible Gengar flicker frames, but should be made stable instead of disabled.

Learning:

- Blocking all flicker-state phantom battle starts is too conservative for intended feel.
- A-button battles need a separate path from bump/contact battles: pressing A on a visible apparition should materialize that visible tile into the real object before battle setup.

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

### Attempt 158: Canopy Hopper Pre-Hop Wait

Idea:

Mankey became visible only on the spawn frame, likely because universal return-to-tree immediately direct-placed land-spawned Mankey onto a headbutt tree tile on the first movement decision. Add a visible half-second staging delay before every canopy hop so Mankey stays on its current tile, faces the target, and only executes the direct tile hop after the pause.

Implementation shape:

- Add per-slot pending canopy-hop target state.
- When `OverworldWildSpawns_TryStartHeadbuttTreeHop` chooses a target, store the target, direction, distance, and tired-transition flag instead of immediately calling `OverworldWildSpawns_SetObjectTile`.
- Set `OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES` to `30` frames.
- On the next canopy decision after the cooldown expires, execute the pending hop through the existing direct-placement and `OverworldWildSpawns_HandleFinishedMovementCommand` path.
- Clear pending canopy-hop state on slot reset and fresh spawn initialization.

Why this is new:

- Attempt 157 made off-tree recovery universal but still moved Mankey immediately in the same tick.
- Earlier hop-visibility attempts focused on spot-emote movement commands, `WaitJumpSite`, and partner-Pokemon jump wrappers, not on delaying canopy direct placement.
- No previous attempt added a pre-hop staging delay to the canopy hopper target path.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_ExecutePendingCanopyHop`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- Built as `test258.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the canopy hopper path now stages a pending target before direct placement.
- Verified the staged path sets `OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES` / `30` frames before the hop executes.
- Verified pending canopy-hop state is cleared on slot reset and fresh spawn initialization.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify whether land-spawned Mankey remains visible for about half a second before returning to a tree, and whether tree-to-tree or ambush hops now have a readable pre-hop pause.

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

### Attempt 173: Keep Same Object Across Intermediate Canopy Landings

Idea:

Preserve the live Mankey object through intermediate two-tile canopy segment landings. The current bug appears after a two-tile segment finishes, before the full stored canopy target is reached. That means the risky operation is likely the object refresh in the middle of the hop chain, not only the final tree landing.

Implementation shape:

- Add a `finalLanding` parameter to `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`.
- For canopy-hopper profiles, return `FALSE` when the landing is not the final stored canopy target.
- Continue skipping refresh on final headbutt-tree landings.
- Preserve the existing final non-tree refresh path for now, so ground ambush landings can still use the stabilization behavior.
- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, compute whether the object is already at the stored canopy target before deciding whether to recreate it.

Why this is new:

- Attempt 168 kept the same real object through stock movement segments, but did not include the later boundary cleanup/refined tree-landing rules.
- Attempt 169 recreated after every completed segment.
- Attempt 172 skipped recreation only on headbutt-tree landings.
- Attempt 173 is narrower than Attempt 168 and different from Attempt 172: only intermediate segment landings are forced to keep the same object, because the new runtime clue points at the two-tile segment boundary.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test276.nds` and copied to Delta.
- The first build caught a local declaration placement error before ROM output; that was fixed before the successful `test276.nds` build.

Runtime result:

- User clarified that the first two tiles animate fine. The bug begins after Mankey jumps more than two tiles, when the next segment in the chain should continue.

Learning:

- Attempt 173 corrected the mid-segment delete/recreate path, but the important runtime clue is more specific: the first stock segment is healthy, and the segment-to-segment handoff is suspect.
- The next attempt should stabilize the object after the first two-tile landing and avoid starting the next movement command immediately in the same handoff window.

### Attempt 174: Settle Intermediate Canopy Segment Handoff

Idea:

Treat a successful two-tile canopy segment landing as a boundary that needs a short stabilization window before the next stock movement command starts. The first two tiles animate correctly, so the travel command itself is probably viable. The bug begins when chaining beyond that first segment.

Implementation shape:

- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_SEGMENT_SETTLE_FRAMES`.
- When a canopy segment lands but has not reached the stored full-hop target:
  - keep the same real object;
  - normalize the object to its landed logical tile with `OverworldWildSpawns_SetObjectTile`;
  - clear `BIT_VANISH`;
  - wait a short settle delay before the pending canopy hop can start the next segment.
- Preserve final landing behavior from Attempt 173:
  - skip final headbutt-tree refresh;
  - allow final non-tree refresh/stabilization.

Why this is new:

- Attempt 159 had a half-second wait between early stock jump-chain segments, but that was before strict 5-7 tile targets, before `WaitJumpLeft2` / `WaitJumpRight2`, before boundary-only cleanup, and before the no-intermediate-refresh rule.
- Attempt 173 kept the same object through intermediate segment landings, but still allowed the next segment to be queued immediately.
- Attempt 174 combines current carrier/cleanup rules with explicit landed-tile normalization and a short post-segment settle window.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_SEGMENT_SETTLE_FRAMES`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test277.nds` and copied to Delta.

Runtime result:

- User reported that Mankey is still completely invisible in trees.

Learning:

- The short segment-settle window does not fix the resting-on-tree visibility state.
- The first two tiles can animate, so the remaining issue looks less like the stock hop command itself and more like how the object is left when the full hop finishes on a headbutt-tree tile.
- Ordinary headbutt spawns are created directly at the tree tile and are not followed by the manual `OverworldWildSpawns_SetObjectTile` rewrite used by the canopy refresh helper.
- The next attempt should recreate only at the final tree landing, and should avoid manually normalizing the replacement object's tile after creation.

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

### Attempt 178: Canopy Movement Lists Use Jump2 Runs And No Final Recreate

Idea:

Keep the new vanilla `MapObject_StartMovementList` path from Attempt 177, but build the movement list as a real stock jump sequence:

- `LockDir`
- repeated `Jump*2` commands for same-direction runs
- an optional `Jump*` for an odd final tile
- `ReleaseDir`
- `MovementEnd`

Also stop recreating canopy-hopper objects on final landing. The current object should already be at the movement-list target, so final landing should normalize visibility and finish the canopy hop without deleting/recreating the real Mankey.

Why this is new:

- Attempt 177 introduced the movement-list task, but runtime showed the active list still behaved as 1-2 tile movement. Source verification showed `OverworldWildSpawns_BuildCanopyMovementList` emitted one one-tile `Jump*` command for each path step and did not append `LockDir`/`ReleaseDir`.
- Earlier attempts tried spawner-restarted stock jump commands, helper objects, and manual `posVec` interpolation. This keeps the engine-owned movement-list task but changes the list contents and removes the final recreate handoff.
- Earlier tree-landing attempts skipped only tree final refreshes or only intermediate refreshes; this attempt disables final refresh for canopy hoppers while keeping non-canopy refresh behavior intact.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test344.nds` and copied to Delta.
- The edited overlay compiled with only older unused diagnostics still present.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify whether Mankey now uses longer visible same-direction hop runs, remains visible on/near headbutt trees, and still survives route transitions without crashing/freezing.

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

### Attempt 193: Exact Headbutt Perches And Pre-Stage Carrier Validation

Idea:

Remove the idea of a perch radius from canopy hopper movement. A Mankey perch should be a concrete tile: either the headbutt tree tile itself or one cardinal tile adjacent to a real headbutt tree. Also stop staging canopy targets that the 3-8 same-axis long-jump carrier cannot actually execute.

Implementation shape:

- Replace the old 2-tile "visible perch" scan with `OverworldWildSpawns_IsHeadbuttTreeAdjacentPerchTile`, which checks only the four cardinal neighbors for a headbutt metatile.
- Update canopy "on tree" detection to use the exact adjacent-perch helper instead of the radius scan.
- Update straight-run canopy target selection to require exact adjacent-tree perches.
- Update the Route 29 verifier helper to use cardinal adjacency to the specific tree coordinate, not a radius.
- Make `OverworldWildSpawns_TryResolveHeadbuttTreeHopCandidate` only return same-axis targets in the 3-8 long-jump range.
- Remove the BFS/passable-path gate from that resolver because the active carrier is one direct same-axis jump, not a step path.
- Change `OverworldWildSpawns_StageCanopyHopTarget` to return `BOOL` and reject non-cardinal or out-of-range targets before the pre-hop wait is set.

Why this is new:

- Attempt 192 only range-gated the carrier after target selection.
- Earlier canopy visibility fixes either used broad perch radius logic, path/BFS validation, or post-failure cleanup.
- This attempt changes the tree/perch definition itself and prevents invalid pending targets before the 30-frame windup starts.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsHeadbuttTreeAdjacentPerchTile`
- `OverworldWildSpawns_IsNearHeadbuttTreeForCanopyVerifier`
- `OverworldWildSpawns_TryResolveHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickCanopyStraightRunTarget`
- `OverworldWildSpawns_IsCanopyHopperOnTree`
- `OverworldWildSpawns_StageCanopyHopTarget`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test360.nds` into the Delta ROM folder.
- Overlay compiled with the expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- Pending build/runtime test.

Learning:

- Pending.

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

### Attempt 219: Mankey Lands On Headbutt Tree Top Row

Idea:

Keep Attempt 218's direct and multi-jump pathing, but change Mankey's final landing row from two tiles above a headbutt-tree archive coordinate to the tree top row itself. For paired Route 29 headbutt coords like `(594,389)` and `(595,389)`, this should target `(594,388)` and `(595,388)` rather than `(594,387)` and `(595,387)`.

Why this is new:

- Attempts 217 and 218 deliberately used `treeY - 2`, which matched the earlier "two tiles above" instruction.
- The current request replaces that target rule with "on the headbutt tree on the 2 top tiles."
- This attempt only changes the final/settled target row to `treeY - 1`; it does not reintroduce forced Mankey spawning, tree visibility hacks, or a new movement system.

Implementation shape:

- Change `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET` from `2` to `1`.
- Rename the settled predicate to `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`.
- Keep the direct target scan, bounded jump graph search, and first-hop reconstruction from Attempt 218.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test374.nds` into the Delta ROM folder.
- Build warnings were limited to existing unused helpers/diagnostic symbols on this movement branch plus the existing unused `bsys` battle parameter warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

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
