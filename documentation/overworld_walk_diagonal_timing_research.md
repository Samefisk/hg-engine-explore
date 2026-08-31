# Overworld Walk: diagonal movement and exact frame timing

> **Status: pre-implementation research.** Its descriptions of the "current"
> path predate exact-frame and diagonal Walk. The active timing contract is
> [`overworld_walk_frame_timing_spec.md`](overworld_walk_frame_timing_spec.md),
> and current system ownership is in
> [`overworld-system/architecture.md`](overworld-system/architecture.md).

## Short answer

The current ordinary `Walk` path is cardinal-only and uses the game's stock held-movement commands. The four profile speed values select fixed commands for 16, 8, 4, or 2 frames per tile. Diagonal movement exists only in the custom Hop and chain-reposition paths. Mounted ordinary walking also uses the stock cardinal path: it starts the same held command on the player and the mounted Pokémon.

An exact `1..32` frames-per-tile Walk is feasible. It should be an explicit flat-motion mode that reuses the custom Jump interpolation and lifecycle code, but it must keep the stock Walk rules for collision, logical tile commitment, step completion, effects, chain counting, map streaming, and mounted presentation. It must not be implemented as a zero-height Hop at the behavior level.

There is no Pokémon-specific leg-walk animation system in the current code. Stock movement supplies a generic sprite movement phase. A sprite only appears to move its legs if its graphics have suitable frames. The new Walk engine should preserve that generic phase; it does not need a new leg-animation option.

## What the current code does

### Direction selection and collision

- Directed ordinary movement builds at most two cardinal candidates. It tries the dominant axis first and then the other axis. It does not emit a diagonal direction (`src/overworld_follower_selector_overlay/follower_selector_ui.c:249-268`). Random ordinary movement also shuffles only the four cardinal directions (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:6873-6879`).
- The ordinary one-tile path validates terrain, reservations, native direction blocking, and the player tile before it starts a command (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:6444-6547`).
- Vanilla HeartGold itself has only north, south, west, east, and none as field-map directions (`.codex-reference/pokeheartgold/include/constants/global_fieldmap.h:4-10`). When two D-pad axes are held, vanilla resolves them to one cardinal direction instead of moving diagonally (`.codex-reference/pokeheartgold/asm/unk_0205CB48.s:2355-2449`).
- Custom Hop accepts a diagonal displacement only when non-cardinal travel is allowed and the two axes have equal magnitude. It still keeps one cardinal value for facing (`src/pokemon_move_history_task6_overlay/overworld_wild_hop_trajectory.c:36-71`). Chain reposition already searches eight neighboring offsets and can launch a custom move to one of them (`src/pokemon_move_history_task6_overlay/overworld_wild_hop_trajectory.c:255-342`).

Therefore, changing the speed field alone will not add diagonal ordinary walking. That requires an eight-neighbor Walk planner and diagonal collision rules. A diagonal Walk should require a valid destination and a valid corner route; it must not cut through two blocked cardinal edges. Hop landing validation alone is too permissive because Hop is allowed to cross obstacles.

### Timing and exact motion

- Current profile speeds are tiers `1..4` (`include/overworld_wild_movement.h:21-41`). The wild movement code maps them to held commands `0x08`, `0x0C`, `0x10`, and `0x14` (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:3804-3816`).
- In vanilla, those command groups move one tile in exactly 16, 8, 4, and 2 frames respectively (`.codex-reference/pokeheartgold/asm/unk_02062108.s:719-931`). The shared command setup stores the per-frame delta and duration, and the runner applies it until completion (`.codex-reference/pokeheartgold/asm/unk_02062108.s:594-663`).
- Ordinary wild Walk starts that stock held command and tracks ownership until it finishes (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:6032-6053,6066-6126,10227-10270`).
- The custom Jump engine already performs exact X, Y, and height interpolation for an arbitrary total duration. It updates rendered/logical coordinates as the object crosses tiles and can use a zero arc (`src/pokemon_move_history_task6_overlay/overworld_wild_hop_trajectory.c:374-468`; `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:13613-13794`). Today its flat-Walk case is reached by chain reposition, not by normal Walk.

This makes the clean seam a shared **custom flat movement** service. It can reuse Jump's fixed-point interpolation, storage, and frame task, while exposing Walk-specific start and completion callbacks.

### Logical tiles, effects, skids, acceleration, and chains

- Vanilla commits the destination logical tile when a movement command starts; the sprite catches up over the command frames (`.codex-reference/pokeheartgold/asm/unk_0205FD20.s:2283-2316,2734-2746`). Player step events occur only after physical movement completes (`.codex-reference/pokeheartgold/asm/unk_0205CB48.s:401-506`; `.codex-reference/pokeheartgold/src/field/field_control.c:171-175,211-215`).
- Wild movement records the origin before it starts, then records the completed direction and distance, applies surface height, and updates its last-known tile at completion (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:5556-5604`).
- A completed Walk counts only when it is a real one-tile locomotion decision. Skid completion returns before chain accounting, and deferred chain pauses commit after skid handling (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:8123-8214`). The mount chain controller likewise decrements its counter once per completed Walk decision, not per render tile or skid tile (`src/overworld_mount_overlay/overworld_mount_overlay.c:140-223`).
- Current acceleration increments a tier after `tilesToAccelerate` completed one-tile Walks. Skids and other distances do not accelerate it (`src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c:382-503`).
- Current stop/turn skid length is tier-based: speed 3 gives one tile and speed 4 gives two (`src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c:269-380`). Dirt uses the landing particle, and stomp uses the same particle plus its sound (`src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c:6142-6167,8175-8205`; `src/overworld_mount_overlay/overworld_mount_overlay.c:856-872`).

