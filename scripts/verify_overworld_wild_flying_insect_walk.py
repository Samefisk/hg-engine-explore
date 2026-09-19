#!/usr/bin/env python3
"""Verify the Flying insect flat-Walk profile and its shared movement policy."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WALK_OVERLAY_BASE = 0x023BE400
RETIRED_WALK_TABLES_START = 0x023BF400
RETIRED_WALK_TABLES_END = 0x023BF488
sys.path.insert(0, str(REPO))

from scripts import overworld_behavior_profile_viewer as profile_viewer
from scripts.verify_overworld_role_controller import (
    function_bodies,
    matching_delimiter,
    strip_c_noncode,
)
from scripts.verify_pokemon_move_history_capture import elf_bytes_at


def verify_face_player_call_gating(spawns: str) -> None:
    """Face-player stays live through every normal and reposition motion."""
    tick = function_bodies(spawns).get("OverworldWildSpawns_TickMovementParams")
    if tick is None:
        raise SystemExit("missing movement tick owner")
    clean = strip_c_noncode(tick)
    call = r"\bOverworldWildSpawns_ApplyFacePlayerFacing\s*\("
    if len(re.findall(call, clean)) != 1:
        raise SystemExit("movement tick must have one canonical face-player call")
    motion_owner = re.sub(r"\s+", "", """
        actorPolicyKnown = OverworldActorPolicy_Inspect((u8)i, &policy);
        actorMotionOwnsFacing = actorPolicyKnown
            && policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE
            && policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED;
    """)
    if motion_owner not in re.sub(r"\s+", "", clean):
        raise SystemExit("movement tick does not identify the active Motion facing owner")
    expected = "OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile.owner.walkOptions)"
    for match in re.finditer(r"\bif\s*\(", clean):
        opening = clean.index("(", match.start())
        closing = matching_delimiter(clean, opening, "(", ")")
        if closing < 0:
            continue
        body_start = closing + 1
        while body_start < len(clean) and clean[body_start].isspace():
            body_start += 1
        if body_start >= len(clean) or clean[body_start] != "{":
            continue
        body_end = matching_delimiter(clean, body_start, "{", "}")
        if body_end < 0:
            continue
        condition = re.sub(r"\s+", "", clean[opening + 1:closing])
        if condition == expected and re.search(call, clean[body_start + 1:body_end]):
            break
    else:
        raise SystemExit("Face-player work must stay live through chain reposition")
    call_end = clean.index(");", re.search(call, clean).start()) + 2
    idle_guard = clean.find("if (actorMotionOwnsFacing)", call_end)
    cooldown = clean.find("if (cooldown > 0)", idle_guard)
    if idle_guard < 0 or cooldown < 0 or idle_guard > cooldown:
        raise SystemExit("idle Wild AI can run before the active Motion owner returns control")


def verify_walk_start_requires_idle_motion(spawns: str) -> None:
    """No movement candidate or facing fallback may run while Motion is busy."""
    body = function_bodies(spawns).get(
        "OverworldWildSpawns_TryStartSpawnerMovementCommand"
    )
    if body is None:
        raise SystemExit("missing Wild Walk start owner")
    clean = re.sub(r"\s+", "", strip_c_noncode(body))
    required = re.sub(r"\s+", "", """
        if (policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE
            && policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED) {
            return FALSE;
        }
    """)
    idle = clean.find(required)
    locomotion = clean.find("locomotion=OverworldWildSpawns_GetCurrentMovementLocomotion")
    facing = clean.find("turn_around:")
    if idle < 0 or locomotion < 0 or facing < 0 or not idle < locomotion < facing:
        raise SystemExit("Wild Walk candidates can alter facing while shared Motion is busy")


def verify_blocked_flee_has_fallback(spawns: str, helper: str) -> None:
    """A blocked flee may recover inward, but cannot reverse straight back."""
    body = function_bodies(spawns).get(
        "OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand"
    )
    if body is None:
        raise SystemExit("missing frame-driven active movement owner")
    clean = strip_c_noncode(body)
    if "OW_WILD_HELPER_HOP_PLAN_FLEE" not in clean:
        raise SystemExit("blocked flee movement has no distance-preserving fallback")
    if not re.search(
        r"if\s*\(\s*!movementStarted\s*&&\s*"
        r"movementTarget\s*==\s*OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER\s*\)\s*\{.*?"
        r"OverworldWildSpawns_TryStartRandomBehaviorHopCommand\(",
        clean,
        re.DOTALL,
    ):
        raise SystemExit("blocked flee cannot leave a dead-end tile")

    directed = function_bodies(spawns).get(
        "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand"
    )
    if directed is None:
        raise SystemExit("missing directed flee movement owner")
    directed_clean = strip_c_noncode(directed)
    for required in (
        "lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_WANDER",
        "!OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(lane->walkOptions)",
    ):
        if required not in directed_clean:
            raise SystemExit(f"directed flat-Walk policy is missing: {required}")
    if not re.search(
        r"if\s*\(\s*planMode\s*==\s*OW_WILD_HELPER_HOP_PLAN_FLEE\s*\)\s*\{.*?"
        r"OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand\(.*?"
        r"OW_WILD_HELPER_HOP_PLAN_FLEE\).*?goto\s+blocked\s*;",
        directed_clean,
        re.DOTALL,
    ):
        raise SystemExit("blocked flee can bypass its distance-preserving planner")
    plan_step = function_bodies(spawns).get(
        "OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand"
    )
    if plan_step is None or not re.search(
        r"validationContext\.rejectPreviousTile\s*=\s*"
        r"planMode\s*==\s*OW_WILD_HELPER_HOP_PLAN_FLEE\s*;",
        strip_c_noncode(plan_step),
    ):
        raise SystemExit("flee planning does not reject an immediate reversal")

    validator = function_bodies(spawns).get(
        "OverworldWildSpawns_ValidateBehaviorHopLanding"
    )
    if validator is None:
        raise SystemExit("missing directed hop landing validator")
    validator_clean = strip_c_noncode(validator)
    for required in (
        "context->rejectPreviousTile",
        "context->state->movementStagedHopAvoidValid[context->slot]",
        "context->state->movementStagedHopAvoidX[context->slot]",
        "context->state->movementStagedHopAvoidY[context->slot]",
    ):
        if required not in validator_clean:
            raise SystemExit(f"flee reversal guard is missing: {required}")

    plan_step_clean = strip_c_noncode(plan_step)
    for required in (
        "config.directionCount |= 0x20",
        "config.directionCount |= 0x80",
        "config.directions[5] = lane->wanderStraightChance",
        "config.directions[6] = (u8)OverworldWalk_DeltaX(",
        "config.directions[7] = (u8)OverworldWalk_DeltaY(",
    ):
        if required not in plan_step_clean:
            raise SystemExit(f"directed straight-chance policy is missing: {required}")

    random_walk = function_bodies(spawns).get(
        "OverworldWildSpawns_TryStartRandomBehaviorHopCommand"
    )
    if random_walk is None:
        raise SystemExit("missing random flat-Walk owner")
    random_clean = strip_c_noncode(random_walk)
    for required in (
        "config.targetX = state->movementStagedHopAvoidX[slot]",
        "config.targetY = state->movementStagedHopAvoidY[slot]",
        "config.directionCount = 0x80",
        "lane->wanderStraightChance",
    ):
        if required not in random_clean:
            raise SystemExit(f"random straight-chance policy is missing: {required}")

    random_picker = function_bodies(helper).get(
        "OverworldWildHelper_PickRandomBehaviorHop"
    )
    if random_picker is None:
        raise SystemExit("missing random flat-Walk helper")
    random_picker_clean = strip_c_noncode(random_picker)
    for required in (
        "config->objectX > config->targetX",
        "config->objectX < config->targetX",
        "config->objectY > config->targetY",
        "config->objectY < config->targetY",
        "fallbackIndex = gf_rand() % fallbackCount",
    ):
        if required not in random_picker_clean:
            raise SystemExit("random Walk does not normalize multi-tile history")

    planner = function_bodies(helper).get(
        "OverworldWildHelper_PlanBehaviorHopStep"
    )
    if planner is None:
        raise SystemExit("missing blocked-flee planner owner")
    planner_clean = strip_c_noncode(planner)
    for required in (
        "config->planMode == OW_WILD_HELPER_HOP_PLAN_FLEE",
        "playerX = config->objectX * 2 - config->targetX",
        "playerY = config->objectY * 2 - config->targetY",
        ") <= currentDistance",
        "rejectStraight = (config->directionCount & 0x80) != 0",
        "(gf_rand() % 100) >= config->directions[5]",
        "stepXs[directionIndex] == (s8)config->directions[6]",
        "stepYs[directionIndex] == (s8)config->directions[7]",
        "randomizeDirections = (config->directionCount & 0xA0) != 0",
        "(gf_rand() % randomCandidateCount) == 0",
        "straightFallbackPass = TRUE",
        "goto retry_directions",
    ):
        if required not in planner_clean:
            raise SystemExit(f"blocked-flee planner loses its distance rule: {required}")

    direction_builder = function_bodies(helper).get(
        "OverworldWildHelper_BuildHopPlanDirections"
    )
    if direction_builder is None or "(config->directionCount & 0x0F)" not in \
            strip_c_noncode(direction_builder):
        raise SystemExit("directed straight metadata can leak into direction count")


def main() -> int:
    catalog = json.loads(
        (REPO / "data/overworld_behavior_profiles.json").read_text()
    )
    profile_by_id = {profile["id"]: profile for profile in catalog["profiles"]}
    for profile_id in ("default-active", "default-tired"):
        if profile_by_id[profile_id]["fields"]:
            raise SystemExit(f"{profile_id} must inherit every behavior field")

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
    application_indexes = {
        application["id"]: index
        for index, application in enumerate(catalog["applications"])
    }
    expected = {
        "chillSpeed": 5,
        "walkTimeVariance": 5,
        "chillAction": 1,
        "hopAllowNonCardinal": 2,
        "hopMinDistance": 1,
        "hopMaxDistance": 1,
        "hopPause": 0,
        "ramAccelerationSteps": 8,
        "chainMovementVariance": 6,
        "activeProfile": application_indexes["apply-default-active"],
        "tiredProfile": application_indexes["apply-default-tired"],
        "chainPauseAction": 5,
        "chainPauseActionChance": 60,
        "avoidPreviousTile": 1,
        "wanderStraightChance": 0,
        "walkOptions": 0x60,
        "walkPause": 0,
        "tilesBeforeTurnSkid": 0,
        "chainRepositionJumpCount": 4,
        "chainRepositionSpeed": 2,
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
    rattata = next(
        item
        for item in overview["assignments"]
        if item["species"]["symbol"] == "SPECIES_RATTATA"
    )
    default_terrain = macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0)
    normal_results = profile_viewer.resolve_native_requests(
        [
            {
                "species": assignment["species"]["value"],
                "level": 1,
                "terrain": default_terrain,
                "shiny": 0,
                "groupFlags": 0,
                "forcedOverrideMask": 0,
                "behaviorClass": "auto",
            }
            for assignment in (ledyba, rattata)
        ]
    )
    resolved_ledyba = profile_viewer.decode_native_resolved_profile(
        macros,
        normal_results[0]["profileHex"],
    )
    for lane_name, lane in (
        ("Owner", resolved_ledyba),
        ("Active", resolved_ledyba["_activeProfileData"]),
        ("Tired", resolved_ledyba["_tiredProfileData"]),
    ):
        if profile_viewer.numeric(lane["chillState"]) != macros[
            "OW_WILD_BEHAVIOR_KIND_WANDER"
        ]:
            raise SystemExit(
                f"Flying insect {lane_name} lane is not random wander movement"
            )
        if profile_viewer.numeric(lane["chillTarget"]) != macros[
            "OW_WILD_BEHAVIOR_TARGET_NONE"
        ]:
            raise SystemExit(
                f"Flying insect {lane_name} lane still has a directed target"
            )
    resolved_rattata = profile_viewer.decode_native_resolved_profile(
        macros,
        normal_results[1]["profileHex"],
    )
    if profile_viewer.numeric(resolved_rattata["walkOptions"]) & 0x20:
        raise SystemExit("Flying insect Walk policy leaked into Rattata")

    follower_mask = 1 << (int(follower_entry["order"]) - 1)
    forced_results = profile_viewer.resolve_native_requests(
        [
            {
                "species": assignment["species"]["value"],
                "level": 1,
                "terrain": default_terrain,
                "shiny": 0,
                "groupFlags": 0,
                "forcedOverrideMask": follower_mask,
                "behaviorClass": "auto",
            }
            for assignment in (ledyba, rattata)
        ]
    )
    resolved_ledyba_follower = profile_viewer.decode_native_resolved_profile(
        macros,
        forced_results[0]["profileHex"],
    )
    for lane_name, lane in (
        ("Chill", resolved_ledyba_follower),
        ("Active", resolved_ledyba_follower["_activeProfileData"]),
        ("Tired", resolved_ledyba_follower["_tiredProfileData"]),
    ):
        if profile_viewer.numeric(lane["chillSpeed"]) != 5:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane does not start at 5 frames"
            )
        if profile_viewer.numeric(lane["walkTimeVariance"]) != 5:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane does not keep 5-frame variance"
            )
        if profile_viewer.numeric(lane["maxWalkSpeed"]) != 2:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane does not keep its 2-frame fastest time"
            )
        if not profile_viewer.numeric(lane["walkOptions"]) & 0x20:
            raise SystemExit(
                f"Flying insect follower {lane_name} lane loses Disable acceleration"
            )
    resolved_rattata_follower = profile_viewer.decode_native_resolved_profile(
        macros,
        forced_results[1]["profileHex"],
    )
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
        / "src/overworld_wild_movement.c"
    ).read_text()
    walk_module = (
        REPO
        / "src/pokemon_move_history_overlay/overworld_walk_module.c"
    ).read_text()
    hop_trajectory = spawns
    runtime_sources = spawns + walk_runtime + face_player_runtime
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
    if "call->chainTicks = call->lane->chainRepositionSpeed;" not in walk_runtime:
        raise SystemExit("shared flat Reposition policy does not use exact frame timing")
    if "startIndex = gf_rand();" not in hop_trajectory \
            or "directionIndex = (startIndex + attempt) & 7;" not in hop_trajectory \
            or "startIndex = gf_rand() & 3;" in hop_trajectory:
        raise SystemExit("Reposition direction search does not randomize all eight directions")
    if "OverworldWalk_AccelerateTime(" not in walk_runtime \
            or "OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION" not in walk_runtime:
        raise SystemExit("wild Walk completion does not use exact-frame acceleration")
    if "reduceWalk(&call)" not in mount \
            or "OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY" not in mount:
        raise SystemExit("mounted Walk does not use the shared acceleration reducer")
    reposition_blocks = re.findall(
        r"if \(chainReposition\s*&&\s*!repositionUsesArc\) \{(.*?)\n\s*\}",
        spawns,
        re.DOTALL,
    )
    reposition_timing = next(
        (
            block
            for block in reposition_blocks
            if "frameCount = policy.chainPauseTicks;" in block
        ),
        None,
    )
    if reposition_timing is None:
        raise SystemExit("flat Reposition does not use its authored total duration")
    if "frameCount *= distance;" in reposition_timing:
        raise SystemExit("flat Reposition still multiplies total duration by distance")
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
    for required in ("straightX", "fallbackCount", "candidateCount"):
        if required not in helper:
            raise SystemExit(f"flat-Walk direction policy is missing: {required}")
    face_player_body = re.search(
        r"OverworldWildSpawns_ApplyFacePlayerFacing\s*\([^)]*\)\s*"
        r"\{(?P<body>.*?)\n\}",
        face_player_runtime,
        re.DOTALL,
    )
    if face_player_body is None or not all(
        value in face_player_body.group("body")
        for value in (
            "object = state->spawns[slot].object;",
            "if (!emotePlayHopSound)",
            "fieldSystem = state->movementFieldSystem;",
            "playerObject = fieldSystem->playerAvatar->mapObject;",
            "if (playerObject == NULL)",
            "dx = playerObject->xCurr - object->xCurr;",
            "dy = playerObject->yCurr - object->yCurr;",
            "direction = dx >= dy ? horizontal : vertical;",
            "object->curFacing = direction;",
        )
    ):
        raise SystemExit("canonical face-player readiness or tie behavior is missing")
    if "Walk_ApplyFacePlayerFacing" in walk_module:
        raise SystemExit("duplicate Walk-overlay face-player owner is present")
    verify_face_player_call_gating(spawns)
    verify_walk_start_requires_idle_motion(spawns)
    verify_blocked_flee_has_fallback(spawns, helper)
    if not re.search(
        r"if \(!commandFinished && MapObject_IsSingleMovementActive\(object\)\) \{\s*"
        r"/\*.*?\*/\s*"
        r"OverworldWildSpawns_FinishActivePresentationCommand\(object\);\s*\}",
        spawns,
        re.DOTALL,
    ):
        raise SystemExit(
            "short Walk completion does not finish its native movement shell"
        )

    movement_header = (REPO / "include/overworld_walk_module.h").read_text()
    for retired in (
        "OVERWORLD_WALK_FACE_MODULE_ENTRY_ADDR",
        "OverworldWalkFaceModuleEntry",
        "gOverworldWalkFaceModuleEntry",
    ):
        if retired in movement_header:
            raise SystemExit(f"retired face-player service remains: {retired}")

    walk_linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    if not re.search(
        r"\.\s*=\s*ORIGIN\(rom\)\s*\+\s*0x1000;.*?"
        r"KEEP\(\*\(\.overworld_walk_decelerate_time\)\).*?"
        r"OverworldWalk_DecelerateTime\s*==\s*ORIGIN\(rom\)\s*\+\s*0x1000.*?"
        r"KEEP\(\*\(\.overworld_walk_propose_step\)\).*?"
        r"OverworldWalk_ProposeStep\s*==\s*ORIGIN\(rom\)\s*\+\s*0x105C.*?"
        r"ASSERT\(\.\s*<=\s*ORIGIN\(rom\)\s*\+\s*0x1088,",
        walk_linker,
        re.DOTALL,
    ):
        raise SystemExit("direct Walk deceleration helper slot is not fixed")

    core_object = REPO / "build/overworld_wild_movement.o"
    walk_object = REPO / "build/pokemon_move_history_overlay_linked.o"
    walk_binary = REPO / "build/output_pokemon_move_history_overlay.bin"
    spawns_object = REPO / "build/overworld_wild_spawns_overlay_linked.o"
    if all(
        path.is_file()
        for path in (core_object, walk_object, walk_binary, spawns_object)
    ):
        core_symbols = subprocess.check_output(
            ["arm-none-eabi-nm", "-n", str(core_object)],
            text=True,
        )
        if "OverworldWildSpawns_ApplyFacePlayerFacing" not in core_symbols:
            raise SystemExit("built canonical face-player function is missing")
        walk_symbols = subprocess.check_output(
            ["arm-none-eabi-nm", "-n", str(walk_object)],
            text=True,
        )
        for retired in (
            "gOverworldWalkModuleEntry",
            "gOverworldWalkProfileModuleEntry",
            "gOverworldWalkMountModuleEntry",
            "gOverworldWalkFaceModuleEntry",
            "gOverworldWalkWildPolicyModuleEntry",
            "Walk_ApplyFacePlayerFacing",
        ):
            if retired in walk_symbols:
                raise SystemExit(f"built retired Walk owner is present: {retired}")
        walk_image = walk_binary.read_bytes()
        slot_start = RETIRED_WALK_TABLES_START - WALK_OVERLAY_BASE
        slot_end = RETIRED_WALK_TABLES_END - WALK_OVERLAY_BASE
        for name, address in (
            ("OverworldWalk_DecelerateTime", RETIRED_WALK_TABLES_START),
            ("OverworldWalk_ProposeStep", RETIRED_WALK_TABLES_START + 0x5C),
        ):
            helper = re.search(
                rf"^([0-9A-Fa-f]{{8}})\s+[A-Za-z]\s+{name}$",
                walk_symbols,
                re.MULTILINE,
            )
            if helper is None or int(helper.group(1), 16) != address:
                raise SystemExit(f"built direct Walk helper moved: {name}")
        if walk_image[slot_start:slot_end] != elf_bytes_at(
            walk_object,
            RETIRED_WALK_TABLES_START,
            RETIRED_WALK_TABLES_END - RETIRED_WALK_TABLES_START,
        ):
            raise SystemExit("built direct Walk deceleration helper is not packaged exactly")
        spawns_symbols = subprocess.check_output(
            ["arm-none-eabi-nm", "-n", str(spawns_object)],
            text=True,
        )
        canonical_match = re.search(
            r"^([0-9A-Fa-f]{8})\s+[A-Za-z]\s+"
            r"OverworldWildSpawns_ApplyFacePlayerFacing$",
            spawns_symbols,
            re.MULTILINE,
        )
        if canonical_match is None:
            raise SystemExit("wild-spawns link lacks the canonical face-player symbol")
        canonical_target = int(canonical_match.group(1), 16) & ~1
        spawns_disassembly = subprocess.check_output(
            ["arm-none-eabi-objdump", "-d", str(spawns_object)],
            text=True,
        )
        if re.search(
            rf"\bblx?\s+0*{canonical_target:x}\b",
            spawns_disassembly,
        ) is None:
            raise SystemExit("wild-spawns binary does not call the canonical face-player owner")
        if "__OverworldWildSpawns_ApplyFacePlayerFacing_from_thumb" in spawns_symbols:
            raise SystemExit("Face-player call uses an unexpected veneer")
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
        "OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_MASK",
        "(7u << OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_SHIFT)",
        "OW_WILD_BEHAVIOR_WALK_OPTIONS_RESERVED_MASK 0x00",
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
    if "Horizontal sway" not in viewer or 'part === "sway"' not in viewer:
        raise SystemExit("V2 editor does not expose Walk horizontal sway")

    print("Flying insect flat-Walk profile and movement policy verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
