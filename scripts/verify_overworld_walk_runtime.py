#!/usr/bin/env python3
"""Verify mounted and wild exact-frame movement in the live emulator."""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HEADLESS_HELPER = REPO / "scripts/headless-overworld-test.py"
NM = os.environ.get("ARM_NONE_EABI_NM", "arm-none-eabi-nm")

spec = importlib.util.spec_from_file_location(
    "headless_overworld_test",
    HEADLESS_HELPER,
)
if spec is None or spec.loader is None:
    raise SystemExit(f"cannot load {HEADLESS_HELPER}")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


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


MOUNT_SYMBOLS = linked_symbols(REPO / "build/overworld_mount_overlay_linked.o")
SELECTOR_SYMBOLS = linked_symbols(
    REPO / "build/overworld_follower_selector_overlay_linked.o"
)
WILD_SYMBOLS = linked_symbols(REPO / "build/overworld_wild_spawns_overlay_linked.o")
RUNTIME_SYMBOLS = linked_symbols(REPO / "build/overworld_wild_runtime_overlay_linked.o")
TASK6_SYMBOLS = linked_symbols(
    REPO / "build/pokemon_move_history_task6_overlay_linked.o"
)

MOUNT = MOUNT_SYMBOLS["sOverworldMountState"]
UPDATE_MOUNT_MOTION = MOUNT_SYMBOLS["OverworldMount_UpdateCustomMotion"]
TRY_START_MOUNT_MOTION = MOUNT_SYMBOLS["OverworldMount_TryStartCustomMotion"]
FINISH_MOUNT_MOTION = MOUNT_SYMBOLS["OverworldMount_FinishCustomMotion"]
TICK_MOUNT = MOUNT_SYMBOLS["OverworldMount_Tick"]
# Observe the next mount tick. The prior tick has already finished its final
# presentation sync, so committed logical and render state is stable here.
# A fixed instruction offset became stale whenever Tick changed code size.
TICK_MOUNT_POST_SYNC = TICK_MOUNT
G_FIELD_SYS_PTR = MOUNT_SYMBOLS["gFieldSysPtr"]
WILD_STATE = MOUNT_SYMBOLS["sOverworldWildSpawnState"]
FOLLOWER_SLOT = WILD_STATE + 7 * 20
SELECTOR_HIGHLIGHT = SELECTOR_SYMBOLS["sFollowerRecall"] + 0x63
SELECTOR_STATE = SELECTOR_SYMBOLS["sFollowerSelectorInputState"]
APPLY_WILD_RENDER = WILD_SYMBOLS["OverworldWildSpawns_ApplyCustomJumpRenderOffset"]
CLEAR_WILD_JUMP = WILD_SYMBOLS["OverworldWildSpawns_ClearCustomJump"]
START_NATIVE_JUMP = 0x02062958
LCRNG_STATE = 0x021D15A8
LANDING_PARTICLE = RUNTIME_SYMBOLS["OverworldWildRuntime_PlayLandingHopParticle"]
PLAY_SE = MOUNT_SYMBOLS["PlaySE"] & ~1
PREPARE_CHAIN_PAUSE = MOUNT_SYMBOLS[
    "OverworldWildMovementPolicy_PrepareChainPause"
]
APPLY_CHAIN_PAUSE = WILD_SYMBOLS[
    "OverworldWildSpawns_ApplyUniversalChainMovementPause"
]
TRY_START_CHAIN_PAUSE_ACTION = WILD_SYMBOLS[
    "OverworldWildSpawns_TryStartChainPauseAction"
]
RUN_CHAIN_REPOSITION = TASK6_SYMBOLS["OverworldWild_RunChainReposition"]

WILD_RUNTIME_PTR_OFFSET = 0xE4
WILD_MAP_ID_OFFSET = 0xD4
WILD_FRAME_COUNTS_OFFSET = 0xDC
WILD_ELAPSED_OFFSET = 0xF0
WILD_ARC_OFFSET = 0x438
WILD_MOTION_MODES_OFFSET = 0x442
WILD_PREP_ACTIVE_OFFSET = 0x00
WILD_ACTIVE_OFFSET = 0x0A
WILD_START_X_OFFSET = 0x3C
WILD_START_Y_OFFSET = 0x50
WILD_TARGET_X_OFFSET = 0x64
WILD_TARGET_Y_OFFSET = 0x78
WILD_MOVEMENT_COOLDOWNS_OFFSET = 0xEE
WILD_MOVEMENT_IN_PROGRESS_MASK_OFFSET = 0xF8

MAP_CHERRYGROVE = 67
SPECIES_TENTACOOL = 72
SPAWN_TERRAIN_SURF = 1


def unsigned(emu, address, size=4):
    return emu.memory.unsigned[address:address:size]


def signed(emu, address, size=4):
    return emu.memory.signed[address:address:size]


def write_u8(emu, address, value):
    emu.memory.unsigned[address:address:1] = [value]


def write_u32(emu, address, value):
    emu.memory.unsigned[address:address:4] = [value & 0xFFFFFFFF]


def player_ptr(emu):
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    avatar = unsigned(emu, field_system + 0x40) if field_system else 0
    return unsigned(emu, avatar + 0x30) if avatar else 0


def avatar_ptr(emu):
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    return unsigned(emu, field_system + 0x40) if field_system else 0


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


def mount_state(emu):
    return {
        "phase": unsigned(emu, MOUNT + 0x64, 1),
        "mode": unsigned(emu, MOUNT + 0x66, 1),
        "attached": unsigned(emu, MOUNT + 0x7A, 1),
        "base": unsigned(emu, MOUNT + 0x7E, 1),
        "fastest": unsigned(emu, MOUNT + 0x7F, 1),
        "speed": unsigned(emu, MOUNT + 0x80, 1),
        "tiles": unsigned(emu, MOUNT + 0x81, 1),
        "direction": unsigned(emu, MOUNT + 0x83, 1),
        "counter": unsigned(emu, MOUNT + 0x84, 1),
        "skid": unsigned(emu, MOUNT + 0x85, 1),
        "turn": unsigned(emu, MOUNT + 0x86, 1),
        "resume": unsigned(emu, MOUNT + 0x87, 1),
        "pending": unsigned(emu, MOUNT + 0x88, 1),
        "pending_skid": unsigned(emu, MOUNT + 0x89, 1),
        "buffered": unsigned(emu, MOUNT + 0x8A, 1),
        "stop": unsigned(emu, MOUNT + 0x8B, 1),
        "motion_direction": unsigned(emu, MOUNT + 0x8C, 1),
        "arc": unsigned(emu, MOUNT + 0x8D, 1),
        "flicker": unsigned(emu, MOUNT + 0x8E, 1),
        "frames": unsigned(emu, MOUNT + 0x90, 2),
        "elapsed": unsigned(emu, MOUNT + 0x92, 2),
        "cooldown": unsigned(emu, MOUNT + 0x94, 2),
        "start_x": signed(emu, MOUNT + 0x98, 2),
        "start_y": signed(emu, MOUNT + 0x9A, 2),
        "target_x": signed(emu, MOUNT + 0x9C, 2),
        "target_y": signed(emu, MOUNT + 0x9E, 2),
        "stream_preparing": unsigned(emu, MOUNT + 0xB4, 1),
        "landing_pause_started": unsigned(emu, MOUNT + 0xB6, 1),
    }


def wait_until(emu, predicate, limit, mask=0, frame_clock=None):
    for frame in range(limit + 1):
        if predicate():
            return frame
        h.cycle(emu, 1, mask)
        if frame_clock is not None:
            frame_clock["vblank"] += 1
    return None


def boot(emu, save_path, dsv):
    raw_save = h.extract_raw_save(save_path) if dsv else save_path.read_bytes()
    emu.volume_set(0)
    emu.open(str(REPO / "test.nds"))
    with tempfile.NamedTemporaryFile(suffix=".sav") as raw_file:
        raw_file.write(raw_save)
        raw_file.flush()
        emu.backup.import_file(raw_file.name, force_size=0)
        h.cycle(emu, 420)
        for _ in range(8):
            h.tap_key(emu, "A", 24, 36)
        h.cycle(emu, 600)


def mount_party_slot(emu, party_slot, species):
    h.tap_key(emu, "Y", 6, 8)
    visible = wait_until(
        emu,
        lambda: unsigned(emu, SELECTOR_STATE, 1) == 2,
        300,
    )
    selections = [unsigned(emu, SELECTOR_HIGHLIGHT, 1)]
    while selections[-1] != party_slot and len(selections) < 8:
        h.tap_key(emu, "R", 3, 4)
        selections.append(unsigned(emu, SELECTOR_HIGHLIGHT, 1))
    h.tap_key(emu, "SELECT", 6, 10)
    riding = wait_until(
        emu,
        lambda: mount_state(emu)["phase"] == 2
        and unsigned(emu, FOLLOWER_SLOT + 0x0A, 2) == species,
        1800,
    )
    result = {
        "visible": visible,
        "selections": selections,
        "riding": riding,
        "species": unsigned(emu, FOLLOWER_SLOT + 0x0A, 2),
    }
    result["passed"] = (
        visible is not None
        and selections[-1] == party_slot
        and riding is not None
        and result["species"] == species
    )
    return result


def reset_walk_state(emu, travel_time):
    write_u8(emu, MOUNT + 0x7E, travel_time)
    write_u8(emu, MOUNT + 0x7F, travel_time)
    write_u8(emu, MOUNT + 0x80, travel_time)
    write_u8(emu, MOUNT + 0x81, 0)
    write_u8(emu, MOUNT + 0x83, 0xFF)
    for offset in range(0x84, 0x8B):
        write_u8(emu, MOUNT + offset, 0)
    write_u8(emu, MOUNT + 0x8A, 0xFF)


def set_object_facing(emu, obj, direction):
    for offset in (0x28, 0x2C, 0x30, 0x34):
        write_u32(emu, obj + offset, direction)


def place_object_on_tile(emu, obj, x, y):
    for offset in (0x4C, 0x58, 0x64):
        write_u32(emu, obj + offset, x)
    for offset in (0x54, 0x60, 0x6C):
        write_u32(emu, obj + offset, y)
    write_u32(emu, obj + 0x70, (x << 16) + 0x8000)
    write_u32(emu, obj + 0x78, (y << 16) + 0x8000)


def evacuate_wild_objects(emu):
    """Move random wild actors away from a deterministic movement lane."""
    for slot in range(6):
        wild_object = wild_spawn(emu, slot)["object"]
        if wild_object == 0:
            continue
        for offset in (0x4C, 0x58, 0x64):
            write_u32(emu, wild_object + offset, 0)
        for offset in (0x54, 0x60, 0x6C):
            write_u32(emu, wild_object + offset, 0)
        write_u32(emu, wild_object + 0x70, 0x8000)
        write_u32(emu, wild_object + 0x78, 0x8000)


def evacuate_map_event_objects(emu):
    """Move Route 29 event objects away from the transition test route."""
    field_system = unsigned(emu, G_FIELD_SYS_PTR)
    manager = unsigned(emu, field_system + 0x3C)
    object_count = unsigned(emu, manager + 4)
    objects = unsigned(emu, manager + 0x124)
    player = player_ptr(emu)
    follower = unsigned(emu, FOLLOWER_SLOT)
    for slot in range(object_count):
        obj = objects + slot * 0x12C
        if not (unsigned(emu, obj) & 1) or obj in (player, follower):
            continue
        for offset in (0x4C, 0x58, 0x64):
            write_u32(emu, obj + offset, 0)
        for offset in (0x54, 0x60, 0x6C):
            write_u32(emu, obj + offset, 0)
        write_u32(emu, obj + 0x70, 0x8000)
        write_u32(emu, obj + 0x78, 0x8000)


def walk_boundary_case(emu, name, travel_time, keys, trace):
    wait_until(
        emu,
        lambda: mount_state(emu)["mode"] == 0
        and mount_state(emu)["pending"] == 0,
        100,
    )
    reset_walk_state(emu, travel_time)
    trace["active"] = name
    mask = 0
    for key in keys:
        mask |= h.keymask(h.key_constant(key))
    started = None
    for _ in range(200):
        h.cycle(emu, 1, mask)
        state = mount_state(emu)
        if state["mode"] == 4:
            started = dict(state)
            break
    h.set_key_mask(emu, 0)
    completed = None
    if started is not None:
        for _ in range(300):
            state = mount_state(emu)
            position = object_state(emu, player_ptr(emu))
            if (
                state["mode"] == 0
                and position["x"] == started["target_x"]
                and position["y"] == started["target_y"]
            ):
                completed = dict(state)
                break
            h.cycle(emu, 1, 0)
    wait_until(emu, lambda: mount_state(emu)["pending"] == 0, 100)
    player = object_state(emu, player_ptr(emu))
    follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
    calls = trace["cases"].get(name, [])
    elapsed = [call["elapsed"] for call in calls]
    passed = (
        started is not None
        and completed is not None
        and started["frames"] == travel_time
        and started["arc"] == 0
        and elapsed == list(range(travel_time))
        and all(call["frames"] == travel_time for call in calls)
        and player["x"] == started["target_x"]
        and player["y"] == started["target_y"]
        and all(player[key] == follower[key] for key in (
            "x", "y", "pos_x", "pos_y", "pos_z"
        ))
    )
    return {
        "name": name,
        "travel_time": travel_time,
        "start": None if started is None else [started["start_x"], started["start_y"]],
        "target": None if started is None else [started["target_x"], started["target_y"]],
        "elapsed": elapsed,
        "passed": passed,
    }


