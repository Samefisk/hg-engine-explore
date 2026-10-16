"""Read the linked player HP record from a paused, shared melonDS session.

The descriptor names one build. Every read is bounded to its checked overlay,
runtime record, field owner, or save block. This reader makes no native call and
does not advance the emulator.
"""

import hashlib
import json
from pathlib import Path
import struct

from tools.overworld.devtools_runtime import DevtoolsFailure, require


DESCRIPTOR = "build/player-health.debug.json"
ENTRY_SIZE = 0x34
EXPECTED_OFFSETS = {
    "lastFrame": 0, "acceptedHits": 4, "restFrames": 8,
    "protectionFrames": 10, "healRemainder": 12, "hp": 14,
    "frameActive": 15, "hitThisFrame": 16,
    "protectionAdvancedThisFrame": 17, "recoveryPending": 18,
    "lastDamage": 19,
}
EXPECTED_OWNER_OFFSETS = {"saveData": 20, "fieldSystem": 24,
                          "initialized": 56}
EXPECTED_SAVE = {"dynamicRegion": 0x10, "arrayHeaders": 0x2F014,
                 "arrayHeaderSize": 0x10, "miscBlock": 9,
                 "signature": 0x2D5, "state": 0x2DD,
                 "magic": [ord("P"), ord("H"), 1],
                 "minSpawn": 1, "maxSpawn": 30}
PLAYER_DATA_BLOCK = 1
BAG_BLOCK = 3
PROFILE_MONEY_OFFSET = 24
# SaveArray's current expanded bag block includes four bytes after BAG_DATA.
BAG_SIZE = 2448


def _u32(data, offset=0):
    return struct.unpack_from("<I", data, offset)[0]


def _main_pointer(value):
    return value % 4 == 0 and 0x02000000 <= value < 0x02400000


def _save_block(session, save, layout, block_id, minimum_size,
                maximum_size):
    header_address = save + layout["arrayHeaders"] \
        + block_id * layout["arrayHeaderSize"]
    require(0x02000000 <= header_address <= 0x02400000 - 0x10,
            "player HP save header is outside main RAM", "hp-owner")
    observed_id, size, offset = struct.unpack_from(
        "<III", session.read(header_address, 0x10))
    require(observed_id == block_id
            and minimum_size <= size <= maximum_size
            and offset <= 0x2F000 - size,
            "player HP save block header is invalid: "
            f"block={block_id} id={observed_id} size={size} offset={offset}",
            "hp-owner")
    base = save + layout["dynamicRegion"] + offset
    require(0x02000000 <= base and base + size <= 0x02400000,
            "player HP save block is outside main RAM", "hp-owner")
    return base, size


def _check_descriptor(value):
    require(type(value) is dict and value.get("formatVersion") == 1,
            "player HP descriptor version is missing or wrong", "hp-identity")
    overlay = value.get("overlay")
    entry = value.get("entry")
    runtime = value.get("runtime")
    require(type(overlay) is dict and type(entry) is dict and type(runtime) is dict,
            "player HP descriptor is incomplete", "hp-identity")
    require(overlay.get("id") == 161 and overlay.get("base") == 0x01FFA580
            and overlay.get("capacity") == 0x5A80
            and type(overlay.get("fileSize")) is int
            and ENTRY_SIZE <= overlay["fileSize"] <= 0x5A80
            and type(overlay.get("sha256")) is str
            and len(overlay["sha256"]) == 64,
            "player HP overlay identity is invalid", "hp-identity")
    require(entry.get("address") == overlay["base"]
            and entry.get("size") == ENTRY_SIZE
            and entry.get("magic") == 0x484C5048
            and entry.get("version") == 2
            and type(entry.get("bytesHex")) is str
            and len(entry["bytesHex"]) == 2 * ENTRY_SIZE,
            "player HP entry identity is invalid", "hp-identity")
    require(type(runtime.get("address")) is int
            and runtime["address"] % 4 == 0
            and overlay["base"] + ENTRY_SIZE <= runtime["address"]
            and runtime["address"] + 0x3C <= overlay["base"] + overlay["fileSize"]
            and runtime.get("size") == 0x3C
            and runtime.get("runtimeSize") == 0x3C
            and runtime.get("stateSize") == 20
            and runtime.get("maxHp") == 100
            and runtime.get("stateOffsets") == EXPECTED_OFFSETS
            and runtime.get("ownerOffsets") == EXPECTED_OWNER_OFFSETS
            and runtime.get("save") == EXPECTED_SAVE,
            "player HP runtime descriptor layout is invalid", "hp-identity")
    try:
        entry_bytes = bytes.fromhex(entry["bytesHex"])
    except ValueError as error:
        raise DevtoolsFailure("hp-identity", "player HP entry bytes are invalid") from error
    require(struct.unpack_from("<IHH", entry_bytes) == (0x484C5048, 2, ENTRY_SIZE)
            and _u32(entry_bytes, 16) == entry.get("getState")
            and type(entry.get("getState")) is int
            and entry["getState"] & 1
            and overlay["base"] + ENTRY_SIZE <= (entry["getState"] & ~1)
            < overlay["base"] + overlay["fileSize"],
            "player HP entry callback is invalid", "hp-identity")
    return overlay, entry, runtime, entry_bytes



