"""Engine transport and read-only observation for the shared development tools.

No scenario dispatch, fixture injection, proof registry, or accepted verdict lives
here. The worker authenticates the native module first, then calls initialize.
Importing this module alone does not open a core or load a ROM.
"""
from __future__ import annotations

import os
import hashlib
import struct
from functools import lru_cache
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
ROM = REPO / "test.nds"
NM = os.environ.get("ARM_NONE_EABI_NM", "arm-none-eabi-nm")
EXECUTED_FRAME_COUNT = 0
h = None
actor_probe = None
ACTOR_DESCRIPTOR = None
ACTOR_STATE_SIZE = 0
ACTOR_SYMBOLS = None  # Filled by the shared observer's existing linked-symbol load.
MOUNT_SYMBOLS = None
SELECTOR_SYMBOLS = None
WILD_SYMBOLS = None
WALK_SYMBOLS = None
TASK6_SYMBOLS = None
G_FIELD_SYS_PTR = WILD_STATE = SELECTOR_HIGHLIGHT = SELECTOR_STATE = 0
_native_cycle = None

# BoxPokemon GetSubstruct permutation (32 rows, four 32-byte blocks).
# Verified against the local vanilla pokemon.c GetSubstruct table. Read-only
# decoding uses this data; no verifier source file is a runtime dependency.
SUBSTRUCT_OFFSETS = (
    (0x00, 0x20, 0x40, 0x60),
    (0x00, 0x20, 0x60, 0x40),
    (0x00, 0x40, 0x20, 0x60),
    (0x00, 0x60, 0x20, 0x40),
    (0x00, 0x40, 0x60, 0x20),
    (0x00, 0x60, 0x40, 0x20),
    (0x20, 0x00, 0x40, 0x60),
    (0x20, 0x00, 0x60, 0x40),
    (0x40, 0x00, 0x20, 0x60),
    (0x60, 0x00, 0x20, 0x40),
    (0x40, 0x00, 0x60, 0x20),
    (0x60, 0x00, 0x40, 0x20),
    (0x20, 0x40, 0x00, 0x60),
    (0x20, 0x60, 0x00, 0x40),
    (0x40, 0x20, 0x00, 0x60),
    (0x60, 0x20, 0x00, 0x40),
    (0x40, 0x60, 0x00, 0x20),
    (0x60, 0x40, 0x00, 0x20),
    (0x20, 0x40, 0x60, 0x00),
    (0x20, 0x60, 0x40, 0x00),
    (0x40, 0x20, 0x60, 0x00),
    (0x60, 0x20, 0x40, 0x00),
    (0x40, 0x60, 0x20, 0x00),
    (0x60, 0x40, 0x20, 0x00),
    (0x00, 0x20, 0x40, 0x60),
    (0x00, 0x20, 0x60, 0x40),
    (0x00, 0x40, 0x20, 0x60),
    (0x00, 0x60, 0x20, 0x40),
    (0x00, 0x40, 0x60, 0x20),
    (0x00, 0x60, 0x40, 0x20),
    (0x20, 0x00, 0x40, 0x60),
    (0x20, 0x00, 0x60, 0x40),
)


def initialize(native):
    """Bind one authenticated native transport; initialization creates no core."""
    global h, actor_probe, ACTOR_DESCRIPTOR, ACTOR_STATE_SIZE
    global MOUNT_SYMBOLS, SELECTOR_SYMBOLS, WILD_SYMBOLS, WALK_SYMBOLS, TASK6_SYMBOLS
    global G_FIELD_SYS_PTR, WILD_STATE
    global SELECTOR_HIGHLIGHT, SELECTOR_STATE, _native_cycle
    if h is not None:
        raise RuntimeError("engine transport already initialized; use a new worker")
    if getattr(native, "ISOLATED_STARTUP_AUTHENTICATED", False) is not True:
        raise RuntimeError("native transport did not authenticate isolated startup")
    from tools.overworld import actor_probe as probe
    mount = linked_symbols(REPO / "build/overworld_mount_overlay_linked.o")
    selector = linked_symbols(REPO / "build/overworld_follower_selector_overlay_linked.o")
    # The native operation bridge selects these three tables by name. They
    # are actual runtime dependencies even without a direct rt.TABLE access.
    wild = linked_symbols(REPO / "build/overworld_wild_spawns_overlay_linked.o")
    walk = linked_symbols(REPO / "build/pokemon_move_history_overlay_linked.o")
    task6 = linked_symbols(REPO / "build/pokemon_move_history_task6_overlay_linked.o")
    descriptor = probe.load_debug_descriptor(REPO / "build/overworld-system.debug.json")
    G_FIELD_SYS_PTR = mount["gFieldSysPtr"]
    WILD_STATE = mount["sOverworldWildSpawnState"]
    SELECTOR_HIGHLIGHT = selector["sFollowerRecall"] + 0x63
    SELECTOR_STATE = selector["sFollowerSelectorInputState"]
    ACTOR_STATE_SIZE = descriptor["publicLayouts"]["actorState"]["size"]
    MOUNT_SYMBOLS, SELECTOR_SYMBOLS = mount, selector
    WILD_SYMBOLS, WALK_SYMBOLS, TASK6_SYMBOLS = wild, walk, task6
    ACTOR_DESCRIPTOR, actor_probe = descriptor, probe
    _native_cycle = native.cycle
    h = native
    h.cycle = tracked_cycle