def run_mounted_walk_tile(emu, direction):
    ready_after = wait_until(
        emu,
        lambda: mount_state(emu)["mode"] == 0
        and mount_state(emu)["pending"] == 0,
        300,
    )
    before = object_state(emu, player_ptr(emu))
    mask = h.keymask(h.key_constant(direction))
    started_after = wait_until(
        emu,
        lambda: mount_state(emu)["mode"] == 4,
        300,
        mask,
    )
    started = dict(mount_state(emu)) if started_after is not None else None
    h.set_key_mask(emu, 0)
    completed_after = None
    if started is not None:
        completed_after = wait_until(
            emu,
            lambda: mount_state(emu)["mode"] == 0
            and mount_state(emu)["pending"] == 0
            and object_state(emu, player_ptr(emu))["x"]
                == started["target_x"]
            and object_state(emu, player_ptr(emu))["y"]
                == started["target_y"],
            300,
        )
    player = object_state(emu, player_ptr(emu))
    follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
    return {
        "ready_after": ready_after,
        "started_after": started_after,
        "completed_after": completed_after,
        "before": [before["x"], before["y"]],
        "start": None if started is None
            else [started["start_x"], started["start_y"]],
        "target": None if started is None
            else [started["target_x"], started["target_y"]],
        "frames": None if started is None else started["frames"],
        "final": [player["x"], player["y"]],
        "pair_synced": all(
            player[key] == follower[key]
            for key in ("x", "y", "pos_x", "pos_y", "pos_z")
        ),
        "passed": ready_after is not None
            and started is not None
            and completed_after is not None
            and [before["x"], before["y"]]
                == [started["start_x"], started["start_y"]]
            and [started["start_x"], started["start_y"]]
                != [started["target_x"], started["target_y"]]
            and [player["x"], player["y"]]
                == [started["target_x"], started["target_y"]]
            and all(
                player[key] == follower[key]
                for key in ("x", "y", "pos_x", "pos_y", "pos_z")
            ),
    }


def scenario_mounted_frames():
    trace = {"active": None, "cases": {}}
    result = {"cases": []}
    with h.silence_native_output(True):
        emu = h.create_desmume()

        def on_update(_address, _size):
            state = mount_state(emu)
            if trace["active"] is None or state["mode"] != 4:
                return
            trace["cases"].setdefault(trace["active"], []).append({
                "frames": state["frames"],
                "elapsed": state["elapsed"],
            })

        emu.memory.register_exec(UPDATE_MOUNT_MOTION, on_update)
        boot(emu, REPO / "test.dsv", True)
        result["mount"] = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        write_u8(emu, MOUNT + 8 + 19, 1)
        result["cases"].append(walk_boundary_case(
            emu, "cardinal_1", 1, ["RIGHT"], trace
        ))
        result["cases"].append(walk_boundary_case(
            emu, "cardinal_5", 5, ["RIGHT"], trace
        ))
        result["cases"].append(walk_boundary_case(
            emu, "cardinal_32", 32, ["RIGHT"], trace
        ))
        result["cases"].append(walk_boundary_case(
            emu, "diagonal_5", 5, ["RIGHT", "DOWN"], trace
        ))
        write_u8(emu, MOUNT + 8 + 19, 2)
        trace["active"] = None
        cardinal_before = object_state(emu, player_ptr(emu))
        right = h.keymask(h.key_constant("RIGHT"))
        h.cycle(emu, 60, right)
        h.set_key_mask(emu, 0)
        h.cycle(emu, 30, 0)
        cardinal_after = object_state(emu, player_ptr(emu))
        cardinal_state = dict(mount_state(emu))
        result["diagonal_only_cardinal"] = {
            "before": [cardinal_before["x"], cardinal_before["y"]],
            "after": [cardinal_after["x"], cardinal_after["y"]],
            "mode": cardinal_state["mode"],
            "pending": cardinal_state["pending"],
        }
        result["cases"].append(walk_boundary_case(
            emu, "diagonal_only", 5, ["RIGHT", "DOWN"], trace
        ))
        result["screenshot"] = h.save_screenshot(
            emu,
            "documentation/verification_screenshots/overworld_walk_frames.png",
        )
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, None)
        emu.destroy()
    diagonal = next(
        case for case in result["cases"] if case["name"] == "diagonal_5"
    )
    diagonal_only = next(
        case for case in result["cases"] if case["name"] == "diagonal_only"
    )
    cardinal_only_attempt = result["diagonal_only_cardinal"]
    result["passed"] = (
        result["mount"]["passed"]
        and all(case["passed"] for case in result["cases"])
        and diagonal["target"][0] - diagonal["start"][0] == 1
        and diagonal["target"][1] - diagonal["start"][1] == 1
        and cardinal_only_attempt["after"] == cardinal_only_attempt["before"]
        and cardinal_only_attempt["mode"] == 0
        and cardinal_only_attempt["pending"] == 0
        and diagonal_only["target"][0] - diagonal_only["start"][0] == 1
        and diagonal_only["target"][1] - diagonal_only["start"][1] == 1
    )
    return result


def scenario_mounted_smoothness():
    events = []
    video_frames = []
    active = {"value": False, "vblank": 0}
    with h.silence_native_output(True):
        emu = h.create_desmume()

        def on_update(_address, _size):
            state = mount_state(emu)
            if not active["value"] or state["mode"] != 4:
                return
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            events.append({
                "vblank": active["vblank"],
                "elapsed": state["elapsed"],
                "frames": state["frames"],
                "start_x": state["start_x"],
                "start_y": state["start_y"],
                "target_x": state["target_x"],
                "target_y": state["target_y"],
                "logical_x": player["x"],
                "logical_y": player["y"],
                "pair_logical_x": follower["x"],
                "pair_logical_y": follower["y"],
                "pos_x": player["pos_x"],
                "pos_y": player["pos_y"],
                "pos_z": player["pos_z"],
                "pair_pos_x": follower["pos_x"],
                "pair_pos_y": follower["pos_y"],
                "pair_pos_z": follower["pos_z"],
                "rider_face_y": player["face_y"],
                "mount_face_y": follower["face_y"],
                "rider_unk88_y": player["unk88_y"],
                "mount_unk88_y": follower["unk88_y"],
                "rider_unk94_y": player["unk94_y"],
                "mount_unk94_y": follower["unk94_y"],
                "rider_facing": player["facing"],
                "mount_facing": follower["facing"],
            })

        emu.memory.register_exec(UPDATE_MOUNT_MOTION, on_update)
        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        initial_player = object_state(emu, player_ptr(emu))
        start_x = initial_player["x"]
        lane_pos_y = initial_player["pos_y"]
        right = h.keymask(h.key_constant("RIGHT"))
        active["value"] = True
        for frame in range(600):
            active["vblank"] = frame
            h.cycle(emu, 1, right)
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            player_render_x = (
                player["pos_x"] + player["face_x"]
                + player["unk88_x"] + player["unk94_x"]
            )
            follower_render_x = (
                follower["pos_x"] + follower["face_x"]
                + follower["unk88_x"] + follower["unk94_x"]
            )
            video_frames.append({
                "vblank": frame,
                "player_render_x": player_render_x,
                "follower_render_x": follower_render_x,
                "separation_x": player_render_x - follower_render_x,
            })
            if object_state(emu, player_ptr(emu))["x"] >= start_x + 7:
                break
        h.set_key_mask(emu, 0)
        settled_after = wait_until(
            emu,
            lambda: mount_state(emu)["mode"] == 0
            and mount_state(emu)["pending"] == 0,
            300,
        )
        active["value"] = False
        end_x = object_state(emu, player_ptr(emu))["x"]
        recovery = run_mounted_walk_tile(emu, "RIGHT")
        avatar = avatar_ptr(emu)
        recovered_avatar = {
            "flags": unsigned(emu, avatar),
            "move_state": unsigned(emu, avatar + 0x10),
            "player_move_state": unsigned(emu, avatar + 0x14),
        }
        screenshot = h.save_screenshot(
            emu,
            "documentation/verification_screenshots/overworld_walk_smoothness.png",
        )
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, None)
        emu.destroy()

    motions = []
    for event in events:
        if event["elapsed"] == 0:
            motions.append([])
        if motions:
            motions[-1].append(event)
    summaries = []
    for motion in motions:
        first = motion[0]
        frames = first["frames"]
        start_pos = (first["start_x"] << 16) + 0x8000
        target_pos = (first["target_x"] << 16) + 0x8000
        expected_z = (first["start_y"] << 16) + 0x8000
        expected_positions = [
            start_pos + (target_pos - start_pos) * elapsed // frames
            for elapsed in range(frames)
        ]
        summaries.append({
            "start_x": first["start_x"],
            "start_y": first["start_y"],
            "target_x": first["target_x"],
            "target_y": first["target_y"],
            "frames": frames,
            "elapsed": [event["elapsed"] for event in motion],
            "positions": [event["pos_x"] for event in motion],
            "expected_positions": expected_positions,
            "expected_pos_y": lane_pos_y,
            "expected_pos_z": expected_z,
            "vblanks": [event["vblank"] for event in motion],
            "logical_positions": [
                [event["logical_x"], event["logical_y"]]
                for event in motion
            ],
            "pair_logical_positions": [
                [event["pair_logical_x"], event["pair_logical_y"]]
                for event in motion
            ],
            "pair_synced": all(
                event["pos_x"] == event["pair_pos_x"]
                and event["pos_y"] == event["pair_pos_y"]
                and event["pos_z"] == event["pair_pos_z"]
                and (
                    event["rider_face_y"]
                    + event["rider_unk88_y"]
                    + event["rider_unk94_y"]
                    - event["mount_face_y"]
                    - event["mount_unk88_y"]
                    - event["mount_unk94_y"]
                ) == 0x8000
                and event["rider_facing"] == event["mount_facing"]
                for event in motion
            ),
            "first_pair_sample": {
                "elapsed": first["elapsed"],
                "rider": {
                    "pos_x": first["pos_x"],
                    "pos_y": first["pos_y"],
                    "pos_z": first["pos_z"],
                    "face_y": first["rider_face_y"],
                    "unk88_y": first["rider_unk88_y"],
                    "unk94_y": first["rider_unk94_y"],
                    "facing": first["rider_facing"],
                },
                "mount": {
                    "pos_x": first["pair_pos_x"],
                    "pos_y": first["pair_pos_y"],
                    "pos_z": first["pair_pos_z"],
                    "face_y": first["mount_face_y"],
                    "unk88_y": first["mount_unk88_y"],
                    "unk94_y": first["mount_unk94_y"],
                    "facing": first["mount_facing"],
                },
            },
            "logical_stable": all(
                event["logical_x"] == event["start_x"]
                and event["logical_y"] == event["start_y"]
                and event["pair_logical_x"] == event["start_x"]
                and event["pair_logical_y"] == event["start_y"]
                for event in motion
            ),
            "lane_stable": all(
                event["start_y"] == event["target_y"]
                and event["pos_y"] == lane_pos_y
                and event["pair_pos_y"] == lane_pos_y
                and event["pos_z"] == expected_z
                and event["pair_pos_z"] == expected_z
                for event in motion
            ),
        })
    callback_gaps = [
        events[index]["vblank"] - events[index - 1]["vblank"]
        for index in range(1, len(events))
    ]
    boundary_gaps = [
        summaries[index]["vblanks"][0]
        - summaries[index - 1]["vblanks"][-1]
        for index in range(1, len(summaries))
    ]
    movement_deltas = [
        events[index]["pos_x"] - events[index - 1]["pos_x"]
        for index in range(1, len(events))
    ]
    acceleration_deltas = [
        abs(movement_deltas[index] - movement_deltas[index - 1])
        for index in range(1, len(movement_deltas))
    ]
    pair_delta_mismatches = []
    for index in range(1, len(video_frames)):
        player_delta = (
            video_frames[index]["player_render_x"]
            - video_frames[index - 1]["player_render_x"]
        )
        follower_delta = (
            video_frames[index]["follower_render_x"]
            - video_frames[index - 1]["follower_render_x"]
        )
        if player_delta != follower_delta:
            pair_delta_mismatches.append({
                "vblank": video_frames[index]["vblank"],
                "player_delta": player_delta,
                "follower_delta": follower_delta,
                "separation_x": video_frames[index]["separation_x"],
            })
    result = {
        "mount": mount,
        "start_x": start_x,
        "end_x": end_x,
        "settled_after": settled_after,
        "recovery": recovery,
        "recovered_avatar": recovered_avatar,
        "motions": summaries,
        "callback_gaps": callback_gaps,
        "boundary_gaps": boundary_gaps,
        "movement_deltas": movement_deltas,
        "max_acceleration_delta": max(acceleration_deltas, default=0),
        "pair_delta_mismatches": pair_delta_mismatches,
        "separation_values": sorted({
            frame["separation_x"] for frame in video_frames
        }),
        "screenshot": screenshot,
    }
    result["passed"] = (
        mount["passed"]
        and end_x == start_x + 7
        and settled_after is not None
        and recovery["passed"]
        and recovery["before"] == [end_x, initial_player["y"]]
        and recovery["final"] == [end_x + 1, initial_player["y"]]
        and (recovered_avatar["flags"] & 1) == 0
        and recovered_avatar["player_move_state"] in (0, 3)
        and [motion["frames"] for motion in summaries[:7]]
            == [8, 8, 8, 4, 4, 4, 2]
        and all(
            summaries[index]["logical_positions"][0]
                == [
                    summaries[index - 1]["target_x"],
                    summaries[index - 1]["target_y"],
                ]
            for index in range(1, 7)
        )
        and [end_x, initial_player["y"]]
            == [summaries[6]["target_x"], summaries[6]["target_y"]]
        and all(
            motion["elapsed"] == list(range(motion["frames"]))
            and motion["positions"] == motion["expected_positions"]
            and motion["pair_synced"]
            and motion["logical_stable"]
            and motion["lane_stable"]
            for motion in summaries[:7]
        )
        and callback_gaps
        and max(callback_gaps) <= 3
        and boundary_gaps
        and max(boundary_gaps) <= 3
        and not pair_delta_mismatches
        and all(
            frame["separation_x"] == -0x8000
            for frame in video_frames
        )
    )
    return result