def _presentation_receipt(descriptor, read_overlay, read_memory, read_palette,
                          package, field, fresh,
                          hp, recovery_pending):
    layout = descriptor.get("presentation")
    if layout is None:
        missing = {"available": False, "reason": "presentation descriptor missing"}
        return dict(missing), dict(missing)
    require(type(layout) is dict and layout.get("version") == 3,
            "player HP presentation version is invalid", "hp-presentation-identity")
    expected = {"size": 0x38, "fieldOffset": 0, "receiptOffset": 0x30,
                "receiptSize": 4,
                "receiptOffsets": {"requestedFill": 0, "drawnFill": 1,
                                   "danger": 2, "submittedSprites": 3},
                "boundOffset": 0x34, "textureKeyOffset": 0x35,
                "paletteSlotOffset": 0x36}
    require(all(layout.get(k) == v for k, v in expected.items())
            and type(layout.get("address")) is int
            and layout["address"] % 4 == 0
            and package[0] + ENTRY_SIZE <= layout["address"]
                <= package[0] + len(package[1]) - 0x38,
            "player HP presentation layout is invalid", "hp-presentation-identity")
    getter = layout.get("getter")
    require(type(getter) is dict and type(getter.get("address")) is int
            and getter["address"] % 4 == 0 and getter.get("size") == 12
            and package[0] + ENTRY_SIZE <= getter["address"]
                <= package[0] + len(package[1]) - 12
            and (getter["address"] + 12 <= layout["address"]
                 or layout["address"] + 0x38 <= getter["address"]),
            "player HP presentation getter is invalid", "hp-presentation-identity")
    address = layout["address"]
    code = struct.pack("<4HI", 0x4801, 0x3030, 0x4770, 0x46C0, address)
    offset = getter["address"] - package[0]
    require(getter.get("bytesHex") == code.hex()
            and offset >= ENTRY_SIZE and package[1][offset:offset + 12] == code
            and read_overlay(getter["address"], 12) == code,
            "player HP presentation getter differs from package/live code",
            "hp-presentation-identity")
    record = read_overlay(address, 0x38)
    requested, drawn, danger, count = record[0x30:0x34]
    owner = _u32(record)
    bound, texture, palette = record[0x34:0x37]
    palette_source = _u32(record, 0x1C)
    dma_readable = (0x02000000 <= palette_source <= 0x02400000 - 32
                    and palette_source % 4 == 0) if bound else None
    source = read_memory(palette_source, 32) if dma_readable else None
    source_has_colors = (any(source[i] or source[i + 1]
                             for i in range(2, 30, 2))
                         if source is not None else None)
    vram_matches = (read_palette(0x05000200 + palette * 32, 32)
                    == source if source is not None and palette < 16 else None)
    expected_fill = 0 if recovery_pending or hp == 0 else (hp * 44 + 99) // 100
    require(requested <= 44 and drawn <= 44 and danger in (0, 1)
            and bound in (0, 1) and (texture <= 201 or texture == 255)
            and palette < 16 and count in (0, 1)
            and requested in (0, expected_fill)
            and (not recovery_pending or danger == 0)
            and (not bound or owner == field)
            and (bound or (owner == 0 and requested == 0
                           and drawn == 0 and danger == 0 and count == 0))
            and (drawn == 0 or (drawn == requested == expected_fill
                               and count == 1 and bound
                               and texture == hp * 2 + danger))
            and (count == 0 or drawn != 0)
            and (requested != 0 or (drawn == 0 and count == 0)),
            "player HP presentation receipt is inconsistent", "hp-presentation-state")
    return ({"available": True, "receiptVersion": 2,
             "requestedFill": requested, "drawnFill": drawn,
             "fillWidth": 44, "danger": bool(danger),
             "submittedSprites": count, "freshHealthFrame": fresh,
             "completeSubmission": bool(drawn and count == 1),
             "claim": "native-oam-submission", "hardwareApplied": None},
            {"available": True, "bound": bool(bound),
             "fieldOwner": owner, "fieldMatches": owner == field,
             "textureKey": texture, "paletteSlot": palette,
             "paletteSourceDmaReadable": dma_readable,
             "paletteSourceHasColors": source_has_colors,
             "paletteVramMatchesSource": vram_matches})


