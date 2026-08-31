#!/usr/bin/env python3
"""Verify the resident mount controller and its profile-resolution bridge."""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OVERLAY_ID = 157
OVERLAY_BASE = 0x023BAB00
OVERLAY_ENTRY = 0x023BB600
OVERLAY_LIMIT = 0x023BC800
FIELD_OVERLAY_ID = 131
FIELD_OVERLAY_LIMIT = 0x023CCFD8
ENTRY_MAGIC = 0x544E554D
ENTRY_VERSION = 8
ENTRY_SIZE = 32
PLAYER_CONTROL_WRAPPER = OVERLAY_ENTRY + 0x20
PLAYER_STEP_WRAPPER = OVERLAY_ENTRY + 0xA0
PLAYER_STEP_RESIDENT_HANDLER = 0x023D9B79
PLAYER_STEP_RESIDENT_LITERAL = PLAYER_STEP_WRAPPER + 0x14
FIELD_INPUT_WRAPPER = OVERLAY_ENTRY + 0xE0
CRASH_SOUND_WRAPPER = OVERLAY_ENTRY + 0x140
TOGGLE_LATCH_WRAPPER = OVERLAY_BASE + 0xC78
TOGGLE_LATCH_ADDR = 0x023BC78A
MOVE_CONTROL_CALL_SITES = (0x0203E1F0, 0x0203E260, 0x0203E2E4)
FIELD_INPUT_CALL_SITE = 0x0203E270
CRASH_SOUND_CALL_SITES = (0x0205D532, 0x0205D5C2)
HELD_MOVEMENT_HOOK = 0x0205DA1C
FIELD_OBJECT_OVERLAY_ID = 1
MOUNT_FACING_CALL_SITE = 0x021F8E68
MOUNT_FACING_WRAPPER = 0x023BD3EC


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"mount verifier: {message}")