def scenario_turn_skid():
    result = {"approach": [], "motions": [], "errors": []}
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        result["mount"] = mount_party_slot(emu, 0, 155)
        # Keep random wild placements from blocking the fixed seven-tile lane.
        # These objects belong only to this throwaway emulator session.
        evacuate_wild_objects(emu)
        right = h.keymask(h.key_constant("RIGHT"))
        left = h.keymask(h.key_constant("LEFT"))
        last_tile = (
            object_state(emu, player_ptr(emu))["x"],
            object_state(emu, player_ptr(emu))["y"],
        )
        for _ in range(500):
            state = mount_state(emu)
            position = object_state(emu, player_ptr(emu))
            tile = (position["x"], position["y"])
            if tile != last_tile:
                result["approach"].append([state["speed"], state["counter"]])
                last_tile = tile
                if len(result["approach"]) >= 7 and state["speed"] == 2:
                    break
            h.cycle(emu, 1, right)
        previous_mode = mount_state(emu)["mode"]
        previous_motion = None
        activation = None
        settled = None
        post_turn = None
        for _ in range(500):
            state = mount_state(emu)
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            if state["skid"] and activation is None:
                activation = dict(state)
            motion_signature = (
                state["start_x"],
                state["start_y"],
                state["target_x"],
                state["target_y"],
            )
            if (
                activation is not None
                and state["mode"] == 4
                and motion_signature != previous_motion
            ):
                result["motions"].append({
                    "skid": state["skid"],
                    "frames": state["frames"],
                    "direction": state["direction"],
                    "turn": state["turn"],
                    "start": [state["start_x"], state["start_y"]],
                    "target": [state["target_x"], state["target_y"]],
                    "player_facing": player["facing"],
                    "follower_facing": follower["facing"],
                })
                previous_motion = motion_signature
            if activation is not None and (state["skid"] or state["pending"]):
                if player["facing"] != 3 or follower["facing"] != 3:
                    result["errors"].append("turned during skid")
                if player["x"] != follower["x"] or player["y"] != follower["y"]:
                    result["errors"].append("logical desync")
            if activation is not None and state["skid"] == 0 and state["direction"] == 2:
                settled = dict(state)
                for _ in range(20):
                    h.cycle(emu, 1, left)
                    state = mount_state(emu)
                    if state["mode"] == 4:
                        post_turn = {
                            "state": dict(state),
                            "player_facing": object_state(emu, player_ptr(emu))["facing"],
                            "follower_facing": object_state(
                                emu, unsigned(emu, FOLLOWER_SLOT)
                            )["facing"],
                        }
                        break
                break
            previous_mode = state["mode"]
            h.cycle(emu, 1, left)
        h.set_key_mask(emu, 0)
        result["activation"] = activation
        result["settled"] = settled
        result["post_turn"] = post_turn
        result["screenshot"] = h.save_screenshot(
            emu,
            "documentation/verification_screenshots/overworld_walk_turn_skid.png",
        )
        emu.destroy()
    skid_motions = [motion for motion in result["motions"] if motion["skid"]]
    result["passed"] = (
        result["approach"][:7]
            == [[8, 0], [8, 1], [8, 2], [4, 0], [4, 1], [4, 2], [2, 0]]
        and activation is not None
        and activation["skid"] == 2
        and activation["speed"] == 4
        and activation["direction"] == 3
        and activation["turn"] == 2
        and len(skid_motions) == 2
        and all(motion["frames"] == 4 for motion in skid_motions[:2])
        and all(
            motion["target"][0] == motion["start"][0] + 1
            and motion["player_facing"] == 3
            and motion["follower_facing"] == 3
            for motion in skid_motions[:2]
        )
        and settled is not None
        and settled["speed"] == 2
        and post_turn is not None
        and post_turn["state"]["target_x"] == post_turn["state"]["start_x"] - 1
        and post_turn["player_facing"] == 2
        and post_turn["follower_facing"] == 2
        and not result["errors"]
    )
    return result


def scenario_diagonal_turn_skid():
    result = {"approach": [], "motions": [], "errors": []}
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        result["mount"] = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        write_u8(emu, MOUNT + 8 + 19, 1)
        for _ in range(3):
            result["approach"].append(run_mounted_walk_tile(emu, "RIGHT"))

        player_obj = player_ptr(emu)
        follower_obj = unsigned(emu, FOLLOWER_SLOT)
        set_object_facing(emu, player_obj, 3)
        set_object_facing(emu, follower_obj, 3)
        write_u8(emu, MOUNT + 0x80, 2)
        write_u8(emu, MOUNT + 0x83, 7)
        write_u8(emu, MOUNT + 0x84, 0)
        write_u8(emu, MOUNT + 0x85, 0)
        write_u8(emu, MOUNT + 0x86, 3)
        write_u8(emu, MOUNT + 0x87, 0)
        write_u8(emu, MOUNT + 0x88, 0)
        write_u8(emu, MOUNT + 0x89, 0)
        write_u8(emu, MOUNT + 0x8A, 0xFF)
        write_u8(emu, MOUNT + 0x8B, 0)

        north_west = (
            h.keymask(h.key_constant("UP"))
            | h.keymask(h.key_constant("LEFT"))
        )
        previous_mode = mount_state(emu)["mode"]
        previous_motion = None
        activation = None
        settled = None
        for _ in range(800):
            state = mount_state(emu)
            player = object_state(emu, player_obj)
            follower = object_state(emu, follower_obj)
            if state["skid"] and activation is None:
                activation = dict(state)
            motion_signature = (
                state["start_x"],
                state["start_y"],
                state["target_x"],
                state["target_y"],
            )
            if (
                activation is not None
                and state["mode"] == 4
                and motion_signature != previous_motion
            ):
                motion = {
                    "skid": state["skid"],
                    "frames": state["frames"],
                    "direction": state["direction"],
                    "turn": state["turn"],
                    "start": [state["start_x"], state["start_y"]],
                    "target": [state["target_x"], state["target_y"]],
                    "player_facing": player["facing"],
                    "follower_facing": follower["facing"],
                }
                previous_motion = motion_signature
                if state["skid"]:
                    result["motions"].append(motion)
            if activation is not None and (state["skid"] or state["pending"]):
                if player["facing"] != 3 or follower["facing"] != 3:
                    result["errors"].append("turned during diagonal skid")
                if player["x"] != follower["x"] or player["y"] != follower["y"]:
                    result["errors"].append("logical desync")
            if activation is not None and state["skid"] == 0 and state["direction"] == 4:
                settled = dict(state)
                break
            previous_mode = state["mode"]
            h.cycle(emu, 1, north_west)
        h.set_key_mask(emu, 0)
        result["activation"] = activation
        result["settled"] = settled
        result["final_state"] = mount_state(emu)
        result["final_player"] = object_state(emu, player_obj)
        result["final_follower"] = object_state(emu, follower_obj)
        avatar = avatar_ptr(emu)
        result["avatar"] = {
            "flags": unsigned(emu, avatar),
            "move_state": unsigned(emu, avatar + 0x10),
            "player_move_state": unsigned(emu, avatar + 0x14),
        }
        result["screenshot"] = h.save_screenshot(
            emu,
            "documentation/verification_screenshots/overworld_walk_diagonal_skid.png",
        )
        emu.destroy()
    result["passed"] = (
        result["mount"]["passed"]
        and all(step["passed"] for step in result["approach"])
        and activation is not None
        and activation["skid"] == 2
        and activation["speed"] == 4
        and activation["direction"] == 7
        and activation["turn"] == 4
        and len(result["motions"]) == 2
        and all(
            motion["frames"] == 4
            and motion["direction"] == 7
            and motion["target"][0] == motion["start"][0] + 1
            and motion["target"][1] == motion["start"][1] + 1
            and motion["player_facing"] == 3
            and motion["follower_facing"] == 3
            for motion in result["motions"][:2]
        )
        and settled is not None
        and settled["speed"] == 2
        and result["final_state"]["mode"] == 0
        and result["final_state"]["pending"] == 0
        and result["final_player"]["x"] == result["final_follower"]["x"]
        and result["final_player"]["y"] == result["final_follower"]["y"]
        and (result["avatar"]["flags"] & 1) == 0
        and result["avatar"]["player_move_state"] in (0, 3)
        and not result["errors"]
    )
    return result


def wild_spawn(emu, slot):
    base = WILD_STATE + slot * 20
    return {
        "object": unsigned(emu, base),
        "species": unsigned(emu, base + 0x0A, 2),
        "active": unsigned(emu, base + 0x10, 1),
    }


def scenario_cherrygrove_surf_spawn_terrain():
    """Reject a Cherrygrove Surf encounter when no Surf tile was prepared."""
    finalize_attempts = []
    spawn_events = []
    reached_cherrygrove = False
    finalize_prepared = WILD_SYMBOLS[
        "OverworldWildSpawns_FinalizePreparedSpawn"
    ]
    spawn_prepared = WILD_SYMBOLS["OverworldWildSpawns_SpawnPreparedEncounter"]
    try_refill = WILD_SYMBOLS["OverworldWildSpawns_TryRefill"]
    try_pick_destination = WILD_SYMBOLS[
        "OverworldWildSpawns_TryPickSpawnDestinationMask"
    ]

    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)

        def current_map_id():
            return unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET, 2)

        def on_spawn_prepared(_address, _size):
            regs = emu.memory.register_arm9
            prepared = unsigned(emu, regs.sp)
            if prepared == 0 or current_map_id() != MAP_CHERRYGROVE:
                return
            spawn_events.append({
                "terrain": regs.r2,
                "slot": regs.r3,
                "x": signed(emu, prepared),
                "y": signed(emu, prepared + 4),
                "species": unsigned(emu, prepared + 16, 2),
                "level": unsigned(emu, prepared + 19, 1),
            })

        def on_finalize_prepared(_address, _size):
            regs = emu.memory.register_arm9
            prepared = unsigned(emu, regs.sp)
            if prepared == 0 or current_map_id() != MAP_CHERRYGROVE:
                return
            finalize_attempts.append({
                "terrain": regs.r2,
                "slot": regs.r3,
                "x": signed(emu, prepared),
                "y": signed(emu, prepared + 4),
                "species": unsigned(emu, prepared + 16, 2),
                "level": unsigned(emu, prepared + 19, 1),
            })

        def on_try_refill(_address, _size):
            if current_map_id() == MAP_CHERRYGROVE:
                write_u32(emu, LCRNG_STATE, 0)

        def on_try_pick_destination(_address, _size):
            write_u32(emu, LCRNG_STATE, 0)

        emu.memory.register_exec(finalize_prepared, on_finalize_prepared)
        emu.memory.register_exec(spawn_prepared, on_spawn_prepared)
        emu.memory.register_exec(try_refill, on_try_refill)
        emu.memory.register_exec(
            try_pick_destination,
            on_try_pick_destination,
        )

        # The deterministic save starts just east of Cherrygrove with its menu
        # open. Close it and cross the west map boundary.
        h.cycle(emu, 2, h.keymask(h.key_constant("B")))
        h.cycle(emu, 30, 0)
        for _ in range(500):
            if current_map_id() == MAP_CHERRYGROVE:
                reached_cherrygrove = True
                break
            h.cycle(emu, 1, h.keymask(h.key_constant("LEFT")))

        for _ in range(600):
            h.cycle(emu, 1, 0)
            if any(
                attempt["species"] == SPECIES_TENTACOOL
                for attempt in finalize_attempts
            ):
                break

        emu.memory.register_exec(finalize_prepared, None)
        emu.memory.register_exec(spawn_prepared, None)
        emu.memory.register_exec(try_refill, None)
        emu.memory.register_exec(try_pick_destination, None)
        emu.destroy()

    tentacool_attempts = [
        attempt
        for attempt in finalize_attempts
        if attempt["species"] == SPECIES_TENTACOOL
    ]
    tentacool_events = [
        event
        for event in spawn_events
        if event["species"] == SPECIES_TENTACOOL
    ]
    result = {
        "reached_cherrygrove": reached_cherrygrove,
        "tentacool_attempts": tentacool_attempts,
        "tentacool_events": tentacool_events,
    }
    result["passed"] = (
        reached_cherrygrove
        and any(
            attempt["terrain"] == SPAWN_TERRAIN_SURF
            and attempt["x"] < 0
            and attempt["y"] < 0
            for attempt in tentacool_attempts
        )
        and not tentacool_events
    )
    return result