MAIN_TASK_QUEUE_RETURN = 0x02000DEE
WILD_RUNTIME_PTR_OFFSET = 0xE4
FIELD_MAP_EVENTS_OFFSET = 0x14
FIELD_LOCATION_OFFSET = 0x20
FIELD_LAND_MANAGER_OFFSET = 0x2C
FIELD_MAP_MATRIX_OFFSET = 0x30
FIELD_TERRAIN_ATTRIBUTES_OFFSET = 0x5C
MAP_EVENTS_WARP_COUNT_OFFSET = 0x08
MAP_EVENTS_WARPS_OFFSET = 0x18
WARP_EVENT_SIZE = 12
TERRAIN_MATRIX_INDEX_COUNT = 225
TERRAIN_ATTRIBUTES_OFFSET = 226
TERRAIN_BLOCK_TILE_COUNT = 32 * 32
LAND_MANAGER_CHUNK_POINTERS_OFFSET = 0x90
LAND_MANAGER_CURRENT_MATRIX_INDEX_OFFSET = 0xA4
LAND_MANAGER_CURRENT_SLOT_OFFSET = 0xAC
MAP_MATRIX_MAX_CELLS = 799
MAP_MATRIX_HEADERS_OFFSET = 6
MAP_MATRIX_ALTITUDES_OFFSET = 0x644
MAP_MATRIX_MODELS_OFFSET = 0x964
FIELD_TERRAIN_DISPATCH_OFFSET = 0x60
FIELD_TERRAIN_CONFIG_OFFSET = 0x74
TERRAIN_MAX_BLOCKS = 16
LAND_MANAGER_MATRIX_OFFSET = 0xC0
LAND_MANAGER_WIDTH_OFFSET = 0xC4
LAND_MANAGER_HEIGHT_OFFSET = 0xC8
LAND_MANAGER_TILE_WIDTH_OFFSET = 0xCC
LAND_CHUNK_MATRIX_INDEX_OFFSET = 0x860
LAND_CHUNK_MODEL_LOADED_OFFSET = 0x864
BEHAVIOR_DATA_MAGIC = 0x4F574244
BEHAVIOR_DATA_VERSION = 75
BEHAVIOR_DATA_HEADER_SIZE = 84
SURFACE_TYPE_NAMES = ("rooftop", "signpost", "mailbox", "flowerbed", "canopy")
SURFACE_HEIGHT_PAGE_NATIVE_GROUND = 0x1F
SURFACE_ID_NATIVE_CANOPY = 0xFFFE
SURFACE_ID_NATIVE_GROUND = 0xFFFF


