#!/usr/bin/env python3
"""Verify the Flying insect flat-Walk profile and its shared movement policy."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FACE_PLAYER_RESIDENT_ENTRY = 0x023BF468
sys.path.insert(0, str(REPO))

from scripts import overworld_behavior_profile_viewer as profile_viewer


def main() -> int:
    expressions, _ = profile_viewer.parse_define_expressions(
        profile_viewer.DEFINE_SOURCE_FILES
    )
    macros = profile_viewer.evaluate_defines(expressions)
    numeric_direction = profile_viewer.canonical_profile_change_raw(
        "hopAllowNonCardinal",
        "2",
        macros,
        allow_relative=True,
    )
    if numeric_direction != "OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY":
        raise SystemExit(
            "Profile save does not canonicalize diagonal-only direction value 2"
        )
    if not profile_viewer.walk_options_valid(0x20) \
            or not profile_viewer.walk_options_valid(0x60):
        raise SystemExit("Profile save rejects Disable acceleration")

    overview = json.loads(
        subprocess.check_output(
            [
                "python3",
                str(REPO / "scripts/overworld_behavior_profile_viewer.py"),
                "--json",
            ],
            cwd=REPO,
            text=True,
        )
    )
    profile_entry = next(
        item for item in overview["classes"] if item.get("name") == "Flying insect"
    )
    profile = profile_entry["profile"]
    expected = {
        "chillSpeed": 8,
        "chillAction": 1,
        "hopAllowNonCardinal": 2,
        "hopMinDistance": 1,
        "hopMaxDistance": 1,
        "ramAccelerationSteps": 8,
        "chainMovementVariance": 6,
        "activeProfile": 7,
        "tiredProfile": 7,
        "chainPauseAction": 5,
        "chainPauseActionChance": 60,
        "avoidPreviousTile": 1,
        "wanderStraightChance": 0,
        "walkOptions": 0x60,
        "walkPause": 0,
        "tilesBeforeTurnSkid": 0,
        "chainRepositionJumpCount": 4,
        "chainRepositionSpeed": 8,
        "chainRepositionDistance": 2,
        "chainRepositionDust": 0,
        "chainRepositionAllowCardinal": 0,
        "chainRepositionAllowDiagonal": 1,
        "hopSpinSpeed": 0,
        "hopElevationArcScale": 0,
        "hopSwayWidth": 0,
    }
    mismatches = {
        key: (profile[key]["value"], value)
        for key, value in expected.items()
        if profile[key]["value"] != value
    }
    if mismatches:
        raise SystemExit(f"Flying insect profile mismatch: {mismatches}")

    follower_entry = next(
        item for item in overview["classes"] if item.get("name") == "Follower Pokemon"
    )
    follower_max_speed = follower_entry["profile"]["maxWalkSpeed"]
    if follower_max_speed["value"] is not None:
        raise SystemExit(
            "Follower Pokemon must not cap maximum Walk speed for every species"
        )
    ledyba = next(
        item
        for item in overview["assignments"]
        if item["species"]["symbol"] == "SPECIES_LEDYBA"
    )
    for lane_name, lane in (
        ("Chill", ledyba["profile"]),
        ("Active", ledyba["profile"]["_activeProfileData"]),
        ("Tired", ledyba["profile"]["_tiredProfileData"]),
    ):
        resolved_follower_lane = profile_viewer.clone_profile(lane)
        profile_viewer.merge_profile(
            resolved_follower_lane,
            follower_entry["override"],
        )
        profile_viewer.normalize_profile(resolved_follower_lane, macros)
        if profile_viewer.numeric(resolved_follower_lane["chillSpeed"]) != 8:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane does not start at 8 frames"
            )
        if profile_viewer.numeric(resolved_follower_lane["maxWalkSpeed"]) != 2:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane does not keep its 2-frame fastest time"
            )
        if not profile_viewer.numeric(resolved_follower_lane["walkOptions"]) & 0x20:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane loses Disable acceleration"
            )
    rattata = next(
        item
        for item in overview["assignments"]
        if item["species"]["symbol"] == "SPECIES_RATTATA"
    )
    resolved_rattata_follower = profile_viewer.clone_profile(rattata["profile"])
    profile_viewer.merge_profile(resolved_rattata_follower, follower_entry["override"])
    profile_viewer.normalize_profile(resolved_rattata_follower, macros)
    if profile_viewer.numeric(resolved_rattata_follower["walkOptions"]) & 0x20:
        raise SystemExit("Disable acceleration leaked into another follower profile")

    members = set(profile_entry["memberSymbols"])
    if "SPECIES_SPEAROW" in members or "SPECIES_FEAROW" in members:
        raise SystemExit("Flying insect still contains a bird species")
    if len(members) != 34 or "SPECIES_BEEDRILL" not in members:
        raise SystemExit("Flying insect member set is incomplete")

    spawns = (
        REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    helper = (
        REPO
        / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
    ).read_text()
    mount = (
        REPO
        / "src/overworld_mount_overlay/overworld_mount_overlay.c"
    ).read_text()
    walk_runtime = (
        REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    ).read_text()
    face_player_runtime = (
        REPO
        / "src/pokemon_move_history_overlay/overworld_walk_module.c"
    ).read_text()
    runtime_sources = spawns + face_player_runtime
    for required in (
        "OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION",
        "OW_WILD_BEHAVIOR_WALK_PRESERVES_FACING",
        "OW_WILD_BEHAVIOR_WALK_FACES_PLAYER",
        "OverworldWildSpawns_GetFacingTowardTile",
        "state->movementSpotStates[slot]",
        "movementStagedHopAvoidValid",
        "wanderStraightChance",
        "OverworldWildSpawns_TryStartRandomBehaviorHopCommand",
    ):
        if required not in runtime_sources:
            raise SystemExit(f"flat-Walk runtime is missing: {required}")
    if "pauseTicks = lane->chainRepositionSpeed;" not in mount:
        raise SystemExit("mounted flat Reposition does not use exact frame timing")
    if "OVERWORLD_WALK_MODULE_ENTRY->accelerateTime(" not in walk_runtime \
            or "OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION" not in spawns:
        raise SystemExit("wild Walk completion does not use exact-frame acceleration")
    if not re.search(
        r"OverworldMount_Begin\(.*?"
        r"OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION\(\s*"
        r"profile->owner.walkOptions\).*?"
        r"maxSpeed\s*=\s*baseSpeed;",
        mount,
        re.DOTALL,
    ):
        raise SystemExit("mounted Walk does not disable profile acceleration")
    if not re.search(
        r"if \(chainReposition\s*&&\s*!repositionUsesArc\) \{\s*"
        r"frameCount\s*=\s*runtime->movementDeferredChainPauseTicks\[slot\];\s*"
        r"frameCount\s*\*=\s*distance;\s*"
        r"\}",
        spawns,
    ):
        raise SystemExit("flat Reposition does not use its exact Walk time")
    if not re.search(
        r"profile\.hopTime\s*=\s*profile\.spawnHopTime;\s*"
        r"profile\.hopSwayWidth\s*=\s*profile\.spawnHopSwayWidth;\s*"
        r"profile\.hopAllowVerticalObstacles\s*=\s*1;\s*"
        r"profile\.chillAction\s*=\s*OW_WILD_BEHAVIOR_LOCOMOTION_HOP;",
        spawns,
    ):
        raise SystemExit("Spawn hop does not use its authored timing profile")
    help_queue = re.search(
        r"static void OverworldWildSpawns_SpawnQueuedHelpChildren\(.*?"
        r"(?=static void OverworldWildSpawns_TrySpawnHelpChildren)",
        spawns,
        re.DOTALL,
    )
    if help_queue is None or (
        "if (!OverworldWildSpawns_TrySpawnOneHelpChild(" in help_queue.group(0)
        and "break;" in help_queue.group(0)
    ):
        raise SystemExit("one failed helper placement cancels the whole Call for help")
    for required in ("straightX", "hasBacktrack", "candidateCount"):
        if required not in helper:
            raise SystemExit(f"flat-Walk direction policy is missing: {required}")
    if not all(value in face_player_runtime for value in (
        "Walk_ApplyFacePlayerFacing(",
        "state->movementFieldSystem == NULL",
        "player == NULL",
        "horizontal = dx > 0 ? WALK_DIRECTION_EAST : WALK_DIRECTION_WEST;",
        "vertical = dy > 0 ? WALK_DIRECTION_SOUTH : WALK_DIRECTION_NORTH;",
        "dx = -dx;",
        "dy = -dy;",
        "object->curFacing = dx >= dy ? horizontal : vertical;",
    )):
        raise SystemExit("Face-player readiness or diagonal tie behavior is missing")
    if not re.search(
        r"if \(OW_WILD_BEHAVIOR_WALK_FACES_PLAYER\("
        r"profile\.owner\.walkOptions\)\) \{.*?"
        r"OVERWORLD_WALK_FACE_MODULE_ENTRY->apply\(",
        spawns,
        re.DOTALL,
    ):
        raise SystemExit("Face-player work is not gated before the resident call")

    movement_header = (REPO / "include/overworld_walk_module.h").read_text()
    if (
        f"OVERWORLD_WALK_FACE_MODULE_ENTRY_ADDR 0x{FACE_PLAYER_RESIDENT_ENTRY:08X}"
        not in movement_header
    ):
        raise SystemExit("Face-player resident entry address is stale")

    core_object = REPO / "build/pokemon_move_history_overlay_linked.o"
    spawns_object = REPO / "build/overworld_wild_spawns_overlay_linked.o"
    if core_object.is_file() and spawns_object.is_file():
        core_symbols = subprocess.check_output(
            ["arm-none-eabi-nm", "-n", str(core_object)],
            text=True,
        )
        symbol_match = re.search(
            r"^([0-9A-Fa-f]{8})\s+[A-Za-z]\s+gOverworldWalkFaceModuleEntry$",
            core_symbols,
            re.MULTILINE,
        )
        if symbol_match is None or int(symbol_match.group(1), 16) != FACE_PLAYER_RESIDENT_ENTRY:
            raise SystemExit("Built face-player resident entry moved")
        spawns_symbols = subprocess.check_output(
            ["arm-none-eabi-nm", "-n", str(spawns_object)],
            text=True,
        )
        if "__OverworldWildSpawns_ApplyFacePlayerFacing_from_thumb" in spawns_symbols:
            raise SystemExit("Face-player call still uses the movable core veneer")
    if not re.search(
        r"OverworldWildSpawns_StartSpawnHop\(.*?"
        r"fieldSystem->playerAvatar->mapObject\s*==\s*NULL.*?"
        r"object->posVec\[1\]\s*=\s*fieldSystem->playerAvatar->mapObject->posVec\[1\]",
        spawns,
        re.DOTALL,
    ):
        raise SystemExit("Spawn hop can read the player object before it is ready")

    header = (REPO / "include/overworld_wild_behavior_data.h").read_text()
    for required in (
        "OW_WILD_BEHAVIOR_WALK_OPTION_DISABLE_ACCELERATION (1u << 5)",
        "OW_WILD_BEHAVIOR_WALK_OPTION_FACE_PLAYER (1u << 6)",
        "OW_WILD_BEHAVIOR_WALK_OPTION_FIXED_FACING (1u << 7)",
        "OW_WILD_BEHAVIOR_WALK_OPTIONS_RESERVED_MASK 0x0E",
    ):
        if required not in header:
            raise SystemExit(f"Walk facing schema is missing: {required}")

    viewer = (
        REPO / "tools/overworld-viewer-v2/static/profiles.js"
    ).read_text()
    if '<option value="player"' not in viewer or "options & ~0xC0" not in viewer:
        raise SystemExit("V2 editor does not expose the three-state Walk facing selector")
    if "Allow acceleration" not in viewer or 'part === "acceleration"' not in viewer:
        raise SystemExit("V2 editor does not expose Disable acceleration")

    print("Flying insect flat-Walk profile and movement policy verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