def scenario_wild_walk():
    moves = []
    active_moves = {}
    with h.silence_native_output(True):
        emu = h.create_desmume()

        def on_render(_address, _size):
            regs = emu.memory.register_arm9
            runtime = unsigned(emu, WILD_STATE + WILD_RUNTIME_PTR_OFFSET)
            slot = regs.r1
            if runtime == 0 or slot >= 10:
                return
            if unsigned(emu, runtime + WILD_MOTION_MODES_OFFSET + slot, 1) != 1:
                return
            obj = regs.r2
            elapsed = regs.r3
            frames = unsigned(
                emu, runtime + WILD_FRAME_COUNTS_OFFSET + slot * 2, 2
            )
            if slot not in active_moves:
                state = object_state(emu, obj)
                move = {
                    "slot": slot,
                    "species": wild_spawn(emu, slot)["species"],
                    "object": obj,
                    "start": [
                        signed(emu, runtime + WILD_START_X_OFFSET + slot * 2, 2),
                        signed(emu, runtime + WILD_START_Y_OFFSET + slot * 2, 2),
                    ],
                    "target": [
                        signed(emu, runtime + WILD_TARGET_X_OFFSET + slot * 2, 2),
                        signed(emu, runtime + WILD_TARGET_Y_OFFSET + slot * 2, 2),
                    ],
                    "logical_at_first_render": [state["x"], state["y"]],
                    "frames": frames,
                    "arc": unsigned(emu, runtime + WILD_ARC_OFFSET + slot, 1),
                    "elapsed": [],
                    "state_elapsed": [],
                    "logical_positions": [],
                    "render_positions": [],
                    "clear_observed": False,
                    "completed": False,
                }
                active_moves[slot] = move
                moves.append(move)
            move = active_moves[slot]
            move["elapsed"].append(elapsed)
            move["state_elapsed"].append(unsigned(
                emu, runtime + WILD_ELAPSED_OFFSET + slot * 2, 2
            ))
            state = object_state(emu, obj)
            move["logical_positions"].append([state["x"], state["y"]])
            move["render_positions"].append([state["pos_x"], state["pos_z"]])

        def on_clear(_address, _size):
            slot = emu.memory.register_arm9.r1
            move = active_moves.get(slot)
            if move is None:
                return
            state = object_state(emu, move["object"])
            move["final"] = [state["x"], state["y"]]
            move["clear_observed"] = True
            move["completed"] = True
            active_moves.pop(slot)

        boot(emu, REPO / "test.dsv", True)
        emu.memory.register_exec(APPLY_WILD_RENDER, on_render)
        emu.memory.register_exec(CLEAR_WILD_JUMP, on_clear)
        right = h.keymask(h.key_constant("RIGHT"))
        for frame in range(5000):
            h.cycle(emu, 1, right if frame < 300 else 0)
            if sum(
                move["completed"]
                and move["species"] == 19
                and move["slot"] != 7
                for move in moves
            ) >= 2:
                break
        result = {
            "spawns": [
                {"slot": slot, **wild_spawn(emu, slot)}
                for slot in range(10)
                if wild_spawn(emu, slot)["active"]
            ],
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/overworld_wild_walk.png",
            ),
        }
        emu.memory.register_exec(APPLY_WILD_RENDER, None)
        emu.memory.register_exec(CLEAR_WILD_JUMP, None)
        emu.destroy()
    completed = [
        move
        for move in moves
        if move["completed"] and move["species"] == 19 and move["slot"] != 7
    ]
    result["moves"] = moves
    result["passed"] = (
        len(completed) >= 2
        and all(
            move["species"] == 19
            and move["slot"] != 7
            and move["arc"] == 0
            and move["frames"] == 4
            and move["start"] != move["target"]
            and move["logical_at_first_render"] == move["start"]
            and move["logical_positions"]
            and all(
                position in (move["start"], move["target"])
                for position in move["logical_positions"]
            )
            and move["logical_positions"][-1] == move["target"]
            and sum(
                move["logical_positions"][index]
                    != move["logical_positions"][index - 1]
                for index in range(1, len(move["logical_positions"]))
            ) == 1
            and move["elapsed"] == list(range(1, move["frames"] + 1))
            and move["state_elapsed"] == move["elapsed"]
            and move["render_positions"] == [
                [
                    (move["start"][0] << 16) + 0x8000
                    + ((move["target"][0] - move["start"][0]) << 16)
                    * elapsed // move["frames"],
                    (move["start"][1] << 16) + 0x8000
                    + ((move["target"][1] - move["start"][1]) << 16)
                    * elapsed // move["frames"],
                ]
                for elapsed in range(move["frames"])
            ]
            and move["clear_observed"]
            and move["final"] == move["target"]
            for move in completed
        )
    )
    return result