class Hooks:
    """Own read-only entry/return taps, including shared return addresses."""

    def __init__(self, rt, emu):
        self.rt, self.emu = rt, emu
        self.callbacks = {}
        self.error = None

    def add(self, address, callback):
        address &= ~1
        if address not in self.callbacks:
            self.callbacks[address] = []

            def dispatch(_address, _size):
                if self.error is not None:
                    return  # Preserve the first cause until the native cycle returns.
                try:
                    for item in tuple(self.callbacks.get(address, ())):
                        item()
                except Exception as error:
                    self.error = f"observation callback at {address:#010x}: {type(error).__name__}: {error}"

            self.emu.memory.register_exec(address, dispatch)
        self.callbacks[address].append(callback)
        return address, callback

    def remove(self, token):
        address, callback = token
        callbacks = self.callbacks.get(address, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if address in self.callbacks and not callbacks:
            self.emu.memory.register_exec(address, None)
            del self.callbacks[address]

    def observe_call(self, address, before, after):
        def entry():
            context = before()
            if context is None:
                return
            regs = self.emu.memory.register_arm9
            expected_sp = regs.sp
            token = None

            def returned():
                if self.emu.memory.register_arm9.sp != expected_sp:
                    return
                self.remove(token)
                after(context)

            token = self.add(regs.lr, returned)

        return self.add(address, entry)

    def close(self):
        for address in tuple(self.callbacks):
            self.emu.memory.register_exec(address, None)
        self.callbacks.clear()


def tracked_cycle(emu, frames, key_mask=None):
    """Count frames that the runtime scenario actually executes."""
    global EXECUTED_FRAME_COUNT
    EXECUTED_FRAME_COUNT += frames
    return _native_cycle(emu, frames, key_mask)


def linked_symbols(path):
    output = subprocess.run(
        [NM, "-n", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    symbols = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                symbols[parts[2]] = int(parts[0], 16)
            except ValueError:
                pass
    return symbols


def linked_symbol(symbols, name):
    """Resolve a source symbol even when the build adds a local clone suffix."""
    if name in symbols:
        return symbols[name]
    matches = [
        address
        for symbol, address in symbols.items()
        if symbol.startswith(f"{name}.")
    ]
    if len(matches) != 1:
        raise KeyError(name)
    return matches[0]


def unsigned(emu, address, size=4):
    return emu.memory.unsigned[address:address:size]


def signed(emu, address, size=4):
    return emu.memory.signed[address:address:size]


def field_map_id(emu):
    """Read the live field location instead of a subsystem's cached map."""
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    location = unsigned(emu, field_system + FIELD_LOCATION_OFFSET)
    return unsigned(emu, location) if location else None


def loaded_warp_events(emu):
    """Decode the currently loaded stock MapEvents warp table."""
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    events = unsigned(emu, field_system + FIELD_MAP_EVENTS_OFFSET)
    if events == 0:
        return []
    count = unsigned(emu, events + MAP_EVENTS_WARP_COUNT_OFFSET)
    warps = unsigned(emu, events + MAP_EVENTS_WARPS_OFFSET)
    if count > 64 or (count and warps == 0):
        return []
    return [
        {
            "index": index,
            "x": unsigned(emu, warps + index * WARP_EVENT_SIZE, 2),
            "y": unsigned(emu, warps + index * WARP_EVENT_SIZE + 2, 2),
            "header": unsigned(
                emu, warps + index * WARP_EVENT_SIZE + 4, 2
            ),
            "anchor": unsigned(
                emu, warps + index * WARP_EVENT_SIZE + 6, 2
            ),
            "height": unsigned(
                emu, warps + index * WARP_EVENT_SIZE + 8
            ),
        }
        for index in range(count)
    ]


def loaded_terrain_cell(emu, x, y):
    """Read one verified loaded metatile, or None when its store is unknown.

    This reads native memory only: no engine calls, frames, grid scan or cache.
    Stock field dispatch (unk_02054648.s) selects full attributes or the four
    rolling blocks (ov01_021F654C/635C/65E4). A rolling chunk's matrix tag is
    assigned before loading: also require completion and no pending reuse.
    Provenance describes this read, not a completed-game-frame observation;
    the caller must supply its observation clock. It proves neither geometry
    collision nor elevation, and the matrix land-data ID is not a byte hash.
    """
    if type(x) is not int or type(y) is not int or x < 0 or y < 0:
        return None
    observed = {}

    def span(pointer, size, alignment=4):
        if pointer % alignment or not 0x02000000 <= pointer < pointer + size <= 0x02400000:
            raise ValueError("terrain pointer is outside aligned main RAM")
        return pointer

    def read(address, size=4):
        span(address, size, min(size, 4))
        value = unsigned(emu, address, size)
        key = (address, size)
        if key in observed and observed[key] != value:
            raise ValueError("terrain context changed during its read")
        observed[key] = value
        return value

    try:
        field_system = span(read(G_FIELD_SYS_PTR), FIELD_TERRAIN_CONFIG_OFFSET + 4)
        map_matrix = span(read(field_system + FIELD_MAP_MATRIX_OFFSET),
                          MAP_MATRIX_MODELS_OFFSET + MAP_MATRIX_MAX_CELLS * 2)
        width, height, matrix_id = read(map_matrix, 1), read(map_matrix + 1, 1), read(map_matrix + 2, 1)
        if not width or not height or width * height > MAP_MATRIX_MAX_CELLS \
                or x >= width * 32 or y >= height * 32 \
                or (read(map_matrix + 4, 1), read(map_matrix + 5, 1)) != (height, width):
            return None
        matrix_index = (y // 32) * width + x // 32
        local_index = (y & 31) * 32 + (x & 31)
        land_data_id = read(map_matrix + MAP_MATRIX_MODELS_OFFSET + matrix_index * 2, 2)
        if land_data_id == 0xFFFF:
            return None
        header_id = read(map_matrix + MAP_MATRIX_HEADERS_OFFSET + matrix_index * 2, 2)
        altitude = read(map_matrix + MAP_MATRIX_ALTITUDES_OFFSET + matrix_index, 1)
        terrain = read(field_system + FIELD_TERRAIN_ATTRIBUTES_OFFSET)
        dispatch = span(read(field_system + FIELD_TERRAIN_DISPATCH_OFFSET), 8)
        reader = read(dispatch + 4)
        provenance = {"fieldPointer": field_system, "mapMatrixPointer": map_matrix,
            "matrixId": matrix_id, "matrixWidth": width, "matrixHeight": height,
            "mapHeaderId": header_id, "landDataId": land_data_id,
            "landDataIdentity": "current-map-matrix", "matrixAltitude": altitude,
            "landManagerPointer": None, "terrainAttributesPointer": terrain or None,
            "readerPointer": reader}
        if terrain:
            if reader != 0x02054825 or width * height > TERRAIN_MATRIX_INDEX_COUNT:
                return None
            config = span(read(field_system + FIELD_TERRAIN_CONFIG_OFFSET), 4)
            config_word = read(config)
            block_count = (config_word >> 24) & 0xFF
            # Field config selects the full reader and passes unk0_18 to
            # TerrainAttributes_New/Load. Capacity16 is not the loaded count.
            if ((config_word >> 8) & 0xF) != 1 or not ((config_word >> 16) & 0xF) \
                    or not 1 <= block_count <= TERRAIN_MAX_BLOCKS:
                return None
            span(terrain, TERRAIN_ATTRIBUTES_OFFSET + TERRAIN_MAX_BLOCKS * TERRAIN_BLOCK_TILE_COUNT * 2)
            block = read(terrain + matrix_index, 1)
            if block >= block_count:
                return None
            attribute_address = terrain + TERRAIN_ATTRIBUTES_OFFSET \
                + (block * TERRAIN_BLOCK_TILE_COUNT + local_index) * 2
            provenance.update(store="full-terrain-attributes", fieldConfigPointer=config,
                fieldConfigWord=config_word, loadedBlockCount=block_count)
        else:
            if reader != 0x020547D9:
                return None
            manager = span(read(field_system + FIELD_LAND_MANAGER_OFFSET), 0x110)
            if (read(manager + LAND_MANAGER_MATRIX_OFFSET), read(manager + LAND_MANAGER_WIDTH_OFFSET),
                    read(manager + LAND_MANAGER_HEIGHT_OFFSET), read(manager + LAND_MANAGER_TILE_WIDTH_OFFSET)) \
                    != (map_matrix, width, height, width * 32):
                return None
            current = read(manager + LAND_MANAGER_CURRENT_MATRIX_INDEX_OFFSET)
            current_slot = read(manager + LAND_MANAGER_CURRENT_SLOT_OFFSET, 1)
            if current >= width * height or current_slot >= 4:
                return None
            # The four stock switch branches are one 2x2 window. Work in x/y
            # so right-edge indices cannot wrap onto the next matrix row.
            dx = x // 32 - (current % width - (current_slot & 1))
            dy = y // 32 - (current // width - (current_slot >> 1))
            if dx not in (0, 1) or dy not in (0, 1):
                return None
            block = dx + 2 * dy
            pointers = [read(manager + LAND_MANAGER_CHUNK_POINTERS_OFFSET + i * 4) for i in range(4)]
            chunk = span(pointers[block], 0xA74)
            if pointers.count(chunk) != 1:
                return None
            chunk_index = read(chunk + LAND_CHUNK_MATRIX_INDEX_OFFSET)
            loaded = read(chunk + LAND_CHUNK_MODEL_LOADED_OFFSET)
            if chunk_index != matrix_index or loaded != 1 or read(manager + 0x80 + block * 4) != 0:
                return None
            # ov01_021F5038 assigns the new matrix tag when it queues work,
            # before the old attributes are replaced. Two 0x30-byte queues
            # and one deferred pair can still own this chunk at that point.
            for base in (0, 0x30):
                if read(manager + base + 0x2C) and chunk in (
                        read(manager + base + 4), read(manager + base + 8)):
                    return None
            if read(manager + 0x6C) and chunk in (read(manager + 0x64), read(manager + 0x68)):
                return None
            attribute_address = chunk + local_index * 2
            provenance.update(store="rolling-land-manager", landManagerPointer=manager,
                currentMatrixIndex=current, currentSlot=current_slot, selectedSlot=block,
                chunkPointer=chunk, chunkMatrixIndex=chunk_index, chunkModelLoaded=loaded)
        attribute = read(attribute_address, 2)
        # A pause normally makes these stable. Still reject a mismatched
        # reader/owner/tag if a caller samples while another owner advances.
        if any(unsigned(emu, address, size) != value for (address, size), value in observed.items()):
            return None
        provenance.update(attributeAddress=attribute_address, rawWord=attribute)
    except ValueError:
        return None
    return {
        "x": x,
        "y": y,
        "attribute": attribute,
        "behavior": attribute & 0xFF,
        "collision": bool(attribute & 0x8000),
        "terrain_class": (attribute >> 8) & 0x7F,
        "matrix_index": matrix_index,
        "block": block,
        "provenance": provenance,
    }


def loaded_surface_cell(emu, x, y, terrain_cell):
    """Read the authored surface catalog for one verified loaded tile.

    This mirrors OverworldWildRuntime_QuerySurface without executing game
    code. Native-ground catalog heights are relative offsets. They are not
    mislabeled as a final world height because that requires the stock native
    terrain-height query.
    """
    if not isinstance(terrain_cell, dict):
        return {"known": False, "present": None, "reason": "base-terrain-unknown"}
    provenance = terrain_cell.get("provenance")
    if not isinstance(provenance, dict):
        return {"known": False, "present": None, "reason": "base-terrain-provenance-missing"}
    symbols = WILD_SYMBOLS
    if not isinstance(symbols, dict) or "sOverworldWildBehaviorDataBlob" not in symbols:
        return {"known": False, "present": None, "reason": "surface-catalog-symbol-unavailable"}

    def read(address, size=4):
        if (not isinstance(address, int) or not isinstance(size, int) or size <= 0
                or not 0x02000000 <= address < address + size <= 0x02400000):
            raise ValueError("surface catalog address is outside main RAM")
        return unsigned(emu, address, size)

    try:
        pointer_address = symbols["sOverworldWildBehaviorDataBlob"]
        blob = read(pointer_address)
        if not blob:
            return {"known": False, "present": None, "reason": "surface-catalog-not-loaded"}
        header = bytes(read(blob + offset, 1) for offset in range(BEHAVIOR_DATA_HEADER_SIZE))
        magic, version, header_size, blob_size = struct.unpack_from("<IHHI", header)
        if (magic, version, header_size) != (
                BEHAVIOR_DATA_MAGIC, BEHAVIOR_DATA_VERSION, BEHAVIOR_DATA_HEADER_SIZE):
            raise ValueError("behavior data header differs")
        if not BEHAVIOR_DATA_HEADER_SIZE <= blob_size <= 0x40000:
            raise ValueError("behavior data size differs")
        models_offset, model_count, model_size = struct.unpack_from("<IHH", header, 60)
        instances_offset, instance_count, instance_size = struct.unpack_from("<IHH", header, 68)
        templates_offset, template_count, template_size = struct.unpack_from("<IHH", header, 76)
        if (model_size, instance_size, template_size) != (6, 8, 2) \
                or not 0 < model_count < 0xFF \
                or not 0 < instance_count <= 0xFFFF \
                or not 0 < template_count <= 0x100:
            raise ValueError("surface catalog layout differs")
        for offset, count, size in (
                (models_offset, model_count, model_size),
                (instances_offset, instance_count, instance_size),
                (templates_offset, template_count, template_size)):
            if offset < header_size or offset + count * size > blob_size:
                raise ValueError("surface catalog range differs")

        land_data_id = provenance.get("landDataId")
        if not isinstance(land_data_id, int):
            raise ValueError("loaded tile lacks land data identity")
        selected = None
        previous_land = -1
        for index in range(model_count):
            address = blob + models_offset + index * model_size
            model_land = read(address, 2)
            first_instance = read(address + 2, 2)
            count = read(address + 4, 1)
            reserved = read(address + 5, 1)
            if model_land <= previous_land or reserved or first_instance + count > instance_count:
                raise ValueError("surface model directory differs")
            previous_land = model_land
            if model_land == land_data_id:
                selected = (index, first_instance, count)
                break
            if model_land > land_data_id:
                break
        base = {
            "known": True,
            "present": False,
            "catalogPointer": blob + models_offset,
            "landDataId": land_data_id,
            "localX": x & 31,
            "localZ": y & 31,
            "scope": "live authored surface catalog; native-ground offsets are not final world heights",
        }
        if selected is None:
            return base

        model_index, first_instance, count = selected
        local_x, local_y = x & 31, y & 31
        for relative_index in range(count):
            instance_index = first_instance + relative_index
            address = blob + instances_offset + instance_index * instance_size
            min_x, min_y, template_id, local_surface_id = (
                read(address + offset, 1) for offset in range(4))
            height_q4 = read(address + 4, 2)
            packed_surface = read(address + 6, 1)
            anchor_offsets = read(address + 7, 1)
            if template_id >= template_count:
                raise ValueError("surface template index differs")
            template_address = blob + templates_offset + template_id * template_size
            width, height = read(template_address, 1), read(template_address + 1, 1)
            if not width or not height or width * height > 0xFF:
                raise ValueError("surface template shape differs")
            if not (min_x <= local_x < min_x + width and min_y <= local_y < min_y + height):
                continue
            surface_type = packed_surface >> 5
            height_page = packed_surface & 0x1F
            if surface_type >= len(SURFACE_TYPE_NAMES):
                raise ValueError("surface type differs")
            node_id = (local_y - min_y) * width + local_x - min_x
            result = {
                **base,
                "present": True,
                "type": SURFACE_TYPE_NAMES[surface_type],
                "typeId": surface_type,
                "modelIndex": model_index,
                "instanceIndex": instance_index,
                "templateId": template_id,
                "rectangle": {"minX": min_x, "minZ": min_y, "width": width, "height": height},
                "nodeId": node_id,
                "heightQ4": height_q4,
            }
            if height_page == SURFACE_HEIGHT_PAGE_NATIVE_GROUND:
                surface_id = (SURFACE_ID_NATIVE_GROUND - (surface_type >> 2)) & 0xFFFF
                result.update(
                    surfaceId=surface_id,
                    heightMode="native-ground-offset" if height_q4 else "native-ground",
                    heightOffsetFx32=height_q4 << 4,
                    finalHeightKnown=False,
                )
            else:
                dx = anchor_offsets & 0x0F
                dz = anchor_offsets >> 4
                dx = dx - 16 if dx & 8 else dx
                dz = dz - 16 if dz & 8 else dz
                matrix_width = provenance.get("matrixWidth")
                matrix_height = provenance.get("matrixHeight")
                matrix_index = terrain_cell.get("matrix_index")
                matrix_pointer = provenance.get("mapMatrixPointer")
                if not all(isinstance(value, int) for value in (
                        matrix_width, matrix_height, matrix_index, matrix_pointer)):
                    raise ValueError("surface anchor lacks matrix identity")
                anchor_index = matrix_index + dx + dz * matrix_width
                if not 0 <= anchor_index < matrix_width * matrix_height:
                    raise ValueError("surface anchor is outside map matrix")
                altitude = read(matrix_pointer + MAP_MATRIX_ALTITUDES_OFFSET + anchor_index, 1)
                result.update(
                    surfaceId=((anchor_index << 4) | local_surface_id) & 0xFFFF,
                    heightMode="absolute",
                    heightFx32=(height_page << 20) + (height_q4 << 4)
                        + (altitude << 15),
                    finalHeightKnown=True,
                    anchorMatrixIndex=anchor_index,
                )
            if read(pointer_address) != blob:
                raise ValueError("surface catalog owner changed during read")
            return result
        return base
    except (KeyError, struct.error, ValueError):
        return {"known": False, "present": None, "reason": "surface-catalog-read-incoherent"}


def actor_memory_read(emu, address, size):
    return bytes(emu.memory.unsigned[address:address + size:1])


def actor_memory_write(emu, address, data):
    emu.memory.unsigned[address:address + len(data):1] = list(data)


def actor_state(emu, slot):
    state = ACTOR_DESCRIPTOR["state"]
    address = (
        state["address"]
        + state["offsets"]["actors"]
        + slot * state["actorStride"]
    )
    return actor_probe.decode_actor_state(
        actor_memory_read(emu, address, ACTOR_STATE_SIZE),
        ACTOR_DESCRIPTOR,
    )


def movement_policy_state(emu, slot):
    state = ACTOR_DESCRIPTOR["state"]
    base = (
        state["address"]
        + state["offsets"]["actors"]
        + slot * state["actorStride"]
        + state["actorPolicyOffset"]
    )
    fields = {
        "direction": base,
        "counter": base + 1,
        "speed": base + 2,
        "base": base + 3,
        "spotState": base + 4,
        "skid": base + 5,
        "turn": base + 6,
        "resume": base + 7,
        "chain": base + 16,
        "ticks": base + 17,
        "action": base + 18,
        "variance": base + 19,
        "buffered": base + 20,
        "stop": base + 21,
        "pending": base + 22,
        "pendingSkid": base + 23,
        "streamState": base + 24,
    }
    return {
        name: unsigned(emu, address, 1)
        for name, address in fields.items()
    }


def player_ptr(emu):
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    avatar = unsigned(emu, field_system + 0x40) if field_system else 0
    return unsigned(emu, avatar + 0x30) if avatar else 0


def object_state(emu, obj):
    return {
        "flags": unsigned(emu, obj),
        "x_prev": signed(emu, obj + 0x58),
        "y_prev": signed(emu, obj + 0x60),
        "x": signed(emu, obj + 0x64),
        "y": signed(emu, obj + 0x6C),
        "pos_x": signed(emu, obj + 0x70),
        "pos_y": signed(emu, obj + 0x74),
        "pos_z": signed(emu, obj + 0x78),
        "face_x": signed(emu, obj + 0x7C),
        "face_y": signed(emu, obj + 0x80),
        "face_z": signed(emu, obj + 0x84),
        "unk88_y": signed(emu, obj + 0x8C),
        "unk88_x": signed(emu, obj + 0x88),
        "unk94_y": signed(emu, obj + 0x98),
        "unk94_x": signed(emu, obj + 0x94),
        "movement_cmd": unsigned(emu, obj + 0xA4),
        "movement_step": unsigned(emu, obj + 0xA8),
        "facing": signed(emu, obj + 0x28),
    }


def wait_until(
    emu, predicate, limit, mask=0, frame_clock=None,
    gameplay_counter=None,
):
    for frame in range(limit + 1):
        if predicate():
            return frame
        h.cycle(emu, 1, mask)
        if frame_clock is not None:
            frame_clock["vblank"] += 1
        if gameplay_counter is not None:
            gameplay_counter["frames"] += 1
    return None


def boot(emu, save_path, dsv, on_rom_open=None):
    raw_save = h.extract_raw_save(save_path) if dsv else save_path.read_bytes()
    emu.volume_set(0)
    emu.open(str(ROM))
    if on_rom_open is not None:
        on_rom_open()
    with tempfile.NamedTemporaryFile(suffix=".sav") as raw_file:
        raw_file.write(raw_save)
        raw_file.flush()
        emu.backup.import_file(raw_file.name, force_size=0)
        h.cycle(emu, 420)
        for _ in range(8):
            # Keep the confirm pulse short. A long hold can reach the field
            # and start the registered fishing action before readiness is
            # sampled, which pauses the actor frame clock.
            h.tap_key(emu, "A", 2, 34)
            ready = wait_until(
                emu,
                lambda: (
                    unsigned(emu, G_FIELD_SYS_PTR) != 0
                    and unsigned(emu, WILD_STATE + 0xE0)
                        == unsigned(emu, G_FIELD_SYS_PTR)
                    and unsigned(emu, WILD_STATE + WILD_RUNTIME_PTR_OFFSET)
                        != 0
                ),
                180,
            )
            if ready is not None:
                h.cycle(emu, 600)
                actor_state_address = ACTOR_DESCRIPTOR["state"]["address"]
                actor_frame = unsigned(emu, actor_state_address + 8)
                if wait_until(
                    emu,
                    lambda: unsigned(emu, actor_state_address + 8)
                        != actor_frame,
                    60,
                ) is not None:
                    return
                # Do not close a menu or clear a pause with recovery input:
                # that would hide the original save-load failure. These are
                # bounded endpoint reads, not a completed actor observation.
                diagnostic = ["boundary=paused-native-cycle-end",
                              f"actorFrameBefore={actor_frame}"]
                try:
                    diagnostic.append(f"actorFrameAfter={unsigned(emu, actor_state_address + 8)}")
                    field = unsigned(emu, G_FIELD_SYS_PTR)
                    diagnostic.append(f"field=0x{field:08X}")
                    if field:
                        # Stock field_system.h and task.h layouts. Read only
                        # the current task header, never its arbitrary env.
                        root = unsigned(emu, field)
                        task = unsigned(emu, field + 0x10)
                        diagnostic.extend((f"fieldRoot=0x{root:08X}",
                                           f"taskman=0x{task:08X}",
                                           f"fieldReady={unsigned(emu, field + 0x6C)}"))
                        if root:
                            diagnostic.append(f"isPaused={unsigned(emu, root + 8)}")
                        if task:
                            diagnostic.extend((f"taskFunction=0x{unsigned(emu, task + 4):08X}",
                                               f"taskState={unsigned(emu, task + 8)}"))
                except Exception as error:
                    diagnostic.append(f"diagnosticReadError={str(error)[:200]}")
                raise RuntimeError(
                    "save reached the field but actor clock stalled; no recovery input sent: "
                    + ", ".join(diagnostic)
                )
        field_system = unsigned(emu, G_FIELD_SYS_PTR)
        wild_field_system = unsigned(emu, WILD_STATE + 0xE0)
        wild_runtime = unsigned(emu, WILD_STATE + WILD_RUNTIME_PTR_OFFSET)
        field_root = unsigned(emu, field_system) if field_system else 0
        field_overlay = unsigned(emu, field_root) if field_root else 0
        field_taskman = (
            unsigned(emu, field_system + 0x10) if field_system else 0
        )
        field_ready = (
            unsigned(emu, field_system + 0x6C) if field_system else 0
        )
        raise RuntimeError(
            "save did not reach the overworld before input limit: "
            f"field=0x{field_system:08X}, "
            f"wildField=0x{wild_field_system:08X}, "
            f"wildRuntime=0x{wild_runtime:08X}, "
            f"fieldRoot=0x{field_root:08X}, "
            f"fieldOverlay=0x{field_overlay:08X}, "
            f"taskman=0x{field_taskman:08X}, "
            f"fieldReady=0x{field_ready:08X}"
        )


def wild_spawn(emu, slot):
    base = WILD_STATE + slot * 20
    return {
        "object": unsigned(emu, base),
        "personality": unsigned(emu, base + 0x04),
        "map_id": unsigned(emu, base + 0x08, 2),
        "species": unsigned(emu, base + 0x0A, 2),
        "form": unsigned(emu, base + 0x0C, 1),
        "level": unsigned(emu, base + 0x0D, 1),
        "active": unsigned(emu, base + 0x10, 1),
        "object_id": unsigned(emu, base + 0x11, 1),
        "encounter_generation": unsigned(emu, base + 0x12, 2),
    }


@lru_cache(maxsize=1)
def _wild_staged_layout():
    """Immutable worker package binding; ARM header tests anchor these offsets."""
    from tools.overworld.devtools_field_cleanup import symbol
    address, _, _ = symbol((REPO / "build/linked.o").read_bytes(),
                           "sOverworldWildSpawnState", 1, expected_size=964)
    image = (REPO / "build/overworld_wild_spawns_overlay_linked.o").read_bytes()
    entry, _, code = symbol(image,
                           "OverworldWildSpawns_ClearStagedHopTargetLocal", 2, expected_size=116)
    # Only these two Thumb BL displacements may change as linked code moves.
    # All loads, stores, offsets, literals and other instructions stay exact.
    calls = ((14, "OverworldWildSpawns_ClearStagedHopMovementListTask"),
             (22, "OverworldWildSpawns_ClearCustomJumpLocal"))
    shape = bytearray(code)
    for offset, _ in calls:
        shape[offset:offset + 4] = bytes(4)
    if len(code) != 116 or hashlib.sha256(shape).hexdigest() != "dabbe8cd1025a4646982d766850ce2ebdd57af308dde2c6132014f55deacf6b5":
        raise ValueError("staged-motion-layout-code-unknown")
    for offset, name in calls:
        high, low = struct.unpack_from("<HH", code, offset)
        if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
            raise ValueError("staged-motion-layout-call-encoding-differs")
        displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
        if displacement & 0x400000:
            displacement -= 0x800000
        target, _, _ = symbol(image, name, 2)
        if entry + offset + 4 + displacement != target:
            raise ValueError("staged-motion-layout-call-target-differs: " + name)
    return address, entry, code


def wild_staged_motion(emu, slot):
    """Read staged target state only; actor/motion identity remains caller-owned."""
    result = {"known": False, "reason": "unread", "slot": slot}
    try:
        if type(slot) is not int or not 0 <= slot < 10:
            raise ValueError("staged-motion-slot-out-of-bounds")
        address, entry, code = _wild_staged_layout()
        if address != WILD_STATE or address & 3 or not 0x02000000 <= address <= 0x02400000 - 964:
            raise ValueError("staged-motion-state-owner-differs")
        def read(pointer, size):
            data = bytes(emu.memory.unsigned[pointer:pointer + size:1])
            if len(data) != size:
                raise ValueError("staged-motion-short-read")
            return data
        if read(entry, len(code)) != code:
            raise ValueError("staged-motion-live-code-differs-or-overlay-absent")
        # A single bounded state read also retains the slot's current object.
        data = read(address, 964)
        pending, distance = data[704 + slot], data[684 + slot]
        result.update(known=True, reason="observed", pending=pending, distance=distance,
                      pendingDirection=data[434 + slot], pendingDistance=data[444 + slot],
                      objectPointer=int.from_bytes(data[slot * 20:slot * 20 + 4], "little"),
                      idle=pending == 0 and distance == 0)
    except (ValueError, TypeError, KeyError, OSError) as error:
        result["reason"] = str(error)[:160]
    return result


def live_wild_object_identity(emu, slot, *, id_scan_cache=None):
    """Read slot membership and a separate bounded stock-ID lookup receipt.

    The receipt mirrors MapObjectManager_GetFirstActiveObjectByID in vanilla
    src/map_object.c:728: first ACTIVE matching ID, excluding flag25. Neither
    map ID nor script ID is part of that stock lookup. This does not invoke the
    game function or change the existing identity acceptance checks.

    A caller may share one fresh dict across ONE paused snapshot. Only the
    completed manager ID tuple is cached; all source and matching-row fields
    remain live reads. Discard the dict before any guest execution.
    """
    spawn = wild_spawn(emu, slot)
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    manager = unsigned(emu, field_system + 0x3C) if field_system else 0
    object_count = unsigned(emu, manager + 4) if manager else 0
    objects = unsigned(emu, manager + 0x124) if manager else 0
    obj = spawn["object"]
    delta = obj - objects if obj and objects else -1
    aligned = delta >= 0 and delta % 0x12C == 0
    manager_index = delta // 0x12C if aligned else -1
    in_manager = aligned and manager_index < object_count
    location = unsigned(emu, field_system + FIELD_LOCATION_OFFSET) \
        if field_system else 0
    current_map = unsigned(emu, location) if location else 0xFFFFFFFF
    lookup = {
        "status": "invalid-manager-bounds",
        "source": "stock-first-active-id-semantics",
        "requested_id": spawn["object_id"],
        "object_count": object_count,
        "capacity_limit": 64,
        "first_active_pointer": None,
        "first_active_index": None,
        "eligible_count": None,
        "pointer_matches": None,
        "matching_objects": [],
    }
    # Both stock field creation and save restore create a 64-entry manager.
    # Validate the complete typed span, then read only IDs and matching rows;
    # copying the full 19,200-byte array per actor is needlessly expensive.
    if (manager and 1 <= object_count <= 64 and objects % 4 == 0
            and 0x02000000 <= objects
            and objects + object_count * 0x12C <= 0x02400000):
        try:
            ids = None
            if id_scan_cache is not None:
                key = (field_system, manager, objects, object_count)
                ids = id_scan_cache.get(key)
                if ids is None:
                    ids = tuple(unsigned(emu, objects + index * 0x12C + 0x08)
                                for index in range(object_count))
                    id_scan_cache[key] = ids  # publish only after every ID read succeeds
            matches = []
            for index in range(object_count):
                pointer = objects + index * 0x12C
                object_id = unsigned(emu, pointer + 0x08) if ids is None else ids[index]
                if object_id != spawn["object_id"]:
                    continue
                flags = unsigned(emu, pointer)
                active = bool(flags & 1)
                flag25 = bool(flags & (1 << 25))
                matches.append({
                    "pointer": pointer,
                    "manager_index": index,
                    "object_id": object_id,
                    "object_map_id": unsigned(emu, pointer + 0x0C),
                    "script_id": unsigned(emu, pointer + 0x20),
                    "flags": flags,
                    "active": active,
                    "flag25": flag25,
                    "lookup_eligible": active and not flag25,
                })
            eligible = [row for row in matches if row["lookup_eligible"]]
            first = eligible[0] if eligible else None
            lookup.update(
                status="complete", matching_objects=matches,
                first_active_pointer=first["pointer"] if first else 0,
                first_active_index=first["manager_index"] if first else None,
                eligible_count=len(eligible),
                pointer_matches=bool(first and first["pointer"] == obj))
        except Exception as error:
            # A partial scan is not an empty/unique lookup. Preserve the main
            # actor observation and expose the diagnostic read failure.
            lookup.update(status="read-error", error=str(error)[:240])
    return {
        "pointer": obj,
        "manager_index": manager_index,
        "in_manager": in_manager,
        "active": bool(unsigned(emu, obj) & 1) if in_manager else False,
        "object_id": unsigned(emu, obj + 0x08) if in_manager else None,
        "object_map_id": unsigned(emu, obj + 0x0C) if in_manager else None,
        "script_id": unsigned(emu, obj + 0x20) if in_manager else None,
        "object_manager": unsigned(emu, obj + 0xB4) if in_manager else None,
        "current_manager": manager,
        "spawn_object_id": spawn["object_id"],
        "spawn_map_id": spawn["map_id"],
        "current_map_id": current_map,
        "encounter_generation": spawn["encounter_generation"],
        "id_lookup": lookup,
    }