def decode_thumb_bl(arm9: bytes, load_address: int, address: int) -> int:
    offset = address - load_address
    require(0 <= offset <= len(arm9) - 4, f"BL site 0x{address:08X} is outside ARM9")
    high, low = struct.unpack_from("<HH", arm9, offset)
    require(
        high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800,
        f"site 0x{address:08X} is not a Thumb-1 BL",
    )
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    fat_offset, fat_size = struct.unpack_from("<2I", rom, 0x48)
    y9_offset, y9_size = struct.unpack_from("<2I", rom, 0x50)
    require(y9_size >= (OVERLAY_ID + 1) * 0x20, "overlay 157 row is missing")
    require(fat_size >= (OVERLAY_ID + 1) * 8, "overlay 157 FAT row is missing")

    row = struct.unpack_from("<8I", rom, y9_offset + OVERLAY_ID * 0x20)
    overlay_id, load_address, file_size, bss_size, init_start, init_end, file_id, flags = row
    require(overlay_id == OVERLAY_ID, "overlay ID differs")
    require(load_address == OVERLAY_BASE, "load address differs")
    require(file_id == OVERLAY_ID, "file ID differs")
    require(init_start == 0 and init_end == 0 and flags == 0, "metadata differs")
    require(
        file_size > 0
        and bss_size > 0
        and load_address + file_size + bss_size <= OVERLAY_LIMIT,
        "code and state exceed the dedicated 4 KiB reservation",
    )

    field_row = struct.unpack_from(
        "<8I", rom, y9_offset + FIELD_OVERLAY_ID * 0x20
    )
    field_overlay_id, field_load, field_size, field_bss = field_row[:4]
    require(field_overlay_id == FIELD_OVERLAY_ID, "field overlay ID differs")
    require(
        field_load + field_size + field_bss <= FIELD_OVERLAY_LIMIT,
        "field overlay overlaps the overworld wild overlay prefix",
    )

    file_start, file_end = struct.unpack_from("<2I", rom, fat_offset + file_id * 8)
    require(file_end - file_start == file_size, "FAT size differs from y9")
    packaged = rom[file_start:file_end]
    built = (REPO / "build/output_overworld_mount_overlay.bin").read_bytes()
    require(packaged == built, "packaged overlay differs from linked output")
    require(
        struct.unpack_from(
            "<I",
            packaged,
            PLAYER_STEP_RESIDENT_LITERAL - OVERLAY_BASE,
        )[0]
        == PLAYER_STEP_RESIDENT_HANDLER,
        "player-step bridge targets the wrong resident handler",
    )

    player_step_overlay_id = 129
    player_step_row = struct.unpack_from(
        "<8I", rom, y9_offset + player_step_overlay_id * 0x20)
    player_step_load = player_step_row[1]
    player_step_file_id = player_step_row[6]
    player_step_start, player_step_end = struct.unpack_from(
        "<2I", rom, fat_offset + player_step_file_id * 8)
    player_step_overlay = rom[player_step_start:player_step_end]
    require(
        decode_thumb_bl(
            player_step_overlay,
            player_step_load,
            0x023DD558,
        ) == PLAYER_STEP_WRAPPER,
        "canonical player-step call does not target the mount bridge",
    )
    object_row = struct.unpack_from(
        "<8I", rom, y9_offset + FIELD_OBJECT_OVERLAY_ID * 0x20
    )
    object_load = object_row[1]
    object_file_id = object_row[6]
    object_start, object_end = struct.unpack_from(
        "<2I", rom, fat_offset + object_file_id * 8
    )
    object_overlay = rom[object_start:object_end]
    require(
        decode_thumb_bl(
            object_overlay,
            object_load,
            MOUNT_FACING_CALL_SITE,
        ) == MOUNT_FACING_WRAPPER,
        "mounted follower facing vector is overwritten after synchronization",
    )

    entry_offset = OVERLAY_ENTRY - OVERLAY_BASE
    magic, version, size, *callbacks = struct.unpack_from(
        "<IHH6I", packaged, entry_offset)
    require(magic == ENTRY_MAGIC, "entry magic differs")
    require(version == ENTRY_VERSION, "entry version differs")
    require(size == ENTRY_SIZE, "entry size differs")
    require(
        all((callback & 1) != 0 for callback in callbacks),
        "entry contains a non-Thumb callback",
    )
    require(
        all(OVERLAY_BASE <= (callback & ~1) < OVERLAY_BASE + file_size
            for callback in callbacks),
        "entry callback lies outside the mount overlay",
    )
    require(
        callbacks[-1] & ~1 != PLAYER_CONTROL_WRAPPER
        and callbacks[-1] & ~1 != CRASH_SOUND_WRAPPER,
        "frame callback aliases a fixed player-control wrapper",
    )
    toggle_wrapper = packaged[
        TOGGLE_LATCH_WRAPPER - OVERLAY_BASE:
        TOGGLE_LATCH_WRAPPER - OVERLAY_BASE + 0x1C
    ]
    require(
        callbacks[-1] == TOGGLE_LATCH_WRAPPER + 1
        and toggle_wrapper[:0x14]
            == bytes.fromhex(
                "01 b4 04 4b 18 78 80 00 02 43 c0 46 c0 46 01 bc "
                "01 4b 18 47"
            )
        and struct.unpack_from("<I", toggle_wrapper, 0x14)[0]
            == TOGGLE_LATCH_ADDR
        and (
            OVERLAY_BASE
            <= (struct.unpack_from("<I", toggle_wrapper, 0x18)[0] & ~1)
            < OVERLAY_BASE + file_size
        ),
        "missed Select edges do not route through the resident mount latch",
    )

    arm9_offset, arm9_entry, arm9_load, arm9_size = struct.unpack_from(
        "<4I", rom, 0x20
    )
    del arm9_entry
    arm9 = rom[arm9_offset:arm9_offset + arm9_size]
    require(len(arm9) == arm9_size, "ARM9 image is truncated")
    for site in MOVE_CONTROL_CALL_SITES:
        require(
            decode_thumb_bl(arm9, arm9_load, site) == PLAYER_CONTROL_WRAPPER,
            f"player-control call at 0x{site:08X} does not target the mount wrapper",
        )
    require(
        decode_thumb_bl(arm9, arm9_load, FIELD_INPUT_CALL_SITE)
            == FIELD_INPUT_WRAPPER,
        "field-input processing does not target the mounted-Hop transition gate",
    )
    for site in CRASH_SOUND_CALL_SITES:
        require(
            decode_thumb_bl(arm9, arm9_load, site) == CRASH_SOUND_WRAPPER,
            f"crash-sound call at 0x{site:08X} does not target the mount wrapper",
        )
    hook_offset = HELD_MOVEMENT_HOOK - arm9_load
    require(
        arm9[hook_offset:hook_offset + 4] == b"\x00\x4b\x18\x47",
        "held-movement sink is not the bounded r3 trampoline",
    )
    hook_target = struct.unpack_from("<I", arm9, hook_offset + 4)[0]
    require(
        hook_target & 1 != 0
        and OVERLAY_BASE <= (hook_target & ~1) < OVERLAY_BASE + file_size,
        "held-movement hook target is outside the resident mount overlay",
    )

    save_constants = (REPO / "include/constants/save.h").read_text()
    require(
        re.search(r"^#define NEW_HEAP3_SIZE 0x10AB00$", save_constants, re.MULTILINE)
        is not None,
        "heap 3 does not reserve the mount block",
    )
    startup = (REPO / "armips/asm/syntheticoverlay.s").read_text()
    require(
        "mov r1, #157" in startup
        and startup.index("mov r1, #157") < startup.index("mov r1, #156"),
        "mount overlay is not boot-loaded before runtime use",
    )
    field_service = (REPO / "src/field/map_teleport.c").read_text()
    require(
        "PAD_BUTTON_R | PAD_BUTTON_Y | PAD_BUTTON_SELECT" in field_service,
        "Select does not wake the resident overworld field service",
    )
    selector_source = (
        REPO
        / "src/overworld_follower_selector_overlay/follower_selector_input.c"
    ).read_text()
    require(
        "OverworldFollowerSelector_IsYReleasePending()" not in selector_source
        and "OverworldFollowerSelector_IsYPressPending() || mountSelection"
            in selector_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING"
            in selector_source,
        "follower selection is not confirmed by a distinct second Y press",
    )
    require(
        "OVERWORLD_FOLLOWER_TRANSITION_QUEUE->reserved ="
            in selector_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT"
            in selector_source
        and "sFollowerRecall.selectorHighlightedSlot" in selector_source,
        "Select does not publish the highlighted mount request",
    )
    require(
        re.search(
            r"OverworldFollowerSelector_ClearYPressPending\(\);\s*"
            r"while \(sFollowerSelectorInputState\s*"
            r"== FOLLOWER_SELECTOR_INPUT_PREPARING\) \{\s*"
            r"(?:/\*.*?\*/\s*)?"
            r"OverworldFollowerSelectorInput_Task\(\s*"
            r"sFollowerSelectorTask,\s*fieldSystem\s*\);",
            selector_source,
            re.DOTALL,
        ) is not None,
        "active Y menu still waits for staged preload frames",
    )

    spawns = (
        REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    resident_spawns = (REPO / "src/overworld_wild_spawns.c").read_text()
    require(
        "OverworldWildSpawns_BeginMountSelectedFollower" in spawns
        and "OverworldWildSpawns_ResolveBehaviorProfileForContext" in spawns
        and "OVERWORLD_MOUNT_OVERLAY_ENTRY->begin" in spawns,
        "selected-follower profile bridge is missing",
    )
    shared_profile_resolver = (
        "OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot("
        in spawns
        and re.search(
            r"ResolveBehaviorProfileForContext\(\s*&context,\s*NULL,\s*"
            r"slot == OW_WILD_FOLLOWER_SLOT\s*\?\s*"
            r"OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON",
            spawns,
        )
        is not None
        and "OverworldWildSpawns_GetSettledConditionTerrainForSlot" in spawns
    )
    require(
        shared_profile_resolver,
        "mount does not use the follower's override stack and current terrain",
    )
    mount_source = (
        REPO
        / "src/overworld_mount_overlay/overworld_mount_overlay.c"
    ).read_text()
    mount_linker = (
        REPO / "src/overworld_mount_overlay/linker.ld"
    ).read_text()
    mount_header = (REPO / "include/overworld_mount.h").read_text()
    mount_internal = (
        REPO / "include/overworld_mount_internal.h"
    ).read_text()
    runtime_source = (
        REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    ).read_text()
    runtime_linker = (
        REPO / "src/overworld_wild_runtime_overlay/linker.ld"
    ).read_text()
    overworld_patch = (REPO / "armips/asm/overworlds.s").read_text()
    walk_module_source = (
        REPO
        / "src/pokemon_move_history_overlay/overworld_walk_module.c"
    ).read_text()
    walk_module_linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    root_linker = (REPO / "rom.ld").read_text()
    mount_runtime_source = mount_source + "\n" + walk_module_source
    issue_held_movement = re.search(
        r"void\s+OverworldMount_IssueHeldMovement\([^;]*?\)\s*"
        r"\{.*?^\}",
        mount_source,
        re.DOTALL | re.MULTILINE,
    )
    diagonal_walk = re.search(
        r"OverworldMount_TryHandleDiagonalWalk\([^;]*?\)\s*"
        r"\{.*?^\}",
        mount_source,
        re.DOTALL | re.MULTILINE,
    )
    mounted_flat_walk = re.search(
        r"Walk_StartMountedFlatMotion\([^;]*?\)\s*"
        r"\{.*?^\}",
        walk_module_source,
        re.DOTALL | re.MULTILINE,
    )
    require(
        "profile->owner.chillSpeed" in mount_source
        and "profile->owner.tilesToAccelerate" in mount_source
        and "profile->owner.maxWalkSpeed" in mount_source
        and "profile->owner.walkOptions" in mount_source,
        "mounted Walk does not consume the fully resolved owner profile",
    )
    require(
        "MAPOBJECTFLAG_UNK18 | MAPOBJECTFLAG_UNK31" in mount_source
        and "follower->flags &= ~MAPOBJECTFLAG_UNK31;" in mount_source
        and "OverworldWildRuntime_SetFacingVectorUnlessMounted" in runtime_source
        and "2: .word 0x0205F97D" in runtime_source
        and ". = ORIGIN(rom) + 0xBEC;" in runtime_linker
        and "KEEP(*(.overworld_wild_runtime_mount_facing))" in runtime_linker
        and "bl 0x023BD3EC" in overworld_patch,
        "mounted facing-vector ownership is incomplete",
    )
    ground_probe = re.search(
        r"OverworldWildRuntime_GetGroundBaseY\([^;]*?\)\s*"
        r"\{.*?^\}",
        runtime_source,
        re.DOTALL | re.MULTILINE,
    )
    require(
        ground_probe is not None
        and "VecFx32 targetPosition;" in ground_probe.group(0)
        and "OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT(" in ground_probe.group(0)
        and "object->posVec[0] =" not in ground_probe.group(0)
        and "object->posVec[2] =" not in ground_probe.group(0),
        "mounted ground-height probe mutates the live render object",
    )
    require(
        "snapshot.profile.chillAction" in mount_source
        and "OVERWORLD_MOUNT_MOTION_HOP" in mount_source
        and "OVERWORLD_MOUNT_MOTION_TELEPORT" in mount_source
        and "OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY->resolve" in mount_source
        and "OW_WILD_BEHAVIOR_TELEPORT_USES_PER_TILE_TIME" in mount_source
        and "OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER" in mount_source,
        "mounted Hop/Teleport does not consume the resolved owner profile",
    )
    require(
        "OverworldMount_FieldInputProcess" in mount_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION" in mount_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT" in mount_source
        and "== OW_WILD_BEHAVIOR_LOCOMOTION_HOP" in mount_source,
        "mounted Hop does not suppress synthetic warp/step transitions",
    )
    require(
        "OverworldMount_TryNextHopLandingCandidate" in mount_source
        and "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(" in mount_source
        and "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(" in mount_source
        and "lateralMagnitude != search->distance" in mount_source
        and "forwardX * search->distance - forwardY * lateral" in mount_source
        and "forwardY * search->distance + forwardX * lateral" in mount_source
        and "lateralMagnitude = search->lateral == maxDistance" in mount_source
        and "lateralMagnitude >= search->distance" in mount_source
        and "sideCount = lateralMagnitude == 0 ? 1 : 2" in mount_source
        and re.search(
            r"hopSearch\.lateral = 0;\s*"
            r"hopSearch\.distance = maxDistance;\s*"
            r"hopSearch\.side = 0;\s*"
            r"while \(OverworldMount_TryNextHopLandingCandidate\(.*?"
            r"OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY->resolve\(",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted Hop does not widen landing candidates from cardinal to diagonal",
    )
    require(
        "motionStreamAnchor" in mount_runtime_source
        and "motionStreamPreparing" in mount_runtime_source
        and "OverworldMount_UpdateLandStreamAnchor" in mount_source
        and "OverworldMount_RestoreLandStreamTarget" in mount_source
        and "extern void LONG_CALL ov01_021F62E8" in mount_runtime_source
        and "ov01_021F62E8(" in mount_runtime_source
        and "OverworldMount_GetLandDataManager() + 0xA0" in mount_source
        and "ov01_021F62CC(" not in mount_runtime_source
        and "motionStreamAnchor.x +=" in mount_source
        and "motionStreamAnchor.z +=" in mount_source
        and "player->xCurr << 16" in mount_source
        and "player->yCurr << 16" in mount_source
        and "OverworldMount_DrainLandStream" in mount_source
        and mounted_flat_walk is not None
        and "stock land manager" in mounted_flat_walk.group(0)
        and "motionStreamPreparing" not in mounted_flat_walk.group(0)
        and "ov01_021F62E8" not in mounted_flat_walk.group(0)
        and re.search(
            r"OverworldMount_UpdateLandStreamAnchor\(void\).*?"
            r"GetLandDataManager\(\) \+ 0xA0\) != 0\) \{\s*"
            r"return FALSE;",
            mount_source,
            re.DOTALL,
        ) is not None
        and "OVERWORLD_WALK_MOUNT_MODULE_ENTRY->startFlatMotion(" in mount_source
        and "if (state->motionCooldown != 0" in walk_module_source
        and re.search(
            r"OverworldMount_UpdateCustomMotion\(\);\s*"
            r"OverworldMount_DrainLandStream\(\);",
            mount_source,
        ) is not None
        and re.search(
            r"if \(sOverworldMountState\.snapshot\.motionMode\s*"
            r"!= OVERWORLD_MOUNT_MOTION_WALK\s*"
            r"&& \(player->xCurr != baseX >> 16 \|\| "
            r"player->yCurr != baseZ >> 16\)\) \{\s*"
            r"player->xPrev = player->xCurr;\s*"
            r"player->yPrev = player->yCurr;",
            mount_source,
        ) is not None,
        "mounted custom motion does not pre-stream land data or logical history",
    )
    require(
        "OVERWORLD_MOUNT_MOTION_CRASH" in mount_source
        and "OverworldMount_ApplyCrashPresentation" in mount_source
        and "OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING" in mount_runtime_source
        and "lane->hopSwayWidth" in mount_source
        and "lane->hopSpinSpeed" in mount_source,
        "mounted Walk crash or player custom-Jump presentation is incomplete",
    )
    require(
        "validateHopLanding" in mount_runtime_source
        and "PlayerAvatar_ResetMovement" in mount_source
        and mount_runtime_source.count(
            "MapObject_SetPositionFromVectorAndDirection("
        ) >= 3
        and "memcpy(follower->posVec, player->posVec" in mount_source
        and "memcpy(&follower->xPrev, &player->xPrev" in mount_source,
        "mounted custom motion lacks landing or avatar-state safeguards",
    )
    require(
        re.search(
            r"motionDirection = direction;\s*"
            r"if \(\(sOverworldMountState\.motionFlicker & 0x0F\) != 0\) \{\s*"
            r"sOverworldMountState\.motionDirection = player->curFacing;",
            mount_source,
        ) is not None
        and re.search(
            r"OverworldMount_CommitMotionTarget\(LocalMapObject \*player\).*?"
            r"MapObject_SetPositionFromVectorAndDirection\(\s*"
            r"player,\s*\(VecFx32 \*\)player->posVec,\s*player->curFacing\);",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted spinning Hop resets facing at takeoff or landing",
    )
    require(
        "bufferedDirection" in mount_runtime_source
        and "stopPending" in mount_runtime_source
        and "Defer stop skid for one sample" in mount_runtime_source
        and "MAPOBJECTFLAG_UNK7" in mount_source
        and "MapObject_SetPositionFromVectorAndDirection" in mount_source
        and "memcpy(follower->posVec, player->posVec" in mount_source
        and "memcpy(&follower->xPrev, &player->xPrev" in mount_source
        and "MapObject_StartMovementCommandInternal(\n        follower,\n"
            not in walk_module_source
        and "follower->xPrev = player->xPrev;" in mount_source
        and "follower->yPrev = player->yPrev;" in mount_source
        and "OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND" in mount_source
        and mount_runtime_source.count(
            "MapObject_StartMovementCommandInternal("
        ) >= 4
        and issue_held_movement is not None
        and re.search(
            r"if \(trackedStep\) \{\s*"
            r"u8 facingDirection = direction;.*?"
            r"OverworldMount_TryStartCustomMotion\(\s*"
            r"avatar,\s*direction,\s*facingDirection\)",
            issue_held_movement.group(0),
            re.DOTALL,
        ) is not None
        and "turnDirection" not in issue_held_movement.group(0),
        "mounted turn skid does not keep its committed travel and facing",
    )
    require(
        "OVERWORLD_WALK_MOUNT_MODULE_ENTRY->filterInput(" in mount_source
        and re.search(
            r"OverworldMount_TryStartWalkFromInput\(\s*"
            r"FIELD_PLAYER_AVATAR \*avatar,\s*u32 \*newKeys,\s*"
            r"u32 \*heldKeys\).*?"
            r"OverworldMount_ResolveDiagonalInput\(avatar, newKeys, heldKeys\);"
            r".*?OverworldMount_FilterMovementInput\(avatar, newKeys, heldKeys\);"
            r".*?OverworldMount_TryHandleDiagonalWalk\(\s*"
            r"avatar,\s*\*newKeys,\s*\*heldKeys\);",
            mount_source,
            re.DOTALL,
        ) is not None
        and "avatar,\n            &newKeys,\n            &heldKeys" in mount_source
        and "state->motionFrameCount = Walk_ClampTime(state->speed);"
            in walk_module_source
        and "state->motionArcHeightQ4 = 0;" in walk_module_source
        and "Walk_StrictDiagonalAllowed" in walk_module_source
        and "Walk_CanCardinal(avatar, vertical)" in walk_module_source
        and "Walk_CanCardinal(avatar, horizontal)" in walk_module_source
        and "Walk_IsFortyFiveDegreeTurn" in walk_module_source
        and "!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(" in walk_module_source
        and "requestedDirection < WALK_DIRECTION_NORTH_WEST"
            in walk_module_source
        and "A queued direction cannot bypass the profile's movement mode."
            in walk_module_source
        and "state->bufferedDirection < WALK_DIRECTION_NORTH_WEST"
            in walk_module_source
        and "state->snapshot.profile.tilesBeforeTurnSkid" in walk_module_source
        and diagonal_walk is not None
        and re.search(
            r"facingDirection = requestedDirection;.*?"
            r"OverworldMount_TryStartCustomMotion\(\s*"
            r"avatar,\s*requestedDirection,\s*facingDirection\)",
            diagonal_walk.group(0),
            re.DOTALL,
        ) is not None
        and "turnDirection" not in diagonal_walk.group(0),
        "mounted exact-frame diagonal Walk policy is incomplete",
    )
    update_motion = re.search(
        r"OverworldMount_UpdateCustomMotion\(void\)\s*\{(?P<body>.*?)"
        r"typedef struct OverworldMountHopSearch",
        mount_source,
        re.DOTALL,
    )
    require(
        update_motion is not None
        and update_motion.group("body").find("motionElapsed++;")
            < update_motion.group("body").find(
                "Commit on the Nth update."
            )
            < update_motion.group("body").find(
                "OverworldMount_FinishCustomMotion();",
                update_motion.group("body").find("Commit on the Nth update."),
            )
        and "stationary player command stays" in update_motion.group("body"),
        "mounted flat Walk does not finish on its exact Nth frame",
    )
    require(
        "#define OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND 0x3E"
            in mount_source
        and "#define OVERWORLD_MOUNT_WALK_FREEZE_COMMAND 0x3C"
            in mount_source
        and "#define WALK_MOUNT_FREEZE_COMMAND 0x3C"
            in walk_module_source
        and mount_source.count("OverworldMount_CompletePendingStep(") == 3,
        "mounted Walk uses a fixed-delay boundary or has competing step consumers",
    )
    require(
        "ASSERT(. <= ORIGIN(rom) + 0x1BF0" in mount_linker
        and ". = ORIGIN(rom) + 0x1BF0;" in mount_linker,
        "mount overlay file size can drift from its packaged Y9/FAT metadata",
    )
    require(
        re.search(
            r"if \(walkMotion\) \{.*?"
            r"player->posVec\[2\].*?"
            r"OverworldMount_ClearObjectCommand\(follower\);\s*\}.*?"
            r"if \(walkMotion\) \{.*?"
            r"sOverworldMountState\.pendingStep = TRUE;.*?\}.*?"
            r"OverworldMount_SyncPresentation\(\);",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted flat Walk does not finish player and mount presentation together",
    )
    cancel_mount = re.search(
        r"static void OverworldMount_Cancel\(u8 reason\)\s*\{"
        r"(?P<body>.*?)\n\}",
        mount_source,
        re.DOTALL,
    )
    detach_mount = mount_source.split(
        "static void OverworldMount_DetachPresentation(void)", 1
    )[1].split("static void OverworldMount_Cancel", 1)[0]
    require(
        cancel_mount is not None
        and "OverworldWalkMount_RebaseMotionTarget(&sOverworldMountState);"
            in cancel_mount.group("body")
        and "OverworldMount_DetachPresentation();"
            in cancel_mount.group("body")
        and "OverworldMount_ClearObjectCommand(player);" in detach_mount
        and "OverworldMount_ResetAvatarAfterCancel(avatar);" in detach_mount
        and "if (sOverworldMountState.pendingStep)" not in detach_mount,
        "mounted cancellation can leave the player movement command active",
    )
    require(
        "section(\".overworld_walk_mount_abort\")" in walk_module_source
        and "OverworldWalkMount_RebaseMotionTargetImpl"
            in walk_module_source
        and ". = ORIGIN(rom) + 0x1BEA;" in walk_module_linker
        and "KEEP(*(.overworld_walk_mount_abort))" in walk_module_linker
        and "OverworldWalkMount_RebaseMotionTarget = 0x023BFFEA | 1;"
            in root_linker,
        "mounted cancellation rollback helper is not fixed in resident code",
    )
    resume_follower = re.search(
        r"OverworldMount_ResumeFollowerCommand\(.*?\)\s*\{"
        r"(?P<body>.*?)\n\}",
        mount_source,
        re.DOTALL,
    )
    require(
        resume_follower is not None
        and "!= OVERWORLD_MOUNT_MOTION_WALK"
            in resume_follower.group("body"),
        "mounted Walk transition resumes an independent follower command",
    )
    require(
        "movementCrashShakeTimers[\n        OW_WILD_FOLLOWER_SLOT] = 0;"
            in mount_source,
        "mounted presentation can be overwritten by a stale crash shake",
    )
    require(
        re.search(
            r"KEEP\(\*\(\.overworld_mount_step\)\)\s*"
            r"KEEP\(\*\(\.overworld_mount_step_extra\)\)",
            mount_linker,
        ) is not None
        and re.search(
            r"KEEP\(\*\(\.overworld_mount_field_input\)\)\s*"
            r"KEEP\(\*\(\.overworld_mount_field_input_extra\)\)",
            mount_linker,
        ) is not None
        and re.search(
            r"KEEP\(\*\(\.overworld_mount_crash\)\)\s*"
            r"KEEP\(\*\(\.overworld_mount_crash_extra\)\)",
            mount_linker,
        ) is not None,
        "mount helper code is not kept inside the audited ABI reserves",
    )
    require(
        "OVERWORLD_MOUNT_TOGGLE_BUTTON PAD_BUTTON_SELECT" in mount_source
        and "beginMountSelectedFollower(fieldSystem, state)" in mount_source,
        "Select does not bind the current follower through the profile bridge",
    )
    require(
        "if (sOverworldMountState.motionCooldown != 0) {\n        "
            "/* Field input has already resolved its direction"
            in mount_source
        and "*newKeys &= ~PAD_PLUS_KEY_MASK;" not in mount_source
        and "*heldKeys &= ~PAD_PLUS_KEY_MASK;" not in mount_source,
        "landing pause can leak a stale direction into stock player control",
    )
    require(
        "The held-movement hook can run before the current exact-frame"
            in mount_source
        and re.search(
            r"if \(trackedStep\) \{.*?"
            r"snapshot.motionMode\s*!= OVERWORLD_MOUNT_MOTION_NONE"
            r".*?return;",
            mount_source,
            re.DOTALL,
        ) is not None,
        "held input can replace an active mounted Walk motion",
    )
    require(
        "/* Custom locomotion owns the player for its complete idle/move/pause"
            in mount_source
        and "Overlay 1 asks the stock avatar collision helper" in mount_source
        and re.search(
            r"if \(avatar->unk10 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE"
            r".*?OverworldMount_ResetAvatarAfterCancel\(avatar\);",
            mount_source,
            re.DOTALL,
        ) is not None
        and re.search(
            r"OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT\(rawLocomotion\)\) \{"
            r".*?OverworldMount_TryStartCustomMotion\(.*?return TRUE;\s*\}",
            mount_source,
            re.DOTALL,
        ) is not None,
        "idle custom locomotion can fall through to stock player control",
    )
    require(
        "direction >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST\n"
            "        && direction <= OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST"
            in mount_source,
        "no-direction input can be misread as a mounted diagonal",
    )
    capture_toggle = re.search(
        r"static void OverworldWildSpawns_CaptureMountToggle\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    resident_field_ready_task = re.search(
        r"static void OverworldWildSpawns_FieldReadyTask\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    require(
        "OVERWORLD_MOUNT_TOGGLE_LATCH_ADDR 0x023BC78A" in mount_header
        and "u8 bufferedTogglePending;" in mount_internal
        and "u8 bufferedToggleDown;" in mount_internal
        and "bufferedTogglePending) == 0x96" in mount_internal
        and capture_toggle is not None
        and "reg_PAD_KEYINPUT & PAD_BUTTON_SELECT"
            in capture_toggle.group(0)
        and "fieldSystem->taskman == NULL" in capture_toggle.group(0)
        and "!OverworldFollowerSelector_IsActiveFlagSet()"
            in capture_toggle.group(0)
        and "OVERWORLD_MOUNT_TOGGLE_PENDING = TRUE;"
            in capture_toggle.group(0)
        and "togglePressed = sOverworldMountState.bufferedTogglePending != 0"
            in mount_source
        and "sOverworldMountState.bufferedTogglePending = FALSE;"
            in mount_source
        and "u8 bufferedToggleDown = sOverworldMountState.bufferedToggleDown;"
            in mount_source
        and "sOverworldMountState.bufferedToggleDown = bufferedToggleDown;"
            in mount_source
        and "until a toggle succeeds" in mount_source
        and resident_field_ready_task is not None
        and resident_field_ready_task.group(0).find(
            "OverworldWildSpawns_CaptureMountToggle(fieldSystem);"
        ) < resident_field_ready_task.group(0).find(
            "if (!sub_0203DF8C(fieldSystem))"
        )
        and "section(\".overworld_mount_toggle_latch\")" in mount_source
        and "OverworldMount_TickLatched" in mount_source
        and "OverworldMount_TickLatched," in mount_source
        and ". = ORIGIN(rom) + 0xC78;" in mount_linker
        and "KEEP(*(.overworld_mount_toggle_latch))" in mount_linker,
        "Select input can be lost while the mount frame service is stopped",
    )
    require(
        "OVERWORLD_MOUNT_RIDER_SPRITE_MALE 178" in mount_source
        and "OVERWORLD_MOUNT_RIDER_SPRITE_FEMALE 179" in mount_source
        and "savedPlayerGfxId" in mount_source
        and "ChangeMapObjSprite(" in mount_source
        and "ChangeMapObjSprite(player, sOverworldMountState.savedPlayerGfxId)"
            in mount_source,
        "mounted rider does not apply and restore the swim hero/heroine sprite",
    )
    require(
        "OverworldMount_HandleFollowerSelectionRequest" in mount_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING" in mount_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT" in mount_source
        and "OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND" in mount_source
        and "->beginMountSelectedFollower(fieldSystem, state)" in mount_source,
        "mount controller does not consume selector mount requests",
    )
    require(
        "OverworldMount_AdvanceMovementChain" not in mount_source
        and "OverworldMount_StartChainPause" not in mount_source
        and "OverworldMount_ApplyChainPauseInput" not in mount_source,
        "mounted movement still contains a chain executor",
    )
    behavior_data = (REPO / "data/OverworldWildBehaviorData.c").read_text()
    follower_override = re.search(
        r"/\* profile: Follower Pokemon \*/(?P<body>.*?)"
        r"/\* profile:",
        behavior_data,
        re.DOTALL,
    )
    require(follower_override is not None, "follower override profile is missing")
    follower_override_body = follower_override.group("body")
    disabled_chain_masks = (
        "OW_WILD_BEHAVIOR_OVERRIDE2_RAM_ACCELERATION_STEPS",
        "OW_WILD_BEHAVIOR_OVERRIDE2_RAM_MAX_SPEED",
        "OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_PAUSE_ACTION",
        "OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_MOVEMENT_VARIANCE",
        "OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_VARIANCE",
    )
    require(
        all(mask in follower_override_body for mask in disabled_chain_masks),
        "follower/mount override does not explicitly disable every chain field",
    )
    repel_source = (REPO / "src/repel.c").read_text()
    require(
        "OverworldMount_PlayerStepBridgeEntry(fieldSystem)" in repel_source,
        "mounted Movement Chain does not use the test2824 player-step callback",
    )
    require(
        "OVERWORLD_MOUNT_CANCEL_FIELD_BUSY" in spawns
        and "OVERWORLD_MOUNT_CANCEL_MAP_CHANGE" in mount_source
        and "prepareMapTransition((u8)mode)" in spawns
        and "preserveTransitionPrepared" in mount_source
        and "binding->mapId = spawn->mapId;" in mount_source
        and "binding->mapGeneration = state->mapGeneration;" in mount_source
        and "OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST" in spawns
        and "OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP" in spawns,
        "lifecycle cancellation coverage is incomplete",
    )
    transition_prepare = re.search(
        r"static void OverworldMount_PrepareMapTransition\(u8 mode\)"
        r"(?P<body>.*?)"
        r"static void __attribute__\(\(noinline, section\(\"\.overworld_mount_motion\"\)\)\)\s*"
        r"OverworldMount_ResumeCustomMotionAfterMapTransition",
        mount_source,
        re.DOTALL,
    )
    require(
        transition_prepare is not None
        and "OverworldMount_FinishCustomMotion" not in transition_prepare.group("body")
        and "preserveTransitionPrepared = TRUE" in transition_prepare.group("body")
        and "OverworldMount_ResumeCustomMotionAfterMapTransition();"
            in mount_source
        and re.search(
            r"freezeCommand = sOverworldMountState\.snapshot\.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK\s*"
            r"\? OVERWORLD_MOUNT_WALK_FREEZE_COMMAND\s*"
            r": OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND;",
            mount_source,
        ) is not None
        and mount_source.count(
            "OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND"
        ) >= 4,
        "mounted custom motion does not survive a preserved map-area transition",
    )
    helper_source = (
        REPO
        / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
    ).read_text()
    require(
        "OW_WILD_MAP_HEADER_CHANGE_RESUME_PRESENTATION" in helper_source
        and "OverworldMount_UpdateCustomMotion();" in mount_source
        and "OverworldMount_SyncPresentation();" in mount_source
        and "OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING" in mount_source,
        "preserved map transition leaves mounted presentation one frame behind",
    )
    refill_function = re.search(
        r"static BOOL [^;]*?OverworldWildSpawns_TryRefill\([^;]*?\)\s*\{"
        r".*?\n\}",
        spawns,
        re.DOTALL,
    )
    runtime_refill_timer = re.search(
        r"static void OverworldRuntime_TickWildRefillTimer\([^;]*?\)\s*\{"
        r".*?\n\}",
        mount_source,
        re.DOTALL,
    )
    player_step = re.search(
        r"static BOOL [^;]*?OverworldWildSpawns_OverlayOnPlayerStep\([^;]*?\)\s*\{"
        r".*?\n\}",
        spawns,
        re.DOTALL,
    )
    require(
        "#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 32" in spawns
        and refill_function is not None
        and "spawnCooldown--" not in refill_function.group(0)
        and "OW_WILD_REFILL_BASE_INTERVAL_FRAMES * sharedSpawnCount"
            in refill_function.group(0)
        and runtime_refill_timer is not None
        and "state->spawnCooldown--" in runtime_refill_timer.group(0)
        and "state->spawnCooldown = OW_WILD_REFILL_TIMER_PENDING;"
            in runtime_refill_timer.group(0)
        and "gOverworldWildFieldIdleRearmPending != 0"
            in runtime_refill_timer.group(0)
        and "gOverworldWildFieldIdleRearmPending |="
            in runtime_refill_timer.group(0)
        and mount_source.count("OverworldRuntime_TickWildRefillTimer(state);") == 1
        and player_step is not None
        and "OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING"
            in player_step.group(0)
        and "OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING) == 0"
            in player_step.group(0)
        and player_step.group(0).count(
            "OW_WILD_PLAYER_STEP_MAINTENANCE_QUEUED"
        ) == 1,
        "wild refill cadence is still coupled to player-step calls",
    )
    require(
        refill_function.group(0).find("state->spawnCooldown = refillCooldown;")
            < refill_function.group(0).find(
                "OverworldWildSpawns_ReconcileFollowerSelection("
            ),
        "an early follower refill exit can leave the runtime timer locked",
    )
    require(
        "OW_WILD_FIELD_IDLE_REARM_PENDING" in field_service
        and "OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING" in field_service
        and "state->spawnCooldown = 0;" in player_step.group(0),
        "map transitions do not request an immediate population reconciliation",
    )
    field_ready_task = re.search(
        r"static void OverworldWildSpawns_FieldReadyTask\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    resident_player_step = re.search(
        r"BOOL OverworldWildSpawns_OnPlayerStep\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    cold_load_gate = re.search(
        r"if \(!IsOverlayLoaded\(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION\)\) \{"
        r"(?P<body>.*?)\n\s*\}",
        field_ready_task.group(0) if field_ready_task else "",
        re.DOTALL,
    )
    field_ready_before_poll = (
        field_ready_task.group(0).split(
            "OverworldFieldService_PollFrame(fieldSystem);", 1
        )[0]
        if field_ready_task is not None
        else ""
    )
    transition_tail = (
        field_ready_task.group(0).split(
            "sFieldReadyTaskMapId = currentMapId;", 1
        )[1].split("/* Overlay 131", 1)[0]
        if field_ready_task is not None
        and "sFieldReadyTaskMapId = currentMapId;"
            in field_ready_task.group(0)
        else "return;"
    )
    require(
        field_ready_task is not None
        and cold_load_gate is not None
        and "HandleLoadOverlay(" in cold_load_gate.group("body")
        and "return;" in cold_load_gate.group("body")
        and "OverworldFieldService_PollFrame(fieldSystem);"
            in field_ready_task.group(0)
        and resident_player_step is not None
        and "gOverworldWildFieldIdleRearmPending != 0"
            in resident_player_step.group(0)
        and player_step is not None
        and "if (state->battleGraceSteps != 0) {\n        return FALSE;\n    }"
            not in player_step.group(0),
        "save-load refill can use a cold overlay in the load frame",
    )
    require(
        "gOverworldWildFieldIdleRearmPending != 0"
            in field_ready_before_poll
        and "OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->onPlayerStep("
            in field_ready_before_poll,
        "stale map context can reach Y or throw service before rearm",
    )
    follower_refill_branch = player_step.group(0).split(
        "OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING", 1
    )[1]
    follower_ball_tick = follower_refill_branch.find(
        "OverworldWildSpawns_TickPlayerBallProjectile("
    )
    follower_refill = follower_refill_branch.find(
        "OverworldWildSpawns_TryRefill("
    )
    require(
        0 <= follower_ball_tick < follower_refill,
        "follower refill retries before its release ball can advance",
    )
    require(
        field_ready_task is not None
        and "return;" in transition_tail
        and resident_player_step is not None
        and "OverworldWildSpawns_GetOverlayEntry(TRUE)"
            in resident_player_step.group(0),
        "map-header reconciliation can reach input or refill in the same frame",
    )
    require(
        "HandleLoadOverlay("
            in field_ready_before_poll
        and "OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG"
            in field_ready_before_poll
        and "OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->validate()"
            in field_ready_before_poll
        and field_ready_task.group(0).find(
            "OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->onPlayerStep("
        ) < field_ready_task.group(0).find(
            "OverworldFollowerSelectorTaskPollEntry(fieldSystem);"
        ) < field_ready_task.group(0).find(
            "OverworldFieldService_PollFrame(fieldSystem);"
        ),
        "first-ready map, selector, and input ordering is unsafe",
    )
    poll_frame = re.search(
        r"static BOOL OverworldFieldService_PollFrameImpl\([^;]*?\)\s*\{"
        r".*?\n\}",
        field_service,
        re.DOTALL,
    )
    poll_before_run = (
        poll_frame.group(0).split(
            "if (OverworldFollowerSelector_IsYPressPending()", 1
        )[0]
        if poll_frame is not None
        else "return TRUE;"
    )
    poll_after_run = (
        "if (OverworldFollowerSelector_IsYPressPending()"
        + poll_frame.group(0).split(
            "if (OverworldFollowerSelector_IsYPressPending()", 1
        )[1]
        if poll_frame is not None
        and "if (OverworldFollowerSelector_IsYPressPending()"
            in poll_frame.group(0)
        else ""
    )
    require(
        poll_frame is not None
        and "if (!HandleLoadOverlay("
            in poll_before_run
        and "return TRUE;" not in poll_before_run.split(
            "if (!HandleLoadOverlay(", 1
        )[1]
        and "return FALSE;"
            in poll_before_run.split("if (!HandleLoadOverlay(", 1)[1]
        and "OverworldFollowerSelector_IsYPressPending()"
            in poll_after_run
        and "OverworldFollowerSelector_IsDirectLoaded()"
            in poll_after_run
        and "OverworldFollowerSelector_ValidateLoaded()"
            in poll_after_run
        and poll_after_run.find(
            "OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->inputFilter("
        ) < poll_after_run.find("entry->onPlayerFrame("),
        "cold Y or R input still waits a frame after overlay load",
    )
    field_linker = (REPO / "src/field/linker.ld").read_text()
    require(
        "ASSERT(ADDR(.data) + SIZEOF(.data) <= 0x023CCFD8"
            in field_linker,
        "field overlay boundary is not enforced by the linker",
    )
    require(
        "(void)OverworldMount_UpdateLandStreamAnchor();" in mount_source
        and re.search(
            r"OverworldMount_Cancel\(u8 reason\).*?"
            r"if \(sOverworldMountState\.motionStreamPreparing.*?"
            r"OverworldMount_RestoreLandStreamTarget\(.*?\);\s*"
            r"sOverworldMountState\.motionStreamPreparing = FALSE;",
            mount_source,
            re.DOTALL,
        ) is not None
        and re.search(
            r"OverworldMount_UpdateCustomMotion\(\);\s*"
            r"OverworldMount_DrainLandStream\(\);",
            mount_source,
        ) is not None,
        "landed custom motion does not release before its land stream drains",
    )
    complete_step = re.search(
        r"static BOOL(?:\s+__attribute__\(\([^)]*\)\))?\s*"
        r"OverworldMount_CompletePendingStep\([^;]*?\)\s*\{"
        r".*?\n\}",
        mount_source,
        re.DOTALL,
    )
    require(
        complete_step is not None
        and "MapObject_IsMovementPaused(avatar->mapObject)"
            in complete_step.group(0)
        and "MapObject_IsMovementPaused(follower)"
            not in complete_step.group(0)
        and "OverworldMount_NormalizeFollowerAfterStep(avatar->mapObject)"
            in complete_step.group(0)
        and "avatar->unk14 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_END"
            not in complete_step.group(0),
        "mounted skid completion is not player-authoritative",
    )

    print(
        "mount verification passed: "
        f"load=0x{OVERLAY_BASE:08X}, entry=0x{OVERLAY_ENTRY:08X}, "
        f"file=0x{file_size:X}, "
        f"bss=0x{bss_size:X}, free=0x{OVERLAY_LIMIT - load_address - file_size - bss_size:X}"
    )


if __name__ == "__main__":
    main()