def scenario_wild_ledge_hop():
    """Exercise a real south-facing Route 29 ledge with a wild Rattata."""
    origin = [590, 395]
    target = [590, 397]
    slot = 0
    native_jump_calls = []
    ledge_samples = []
    custom_ledge_started = False
    completed = False
    slot_stable = True
    screenshot = None
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)

        def slot_is_clean_and_idle():
            current = wild_spawn(emu, slot)
            runtime = unsigned(emu, WILD_STATE + WILD_RUNTIME_PTR_OFFSET)
            if (
                runtime == 0
                or not current["active"]
                or current["species"] != 19
                or current["object"] == 0
            ):
                return False
            state = object_state(emu, current["object"])
            return (
                (unsigned(
                    emu,
                    WILD_STATE + WILD_MOVEMENT_IN_PROGRESS_MASK_OFFSET,
                    2,
                ) & (1 << slot)) == 0
                and unsigned(emu, runtime + WILD_PREP_ACTIVE_OFFSET + slot, 1) == 0
                and unsigned(emu, runtime + WILD_ACTIVE_OFFSET + slot, 1) == 0
                and unsigned(
                    emu,
                    runtime + WILD_MOTION_MODES_OFFSET + slot,
                    1,
                ) == 0
                and state["unk88_y"] == 0
                and state["unk94_y"] == 0
                and state["movement_cmd"] == 0xFF
            )

        ready = wait_until(
            emu,
            slot_is_clean_and_idle,
            600,
        )
        spawn = wild_spawn(emu, slot)
        obj = spawn["object"]
        initial = object_state(emu, obj) if obj else None

        def on_start_native_jump(_address, _size):
            regs = emu.memory.register_arm9
            if regs.r0 != obj:
                return
            native_jump_calls.append({
                "direction": regs.r1,
                "delta": regs.r2,
                "frames": regs.r3,
                "jump_type": unsigned(emu, regs.r13),
                "arc_table": signed(emu, regs.r13 + 4),
                "arc_step": unsigned(emu, regs.r13 + 8),
            })

        emu.memory.register_exec(START_NATIVE_JUMP, on_start_native_jump)
        if ready is not None:
            place_object_on_tile(emu, obj, *origin)
            set_object_facing(emu, obj, 1)
            write_u8(
                emu,
                WILD_STATE + WILD_MOVEMENT_COOLDOWNS_OFFSET + slot,
                0,
            )

            for _ in range(1200):
                current_spawn = wild_spawn(emu, slot)
                runtime = unsigned(emu, WILD_STATE + WILD_RUNTIME_PTR_OFFSET)
                state = object_state(emu, obj)
                if (
                    not current_spawn["active"]
                    or current_spawn["species"] != 19
                    or current_spawn["object"] != obj
                ):
                    slot_stable = False
                    break
                mode = unsigned(
                    emu,
                    runtime + WILD_MOTION_MODES_OFFSET + slot,
                    1,
                )
                if (
                    mode == 2
                    and signed(
                        emu,
                        runtime + WILD_TARGET_X_OFFSET + slot * 2,
                        2,
                    ) == target[0]
                    and signed(
                        emu,
                        runtime + WILD_TARGET_Y_OFFSET + slot * 2,
                        2,
                    ) == target[1]
                ):
                    custom_ledge_started = True
                in_progress = unsigned(
                    emu,
                    WILD_STATE + WILD_MOVEMENT_IN_PROGRESS_MASK_OFFSET,
                    2,
                ) & (1 << slot)
                if custom_ledge_started and mode == 2:
                    sample = {
                        "elapsed": unsigned(
                            emu,
                            runtime + WILD_ELAPSED_OFFSET + slot * 2,
                            2,
                        ),
                        "frames": unsigned(
                            emu,
                            runtime + WILD_FRAME_COUNTS_OFFSET + slot * 2,
                            2,
                        ),
                        "arc": unsigned(
                            emu,
                            runtime + WILD_ARC_OFFSET + slot,
                            1,
                        ),
                        "start_x": signed(
                            emu,
                            runtime + WILD_START_X_OFFSET + slot * 2,
                            2,
                        ),
                        "start_y": signed(
                            emu,
                            runtime + WILD_START_Y_OFFSET + slot * 2,
                            2,
                        ),
                        "x": state["x"],
                        "y": state["y"],
                        "pos_x": state["pos_x"],
                        "pos_y": state["pos_y"],
                        "pos_z": state["pos_z"],
                        "unk88_y": state["unk88_y"],
                        "unk94_y": state["unk94_y"],
                        "flags": state["flags"],
                    }
                    ledge_samples.append(sample)
                    if (
                        screenshot is None
                        and sample["frames"] > 0
                        and sample["elapsed"] * 2 >= sample["frames"] - 1
                        and sample["unk88_y"] > 0
                    ):
                        screenshot = h.save_screenshot(
                            emu,
                            "documentation/verification_screenshots/overworld_wild_ledge_hop.png",
                        )
                elif custom_ledge_started:
                    completed = (
                        not in_progress
                        and [state["x"], state["y"]] == target
                        and state["pos_x"] == (target[0] << 16) + 0x8000
                        and state["pos_z"] == (target[1] << 16) + 0x8000
                        and state["unk88_y"] == 0
                        and state["unk94_y"] == 0
                        and state["movement_cmd"] == 0xFF
                        and state["movement_step"] == 0
                        and unsigned(
                            emu,
                            runtime + WILD_PREP_ACTIVE_OFFSET + slot,
                            1,
                        ) == 0
                        and unsigned(
                            emu,
                            runtime + WILD_ACTIVE_OFFSET + slot,
                            1,
                        ) == 0
                        and mode == 0
                    )
                    if completed:
                        break
                elif not in_progress and [state["x"], state["y"]] != origin:
                    place_object_on_tile(emu, obj, *origin)
                    set_object_facing(emu, obj, 1)
                    write_u8(
                        emu,
                        WILD_STATE + WILD_MOVEMENT_COOLDOWNS_OFFSET + slot,
                        0,
                    )
                h.cycle(emu, 1, 0)

        final = object_state(emu, obj) if obj else None
        final_spawn = wild_spawn(emu, slot)
        if screenshot is None:
            screenshot = h.save_screenshot(
                emu,
                "documentation/verification_screenshots/overworld_wild_ledge_hop.png",
            )
        emu.memory.register_exec(START_NATIVE_JUMP, None)
        emu.destroy()

    unique_samples = [
        sample
        for index, sample in enumerate(ledge_samples)
        if index == 0
        or sample["elapsed"] != ledge_samples[index - 1]["elapsed"]
    ]
    frame_count = unique_samples[0]["frames"] if unique_samples else 0
    arc_height = unique_samples[0]["arc"] if unique_samples else 0
    expected_arc_samples = [
        [
            elapsed,
            arc_height * (((
                4 * elapsed * (frame_count - elapsed) // frame_count
            ) << 12) // frame_count),
        ]
        for elapsed in range(frame_count)
    ] if frame_count else []
    actual_arc_samples = [
        [sample["elapsed"], sample["unk88_y"]]
        for sample in unique_samples
    ]
    expected_render_positions = [
        [
            (origin[0] << 16) + 0x8000,
            (origin[1] << 16) + 0x8000
                + ((target[1] - origin[1]) << 16) * elapsed
                // frame_count,
        ]
        for elapsed in range(frame_count)
    ] if frame_count else []
    actual_render_positions = [
        [sample["pos_x"], sample["pos_z"]]
        for sample in unique_samples
    ]
    result = {
        "ready": ready,
        "spawn": spawn,
        "initial": initial,
        "origin": origin,
        "target": target,
        "native_jump_calls": native_jump_calls,
        "custom_ledge_started": custom_ledge_started,
        "completed": completed,
        "slot_stable": slot_stable,
        "arc_samples": actual_arc_samples,
        "expected_arc_samples": expected_arc_samples,
        "render_positions": actual_render_positions,
        "expected_render_positions": expected_render_positions,
        "final_spawn": final_spawn,
        "final": final,
        "screenshot": screenshot,
    }
    result["passed"] = (
        ready is not None
        and spawn["active"]
        and spawn["species"] == 19
        and initial is not None
        and custom_ledge_started
        and completed
        and slot_stable
        and not native_jump_calls
        and frame_count == 7
        and arc_height == 16
        and [unique_samples[0]["start_x"], unique_samples[0]["start_y"]]
            == origin
        and actual_arc_samples == expected_arc_samples
        and actual_render_positions == expected_render_positions
        and all((sample["flags"] & (1 << 9)) == 0 for sample in unique_samples)
        and final_spawn["active"]
        and final_spawn["species"] == 19
        and final_spawn["object"] == obj
        and final is not None
        and [final["x"], final["y"]] == target
    )
    return result


def scenario_ledyba_chain_pause():
    """Exercise Ledyba's configured reposition-skid action in the live ROM."""
    trace = {
        "profile": None,
        "prepared": [],
        "action_calls": [],
        "reposition_calls": [],
        "motions": [],
        "natural_steps_before": None,
    }
    pending_prepare = {"target": False, "phase": 0}
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        target_slot = next(
            (
                slot
                for slot in range(6)
                if wild_spawn(emu, slot)["active"]
                and wild_spawn(emu, slot)["object"] != 0
            ),
            None,
        )
        if target_slot is None:
            emu.destroy()
            return {"passed": False, "error": "no active land spawn"}

        spawn_base = WILD_STATE + target_slot * 20
        write_u8(emu, spawn_base + 0x0A, 165)
        write_u8(emu, spawn_base + 0x0B, 0)
        target_object = wild_spawn(emu, target_slot)["object"]
        evacuate_wild_objects(emu)
        place_object_on_tile(emu, target_object, 587, 399)
        set_object_facing(emu, target_object, 1)
        write_u8(
            emu,
            WILD_STATE + WILD_MOVEMENT_COOLDOWNS_OFFSET + target_slot,
            0,
        )

        def on_apply_chain_pause(_address, _size):
            regs = emu.memory.register_arm9
            if regs.r1 != target_slot:
                return
            profile = regs.r2
            trace["profile"] = {
                "chain_moves": unsigned(emu, profile + 29, 1),
                "action": unsigned(emu, profile + 31, 1),
                "variance": unsigned(emu, profile + 44, 1),
                "reposition_count": unsigned(emu, profile + 57, 1),
                "reposition_time": unsigned(emu, profile + 60, 1),
                "reposition_distance": unsigned(emu, profile + 61, 1),
                "allow_cardinal": unsigned(emu, profile + 63, 1),
                "allow_diagonal": unsigned(emu, profile + 64, 1),
                "action_chance": unsigned(emu, profile + 67, 1),
            }
            pending_prepare["target"] = True

        def on_prepare_chain_pause(_address, _size):
            if not pending_prepare["target"]:
                return
            pending_prepare["target"] = False
            regs = emu.memory.register_arm9
            lane = unsigned(emu, regs.sp + 4)
            locomotion = unsigned(emu, regs.sp + 8) & 0xFF
            steps_before = unsigned(emu, regs.r0, 1)
            if pending_prepare["phase"] == 0:
                # Reset the borrowed live spawn's old counter. Let the policy
                # sample Ledyba's real 8+variance chain on this completion.
                write_u8(emu, regs.r0, 0)
                pending_prepare["phase"] = 1
            elif pending_prepare["phase"] == 1:
                trace["natural_steps_before"] = steps_before
                # Trigger the action on this completion after proving the
                # naturally sampled counter used the configured range.
                write_u8(emu, regs.r0, 1)
                pending_prepare["phase"] = 2
            trace["prepared"].append(
                {
                    "steps_before": steps_before,
                    "locomotion": locomotion,
                    "action": unsigned(emu, lane + 31, 1),
                }
            )

        def on_try_start_action(_address, _size):
            regs = emu.memory.register_arm9
            if regs.r1 != target_slot:
                return
            trace["action_calls"].append(
                {
                    "action": regs.r3 & 0xFF,
                    "position": [
                        object_state(emu, target_object)["x"],
                        object_state(emu, target_object)["y"],
                    ],
                }
            )

        def on_run_reposition(_address, _size):
            regs = emu.memory.register_arm9
            if regs.r1 != target_slot:
                return
            trace["reposition_calls"].append(
                {
                    "remaining": unsigned(emu, regs.r3, 1),
                    "pending_direction": unsigned(
                        emu,
                        WILD_STATE + 0x1B2 + target_slot,
                        1,
                    ),
                    "position": [
                        object_state(emu, target_object)["x"],
                        object_state(emu, target_object)["y"],
                    ],
                }
            )

        def on_render(_address, _size):
            regs = emu.memory.register_arm9
            slot = regs.r1
            if slot != target_slot or not trace["action_calls"]:
                return
            runtime = unsigned(emu, WILD_STATE + WILD_RUNTIME_PTR_OFFSET)
            if runtime == 0:
                return
            elapsed = regs.r3
            motion_key = (
                signed(emu, runtime + WILD_START_X_OFFSET + slot * 2, 2),
                signed(emu, runtime + WILD_START_Y_OFFSET + slot * 2, 2),
                signed(emu, runtime + WILD_TARGET_X_OFFSET + slot * 2, 2),
                signed(emu, runtime + WILD_TARGET_Y_OFFSET + slot * 2, 2),
            )
            if elapsed != 1:
                return
            trace["motions"].append(
                {
                    "start": list(motion_key[:2]),
                    "target": list(motion_key[2:]),
                    "frames": unsigned(
                        emu,
                        runtime + WILD_FRAME_COUNTS_OFFSET + slot * 2,
                        2,
                    ),
                }
            )

        emu.memory.register_exec(APPLY_CHAIN_PAUSE, on_apply_chain_pause)
        emu.memory.register_exec(PREPARE_CHAIN_PAUSE, on_prepare_chain_pause)
        emu.memory.register_exec(
            TRY_START_CHAIN_PAUSE_ACTION,
            on_try_start_action,
        )
        emu.memory.register_exec(RUN_CHAIN_REPOSITION, on_run_reposition)
        emu.memory.register_exec(APPLY_WILD_RENDER, on_render)
        for _frame in range(12000):
            h.cycle(emu, 1)
            if len(trace["reposition_calls"]) >= 5:
                break
        trace["target"] = {
            "slot": target_slot,
            "species": wild_spawn(emu, target_slot)["species"],
            "final": [
                object_state(emu, target_object)["x"],
                object_state(emu, target_object)["y"],
            ],
        }
        trace["screenshot"] = h.save_screenshot(
            emu,
            "documentation/verification_screenshots/ledyba_chain_pause.png",
        )
        for address in (
            APPLY_CHAIN_PAUSE,
            PREPARE_CHAIN_PAUSE,
            TRY_START_CHAIN_PAUSE_ACTION,
            RUN_CHAIN_REPOSITION,
            APPLY_WILD_RENDER,
        ):
            emu.memory.register_exec(address, None)
        emu.destroy()

    profile = trace["profile"] or {}
    motions = trace["motions"]
    origin = trace["action_calls"][0]["position"] \
        if trace["action_calls"] else None
    continuous_reposition = (
        len(motions) == 4
        and origin is not None
        and motions[0]["start"] == origin
        and all(
            motions[index]["start"] == motions[index - 1]["target"]
            for index in range(1, len(motions))
        )
        and trace["target"]["final"] == motions[-1]["target"]
    )
    canonical_directions = {
        (0, -2): 0,
        (0, 2): 1,
        (-2, 0): 2,
        (2, 0): 3,
        (-2, -2): 4,
        (2, -2): 5,
        (-2, 2): 6,
        (2, 2): 7,
    }
    directions_match = len(trace["reposition_calls"]) >= len(motions) + 1 \
        and all(
            trace["reposition_calls"][index + 1]["pending_direction"]
            == canonical_directions.get(
                (
                    motion["target"][0] - motion["start"][0],
                    motion["target"][1] - motion["start"][1],
                )
            )
            for index, motion in enumerate(motions)
        )
    trace["directions_match"] = directions_match
    trace["passed"] = (
        profile == {
            "chain_moves": 8,
            "action": 5,
            "variance": 6,
            "reposition_count": 4,
            "reposition_time": 8,
            "reposition_distance": 2,
            "allow_cardinal": 0,
            "allow_diagonal": 1,
            "action_chance": 60,
        }
        and any(call["action"] == 5 for call in trace["action_calls"])
        and trace["natural_steps_before"] in range(7, 14)
        and len(trace["reposition_calls"]) >= 5
        and [
            call["remaining"] & 0x0F
            for call in trace["reposition_calls"][1:5]
        ] == [4, 3, 2, 1]
        and continuous_reposition
        and directions_match
        and all(
            motion["frames"] == 16
            and abs(motion["target"][0] - motion["start"][0]) == 2
            and abs(motion["target"][1] - motion["start"][1]) == 2
            for motion in motions
        )
    )
    return trace


def run_mankey_hop(emu, direction):
    ready_after = wait_until(
        emu,
        lambda: mount_state(emu)["mode"] == 0
        and mount_state(emu)["cooldown"] == 0
        and mount_state(emu)["pending"] == 0,
        1000,
    )
    before = object_state(emu, player_ptr(emu))
    mask = h.keymask(h.key_constant(direction))
    started_after = wait_until(
        emu,
        lambda: mount_state(emu)["mode"] == 1,
        500,
        mask,
    )
    if ready_after is None or started_after is None:
        return {
            "direction": direction,
            "ready_after": ready_after,
            "started_after": started_after,
            "passed": False,
        }
    start = dict(mount_state(emu))
    errors = []
    elapsed = []
    arc_samples = []
    base_face_y = object_state(emu, unsigned(emu, FOLLOWER_SLOT))["face_y"]
    for frame in range(1000):
        state = mount_state(emu)
        player = object_state(emu, player_ptr(emu))
        follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
        if state["mode"] == 1:
            elapsed.append(state["elapsed"])
            arc_samples.append([
                state["elapsed"],
                follower["face_y"] - base_face_y,
            ])
            if (
                any(player[key] != follower[key] for key in (
                    "x", "y", "pos_x", "pos_y", "pos_z"
                ))
                or player["face_y"] - follower["face_y"] != 0x8000
                or player["unk88_y"] != follower["unk88_y"]
                or player["unk94_y"] != 0
                or follower["unk94_y"] != 0
            ):
                errors.append(frame)
        elif frame:
            break
        h.cycle(emu, 1, mask)
    h.set_key_mask(emu, 0)
    recovered_after = wait_until(
        emu,
        lambda: mount_state(emu)["mode"] == 0
        and mount_state(emu)["cooldown"] == 0
        and mount_state(emu)["pending"] == 0,
        1000,
    )
    player = object_state(emu, player_ptr(emu))
    follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
    final_state = mount_state(emu)
    avatar = avatar_ptr(emu)
    elapsed_changes = [
        value
        for index, value in enumerate(elapsed)
        if index == 0 or value != elapsed[index - 1]
    ]
    unique_arc_samples = [
        sample
        for index, sample in enumerate(arc_samples)
        if index == 0 or sample[0] != arc_samples[index - 1][0]
    ]
    expected_arc_samples = [
        [
            elapsed_value,
            start["arc"] * (((
                4 * elapsed_value
                * (start["frames"] - elapsed_value)
                // start["frames"]
            ) << 12) // start["frames"]),
        ]
        for elapsed_value in range(start["frames"] + 1)
    ]
    delta_x = start["target_x"] - start["start_x"]
    delta_y = start["target_y"] - start["start_y"]
    requested_axis_matches = {
        "DOWN": delta_x == 0 and delta_y > 0,
        "RIGHT": delta_x > 0 and delta_y == 0,
        "LEFT": delta_x < 0 and delta_y == 0,
    }.get(direction, False)
    return {
        "direction": direction,
        "ready_after": ready_after,
        "started_after": started_after,
        "recovered_after": recovered_after,
        "before": [before["x"], before["y"]],
        "start": [start["start_x"], start["start_y"]],
        "target": [start["target_x"], start["target_y"]],
        "frames": start["frames"],
        "elapsed": elapsed_changes,
        "arc_samples": unique_arc_samples,
        "expected_arc_samples": expected_arc_samples,
        "final": [player["x"], player["y"]],
        "errors": errors[:5],
        "passed": recovered_after is not None
            and start["frames"] > 0
            and start["arc"] > 0
            and elapsed_changes == list(range(start["frames"] + 1))
            and unique_arc_samples == expected_arc_samples
            and requested_axis_matches
            and [before["x"], before["y"]]
                == [start["start_x"], start["start_y"]]
            and [start["target_x"], start["target_y"]]
                != [start["start_x"], start["start_y"]]
            and [player["x"], player["y"]]
                == [start["target_x"], start["target_y"]]
            and not errors
            and player["x"] == follower["x"]
            and player["y"] == follower["y"]
            and final_state["phase"] == 2
            and final_state["attached"] == 1
            and (unsigned(emu, avatar) & 1) == 0,
    }


def scenario_mankey_hops():
    result = {}
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.sav", False)
        result["mount"] = mount_party_slot(emu, 2, 56)
        result["hops"] = [
            run_mankey_hop(emu, "DOWN"),
            run_mankey_hop(emu, "RIGHT"),
            run_mankey_hop(emu, "LEFT"),
        ]
        result["screenshot"] = h.save_screenshot(
            emu,
            "documentation/verification_screenshots/overworld_mankey_hops.png",
        )
        emu.destroy()
    result["passed"] = (
        result["mount"]["passed"]
        and all(hop["passed"] for hop in result["hops"])
    )
    return result


def scenario_mankey_control_stress():
    target_hops = int(os.environ.get("MOUNT_STRESS_HOPS", "200"))
    key_plan = (
        ("UP",),
        ("UP", "RIGHT"),
        ("RIGHT",),
        ("DOWN", "RIGHT"),
        ("DOWN",),
        ("DOWN", "LEFT"),
        ("LEFT",),
        ("UP", "LEFT"),
    )
    clock = {"vblank": 0}
    attempt = {"keys": None}
    motions = []
    active_motion = None
    failure = None
    blocked_attempts = 0
    maps_seen = set()
    toggle_trace = []
    trace_toggle = {"active": False}

    def finish_motion():
        nonlocal active_motion, failure
        if active_motion is None:
            return
        frames = active_motion["frames"]
        active_motion["map_transition"] = (
            len(set(active_motion["maps"])) > 1
        )
        schedule_valid = active_motion["max_gap"] <= 3 or (
            active_motion["max_gap"] == 4
            and active_motion["map_transition"]
        )
        active_motion["passed"] = (
            active_motion["elapsed"] == list(range(frames + 1))
            and schedule_valid
            and not active_motion["errors"]
        )
        if not active_motion["passed"] and failure is None:
            failure = "invalid Mankey motion callback sequence"
        motions.append(active_motion)
        active_motion = None

    with h.silence_native_output(True):
        emu = h.create_desmume()

        def on_update(_address, _size):
            nonlocal active_motion
            state = dict(mount_state(emu))
            if state["mode"] != 1:
                return
            signature = (
                state["start_x"],
                state["start_y"],
                state["target_x"],
                state["target_y"],
            )
            if active_motion is None or active_motion["signature"] != signature:
                finish_motion()
                active_motion = {
                    "signature": signature,
                    "keys": attempt["keys"],
                    "frames": state["frames"],
                    "elapsed": [],
                    "vblanks": [],
                    "maps": [],
                    "max_gap": 0,
                    "errors": [],
                }
            active_motion["elapsed"].append(state["elapsed"])
            active_motion["vblanks"].append(clock["vblank"])
            active_motion["maps"].append(
                unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET)
            )
            if len(active_motion["vblanks"]) > 1:
                gap = (
                    active_motion["vblanks"][-1]
                    - active_motion["vblanks"][-2]
                )
                active_motion["max_gap"] = max(
                    active_motion["max_gap"], gap
                )
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            if any(
                player[key] != follower[key]
                for key in ("x", "y", "pos_x", "pos_y", "pos_z")
            ):
                active_motion["errors"].append("rider and mount separated")
            if player["face_y"] - follower["face_y"] != 0x8000:
                active_motion["errors"].append("rider height separated")

        def on_mount_tick(_address, _size):
            if not trace_toggle["active"]:
                return
            avatar = avatar_ptr(emu)
            field_system = unsigned(emu, G_FIELD_SYS_PTR)
            sample = {
                "keys": emu.memory.register_arm9.r2,
                "previous_toggle_down": unsigned(emu, MOUNT + 0x7B, 1),
                "phase": mount_state(emu)["phase"],
                "taskman": unsigned(emu, field_system + 0x10),
                "avatar_flags": unsigned(emu, avatar),
                "avatar_move_state": unsigned(emu, avatar + 0x10),
                "player_move_state": unsigned(emu, avatar + 0x14),
            }
            if not toggle_trace or sample != toggle_trace[-1]:
                toggle_trace.append(sample)

        boot(emu, REPO / "test.sav", False)
        mount = mount_party_slot(emu, 2, 56)
        evacuate_wild_objects(emu)
        initial_ready_after = wait_until(
            emu,
            lambda: mount_state(emu)["mode"] == 0
            and mount_state(emu)["cooldown"] == 0
            and mount_state(emu)["stream_preparing"] == 0,
            2400,
        )
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, on_update)

        for hop_index in range(target_hops):
            ready_after = wait_until(
                emu,
                lambda: mount_state(emu)["mode"] == 0
                and mount_state(emu)["cooldown"] == 0
                and mount_state(emu)["pending"] == 0
                and mount_state(emu)["stream_preparing"] == 0,
                1800,
            )
            if ready_after is None:
                failure = "Mankey did not return to an input-ready state"
                break
            finish_motion()
            maps_seen.add(unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET))
            started = None
            for key_offset in range(len(key_plan)):
                keys = key_plan[(hop_index + key_offset) % len(key_plan)]
                mask = 0
                for key in keys:
                    mask |= h.keymask(h.key_constant(key))
                attempt["keys"] = "+".join(keys)
                started_after = wait_until(
                    emu,
                    lambda: mount_state(emu)["mode"] == 1,
                    90,
                    mask,
                    clock,
                )
                h.set_key_mask(emu, 0)
                if started_after is not None:
                    started = dict(mount_state(emu))
                    break
                blocked_attempts += 1
                h.cycle(emu, 3, 0)
            if started is None:
                failure = "no direction could start another Mankey hop"
                break
            completed_after = wait_until(
                emu,
                lambda: mount_state(emu)["mode"] == 0
                and mount_state(emu)["cooldown"] == 0
                and mount_state(emu)["stream_preparing"] == 0,
                2400,
                frame_clock=clock,
            )
            if completed_after is None:
                failure = "Mankey hop or landing pause did not finish"
                break
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            if [player["x"], player["y"]] != [
                started["target_x"], started["target_y"]
            ]:
                failure = "Mankey did not commit its landing tile"
                break
            if any(
                player[key] != follower[key]
                for key in ("x", "y", "pos_x", "pos_y", "pos_z")
            ):
                failure = "rider and Mankey separated after landing"
                break
        finish_motion()
        stress_motion_count = len(motions)
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, None)
        emu.memory.register_exec(TICK_MOUNT, on_mount_tick)
        dismount_trials = []
        unmounted_move_after = None
        first_dismounted_after = None
        for _ in range(8):
            avatar = avatar_ptr(emu)
            field_system = unsigned(emu, G_FIELD_SYS_PTR)
            before_toggle = {
                "mount": dict(mount_state(emu)),
                "previous_toggle_down": unsigned(emu, MOUNT + 0x7B, 1),
                "selector_flags": unsigned(emu, 0x023C8148, 1),
                "taskman": unsigned(emu, field_system + 0x10),
                "avatar_flags": unsigned(emu, avatar),
                "avatar_move_state": unsigned(emu, avatar + 0x10),
                "player_move_state": unsigned(emu, avatar + 0x14),
            }
            trace_toggle["active"] = True
            h.tap_key(emu, "SELECT", 6, 10)
            trace_toggle["active"] = False
            dismounted_after = wait_until(
                emu,
                lambda: mount_state(emu)["phase"] == 0,
                300,
            )
            if first_dismounted_after is None:
                first_dismounted_after = dismounted_after
            if dismounted_after is None:
                player = object_state(emu, player_ptr(emu))
                dismount_trials.append({
                    "position": [player["x"], player["y"]],
                    "before_toggle": before_toggle,
                    "dismounted_after": None,
                    "unmounted_move_after": None,
                    "escape_hop": None,
                })
                break
            unmounted_before = object_state(emu, player_ptr(emu))
            for keys in key_plan:
                mask = 0
                for key in keys:
                    mask |= h.keymask(h.key_constant(key))
                unmounted_move_after = wait_until(
                    emu,
                    lambda: (
                        object_state(emu, player_ptr(emu))["x"],
                        object_state(emu, player_ptr(emu))["y"],
                    ) != (unmounted_before["x"], unmounted_before["y"]),
                    120,
                    mask,
                )
                h.set_key_mask(emu, 0)
                if unmounted_move_after is not None:
                    break
            trial = {
                "position": [unmounted_before["x"], unmounted_before["y"]],
                "before_toggle": before_toggle,
                "dismounted_after": dismounted_after,
                "unmounted_move_after": unmounted_move_after,
                "escape_hop": None,
            }
            dismount_trials.append(trial)
            if unmounted_move_after is not None:
                break
            h.tap_key(emu, "SELECT", 6, 10)
            escape_remounted_after = wait_until(
                emu,
                lambda: mount_state(emu)["phase"] == 2,
                1800,
            )
            if escape_remounted_after is None:
                break
            for direction in ("UP", "RIGHT", "DOWN", "LEFT"):
                escape_hop = run_mankey_hop(emu, direction)
                if (
                    escape_hop.get("started_after") is not None
                    and escape_hop.get("recovered_after") is not None
                ):
                    trial["escape_hop"] = escape_hop
                    break
            if trial["escape_hop"] is None:
                break

        h.set_key_mask(emu, 0)
        h.cycle(emu, 60, 0)
        h.tap_key(emu, "SELECT", 6, 10)
        remounted_after = wait_until(
            emu,
            lambda: mount_state(emu)["phase"] == 2,
            1800,
        )
        remount_hop = None
        if remounted_after is not None:
            for direction in ("RIGHT", "UP", "LEFT", "DOWN"):
                candidate = run_mankey_hop(emu, direction)
                if (
                    candidate.get("started_after") is not None
                    and candidate.get("recovered_after") is not None
                ):
                    remount_hop = candidate
                    break
        final_state = dict(mount_state(emu))
        result = {
            "mount": mount,
            "initial_ready_after": initial_ready_after,
            "target_hops": target_hops,
            "completed_hops": stress_motion_count,
            "blocked_attempts": blocked_attempts,
            "maps_seen": sorted(maps_seen),
            "failure": failure,
            "max_callback_gap": max(
                (motion["max_gap"] for motion in motions),
                default=0,
            ),
            "failed_motions": [
                motion for motion in motions if not motion["passed"]
            ][:3],
            "toggle_trace": toggle_trace,
            "dismounted_after": first_dismounted_after,
            "dismount_trials": dismount_trials,
            "unmounted_move_after": unmounted_move_after,
            "remounted_after": remounted_after,
            "remount_hop": remount_hop,
            "final_state": final_state,
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/"
                "overworld_mankey_control_stress.png",
            ),
        }
        emu.memory.register_exec(TICK_MOUNT, None)
        emu.destroy()

    result["passed"] = (
        mount["passed"]
        and failure is None
        and stress_motion_count >= target_hops
        and all(motion["passed"] for motion in motions)
        and first_dismounted_after is not None
        and unmounted_move_after is not None
        and remounted_after is not None
        and remount_hop is not None
        and remount_hop["started_after"] is not None
        and remount_hop["recovered_after"] is not None
        and final_state["phase"] == 2
        and final_state["attached"] == 1
        and final_state["mode"] == 0
        and final_state["stream_preparing"] == 0
    )
    return result


