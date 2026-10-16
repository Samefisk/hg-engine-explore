"""Offline walk check: replay moves over map data and predict where you end up.

  python3 -B -m tools.maps.walk --map 67 --at 559 393 --facing down --moves "DOWN 1"
  python3 -B -m tools.maps.walk --map 542 --at 20 5 --moves "DOWN 1, UP 1" --json
  python3 -B -m tools.maps.walk --check cases.json

Reads rom.nds plus the data/maps override tree (--vanilla: rom.nds only) and
walks the player tile by tile, with a trace line and a reason per step. It is
a pre-build check of what the edited data should do, not proof: walking and
warps are still proven in game with memory reads (README "Prove it in game").

Moves are comma separated: "DIR [N]" takes N whole steps (default 1) with
DIR held, "FACE DIR" only turns. DIR is UP, DOWN, LEFT or RIGHT (north is -z).
In game a press in a new direction first turns the player
(PlayerAvatar_GetFootStepKind): a short tap only turns, and the step needs
the key held past the turn. A step here is "turn if needed, then the full
step", so drive a live test with a long enough hold, or teleport with the
right --facing first. Remaining steps continue after a warp (the key is still
held when the new map starts).

The rules follow the decompilation (.codex-reference/pokeheartgold-full/src);
the citations are in the comments. Anything the model does not cover stops
the walk with status "unmodelled" and reason "unmodelled behavior 0xNN"
instead of guessing. Not modelled: scripts (coord events are only noted,
NPC event flags are assumed clear, NPCs stand on their event tile, the
following Pokémon is ignored), gym puzzles (Gymmick_CheckCollision), dynamic
height plates, ice and spin tiles, Rock Climb/Waterfall/Whirlpool/Strength,
the bike, and maps using the simple (no-BDHC) terrain mode.

Check file (--check): a JSON list of cases, or {"cases": [...]}:

  {"name": "...", "map": 67, "at": [559, 393], "facing": "down",
   "moves": "DOWN 1", "surf": false, "vanilla": false, "expect": [541, 32, 57]}

It prints one line per case and exits 1 if any case ends elsewhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import codecs, world
from .style.bdhc_gen import NEAREST, Query

REPO = Path(__file__).resolve().parents[2]

# Directions as the game numbers them (DIR_NORTH..DIR_EAST) and their deltas
# (gDirectionDeltaX/Y, src/map_object_update.c:117-118).
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
DIR_NAMES = ("up", "down", "left", "right")
DX = (0, 0, -1, 1)
DZ = (-1, 1, 0, 0)

# enum TILE_BEHAVIOR (include/constants/metatile_behavior.h)
B_TALL_GRASS, B_VERY_TALL_GRASS = 2, 3
B_WHIRLPOOL, B_WATERFALL, B_ICE, B_34 = 17, 19, 32, 34
B_JUMP_EAST, B_JUMP_WEST, B_JUMP_NORTH, B_JUMP_SOUTH = 56, 57, 58, 59
B_LADDER_NORTH, B_LADDER_SOUTH, B_LADDER_DOWN = 60, 61, 62
B_SLIDES = (64, 65, 66, 67)
B_ROCK_CLIMB = (75, 76)
B_STAIRS_EAST, B_STAIRS_WEST = 94, 95
B_ENTRANCE_EAST, B_ENTRANCE_WEST, B_ENTRANCE_NORTH, B_ENTRANCE_SOUTH = 98, 99, 100, 101
B_WARP_PANEL, B_DOOR = 103, 105
B_ESCALATOR_FLIP, B_ESCALATOR = 106, 107
B_WARP_EAST, B_WARP_WEST, B_WARP_NORTH, B_WARP_SOUTH = 108, 109, 110, 111
B_BRIDGE_START, B_BRIDGES, B_BRIDGE_OVER_WATER = 112, (113, 114, 115), 115
B_NONE = 0xFF

# Ledge behavior that is jumped when moving in a direction
# (MapObject_IsLedgeInDirection, src/player_avatar_movement.c:945-980).
JUMP_FOR_DIR = {UP: B_JUMP_NORTH, DOWN: B_JUMP_SOUTH, LEFT: B_JUMP_WEST, RIGHT: B_JUMP_EAST}
# MetatileBehavior_IsBlocked{North,South,West,East} (src/metatile_behavior.c:438-452).
BLOCKED = {UP: frozenset({50, 52, 53, B_LADDER_NORTH, 73}), DOWN: frozenset({51, 54, 55, B_LADDER_SOUTH, 73}),
           LEFT: frozenset({49, 53, 55, 74}), RIGHT: frozenset({48, 52, 54, 74})}
OPPOSITE = (DOWN, UP, RIGHT, LEFT)
# TILE_BEHAVIOR_FLAG_SURFABLE in sMetatileBehaviorFlags (src/metatile_behavior.c:7-264).
SURFABLE = frozenset({16, 17, 18, 19, 20, 21, 25, 42, 80, 81, 82, 83, 115, 120, 124})
# FieldSystem_GetHeightStep: a height difference of 0x14000 fx (1.25 tiles) or more blocks
# (src/field_terrain.c:255-276).
HEIGHT_STEP_LIMIT = 0x14000
DYNAMIC_ANCHOR = 0x100   # warp anchor 0x100 (header 0xFFF): "back where you came from"

# Collision result bits (PlayerAvatar_CheckCollision, src/player_avatar_movement.c:890-913).
C_BLOCKED, C_OBJECT, C_LEDGE, C_WATER = 1, 2, 4, 0x20


class Terrain:
    """What the walk reads. WorldTerrain wraps tools.maps.world; tests pass a fake."""

    def matrix_id(self, map_id: int) -> int: ...
    def tile(self, matrix_id: int, x: int, z: int): ...            # (blocked, behavior) or None
    def height(self, matrix_id: int, x: int, z: int, current_y: int): ...  # fx32 or None (no plate)
    def zone(self, matrix_id: int, loaded_map: int, x: int, z: int) -> int: ...
    def events(self, map_id: int) -> dict: ...
    def has_map(self, map_id: int) -> bool: ...


class WorldTerrain(Terrain):
    def __init__(self, w: "world.World"):
        self.world = w
        self._queries: dict[int, Query | None] = {}

    def matrix_id(self, map_id):
        return self.world.headers[map_id]["matrixId"]

    def _land(self, matrix_id, x, z):
        matrix = self.world.member("matrix", matrix_id)
        if x < 0 or z < 0:
            return None
        cx, cz = x // codecs.TILE_GRID, z // codecs.TILE_GRID
        if not (cx < matrix["width"] and cz < matrix["height"]):
            return None
        land_id = matrix["landData"][cz][cx]
        if land_id == 0xFFFF or land_id >= len(self.world.raw["land"]):
            return None
        return land_id

    def tile(self, matrix_id, x, z):
        land_id = self._land(matrix_id, x, z)
        if land_id is None:
            return None
        tiles = self.world.member("land", land_id)["tiles"]
        lx, lz = x % codecs.TILE_GRID, z % codecs.TILE_GRID
        return tiles["collision"][lz][lx] == "#", int(tiles["behavior"][lz].split()[lx], 16)

    def height(self, matrix_id, x, z, current_y):
        land_id = self._land(matrix_id, x, z)
        if land_id is None:
            return None
        if land_id not in self._queries:
            bdhc = self.world.member("land", land_id).get("bdhc")
            self._queries[land_id] = Query(bdhc) if bdhc and bdhc.get("strips") else None
        query = self._queries[land_id]
        if query is None:
            return None
        # Terrain_CalcHeight: BDHC space is chunk-local, centred on the chunk; the
        # player stands on the tile centre (src/field_terrain.c:81-118).
        lx, lz = x % codecs.TILE_GRID, z % codecs.TILE_GRID
        return query.height_fx((lx * 16 + 8 - 256) * 4096, (lz * 16 + 8 - 256) * 4096, current_y, NEAREST)

    def zone(self, matrix_id, loaded_map, x, z):
        # MapMatrix_GetMapHeader; without a header layer every cell is the loaded map
        # (src/map_matrix.c:46-51, src/field/fieldmap.c:387-399).
        matrix = self.world.member("matrix", matrix_id)
        cx, cz = x // codecs.TILE_GRID, z // codecs.TILE_GRID
        if matrix["headers"] is None or not (0 <= cx < matrix["width"] and 0 <= cz < matrix["height"]):
            return loaded_map
        return matrix["headers"][cz][cx]

    def events(self, map_id):
        return self.world.member("events", self.world.headers[map_id]["eventsBank"])

    def has_map(self, map_id):
        if not 0 <= map_id < len(self.world.headers):
            return False
        header = self.world.headers[map_id]
        return (header["matrixId"] < len(self.world.raw["matrix"])
                and header["eventsBank"] < len(self.world.raw["events"]))


def load_terrain(vanilla: bool = False, rom: Path | None = None, overrides: Path | None = None) -> WorldTerrain:
    base = world.load_base(world.RomSource(rom or REPO / "rom.nds"))
    if vanilla:
        return WorldTerrain(base)
    return WorldTerrain(world.apply_overrides(base, overrides or REPO / "data/maps"))


class Stop(Exception):
    """The walk cannot continue faithfully (unmodelled behavior or bad data)."""

    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def _y_coord(y_fx: int) -> int:
    """MapObject y coordinate: (position.y >> 3) / FX32_ONE, C division (map_object.c:639-641)."""
    v = y_fx >> 3
    return int(v / 4096)


@dataclass
class Walker:
    terrain: Terrain
    map_id: int
    x: int
    z: int
    facing: int = DOWN
    surf: bool = False          # Surf may be used: walking into surfable water mounts
    surfing: bool = False
    objects: bool = True        # NPC object events block
    trace: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def __post_init__(self):
        if not self.terrain.has_map(self.map_id):
            raise Stop("error", f"map {self.map_id} has no header/events")
        self.matrix = self.terrain.matrix_id(self.map_id)
        self.loaded_map = self.map_id
        self.y = self._ground_y(self.x, self.z, 0)
        self.on_bridge = False
        self.dynamic = None         # (map, warp index) a 0x100 warp returns to
        start = self._tile(self.x, self.z)
        if start is None:
            raise Stop("error", f"start tile ({self.x}, {self.z}) is outside map {self.map_id}'s land")
        if self.surf and start[1] in SURFABLE:
            self.surfing = True

    # ---------------------------------------------------------------- data

    def _tile(self, x, z):
        return self.terrain.tile(self.matrix, x, z)

    def _behavior(self, x, z) -> int:
        tile = self._tile(x, z)
        return B_NONE if tile is None else tile[1]   # GetMetatileBehavior: 0xFF when not loaded

    def _ground_y(self, x, z, current):
        h = self.terrain.height(self.matrix, x, z, current)
        return 0 if h is None else h    # Terrain_CalcHeight returns 0 without a plate

    def _warp_at(self, x, z):
        # Field_GetWarpEventAtXYPos: first warp of the current map at x/z (src/map_events.c:63-73).
        for index, warp in enumerate(self.terrain.events(self.map_id).get("warps", [])):
            if warp["x"] == x and warp["z"] == z:
                return index, warp
        return None

    def _object_at(self, x, z):
        if not self.objects:
            return None
        # MapObject_IsTileOccupiedInLink: same tile and |dy| < 2 (src/map_object_movement_utilities.c:15-46).
        for obj in self.terrain.events(self.map_id).get("objects", []):
            if obj["x"] != x or obj["z"] != z:
                continue
            h = self.terrain.height(self.matrix, x, z, obj.get("y", 0))
            oy = h if h is not None else obj.get("y", 0)
            if abs(_y_coord(oy) - _y_coord(self.y)) < 2:
                return obj
        return None

    def where(self):
        return [self.map_id, self.x, self.z]

    # ---------------------------------------------------------------- rules

    def collision(self, d):
        """PlayerAvatar_CheckCollision for a step in direction d: (bits, reasons)."""
        tx, tz = self.x + DX[d], self.z + DZ[d]
        tile = self._tile(tx, tz)
        behavior = B_NONE if tile is None else tile[1]
        raw, reasons = 0, []
        # FieldSystem_CheckCollisionHeightAndGimmick (src/field_terrain.c:297-314): the
        # height step first, the collision bit only on level ground.
        h = self._ground_y(tx, tz, self.y)
        if abs(h - self.y) >= HEIGHT_STEP_LIMIT and tile is not None:
            raw |= 2 | 8
            reasons.append(f"height change ({(h - self.y) / 4096 / 16:+.2f} tiles)")
        elif tile is not None and tile[0]:
            raw |= 2
            reasons.append("blocked by collision")
        # MapObject_IsMoveBlockedByBehavior (src/map_object_movement_utilities.c:125-138).
        if behavior == B_NONE:
            raw |= 2
            reasons.append("map edge" if tile is None else "blocked by behavior 0xff")
        else:
            here = self._behavior(self.x, self.z)
            if here in BLOCKED[d]:
                raw |= 2
                reasons.append(f"blocked by one-way behavior 0x{here:02x} (exit)")
            if behavior in BLOCKED[OPPOSITE[d]]:
                raw |= 2
                reasons.append(f"blocked by one-way behavior 0x{behavior:02x} (entry)")
        obj = self._object_at(tx, tz)
        if obj is not None:
            raw |= 4
            flag = f", hidden if flag {obj['eventFlag']} is set" if obj.get("eventFlag") else ""
            reasons.append(f"blocked by object id {obj['id']}{flag}")
        bits = 0
        if raw & 0xA:
            bits |= C_BLOCKED
        if raw & 4:
            bits |= C_OBJECT
        if behavior == JUMP_FOR_DIR[d]:
            bits |= C_LEDGE
        if self._is_water(behavior):
            bits |= C_WATER
        return bits, reasons, behavior

    def _is_water(self, behavior):
        # MapObject_CheckWaterBehavior (src/map_object_movement_utilities.c:140-155). Behavior
        # 34 only counts for two non-player sprites.
        if behavior == B_BRIDGE_OVER_WATER:
            return not self.on_bridge
        return behavior in SURFABLE

    def _can_surf_onto(self, behavior):
        # Field_PlayerCanSurfOnTile (src/field/player_avatar_actions.c:502-516).
        if behavior not in SURFABLE:
            return False
        here = self._behavior(self.x, self.z)
        if (here in B_BRIDGES or here == B_BRIDGE_START) and self.on_bridge:
            return False
        return here != B_34

    def _hold_transition(self, d):
        """FieldSystem_CheckMapTransition (src/field/field_control.c:490-575): warps taken by
        holding a direction while standing (doors, exit mats, stairs, ladders)."""
        here = self._behavior(self.x, self.z)
        if here in (B_LADDER_NORTH, B_LADDER_SOUTH):
            want = UP if here == B_LADDER_NORTH else DOWN
            warp = self._warp_at(self.x, self.z)
            return (warp, "ladder") if d == want and warp else None
        fx, fz = self.x + DX[d], self.z + DZ[d]
        front = self._tile(fx, fz)
        if not (front and front[0]):          # facing tile must have the collision bit
            return None
        warp = self._warp_at(fx, fz)
        if warp and front[1] == B_DOOR:
            return warp, "door"
        need = {B_ENTRANCE_EAST: RIGHT, B_WARP_EAST: RIGHT, B_ENTRANCE_WEST: LEFT, B_WARP_WEST: LEFT,
                B_ENTRANCE_SOUTH: DOWN, B_WARP_SOUTH: DOWN, B_STAIRS_EAST: RIGHT, B_STAIRS_WEST: LEFT}
        if here in need and need[here] != d:
            return None
        warp = self._warp_at(self.x, self.z)
        if warp is None:
            return None
        if here == B_DOOR:
            return warp, "door"
        if here in (B_STAIRS_EAST, B_STAIRS_WEST):
            return warp, "stairs"
        if here in need:
            return warp, "exit mat"
        return None

    def _step_transition(self):
        """FieldSystem_CheckTransition after a finished step (src/field/field_control.c:703-748)."""
        warp = self._warp_at(self.x, self.z)
        if warp is None:
            return None
        here = self._behavior(self.x, self.z)
        if here == B_ESCALATOR_FLIP:
            if self.facing not in (LEFT, RIGHT):
                return None
            self.facing = OPPOSITE[self.facing]
            return warp, "escalator"
        if here == B_ESCALATOR:
            return (warp, "escalator") if self.facing in (LEFT, RIGHT) else None
        if here in (B_ENTRANCE_NORTH, B_WARP_NORTH):
            return warp, "warp tile"
        if here == B_WARP_PANEL:
            return warp, "warp panel"
        if here == B_LADDER_DOWN:
            return warp, "ladder"
        return None

    def _move_to(self, x, z):
        self.x, self.z = x, z
        self.y = self._ground_y(x, z, self.y)   # MapObject_UpdateHeight: nearest plate
        # MapObject_UpdateOnBridgeFlag (src/map_object_update.c:627-633).
        behavior = self._behavior(x, z)
        if behavior == B_BRIDGE_START:
            self.on_bridge = True
        elif self.on_bridge and behavior not in B_BRIDGES:
            self.on_bridge = False
        # FieldMap_ChangeZone: the map ID follows the matrix header layer.
        zone = self.terrain.zone(self.matrix, self.loaded_map, x, z)
        if zone != self.map_id:
            self.notes.append(f"zone {self.map_id} -> {zone}")
            if not self.terrain.has_map(zone):
                raise Stop("error", f"matrix cell maps to map {zone}, which has no header/events")
            self.map_id = zone

    def _warp(self, found, kind, entry):
        index, warp = found
        entrance = (self.map_id, index)
        entry["via"] = [self.map_id, warp["x"], warp["z"]]
        if warp["anchor"] == DYNAMIC_ANCHOR:
            # FieldSystem_MapConnection: anchor 0x100 uses the saved dynamic warp.
            if self.dynamic is None:
                raise Stop("unmodelled", "dynamic warp (anchor 0x100) back to an origin this walk did not see")
            target, anchor = self.dynamic
        else:
            target, anchor = warp["header"], warp["anchor"]
        if not self.terrain.has_map(target):
            raise Stop("error", f"warp {index} leads to map {target}, which has no header/events")
        targets = self.terrain.events(target).get("warps", [])
        if anchor >= len(targets):
            raise Stop("error", f"warp {index} leads to anchor {anchor}; map {target} has {len(targets)} warps")
        landing = targets[anchor]
        # FieldSystem_EnterLocation: the player lands on the target warp's tile
        # (src/field_warp_tasks.c:197-215).
        self.map_id = self.loaded_map = target
        self.matrix = self.terrain.matrix_id(target)
        self.x, self.z = landing["x"], landing["z"]
        self.y = self._ground_y(self.x, self.z, 0)
        self.on_bridge = False
        if landing["anchor"] == DYNAMIC_ANCHOR:
            self.dynamic = entrance
        entry["kind"], entry["reason"] = "warp", f"{kind}: warp {index} -> map {target} warp {anchor}"
        # Fade arrivals on a door tile walk one step south (FieldTransition_EnterWithFade,
        # src/field_transition_effects.c:509-560; DoorTransition_WalkOutOfDoor uses
        # MOVEMENT_STEP_DOWN). Warp panels arrive with Task_WarpPanel, which does not.
        if kind != "warp panel" and self._behavior(self.x, self.z) == B_DOOR:
            self.facing = DOWN
            self._move_to(self.x, self.z + 1)
            entry["reason"] += ", stepped out of the door"

    def _after_step(self, entry):
        """FieldSystem_ProcessStep (src/field/field_control.c:632-660)."""
        for coord in self.terrain.events(self.map_id).get("coords", []):
            if (coord["x"] <= self.x < coord["x"] + coord["w"] and coord["z"] <= self.z < coord["z"] + coord["h"]):
                entry.setdefault("notes", []).append(
                    f"coord event script {coord['scriptId']} runs if var {coord['var']} == {coord['val']} (not modelled)")
                break
        found = self._step_transition()
        if found:
            self._warp(found[0], found[1], entry)
            return
        here = self._behavior(self.x, self.z)
        # Forced movement (ice, gPlayerForcedMovementBehaviors) and spin tiles
        # (PlayerAvatar_TryStartSpinSlide, src/field/spin_slide.c:21-36).
        if here == B_ICE or here in B_SLIDES:
            raise Stop("unmodelled", f"unmodelled behavior 0x{here:02x}")

    def step(self, d):
        """One held step in direction d; appends one trace entry."""
        entry = {"move": DIR_NAMES[d].upper(), "from": self.where()}
        self.trace.append(entry)
        self.notes = []
        if self.facing != d:
            entry["turned"] = True
        self.facing = d
        try:
            self._step(d, entry)
        finally:
            entry["to"] = self.where()
            entry["facing"] = DIR_NAMES[self.facing]
            if self.notes:
                entry.setdefault("notes", []).extend(self.notes)

    def _step(self, d, entry):
        tx, tz = self.x + DX[d], self.z + DZ[d]
        # Field_PlayerAvatar_TryStopSurfing runs before walking (src/field/player_avatar_actions.c:614-629).
        if self.surfing:
            bits, reasons, behavior = self.collision(d)
            if bits == 0:
                self.surfing = False
                self._move_to(tx, tz)
                entry["kind"], entry["reason"] = "surf dismount", "moved onto land (stopped surfing)"
                return
        found = self._hold_transition(d)
        if found:
            self._warp(found[0], found[1], entry)
            return
        bits, reasons, behavior = self.collision(d)
        entry["behavior"] = f"0x{behavior:02x}"
        if self.surfing:
            # PlayerAvatar_FootStep while surfing: only open water moves (src/player_avatar_movement.c:663-674).
            if bits in (0, C_WATER):
                self._move_to(tx, tz)
                entry["kind"], entry["reason"] = "moved", "moved (surfing)"
                self._after_step(entry)
            else:
                self._blocked(entry, bits, reasons, behavior)
            return
        if bits & C_LEDGE:
            # Movement 0x38 (MapObjectMovementCmd056-059): a 2-tile jump, landing unchecked.
            self._move_to(tx, tz)
            self._move_to(tx + DX[d], tz + DZ[d])
            entry["kind"], entry["reason"] = "ledge jump", f"ledge jump over 0x{behavior:02x}"
            self._after_step(entry)
            return
        if bits == 0:
            self._move_to(tx, tz)
            entry["kind"], entry["reason"] = "moved", "moved"
            self._after_step(entry)
            return
        if bits == C_WATER and self.surf and self._can_surf_onto(behavior):
            # Surf from the field menu or A on water: Task_Surf jumps one tile (movement 52).
            self.surfing = True
            self._move_to(tx, tz)
            entry["kind"], entry["reason"] = "surf mount", "started surfing (Surf assumed used)"
            return
        self._blocked(entry, bits, reasons, behavior)

    def _blocked(self, entry, bits, reasons, behavior):
        entry["kind"] = "blocked"
        if bits == C_WATER:
            entry["reason"] = "surf needed" if not self.surfing else "blocked"
            return
        primary = reasons[0] if reasons else "blocked"
        for wanted in ("map edge", "height change", "blocked by collision", "blocked by one-way", "blocked by object"):
            match = next((r for r in reasons if r.startswith(wanted)), None)
            if match:
                primary = match
                break
        if behavior in B_ROCK_CLIMB or behavior in (B_WATERFALL, B_WHIRLPOOL):
            entry.setdefault("notes", []).append(
                f"behavior 0x{behavior:02x} needs a field move (Rock Climb/Waterfall/Whirlpool; not modelled)")
        entry["reason"] = primary
        if len(reasons) > 1:
            entry["details"] = reasons


def parse_moves(text: str) -> list[tuple[str, int, int]]:
    """'DOWN 3, FACE LEFT' -> [('step', DOWN, 3), ('face', LEFT, 1)]."""
    names = {name.upper(): i for i, name in enumerate(DIR_NAMES)}
    out = []
    for part in text.replace(";", ",").split(","):
        words = part.split()
        if not words:
            continue
        op = "step"
        if words[0].upper() in ("FACE", "TURN"):
            op, words = "face", words[1:]
        if not words or words[0].upper() not in names:
            raise ValueError(f"bad move {part.strip()!r}: use UP/DOWN/LEFT/RIGHT [N] or FACE DIR")
        count = 1
        if len(words) > 1:
            if op == "face" or len(words) > 2 or not words[1].isdigit():
                raise ValueError(f"bad move {part.strip()!r}")
            count = int(words[1])
        out.append((op, names[words[0].upper()], count))
    return out


def walk(terrain: Terrain, map_id: int, x: int, z: int, moves: str, facing: int = DOWN,
         surf: bool = False, objects: bool = True) -> dict:
    """Replay `moves`; returns {start, final, status, reason?, trace}."""
    start = {"map": map_id, "x": x, "z": z, "facing": DIR_NAMES[facing]}
    try:
        plan = parse_moves(moves)
        walker = Walker(terrain, map_id, x, z, facing, surf=surf, objects=objects)
    except (ValueError, Stop) as error:
        reason = error.reason if isinstance(error, Stop) else str(error)
        return {"start": start, "final": None, "status": "error", "reason": reason, "trace": []}
    status, reason = "ok", None
    try:
        for op, d, count in plan:
            if op == "face":
                walker.facing = d
                walker.trace.append({"move": f"FACE {DIR_NAMES[d].upper()}", "from": walker.where(),
                                     "to": walker.where(), "kind": "turned", "reason": "turned",
                                     "facing": DIR_NAMES[d]})
                continue
            for _ in range(count):
                walker.step(d)
    except Stop as stop:
        status, reason = stop.status, stop.reason
        if walker.trace:
            walker.trace[-1].update(kind=stop.status, reason=stop.reason)
    for i, entry in enumerate(walker.trace):
        entry["i"] = i
    out = {"start": start,
           "final": {"map": walker.map_id, "x": walker.x, "z": walker.z, "facing": DIR_NAMES[walker.facing],
                     "surfing": walker.surfing},
           "status": status, "trace": walker.trace}
    if reason:
        out["reason"] = reason
    return out


def format_result(result: dict) -> str:
    lines = []
    for entry in result["trace"]:
        turn = " (turned first)" if entry.get("turned") else ""
        via = f" at {_pos(entry['via'])}" if entry.get("via") else ""
        lines.append(f"{entry['i']:3d} {entry['move']:<10} {_pos(entry['from'])} -> {_pos(entry['to'])}  "
                     f"{entry.get('reason', '')}{via}{turn}")
        for note in entry.get("notes", []):
            lines.append(f"      note: {note}")
        for detail in entry.get("details", [])[1:]:
            lines.append(f"      also: {detail}")
    final = result["final"]
    if final:
        lines.append(f"final: map {final['map']} ({final['x']}, {final['z']}) facing {final['facing']}"
                     + (" surfing" if final["surfing"] else "") + f"  [{result['status']}]")
    if result.get("reason"):
        lines.append(f"{result['status']}: {result['reason']}")
    lines.append("prediction only: prove walking and warps in game with memory reads")
    return "\n".join(lines)


def _pos(p) -> str:
    return f"{p[0]}:({p[1]},{p[2]})"


def _dir(name) -> int:
    if isinstance(name, int):
        return name
    return DIR_NAMES.index(str(name).lower())


def run_checks(cases: list, terrains: dict) -> tuple[list, bool]:
    rows, ok = [], True
    for case in cases:
        terrain = terrains[bool(case.get("vanilla"))]
        result = walk(terrain, case["map"], case["at"][0], case["at"][1], case["moves"],
                      _dir(case.get("facing", "down")), bool(case.get("surf")), case.get("objects", True))
        final = result["final"]
        got = [final["map"], final["x"], final["z"]] if final else None
        passed = got == list(case["expect"]) and result["status"] == "ok"
        ok &= passed
        rows.append({"name": case.get("name", ""), "expect": list(case["expect"]), "got": got,
                     "status": result["status"], "reason": result.get("reason"), "pass": passed,
                     "result": result})
    return rows, ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.walk", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", type=int)
    parser.add_argument("--at", type=int, nargs=2, metavar=("X", "Z"))
    parser.add_argument("--facing", choices=DIR_NAMES, default="down")
    parser.add_argument("--moves", default="")
    parser.add_argument("--surf", action="store_true", help="Surf may be used (walking into water mounts)")
    parser.add_argument("--no-objects", action="store_true", help="NPC object events do not block")
    parser.add_argument("--vanilla", action="store_true", help="ignore data/maps/")
    parser.add_argument("--rom", type=Path, default=REPO / "rom.nds")
    parser.add_argument("--overrides", type=Path, default=REPO / "data/maps")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", type=Path, metavar="FILE.json")
    args = parser.parse_args(argv)

    if args.check:
        spec = json.loads(args.check.read_text())
        cases = spec["cases"] if isinstance(spec, dict) else spec
        base = world.load_base(world.RomSource(args.rom))
        terrains = {True: WorldTerrain(base), False: WorldTerrain(world.apply_overrides(base, args.overrides))}
        rows, ok = run_checks(cases, terrains)
        if args.json:
            print(json.dumps({"passed": ok, "cases": rows}, indent=1))
        else:
            for row in rows:
                mark = "PASS" if row["pass"] else "FAIL"
                extra = f" ({row['status']}: {row['reason']})" if row["reason"] else ""
                print(f"{mark} {row['name']}: expect {row['expect']}, got {row['got']}{extra}")
            print(f"{sum(r['pass'] for r in rows)}/{len(rows)} passed")
        return 0 if ok else 1

    if args.map is None or args.at is None:
        parser.error("--map and --at are required (or use --check)")
    terrain = load_terrain(args.vanilla, args.rom, args.overrides)
    result = walk(terrain, args.map, args.at[0], args.at[1], args.moves, DIR_NAMES.index(args.facing),
                  args.surf, not args.no_objects)
    print(json.dumps(result, indent=1) if args.json else format_result(result))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