The custom Walk engine must keep these semantic boundaries. Intermediate render tiles must not become extra steps, extra chain moves, or extra acceleration points. One accepted Walk command must produce exactly one completed Walk decision.

### Mounted presentation and map streaming

- A mounted Pokémon resolves the existing owner profile, including overrides, and copies the ordinary Walk speed, maximum, acceleration, and Walk options (`src/overworld_mount_overlay/overworld_mount_overlay.c:613-663`).
- Mounted input currently resolves to one cardinal direction (`src/overworld_mount_overlay/overworld_mount_overlay.c:741-756`). Ordinary mounted Walk remains on `PlayerAvatar_MoveControl` (`src/overworld_mount_overlay/overworld_mount_overlay.c:1714-1733`). The mount layer then replaces the selected command with the current speed-tier command and starts it on both player and follower (`src/overworld_mount_overlay/overworld_mount_overlay.c:1750-1835`).
- The player is authoritative at completion. The follower is synchronized to the player's tile, effects are emitted, and acceleration advances once (`src/overworld_mount_overlay/overworld_mount_overlay.c:895-960`). Presentation copies the player's position and height offsets to the follower/rider (`src/overworld_mount_overlay/overworld_mount_overlay.c:417-499`).
- Long mounted Hop/Teleport motions explicitly advance the land-stream anchor one tile at a time because custom movement can outrun normal player streaming (`src/overworld_mount_overlay/overworld_mount_overlay.c:1063-1128`). Their interpolation also updates the player's logical tile while crossing render tiles (`src/overworld_mount_overlay/overworld_mount_overlay.c:1188-1316`).

For mounted custom Walk, player and Pokémon should use one shared motion instance. The player remains authoritative; the follower and rider presentation copy that motion every frame. Starting two independent custom motions risks the separation bugs already seen with mounted Hop. A completed one-tile Walk must still pass through the normal player step/event boundary so map streaming and warps retain their current timing. Warps must not trigger on an intermediate interpolated coordinate.

## Recommended `1..32` profile model

Use frames directly:

- `walkTravelTime`: `1..32`; larger is slower.
- `fastestWalkTravelTime`: `1..32`; clamp it to be no slower than the base, so `fastestWalkTravelTime <= walkTravelTime`.
- Keep `tilesToAccelerate`.
- Add `walkAccelerationStep`: the number of frames removed after each completed acceleration interval.
- Update with `currentTime = max(fastestWalkTravelTime, currentTime - walkAccelerationStep)`.
- Migrate existing tiers as `1 -> 16`, `2 -> 8`, `3 -> 4`, `4 -> 2`.
- Treat a stomp threshold as frame time: `0` disables it; otherwise stomp when `currentTime <= threshold`.

The profile and override code currently assumes that a larger number means faster movement (`src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c:642-685,886-1002`). Frame timing reverses that meaning. Exact and relative overrides can remain, but the bound names and comparisons must change:

- `+N` frames means slower; `-N` means faster.
- Replace “at least speed” with “no slower than” and compare against a maximum frame count.
- Replace “at most speed” with “no faster than” and compare against a minimum frame count.

Mounted movement should continue to read the resolved owner profile. This preserves the mounted override profile without a separate mount-speed system.

For the first conversion, a workable skid rule is: 5 or more frames has no speed skid, 3-4 frames gives one tile, 2 frames gives two tiles, and 1 frame gives four tiles. Skid travel time can be twice the current Walk time, capped at 32. This is a policy choice, not an engine limit, and can be reviewed after play testing.

## Implementation shape

1. Change profile, editor, generated data, override math, and migration to frame timing.
2. Extract a shared flat-motion runtime from the current custom Jump interpolation. Give it a target displacement, exact duration, cardinal facing, and Walk-specific completion callback.
3. Move wild cardinal Walk to that runtime first. Preserve current collision, logical origin/destination bookkeeping, effects, acceleration, skid, and chain callbacks.
4. Route existing flat chain reposition through the same runtime. Add eight-neighbor ordinary Walk planning only where the profile permits it.
5. Move mounted cardinal Walk to one player-authoritative flat motion. Keep vanilla player step completion, map streaming, and warp timing.
6. Add mounted diagonal input only as a separate input/collision change. Vanilla input resolution cannot produce it.

## Sprite animation correction

The earlier concern about arbitrary Pokémon leg-animation timing was misplaced. There is no separate Pokémon leg system or profile option. Stock commands set a generic movement-animation mode (`.codex-reference/pokeheartgold/asm/unk_02062108.s:594-624`; `.codex-reference/pokeheartgold/src/map_object.c:1179-1185`). The renderer advances a generic walk or run phase and resets it on direction changes (`.codex-reference/pokeheartgold/asm/overlay_01_021F72DC.s:562-605,900-956,3234-3265`).

The custom flat engine should preserve or emulate that generic phase at a rate derived from the selected travel time. It should not invent a Pokémon leg animation layer.