def scenario_mounted_walk_transition():
    route_plan = (
        ("RIGHT", 10),
        ("DOWN", 3),
        ("RIGHT", 32),
        ("DOWN", 4),
        ("RIGHT", 7),
        ("DOWN", 2),
        ("RIGHT", 11),
        ("DOWN", 3),
        ("RIGHT", 12),
        ("UP", 1),
        ("RIGHT", 6),
        ("UP", 2),
        ("RIGHT", 2),
        ("UP", 2),
        ("RIGHT", 8),
        ("UP", 4),
        ("RIGHT", 6),
    )
    route = []
    trace = []
    motion_callbacks = []
    callback_clock = {"active": False, "vblank": 0}
    with h.silence_native_output(True):
        emu = h.create_desmume()

        def on_update(_address, _size):
            state = dict(mount_state(emu))
            if not callback_clock["active"] or state["mode"] != 4:
                return
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            motion_callbacks.append({
                "vblank": callback_clock["vblank"],
                "map": unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET),
                "state": state,
                "player": player,
                "follower": follower,
            })

        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        evacuate_map_event_objects(emu)
        initial_map = unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET)
        route_passed = True
        for direction, count in route_plan:
            start = object_state(emu, player_ptr(emu))
            completed = 0
            for _ in range(count):
                step = run_mounted_walk_tile(emu, direction)
                if not step["passed"]:
                    route_passed = False
                    break
                completed += 1
            end = object_state(emu, player_ptr(emu))
            route.append({
                "direction": direction,
                "requested": count,
                "completed": completed,
                "start": [start["x"], start["y"]],
                "end": [end["x"], end["y"]],
            })
            if not route_passed:
                break

        route_end = object_state(emu, player_ptr(emu))
        transition = None
        right = h.keymask(h.key_constant("RIGHT"))
        if route_passed:
            emu.memory.register_exec(UPDATE_MOUNT_MOTION, on_update)
            callback_clock["active"] = True
            for frame in range(200):
                callback_clock["vblank"] += 1
                h.cycle(emu, 1, right)
                state = dict(mount_state(emu))
                player = object_state(emu, player_ptr(emu))
                follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
                sample = {
                    "frame": frame,
                    "map": unsigned(
                        emu, WILD_STATE + WILD_MAP_ID_OFFSET
                    ),
                    "state": state,
                    "player": player,
                    "follower": follower,
                }
                trace.append(sample)
                if sample["map"] != initial_map:
                    transition = sample
                    break
        h.set_key_mask(emu, 0)

        settled_after = None
        target_observed_after = None
        if transition is not None:
            for frame in range(300):
                state = dict(mount_state(emu))
                player = object_state(emu, player_ptr(emu))
                follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
                sample = {
                    "frame": len(trace) + frame,
                    "map": unsigned(
                        emu, WILD_STATE + WILD_MAP_ID_OFFSET
                    ),
                    "state": state,
                    "player": player,
                    "follower": follower,
                }
                trace.append(sample)
                if (
                    target_observed_after is None
                    and player["x"] == transition["state"]["target_x"]
                    and player["y"] == transition["state"]["target_y"]
                ):
                    target_observed_after = frame
                if (
                    state["mode"] == 0
                    and state["pending"] == 0
                    and player["x"] == transition["state"]["target_x"]
                    and player["y"] == transition["state"]["target_y"]
                ):
                    settled_after = frame
                    break
                callback_clock["vblank"] += 1
                h.cycle(emu, 1, 0)

        callback_clock["active"] = False
        final_state = dict(mount_state(emu))
        final_player = object_state(emu, player_ptr(emu))
        final_follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
        recovery = (
            run_mounted_walk_tile(emu, "RIGHT")
            if transition is not None and settled_after is not None
            else None
        )
        result = {
            "mount": mount,
            "initial_map": initial_map,
            "route": route,
            "route_end": [route_end["x"], route_end["y"]],
            "transition": transition,
            "trace_samples": len(trace),
            "motion_callback_samples": len(motion_callbacks),
            "settled_after": settled_after,
            "target_observed_after": target_observed_after,
            "target_to_clear": (
                None
                if settled_after is None or target_observed_after is None
                else settled_after - target_observed_after
            ),
            "final_state": final_state,
            "final": [final_player["x"], final_player["y"]],
            "final_pair_synced": all(
                final_player[key] == final_follower[key]
                for key in ("x", "y", "pos_x", "pos_y", "pos_z")
            ),
            "recovery": recovery,
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/"
                "overworld_mounted_walk_transition.png",
            ),
        }
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, None)
        emu.destroy()

    transition_state = None if transition is None else transition["state"]
    transition_player = None if transition is None else transition["player"]
    transition_follower = None if transition is None else transition["follower"]
    motion_trace = [
        sample
        for sample in motion_callbacks
        if transition_state is not None
        and sample["state"]["start_x"] == transition_state["start_x"]
        and sample["state"]["start_y"] == transition_state["start_y"]
        and sample["state"]["target_x"] == transition_state["target_x"]
        and sample["state"]["target_y"] == transition_state["target_y"]
    ]
    motion_elapsed = [sample["state"]["elapsed"] for sample in motion_trace]
    callback_gaps = [
        motion_trace[index]["vblank"]
            - motion_trace[index - 1]["vblank"]
        for index in range(1, len(motion_trace))
    ]
    result["motion_elapsed"] = motion_elapsed
    result["callback_gaps"] = callback_gaps
    result["passed"] = (
        mount["passed"]
        and initial_map == 33
        and route_passed
        and result["route_end"] == [671, 402]
        and transition is not None
        and transition["map"] == 60
        and transition_state["mode"] == 4
        and transition_state["arc"] == 0
        and 0 < transition_state["elapsed"] < transition_state["frames"]
        and [transition_player["x"], transition_player["y"]]
            == [transition_state["start_x"], transition_state["start_y"]]
        and all(
            transition_player[key] == transition_follower[key]
            for key in ("x", "y", "pos_x", "pos_y", "pos_z")
        )
        and motion_elapsed == list(range(transition_state["frames"]))
        and callback_gaps
        and max(callback_gaps) <= 3
        and all(
            sample["player"]["x"] == transition_state["start_x"]
            and sample["player"]["y"] == transition_state["start_y"]
            and sample["player"]["x"] == sample["follower"]["x"]
            and sample["player"]["y"] == sample["follower"]["y"]
            and sample["player"]["pos_x"] == sample["follower"]["pos_x"]
            and sample["player"]["pos_y"] == sample["follower"]["pos_y"]
            and sample["player"]["pos_z"] == sample["follower"]["pos_z"]
            and sample["player"]["face_y"]
                - sample["follower"]["face_y"] == 0x8000
            for sample in motion_trace
        )
        and settled_after is not None
        and target_observed_after is not None
        and result["target_to_clear"] <= 3
        and settled_after <= (
            transition_state["frames"] - transition_state["elapsed"]
        ) * 3
        and final_state["mode"] == 0
        and final_state["pending"] == 0
        and result["final"]
            == [transition_state["target_x"], transition_state["target_y"]]
        and result["final_pair_synced"]
        and recovery is not None
        and recovery["passed"]
        and recovery["ready_after"] == 0
        and recovery["started_after"] <= 3
    )
    return result