def observe_player_health(session, args=None):
    """Return one checked read-only receipt; reject uncertain identity/state."""
    require(args in (None, {}), "player HP observation accepts no arguments",
            "invalid-argument")
    require(session.emu is not None and session.latest_frame is not None
            and session.sample_error is None,
            "no complete player HP field frame is available", "observation-missing")
    require(not session.native_bridge_active and session.pending_samples is None,
            "player HP observation requires a paused native boundary", "busy")
    descriptor_path = Path(session.rt.REPO) / DESCRIPTOR
    require(descriptor_path.is_file(), "player HP descriptor is missing", "hp-identity")
    try:
        descriptor = json.loads(descriptor_path.read_text())
    except (OSError, ValueError) as error:
        raise DevtoolsFailure("hp-identity", "player HP descriptor is unreadable") from error
    overlay, entry, layout, entry_bytes = _check_descriptor(descriptor)
    package = getattr(session, "overlay_code_regions", {}).get(161)
    require(package is not None and package[0] == overlay["base"]
            and len(package[1]) == overlay["fileSize"]
            and hashlib.sha256(package[1]).hexdigest() == overlay["sha256"]
            and package[1][:ENTRY_SIZE] == entry_bytes,
            "ROM player HP overlay differs from the descriptor", "hp-identity")

    def read_overlay(address, size):
        require(overlay["base"] <= address
                and address + size <= overlay["base"] + overlay["fileSize"],
                "player HP read is outside overlay 161", "hp-identity")
        return session.rt.actor_memory_read(session.emu, address, size)

    def read_palette(address, size):
        require(size == 32 and 0x05000200 <= address <= 0x050003E0
                and address % 32 == 0,
                "player HP palette read is outside main OBJ palette VRAM",
                "hp-presentation-identity")
        return session.rt.actor_memory_read(session.emu, address, size)

    live_entry = read_overlay(entry["address"], ENTRY_SIZE)
    require(live_entry == entry_bytes,
            "live player HP API differs from the ROM package", "hp-identity")
    record = read_overlay(layout["address"], layout["size"])
    field = session.field_pointer()
    owner = layout["ownerOffsets"]
    save = _u32(record, owner["saveData"])
    require(record[owner["initialized"]] == 1
            and _u32(record, owner["fieldSystem"]) == field
            and _main_pointer(save)
            and _u32(session.read(field + 0x0C, 4)) == save,
            "player HP runtime has no matching live field/save owner",
            "hp-owner")

    save_layout = layout["save"]
    block_base, _ = _save_block(session, save, save_layout,
                                save_layout["miscBlock"], 0x2E0, 0x2F000)
    signature = session.read(block_base + save_layout["signature"], 3)
    state = session.read(block_base + save_layout["state"], 3)
    require(signature == bytes(save_layout["magic"]),
            "player HP save record is missing or has the wrong version",
            "hp-save-version")
    saved_hp = state[0]
    checkpoint = struct.unpack_from("<H", state, 1)[0]
    player_base, _ = _save_block(session, save, save_layout,
                                 PLAYER_DATA_BLOCK, PROFILE_MONEY_OFFSET + 4,
                                 0x1000)
    bag_base, bag_size = _save_block(session, save, save_layout,
                                     BAG_BLOCK, BAG_SIZE, BAG_SIZE)
    money = _u32(session.read(player_base + PROFILE_MONEY_OFFSET, 4))
    bag_sha256 = hashlib.sha256(session.read(bag_base, bag_size)).hexdigest()
    require(money <= 999999,
            "player HP money value is outside the stock range", "hp-economy")
    offsets = layout["stateOffsets"]
    hp = record[offsets["hp"]]
    last_damage = record[offsets["lastDamage"]]
    flags = {name: record[offsets[name]] for name in (
        "frameActive", "hitThisFrame", "protectionAdvancedThisFrame",
        "recoveryPending")}
    require(hp <= 100 and saved_hp <= 100 and hp == saved_hp
            and save_layout["minSpawn"] <= checkpoint <= save_layout["maxSpawn"]
            and 0 <= last_damage <= 50
            and all(value in (0, 1) for value in flags.values())
            and struct.unpack_from("<H", record, offsets["protectionFrames"])[0] <= 60
            and struct.unpack_from("<H", record, offsets["restFrames"])[0] <= 300
            and struct.unpack_from("<H", record, offsets["healRemainder"])[0] < 60,
            "player HP runtime/save values are inconsistent", "hp-state")
    rest = struct.unpack_from("<H", record, offsets["restFrames"])[0]
    protection = struct.unpack_from("<H", record, offsets["protectionFrames"])[0]
    task = _u32(session.read(field + 0x10, 4))
    context = session.latest_frame.get("context")
    if "presentation" in descriptor:
        require(type(context) is dict
                and all(type(context.get(k)) is int and context[k] > 0
                        for k in ("fieldEpoch", "mapGeneration"))
                and type(context.get("mapId")) is int and context["mapId"] >= 0
                and session.latest_frame.get("fieldAvailable") is True
                and session.latest_frame.get("observationBoundary")
                    == "main-task-queue-completion",
                "player HP presentation has no completed field context",
                "hp-presentation-identity")
    previous = getattr(session, "_player_health_previous", None)
    frame = session.latest_frame["frame"]
    last_health_frame = _u32(record, offsets["lastFrame"])
    clock_paused = None
    if (previous is not None and frame > previous["frame"]
            and previous["field"] == field and previous["save"] == save
            and previous["overlay"] == overlay["sha256"]
            and previous.get("context") == context):
        clock_paused = last_health_frame == previous["healthFrame"]
    fresh = None if clock_paused is None else not clock_paused
    bar_draw, bar_resources = _presentation_receipt(
        descriptor, read_overlay, session.read, read_palette,
        package, field, fresh, hp,
        bool(flags["recoveryPending"]))
    session._player_health_previous = {"frame": frame,
                                       "healthFrame": last_health_frame,
                                       "field": field, "save": save,
                                       "overlay": overlay["sha256"],
                                       "context": dict(context) if context else None}
    band = 0 if hp == 100 else 1 if hp >= 67 else 2 if hp >= 34 else 3
    return {
        "schemaVersion": 1,
        "identity": {"romSha256": session.rom_hash,
                     "overlayId": 161, "overlaySha256": overlay["sha256"],
                     "descriptorVersion": 1},
        "frame": frame,
        "nativeCycle": session.rt.EXECUTED_FRAME_COUNT,
        "fieldSystem": field,
        "observationBoundary": session.latest_frame.get("observationBoundary"),
        "context": dict(context) if context else None,
        "hp": hp, "maxHp": 100, "savedHp": saved_hp,
        "restFrames": rest, "restReadyFrames": 300,
        "protectionFrames": protection, "protectionMaxFrames": 60,
        "healRemainder": struct.unpack_from("<H", record, offsets["healRemainder"])[0],
        "frameActive": bool(flags["frameActive"]),
        "pause": {"fieldTaskActive": bool(task),
                  "healthClockPaused": clock_paused},
        "recoveryPending": bool(flags["recoveryPending"]),
        "checkpointSpawn": checkpoint,
        "economy": {"version": 1, "money": money,
                    "bagSize": bag_size, "bagSha256": bag_sha256},
        "lastDamage": last_damage,
        "acceptedHits": _u32(record, offsets["acceptedHits"]),
        "lastHealthFrame": last_health_frame,
        "hitThisFrame": bool(flags["hitThisFrame"]),
        "dangerBand": band,
        "barDraw": bar_draw,
        "barResources": bar_resources,
    }