def scenario_mounted_transition():
    route = []
    trace = []
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.sav", False)
        mount = mount_party_slot(emu, 2, 56)
        initial_map = unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET)
        transition = None
        for direction, limit in (("RIGHT", 900), ("DOWN", 450), ("RIGHT", 2500)):
            before = object_state(emu, player_ptr(emu))
            mask = h.keymask(h.key_constant(direction))
            for frame in range(limit):
                h.cycle(emu, 1, mask)
                current_map = unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET)
                if current_map != initial_map:
                    state = dict(mount_state(emu))
                    player = object_state(emu, player_ptr(emu))
                    follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
                    transition = {
                        "direction": direction,
                        "frame": frame,
                        "from_map": initial_map,
                        "to_map": current_map,
                        "state": state,
                        "player": player,
                        "follower": follower,
                    }
                    break
            after = object_state(emu, player_ptr(emu))
            route.append({
                "direction": direction,
                "start": [before["x"], before["y"]],
                "end": [after["x"], after["y"]],
            })
            if transition is not None:
                break
        h.set_key_mask(emu, 0)
        if transition is not None:
            for frame in range(400):
                state = dict(mount_state(emu))
                player = object_state(emu, player_ptr(emu))
                follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
                trace.append({
                    "frame": frame,
                    "map": unsigned(emu, WILD_STATE + WILD_MAP_ID_OFFSET),
                    "mode": state["mode"],
                    "elapsed": state["elapsed"],
                    "frames": state["frames"],
                    "pending": state["pending"],
                    "player": player,
                    "follower": follower,
                })
                if (
                    frame
                    and state["mode"] == 0
                    and state["cooldown"] == 0
                    and state["pending"] == 0
                ):
                    break
                h.cycle(emu, 1, 0)
        final_state = dict(mount_state(emu))
        final_player = object_state(emu, player_ptr(emu))
        final_follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
        recovery = run_mankey_hop(emu, "RIGHT") if transition is not None else None
        result = {
            "mount": mount,
            "route": route,
            "transition": transition,
            "trace_samples": len(trace),
            "final_state": final_state,
            "final": [final_player["x"], final_player["y"]],
            "final_pair_synced": all(
                final_player[key] == final_follower[key]
                for key in ("x", "y", "pos_x", "pos_y", "pos_z")
            ),
            "recovery": recovery,
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/overworld_mounted_transition.png",
            ),
        }
        emu.destroy()
    motion_elapsed = []
    for sample in trace:
        if sample["mode"] != 1:
            continue
        if not motion_elapsed or sample["elapsed"] != motion_elapsed[-1]:
            motion_elapsed.append(sample["elapsed"])
    transition_state = None if transition is None else transition["state"]
    transition_player = None if transition is None else transition["player"]
    transition_follower = None if transition is None else transition["follower"]
    result["motion_elapsed"] = motion_elapsed
    result["passed"] = (
        mount["passed"]
        and initial_map == 33
        and transition is not None
        and transition["to_map"] == 60
        and transition_state["mode"] == 1
        and 0 < transition_state["elapsed"] < transition_state["frames"]
        and all(
            transition_player[key] == transition_follower[key]
            for key in ("x", "y", "pos_x", "pos_y", "pos_z")
        )
        and transition_player["face_y"] - transition_follower["face_y"] == 0x8000
        and transition_follower["face_y"] != 0
        and motion_elapsed
        and motion_elapsed == list(range(
            transition_state["elapsed"],
            transition_state["frames"] + 1,
        ))
        and all(
            sample["map"] == 60
            and sample["player"]["x"] == sample["follower"]["x"]
            and sample["player"]["y"] == sample["follower"]["y"]
            and sample["player"]["pos_x"] == sample["follower"]["pos_x"]
            and sample["player"]["pos_y"] == sample["follower"]["pos_y"]
            and sample["player"]["pos_z"] == sample["follower"]["pos_z"]
            and sample["player"]["face_y"] - sample["follower"]["face_y"]
                == 0x8000
            for sample in trace
            if sample["mode"] == 1
        )
        and final_state["mode"] == 0
        and final_state["pending"] == 0
        and result["final"]
            == [transition_state["target_x"], transition_state["target_y"]]
        and result["final_pair_synced"]
        and recovery is not None
        and recovery["passed"]
    )
    return result


def scenario_stomp():
    feedback = {
        "positive": {"sounds": [], "particles": []},
        "negative": {"sounds": [], "particles": []},
    }
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        active = {"case": None}

        def on_sound(_address, _size):
            if active["case"] is not None:
                feedback[active["case"]]["sounds"].append(
                    emu.memory.register_arm9.r0
                )

        def on_particle(_address, _size):
            if active["case"] is not None:
                feedback[active["case"]]["particles"].append(
                    emu.memory.register_arm9.r0
                )

        emu.memory.register_exec(PLAY_SE, on_sound)
        emu.memory.register_exec(LANDING_PARTICLE, on_particle)
        reset_walk_state(emu, 8)
        write_u8(emu, MOUNT + 8 + 70, 8)
        follower_obj = unsigned(emu, FOLLOWER_SLOT)
        active["case"] = "positive"
        positive = run_mounted_walk_tile(emu, "RIGHT")
        active["case"] = None

        reset_walk_state(emu, 8)
        write_u8(emu, MOUNT + 8 + 70, 7)
        active["case"] = "negative"
        negative = run_mounted_walk_tile(emu, "RIGHT")
        active["case"] = None
        result = {
            "mount": mount,
            "positive": positive,
            "negative": negative,
            "feedback": feedback,
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/overworld_walk_stomp.png",
            ),
        }
        emu.memory.register_exec(PLAY_SE, None)
        emu.memory.register_exec(LANDING_PARTICLE, None)
        emu.destroy()
    result["passed"] = (
        mount["passed"]
        and positive["passed"]
        and negative["passed"]
        and positive["frames"] == 8
        and negative["frames"] == 8
        and feedback["positive"]["sounds"].count(2183) == 1
        and feedback["positive"]["particles"].count(follower_obj) == 1
        and feedback["negative"]["sounds"].count(2183) == 0
        and feedback["negative"]["particles"].count(follower_obj) == 0
    )
    return result


def scenario_crash():
    sounds = []
    samples = []
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)

        def on_sound(_address, _size):
            sounds.append(emu.memory.register_arm9.r0)

        emu.memory.register_exec(PLAY_SE, on_sound)
        write_u8(emu, MOUNT + 0x82, 0x11)
        write_u8(emu, MOUNT + 8 + 65, 0x11)
        start = object_state(emu, player_ptr(emu))
        up = h.keymask(h.key_constant("UP"))
        hit = None
        activations = 0
        crash_start = None
        previous_mode = mount_state(emu)["mode"]
        for frame in range(500):
            h.cycle(emu, 1, up)
            state = mount_state(emu)
            if previous_mode != 3 and state["mode"] == 3:
                activations += 1
                if hit is None:
                    hit = frame + 1
                    hit_position = object_state(emu, player_ptr(emu))
                    crash_start = [hit_position["x"], hit_position["y"]]
            if state["mode"] == 3:
                follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
                samples.append({
                    "elapsed": state["elapsed"],
                    "frames": state["frames"],
                    "face_x": follower["face_x"],
                    "face_z": follower["face_z"],
                })
            elif hit is not None and samples:
                break
            previous_mode = state["mode"]
        h.set_key_mask(emu, 0)
        crash_end = object_state(emu, player_ptr(emu))
        reset_state = dict(mount_state(emu))
        write_u8(emu, MOUNT + 0x82, 0)
        write_u8(emu, MOUNT + 8 + 65, 0)
        recovery = run_mounted_walk_tile(emu, "RIGHT")
        result = {
            "mount": mount,
            "hit_after": hit,
            "activations": activations,
            "sounds": sounds,
            "sample_count": len(samples),
            "elapsed": sorted({sample["elapsed"] for sample in samples}),
            "start": [start["x"], start["y"]],
            "crash_start": crash_start,
            "crash_end": [crash_end["x"], crash_end["y"]],
            "reset_state": reset_state,
            "recovery": recovery,
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/overworld_walk_crash.png",
            ),
        }
        emu.memory.register_exec(PLAY_SE, None)
        emu.destroy()
    result["passed"] = (
        mount["passed"]
        and hit is not None
        and activations == 1
        and sounds.count(1536) == 1
        and samples
        and all(sample["frames"] == 32 for sample in samples)
        and result["elapsed"] in (
            list(range(1, 33)),
            list(range(33)),
        )
        and any(
            abs(sample["face_x"]) == 0x2000
            and abs(sample["face_z"]) == 0x2000
            for sample in samples
        )
        and result["start"] == [577, 399]
        and result["crash_start"] == [577, 396]
        and result["crash_end"] == result["crash_start"]
        and reset_state["mode"] == 0
        and reset_state["speed"] == reset_state["base"]
        and reset_state["direction"] == 0xFF
        and reset_state["counter"] == 0
        and reset_state["skid"] == 0
        and reset_state["pending"] == 0
        and recovery["passed"]
        and recovery["final"][0] == recovery["before"][0] + 1
        and recovery["final"][1] == recovery["before"][1]
    )
    return result


def scenario_cyndaquil_control_stress():
    target_commits = int(os.environ.get("CYNDAQUIL_STRESS_COMMITS", "2000"))
    target_direction_changes = max(1, target_commits // 8)
    callback_motions = []
    callback_error = None
    active_callback_motion = None
    active_start_calls = []
    finish_calls = []
    finished_signatures = []
    clock = {"vblank": 0}
    stress = {
        "active": True,
        "ticks": 0,
        "direction": "RIGHT",
        "direction_changes": 0,
        "commits": 0,
        "last_position": None,
        "last_commit_tick": 0,
        "latest_target": None,
        "pending_ticks": 0,
        "idle_ticks": 0,
        "failure": None,
        "state_at_failure": None,
        "last_safe": None,
    }

    def finish_callback_motion():
        nonlocal active_callback_motion, callback_error
        if active_callback_motion is None:
            return
        elapsed = active_callback_motion["elapsed"]
        frames = active_callback_motion["frames"]
        gaps = [
            active_callback_motion["vblanks"][index]
                - active_callback_motion["vblanks"][index - 1]
            for index in range(1, len(active_callback_motion["vblanks"]))
        ]
        active_callback_motion["max_gap"] = max(gaps) if gaps else 0
        sampled_schedule_valid = (
            bool(elapsed)
            and all(0 <= value < frames for value in elapsed)
            and elapsed[-1] < frames
            and all(
                elapsed[index] > elapsed[index - 1]
                for index in range(1, len(elapsed))
            )
        )
        active_callback_motion["passed"] = (
            sampled_schedule_valid
            and active_callback_motion["signature"] in finished_signatures
            and active_callback_motion["max_gap"] <= 3
            and not active_callback_motion["errors"]
        )
        if not active_callback_motion["passed"] and callback_error is None:
            callback_error = {
                "reason": "invalid motion callback sequence",
                "motion": active_callback_motion,
            }
        callback_motions.append(active_callback_motion)
        active_callback_motion = None

    with h.silence_native_output(True):
        emu = h.create_desmume()

        def on_update(_address, _size):
            nonlocal active_callback_motion, callback_error
            state = dict(mount_state(emu))
            if state["mode"] != 4:
                return
            player = object_state(emu, player_ptr(emu))
            signature = (
                state["start_x"],
                state["start_y"],
                state["target_x"],
                state["target_y"],
            )
            stress["latest_target"] = signature[2:]
            if (
                active_callback_motion is None
                or active_callback_motion["signature"] != signature
            ):
                finish_callback_motion()
                active_callback_motion = {
                    "signature": signature,
                    "frames": state["frames"],
                    "elapsed": [],
                    "vblanks": [],
                    "errors": [],
                }
            active_callback_motion["elapsed"].append(state["elapsed"])
            active_callback_motion["vblanks"].append(clock["vblank"])
            if (
                abs(state["target_x"] - state["start_x"])
                    + abs(state["target_y"] - state["start_y"]) != 1
            ):
                active_callback_motion["errors"].append(
                    "target is not one cardinal tile"
                )
            if (
                player["x"] != state["start_x"]
                or player["y"] != state["start_y"]
            ):
                active_callback_motion["errors"].append(
                    "logical position changed before commit"
                )

        def after_sync(_address, _size):
            if not stress["active"]:
                return
            player = object_state(emu, player_ptr(emu))
            follower = object_state(emu, unsigned(emu, FOLLOWER_SLOT))
            state = dict(mount_state(emu))
            avatar = avatar_ptr(emu)
            position = (player["x"], player["y"])

            stress["ticks"] += 1
            if stress["last_position"] is None:
                stress["last_position"] = position
            elif position != stress["last_position"]:
                if (stress["latest_target"] is not None
                        and position != stress["latest_target"]):
                    stress["failure"] = "logical commit missed the active target"
                stress["commits"] += 1
                stress["last_commit_tick"] = stress["ticks"]
                stress["last_position"] = position
                stress["latest_target"] = None

            stress["pending_ticks"] = (
                stress["pending_ticks"] + 1 if state["pending"] else 0
            )
            if state["mode"] == 0 and state["pending"] == 0:
                stress["idle_ticks"] += 1
            else:
                stress["idle_ticks"] = 0

            if stress["direction"] == "RIGHT" and player["x"] >= upper_x:
                stress["direction"] = "LEFT"
                stress["direction_changes"] += 1
            elif stress["direction"] == "LEFT" and player["x"] <= lower_x:
                stress["direction"] = "RIGHT"
                stress["direction_changes"] += 1

            if stress["failure"] is None:
                if state["phase"] != 2 or state["attached"] != 1:
                    stress["failure"] = "mount lifecycle detached"
                elif any(
                    player[key] != follower[key]
                    for key in ("x", "y", "pos_x", "pos_y", "pos_z")
                ):
                    stress["failure"] = "rider and mount separated"
                elif player["y"] != lane_y:
                    stress["failure"] = "stress movement left the horizontal lane"
                elif not initial["x"] <= player["x"] <= initial["x"] + 10:
                    stress["failure"] = "stress movement left the proven clear corridor"
                elif stress["pending_ticks"] > 3:
                    stress["failure"] = "pending step did not clear within three field ticks"
                elif stress["ticks"] - stress["last_commit_tick"] > 120:
                    stress["failure"] = "held input produced no completed tile for 120 field ticks"
                elif callback_error is not None:
                    stress["failure"] = callback_error["reason"]

            stress["last_safe"] = {
                "frame": clock["vblank"],
                "mount": state,
                "player": player,
                "follower": follower,
                "avatar_flags": unsigned(emu, avatar),
                "avatar_move_state": unsigned(emu, avatar + 0x10),
                "player_move_state": unsigned(emu, avatar + 0x14),
            }
            if (stress["failure"] is not None
                    and stress["state_at_failure"] is None):
                stress["state_at_failure"] = {
                    **stress["last_safe"],
                    "direction": stress["direction"],
                    "pending_ticks": stress["pending_ticks"],
                    "idle_ticks": stress["idle_ticks"],
                    "last_commit_tick": stress["last_commit_tick"],
                    "callback_error": callback_error,
                }

        def on_start(_address, _size):
            state = dict(mount_state(emu))
            if state["mode"] != 0:
                active_start_calls.append({
                    "frame": clock["vblank"],
                    "caller": emu.memory.register_arm9.r14,
                    "state": state,
                })

        def on_finish(_address, _size):
            state = dict(mount_state(emu))
            finished_signatures.append((
                state["start_x"],
                state["start_y"],
                state["target_x"],
                state["target_y"],
            ))
            finish_calls.append({
                "frame": clock["vblank"],
                "state": state,
            })

        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, on_update)
        emu.memory.register_exec(TICK_MOUNT_POST_SYNC, after_sync)
        emu.memory.register_exec(TRY_START_MOUNT_MOTION, on_start)
        emu.memory.register_exec(FINISH_MOUNT_MOTION, on_finish)
        player_obj = player_ptr(emu)
        initial = object_state(emu, player_obj)
        lane_y = initial["y"]
        lower_x = initial["x"] + 3
        upper_x = initial["x"] + 7
        stress["last_position"] = (initial["x"], initial["y"])

        for frame in range(40000):
            mask = h.keymask(h.key_constant(stress["direction"]))
            clock["vblank"] = frame
            h.cycle(emu, 1, mask)
            if stress["failure"] is not None:
                break
            if (stress["commits"] >= target_commits
                    and stress["direction_changes"]
                        >= target_direction_changes):
                break

        h.set_key_mask(emu, 0)
        finish_callback_motion()
        settled_after = None
        for settle_frame in range(300):
            clock["vblank"] += 1
            h.cycle(emu, 1, 0)
            safe = stress["last_safe"]
            if safe is None:
                continue
            state = safe["mount"]
            if (state["mode"] == 0
                    and state["pending"] == 0
                    and state["skid"] == 0
                    and state["stop"] == 0
                    and state["direction"] == 0xFF):
                settled_after = settle_frame
                break
        safe = stress["last_safe"]
        settled_state = safe["mount"] if safe is not None else dict(mount_state(emu))
        settled_player = safe["player"] if safe is not None else object_state(emu, player_obj)
        settled_follower = safe["follower"] if safe is not None else object_state(
            emu, unsigned(emu, FOLLOWER_SLOT)
        )
        avatar = avatar_ptr(emu)
        avatar_state = {
            "flags": unsigned(emu, avatar),
            "move_state": unsigned(emu, avatar + 0x10),
            "player_move_state": unsigned(emu, avatar + 0x14),
        }
        recovery_direction = (
            "RIGHT" if settled_player["x"] < upper_x else "LEFT"
        )
        recovery = (
            run_mounted_walk_tile(emu, recovery_direction)
            if stress["failure"] is None and settled_after is not None
            else None
        )
        stress["active"] = False
        h.tap_key(emu, "SELECT", 6, 10)
        dismounted_after = wait_until(
            emu,
            lambda: mount_state(emu)["phase"] == 0,
            300,
        )
        unmounted_before = object_state(emu, player_ptr(emu))
        unmounted_direction = (
            "RIGHT" if unmounted_before["x"] < upper_x else "LEFT"
        )
        unmounted_mask = h.keymask(h.key_constant(unmounted_direction))
        unmounted_move_after = wait_until(
            emu,
            lambda: (
                object_state(emu, player_ptr(emu))["x"],
                object_state(emu, player_ptr(emu))["y"],
            ) != (unmounted_before["x"], unmounted_before["y"]),
            300,
            unmounted_mask,
        )
        h.set_key_mask(emu, 0)
        h.cycle(emu, 60, 0)
        h.tap_key(emu, "SELECT", 6, 10)
        remounted_after = wait_until(
            emu,
            lambda: mount_state(emu)["phase"] == 2,
            1800,
        )
        remount_player = object_state(emu, player_ptr(emu))
        remount_direction = (
            "RIGHT" if remount_player["x"] < upper_x else "LEFT"
        )
        remount_recovery = (
            run_mounted_walk_tile(emu, remount_direction)
            if remounted_after is not None
            else None
        )
        result = {
            "mount": mount,
            "target_commits": target_commits,
            "target_direction_changes": target_direction_changes,
            "commits": stress["commits"],
            "direction_changes": stress["direction_changes"],
            "field_ticks": stress["ticks"],
            "failure": stress["failure"],
            "state_at_failure": stress["state_at_failure"],
            "callback_motions": len(callback_motions),
            "max_callback_gap": max(
                (motion["max_gap"] for motion in callback_motions),
                default=0,
            ),
            "active_start_calls": active_start_calls[:5],
            "finish_calls_near_failure": (
                finish_calls[-5:] if stress["failure"] else []
            ),
            "settled_after": settled_after,
            "settled_state": settled_state,
            "settled_pair_synced": all(
                settled_player[key] == settled_follower[key]
                for key in ("x", "y", "pos_x", "pos_y", "pos_z")
            ),
            "avatar": avatar_state,
            "recovery": recovery,
            "dismounted_after": dismounted_after,
            "unmounted_move_after": unmounted_move_after,
            "remounted_after": remounted_after,
            "remount_recovery": remount_recovery,
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/"
                "overworld_cyndaquil_control_stress.png",
            ),
        }
        emu.memory.register_exec(UPDATE_MOUNT_MOTION, None)
        emu.memory.register_exec(TICK_MOUNT_POST_SYNC, None)
        emu.memory.register_exec(TRY_START_MOUNT_MOTION, None)
        emu.memory.register_exec(FINISH_MOUNT_MOTION, None)
        emu.destroy()

    result["passed"] = (
        mount["passed"]
        and stress["failure"] is None
        and callback_error is None
        and not active_start_calls
        and stress["commits"] >= target_commits
        and stress["direction_changes"] >= target_direction_changes
        and len(callback_motions) >= target_commits
        and all(motion["passed"] for motion in callback_motions)
        and settled_after is not None
        and settled_state["mode"] == 0
        and settled_state["pending"] == 0
        and result["settled_pair_synced"]
        and (avatar_state["flags"] & 1) == 0
        and avatar_state["player_move_state"] in (0, 3)
        and recovery is not None
        and recovery["passed"]
        and recovery["started_after"] <= 3
        and dismounted_after is not None
        and unmounted_move_after is not None
        and remounted_after is not None
        and remount_recovery is not None
        and remount_recovery["passed"]
    )
    return result


def scenario_cyndaquil_step_taps():
    target_steps = int(os.environ.get("CYNDAQUIL_TAP_STEPS", "100"))
    steps = []
    failure = None
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        initial = object_state(emu, player_ptr(emu))
        lower_x = initial["x"] + 2
        upper_x = initial["x"] + 8
        direction = "RIGHT"

        for index in range(target_steps):
            player = object_state(emu, player_ptr(emu))
            if direction == "RIGHT" and player["x"] >= upper_x:
                direction = "LEFT"
            elif direction == "LEFT" and player["x"] <= lower_x:
                direction = "RIGHT"
            step = run_mounted_walk_tile(emu, direction)
            step["index"] = index
            step["direction"] = direction
            steps.append(step)
            if not step["passed"]:
                avatar = avatar_ptr(emu)
                failure = {
                    "step": index,
                    "direction": direction,
                    "mount": dict(mount_state(emu)),
                    "avatar_flags": unsigned(emu, avatar),
                    "avatar_move_state": unsigned(emu, avatar + 0x10),
                    "player_move_state": unsigned(emu, avatar + 0x14),
                    "player": object_state(emu, player_ptr(emu)),
                    "follower": object_state(emu, unsigned(emu, FOLLOWER_SLOT)),
                }
                break
            h.cycle(emu, 3, 0)

        result = {
            "mount": mount,
            "target_steps": target_steps,
            "completed_steps": len([step for step in steps if step["passed"]]),
            "failure": failure,
            "last_steps": steps[-5:],
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/"
                "overworld_cyndaquil_step_taps.png",
            ),
        }
        emu.destroy()

    result["passed"] = (
        mount["passed"]
        and failure is None
        and result["completed_steps"] == target_steps
    )
    return result


def scenario_cyndaquil_streaming_stress():
    samples = []
    with h.silence_native_output(True):
        emu = h.create_desmume()
        boot(emu, REPO / "test.dsv", True)
        mount = mount_party_slot(emu, 0, 155)
        evacuate_wild_objects(emu)
        evacuate_map_event_objects(emu)

        approach = []
        for direction, count in (("RIGHT", 10), ("DOWN", 3)):
            for _ in range(count):
                approach.append(run_mounted_walk_tile(emu, direction))

        start = object_state(emu, player_ptr(emu))
        target_x = start["x"] + 32
        right = h.keymask(h.key_constant("RIGHT"))
        last_x = start["x"]
        last_change_frame = 0
        failure = None
        native_stream_bound = True
        for frame in range(1200):
            h.cycle(emu, 1, right)
            player = object_state(emu, player_ptr(emu))
            state = dict(mount_state(emu))
            field_system = unsigned(emu, G_FIELD_SYS_PTR)
            land = unsigned(emu, field_system + 0x2C)
            land_target_pointer = unsigned(emu, land + 0xDC)
            native_stream_bound &= (
                state["stream_preparing"] == 0
                and land_target_pointer == player_ptr(emu) + 0x70
            )
            if player["x"] != last_x:
                last_x = player["x"]
                last_change_frame = frame
            samples.append({
                "frame": frame,
                "x": player["x"],
                "mode": state["mode"],
                "pending": state["pending"],
                "stream_preparing": state["stream_preparing"],
                "stream_anchor_x": signed(emu, MOUNT + 0xA8),
                "land_busy": unsigned(emu, land + 0xA0, 1),
                "land_target_x": signed(emu, land + 0xD0),
                "land_target_pointer": land_target_pointer,
            })
            if player["x"] >= target_x:
                break
            if frame - last_change_frame > 120:
                avatar = avatar_ptr(emu)
                failure = {
                    "reason": "held Walk stopped before the clear-route target",
                    "frame": frame,
                    "player": player,
                    "mount": state,
                    "avatar_flags": unsigned(emu, avatar),
                    "avatar_move_state": unsigned(emu, avatar + 0x10),
                    "player_move_state": unsigned(emu, avatar + 0x14),
                    "land_busy": unsigned(emu, land + 0xA0, 1),
                    "land_target": [
                        signed(emu, land + 0xD0),
                        signed(emu, land + 0xD4),
                        signed(emu, land + 0xD8),
                    ],
                }
                break
        h.set_key_mask(emu, 0)
        final_player = object_state(emu, player_ptr(emu))
        result = {
            "mount": mount,
            "approach_passed": all(step["passed"] for step in approach),
            "start": [start["x"], start["y"]],
            "target_x": target_x,
            "final": [final_player["x"], final_player["y"]],
            "failure": failure,
            "native_stream_bound": native_stream_bound,
            "tail_samples": samples[-20:],
            "screenshot": h.save_screenshot(
                emu,
                "documentation/verification_screenshots/"
                "overworld_cyndaquil_streaming_stress.png",
            ),
        }
        emu.destroy()

    result["passed"] = (
        mount["passed"]
        and result["approach_passed"]
        and failure is None
        and result["final"][0] >= target_x
        and native_stream_bound
    )
    return result


SCENARIOS = {
    "mounted_frames": scenario_mounted_frames,
    "mounted_smoothness": scenario_mounted_smoothness,
    "turn_skid": scenario_turn_skid,
    "diagonal_turn_skid": scenario_diagonal_turn_skid,
    "cherrygrove_surf_spawn_terrain": scenario_cherrygrove_surf_spawn_terrain,
    "wild_walk": scenario_wild_walk,
    "wild_ledge_hop": scenario_wild_ledge_hop,
    "ledyba_chain_pause": scenario_ledyba_chain_pause,
    "mankey_hops": scenario_mankey_hops,
    "mankey_control_stress": scenario_mankey_control_stress,
    "mounted_walk_transition": scenario_mounted_walk_transition,
    "mounted_transition": scenario_mounted_transition,
    "stomp": scenario_stomp,
    "crash": scenario_crash,
    "cyndaquil_control_stress": scenario_cyndaquil_control_stress,
    "cyndaquil_step_taps": scenario_cyndaquil_step_taps,
    "cyndaquil_streaming_stress": scenario_cyndaquil_streaming_stress,
}


def run_all(include_mankey_save):
    results = {}
    command_prefix = [
        sys.executable,
        "-I",
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        str(Path(__file__).resolve()),
    ]
    scenario_names = [
        name
        for name in SCENARIOS
        if include_mankey_save
        or name not in (
            "mankey_hops",
            "mankey_control_stress",
            "mounted_transition",
        )
    ]
    for name in scenario_names:
        completed = subprocess.run(
            command_prefix + ["--scenario", name],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        try:
            results[name] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            results[name] = {
                "passed": False,
                "error": completed.stderr.strip()
                    or completed.stdout.strip()
                    or f"scenario exited {completed.returncode}",
            }
    return {
        "scenarios": results,
        "passed": all(result.get("passed") for result in results.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS],
        default="all",
    )
    parser.add_argument(
        "--include-mankey-save",
        action="store_true",
        help="include the Mankey scenario that imports the raw MelonDS test.sav",
    )
    args = parser.parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    result = (
        run_all(args.include_mankey_save)
        if args.scenario == "all"
        else SCENARIOS[args.scenario]()
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result.get("passed") else 1)


if __name__ == "__main__":
    main()
