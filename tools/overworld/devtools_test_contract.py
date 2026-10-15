"""Data-only tests over the shared devtools observation stream.

This module owns no emulator, actions, clocks, files, or proof publication.
Service owns bounded execution and immutable artifacts. Passing this evaluator
is not accepted proof: registered measurement adapters and current build/input
identity are separate controller gates. Private inspector fields are NOT test
oracles. Unsupported measurements remain migration gaps.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re

from tools.overworld.devtools_contract import PREPARED_OPS, validate_command
from tools.overworld.devtools_records import HANDLE_FIELDS, _copy_json, select_current_actor
from tools.overworld.devtools_movement_predicates import (
    MOVEMENT_PREDICATE_KINDS, validate_movement_predicate, check_movement_predicate,
)


ACTOR_PATHS = frozenset({"role", "species", "lane", "motionKind", "motionPhase", "matchedLayerMask", "commitSequence",
    "lastCommandSequence", "active", "presentationAttached", "identityVerified", "inputOwnership",
    "logical.x", "logical.y", "render.x", "render.y", "origin.x", "origin.y", "target.x", "target.y",
    "motionElapsed", "motionDuration", "movementPolicy.speed", "lastDecisionName",
    "lastCancelReasonName", "form", "level"})
PLAYER_PATHS = frozenset({"x", "y", "pos_x", "pos_y", "pos_z", "facing", "movement_cmd",
                          "movement_step"})
EVENTS = frozenset({"ACTOR_ATTACHED", "ACTOR_DETACHED", "CONTROL_REBOUND", "PROFILE_RESOLVED",
    "LANE_CHANGED", "INTENT_CREATED", "CANDIDATE_REJECTED", "PLAN_ACCEPTED", "MOTION_STARTED",
    "STREAM_WAITING", "STREAM_ADVANCED", "PATH_ADVANCED", "LOGICAL_COMMIT", "WORLD_EFFECT",
    "PRESENTATION_SYNCED", "MOTION_FINISHED", "MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND",
    "CONTROL_RETURNED", "MOUNT_PRESENTATION_POSITION", "MOUNT_PRESENTATION_STATE",
    "CONDITION_EVALUATED", "CONDITION_TIMERS", "CONDITION_TARGET",
    "CONDITIONAL_RESOLVED"})
OPERATORS = frozenset({"eq", "ne", "gte", "lte"})
ROLES = frozenset({"WILD", "FOLLOWER", "MOUNTED", "SCRIPTED"})
MODES = frozenset({"normal", "prepared", "observer-control"})
POOL_MEASUREMENTS = frozenset({"pool-spawn-v1", "pool-spawn-surface-v1"})
HEIGHT_CONTROL = "live-spawn-height-control-v1"
ROUTE_CONTROL = "live-route-control-v1"
RESOLVER_PARITY = "packaged-resolver-parity-v1"
CONDITION_SERVICE = "packaged-condition-service-v1"
ACTOR_INSPECT = "actor-inspect-handle-v1"
EMOTE_THREE = "emote-three-slots-v1"
PLAYER_HEALTH_INITIAL = "player-health-initial-state-v1"
POKEMON_COMBAT = "pokemon-combat-v1"
POKEMON_SKID_HIT = "pokemon-skid-hit-v1"
APPEARANCE_KINDS = frozenset({"pokemon-damage-palette-v1", "pokemon-cooldown-palette-v1", "pokemon-ambush-cooldown-palette-v1"})
PLAYER_HEALTH_RAM_REST = "player-health-ram-rest-v1"
PLAYER_HEALTH_RAM_LOW_SPEED = "player-health-ram-low-speed-v1"
PLAYER_HEALTH_THROW = "player-health-throw-contact-v1"
PLAYER_HEALTH_HOP = "player-health-hop-contact-v1"
PLAYER_HEALTH_AMBUSH_JUMP = "player-health-ambush-jump-v1"
PLAYER_HEALTH_RUNNING_HIT = "player-health-running-hit-v1"
PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT = "player-health-mounted-ambush-height-v1"
WILD_THROW_MOVING = "wild-throw-moving-candidate-v1"
THROW_COMPETITION = "throw-cargo-competition-v1"
THROW_RETARGET = "throw-cargo-retarget-v1"
THROW_MUTUAL_PICKUP = "throw-mutual-pickup-v1"
FOLLOWER_THROW = "follower-throw-moving-cargo-v1"
FOLLOWER_THROW_NON45 = "follower-throw-away-non45-v1"
FOLLOWER_APPROACH = "follower-throw-approach-cargo-v1"
DAMAGE_FOLLOWER = "follower-throw-player-damage-v1"
FOLLOWER_PRIORITY = "follower-throw-query-priority-v1"
WILD_THROW_SOAK = "wild-throw-ground-lock-soak-v1"
THROW_CARGO_FLEE = "throw-cargo-flee-v1"
BABY_FEAR_KINDS = frozenset({"baby-wild-player-fear-v1", "baby-wild-pokemon-fear-v1", "baby-follower-safety-v1", "baby-follower-damaged-v1", "wild-damaged-flee-v1", "baby-wild-igglybuff-cry-v1"})
PLAYFUL_HOPS = "playful-in-place-hop-v1"
STOMP_SLAM = "stomp-slam-player-contact-v1"
STOMP_SLAM_MOUNTED = "stomp-slam-mounted-player-contact-v1"
RATTATA_LEDGE = "mounted-rattata-walking-ledge-v1"
HELD_THROW_SEARCH = "held-throw-search-v1"
CROSS_HEIGHT_KINDS = frozenset({"follower-throw-target-above-v1", "follower-throw-target-below-v1"})
TARGET_ACCESS_KINDS = frozenset({"follower-target-access-signpost-v1", "follower-target-access-ground-v1"})
DISTANCE_KINDS = frozenset({"distance-despawn-route29-v1", "distance-despawn-cherrygrove-v1"})
PLAYER_HEALTH_MOVING_KINDS = frozenset({"player-health-moving-heal-on-foot-v1", "player-health-moving-heal-mounted-v1"})
PLAYER_HEALTH_MOUNTED_THROW = "player-health-mounted-throw-v1"
PLAYER_HEALTH_BAR = "player-health-bar-v1"
PLAYER_HEALTH_RAM_WARNING = "player-health-ram-warning-v1"
PLAYER_HEALTH_SAVE_RELOAD = "player-health-save-reload-v1"
PLAYER_HEALTH_ZERO_LOAD = "player-health-zero-load-v1"
CHAIN_RETRY = "chain-retry-v1"
ACCELERATION = "acceleration-parity-v1"
WALK_POLICY_CONTROL = "live-walk-policy-control-v1"
MOUNT_PACING = "mounted-frame-pacing-v1"
MOUNT_SPEED_SLEW = "mounted-speed-slew-v1"
MOUNT_CONTROL_STRESS = "mounted-control-stress-v1"
MOUNT_DETACH_FOLLOWER_RESUME = "mount-detach-follower-resume-v1"
MOUNT_POSE_CONTROL = "live-mount-pose-control-v1"
WILD_WALK = "wild-walk-v1"
WILD_LEDGE = "wild-ledge-v1"
WILD_TELEPORT = "wild-teleport-v1"
RUNNER_STOP_SKID = "runner-stop-skid-v1"
RUNNER_TURN_RUNWAY = "runner-turn-runway-v1"
APPEAR_HOP = "appear-hop-timing-v1"
WILD_TRANSITION = "wild-transition-invalidation-v1"
FOLLOWER_TRANSITION = "follower-transition-rebind-v1"
SURFACE_REBIND_ROOF = "wild-roof-rebind-height-v1"
SURFACE_REBIND_SIGN = "wild-signpost-rebind-height-v1"
SURFACE_REBIND_KINDS = frozenset({SURFACE_REBIND_ROOF, SURFACE_REBIND_SIGN})
MOUNTED_STREAMING = "mounted-streaming-path-v1"
MOUNTED_CARDINAL_STREAMING = "mounted-cardinal-streaming-v1"
MOUNTED_WALK_TRANSITION = "mounted-walk-transition-v1"
LAND_SURF = "land-surf-separation-v1"
SPAWN_WORK_BUDGET = "spawn-work-budget-v1"
UNMOUNTED_ZERO_STUTTER = "unmounted-zero-stutter-v1"
SENTRET_THROW = "route30-sentret-throw-pacing-v1"
POPULATION_HEADROOM = "population-headroom-v1"
SPAWN_PRIORITY_KINDS = frozenset({"natural-refill-retry-v1", "natural-water-spawn-v1"})
D1_WARMUP_STEPS = 35


def _d1_warmup_setup():
    """The measured normal-key path; excluded from both D1 claim windows."""
    def settle(action_id, map_id, x, z):
        return {"id": action_id, "op": "wait", "args": {"predicate": {
            "kind": "player-settled-at", "map": map_id, "x": x, "z": z,
            "when": "final"}}, "budget": {
                "maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 8}}
    actions = [settle("warmup-city-start", 67, 564, 392)]
    for name, direction, count, frames, map_id, x, z in (
            ("east", "RIGHT", 1, 16, 67, 565, 392),
            ("south", "DOWN", 7, 40, 67, 565, 398),
            ("east-seam", "RIGHT", 27, 96, 33, 585, 398),
            ("south-start", "DOWN", 35, 48, 33, 585, 406)):
        actions.append({"id": "warmup-" + name, "op": "step", "args": {
            "frames": frames, "keys": [direction, "B"], "until": {
                "kind": "player-step-count", "operator": "eq",
                "value": count, "when": "final"}}, "budget": {
                    "maxSeconds": 30, "maxFrames": frames, "noProgressFrames": 16}})
        actions.append(settle("warmup-" + name + "-settle", map_id, x, z))
    actions.append({"id": "warmup-release", "op": "step", "args": {
        "frames": 16, "keys": []}, "budget": {
            "maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 16}})
    return actions


def _d1_warmup_identity(snapshot, identity=None):
    followers = [a for a in snapshot.get("actors", []) if a.get("active") is True
                 and a.get("role") == "FOLLOWER" and a.get("species") == 56
                 and a.get("identityVerified") is True]
    if (snapshot.get("prepared") is not False
            or snapshot.get("fieldAvailable") is not True
            or snapshot.get("fieldControl", {}).get("taskPointer") != 0
            or len(followers) != 1
            or any(a.get("role") == "MOUNTED" for a in snapshot.get("actors", []))):
        raise ValueError("D1 warm-up lost normal field control or the saved Mankey")
    current = followers[0].get("subjectIdentity")
    party = [p for p in snapshot.get("party", []) if p.get("species") == 56
             and p.get("personality") == current and p.get("identityVerified") is True
             and type(p.get("hp")) is int and p["hp"] > 0]
    if not current or len(party) != 1 or (identity is not None and current != identity):
        raise ValueError("D1 warm-up changed the source Mankey identity")
    return current


def _d1_warmup_initial(snapshot):
    identity = _d1_warmup_identity(snapshot)
    if (snapshot.get("context", {}).get("mapId") != 67
            or [snapshot.get("player", {}).get(k) for k in ("x", "y")] != [564, 392]
            or type(snapshot.get("nativeObservation", {}).get("playerStepCount")) is not int
            or snapshot["nativeObservation"]["playerStepCount"] != 0):
        raise ValueError("D1 warm-up requires the unchanged Cherrygrove start and zero counter")
    return {"identity": identity, "count": 0, "object": None,
            "initialFrame": _int(snapshot.get("frame"), "D1 initial frame", 0, 0xFFFFFFFF)}


def _d1_warmup_observe(state, snapshot, events):
    """Require all35 native admissions; endpoints alone cannot replace this path."""
    _d1_warmup_identity(snapshot, state["identity"])
    for event in events:
        data = event.get("data", {})
        if event.get("kind") != "native-observation" or data.get("observation") != "player-step-admitted":
            continue
        count = state["count"] + 1
        if count == 1:
            direction, origin, target = 3, [564, 392], [565, 392]
        elif count <= 7:
            direction, origin, target = 1, [565, 390 + count], [565, 391 + count]
        elif count <= 27:
            direction, origin, target = 3, [557 + count, 398], [558 + count, 398]
        else:
            direction, origin, target = 1, [585, 370 + count], [585, 371 + count]
        pointer = data.get("objectPointer")
        if (count > D1_WARMUP_STEPS or data.get("setupMode") != "normal"
                or type(data.get("stepIndex")) is not int or data["stepIndex"] != count
                or data.get("direction") != direction
                or data.get("mapId") != (67 if count <= 18 else 33)
                or data.get("origin") != origin or data.get("target") != target
                or [data.get("objectBefore", {}).get(k) for k in ("x", "y")] != origin
                or [data.get("objectAfter", {}).get(k) for k in ("x", "y")] != target
                or type(pointer) is not int or pointer <= 0
                or data.get("returnValue") != pointer
                or (state["object"] is not None and pointer != state["object"])):
            raise ValueError("D1 warm-up native admission differs from the measured route")
        state.update(count=count, object=pointer)
    observation = snapshot.get("nativeObservation", {})
    if (type(observation.get("playerStepCount")) is not int
            or observation["playerStepCount"] != state["count"]
            or observation.get("coverageComplete") is not True
            or observation.get("error") is not None or observation.get("eventsDropped") != 0):
        raise ValueError("D1 warm-up counter lacks its exact native admissions")


def _d1_warmup_arm(state, snapshot, subject):
    _d1_warmup_identity(snapshot, state["identity"])
    if (state["count"] != D1_WARMUP_STEPS
            or snapshot.get("nativeObservation", {}).get("playerStepCount") != D1_WARMUP_STEPS
            or subject.get("subjectIdentity") != state["identity"]
            or snapshot.get("selector", {}).get("physicalPressed") != 0
            or not check_movement_predicate({"kind": "player-settled-at",
                "map": 33, "x": 585, "z": 406}, snapshot)):
        raise ValueError("D1 warm-up did not finish the exact normal35-step route")


def _d1_spawn_remaining_frames(state, snapshot, setup_frames, overall_frames):
    """Charge every dense setup queue once against the same overall frame cap."""
    initial = state.get("initialFrame")
    current = snapshot.get("frame")
    if (type(initial) is not int or type(current) is not int
            or type(setup_frames) is not int or setup_frames < 0
            or type(overall_frames) is not int or overall_frames != 720
            or current - initial != setup_frames
            or not 0 < overall_frames - setup_frames <= overall_frames):
        raise ValueError("D1 setup completed-frame accounting differs")
    return overall_frames - setup_frames


POPULATION_FAST_TRAVEL = "population-fast-travel-v1"
MOUNTED_TELEPORT_MATRIX = "mounted-teleport-matrix-v1"
WARP_GATE = "warp-gate-v1"
WILD_CLEAR_CONTROL = "live-wild-clear-control-v1"
CORNER = "diagonal-corner-v1"
CORNER_CONTROL = "live-corner-control-v1"
CORNER_KINDS = {CORNER, CORNER_CONTROL}
MATRIX = "mounted-frame-matrix-v1"
MATRIX_CONTROL = "live-walk-matrix-control-v1"
MATRIX_KINDS = {MATRIX, MATRIX_CONTROL}
STOMP = "mounted-stomp-v1"
STOMP_CONTROL = "live-stomp-control-v1"
STOMP_KINDS = {STOMP, STOMP_CONTROL}
CRASH = "mounted-crash-v1"
CRASH_CONTROL = "live-crash-control-v1"
CRASH_KINDS = {CRASH, CRASH_CONTROL}
TURN_SKID = "turn-skid-v1"
WILD_BATTLE_HANDOFF = "wild-battle-handoff-v1"
CONDITION_CONTROLLER = "live-condition-controller-v1"
FOLLOWER_STOP = "follower-stop-facing-v1"
RAM_UNTIL_CRASH = "ram-until-crash-v1"
RAM_BEHIND = "ram-behind-entry-v1"
FOLLOWER_RAM = "follower-ram-pokemon-v1"
BASIC_ATTACK = "basic-attack-v1"
RAM_LEDGE = "ram-ledge-continuity-v1"
RAM_BRIEF_NOTICE = "ram-brief-notice-v1"
THROW_NOTICE_WALK_COMMIT = "throw-notice-walk-commit-v1"
FOLLOWER_THROW_HIT_ABORT = "follower-throw-hit-abort-v1"
BLOCKED_NOTICE_HOP = "blocked-notice-hop-v1"
PROFILE_FEATURE_MEASUREMENTS = frozenset({
    "stalker-runtime-v1", "playful-runtime-v1",
    "startled-runtime-v1", "ambush-player-landing-v1",
    "fly-in-runtime-v1", "waddle-runtime-v1",
    "floaty-bounce-hop-pause-v1",
    "held-control-runtime-v1", "blocked-wild-facing-v1",
    FOLLOWER_STOP, RAM_UNTIL_CRASH, RAM_BEHIND, RAM_LEDGE, RAM_BRIEF_NOTICE,
    THROW_NOTICE_WALK_COMMIT, FOLLOWER_THROW_HIT_ABORT,
})
RAW_BOUNDARY_MEASUREMENTS = frozenset({
    WALK_POLICY_CONTROL, MOUNT_PACING, MOUNT_SPEED_SLEW, MOUNT_CONTROL_STRESS, MOUNT_DETACH_FOLLOWER_RESUME,
    MOUNT_POSE_CONTROL,
    WILD_WALK, WILD_LEDGE, WILD_TELEPORT, RUNNER_STOP_SKID, RUNNER_TURN_RUNWAY, MOUNTED_STREAMING,
    MOUNTED_CARDINAL_STREAMING, MOUNTED_WALK_TRANSITION,
    LAND_SURF, SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER,
    POPULATION_FAST_TRAVEL, MOUNTED_TELEPORT_MATRIX,
    WILD_CLEAR_CONTROL, TURN_SKID, WILD_BATTLE_HANDOFF, WARP_GATE,
    CONDITION_CONTROLLER,
    *CORNER_KINDS, *MATRIX_KINDS, *STOMP_KINDS, *CRASH_KINDS,
})
PROFILE_MEASUREMENTS = POOL_MEASUREMENTS | {HEIGHT_CONTROL}
RAW_MEASUREMENTS = frozenset({"unmounted-cadence-v1", "unmounted-game-cadence-v1", "center-entry-exit-v1", "cyndaquil-normal-setup-v1", ROUTE_CONTROL, RESOLVER_PARITY, CONDITION_SERVICE, ACTOR_INSPECT, ACCELERATION, WALK_POLICY_CONTROL, MOUNT_PACING, MOUNT_SPEED_SLEW, MOUNT_CONTROL_STRESS, MOUNT_DETACH_FOLLOWER_RESUME, MOUNT_POSE_CONTROL, WILD_WALK, WILD_LEDGE, WILD_TELEPORT, RUNNER_STOP_SKID, RUNNER_TURN_RUNWAY, WILD_TRANSITION, FOLLOWER_TRANSITION, MOUNTED_STREAMING, MOUNTED_CARDINAL_STREAMING, MOUNTED_WALK_TRANSITION, LAND_SURF, SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER, POPULATION_FAST_TRAVEL, MOUNTED_TELEPORT_MATRIX, WILD_CLEAR_CONTROL, TURN_SKID, WILD_BATTLE_HANDOFF, CONDITION_CONTROLLER, *CORNER_KINDS, *MATRIX_KINDS, *STOMP_KINDS, *CRASH_KINDS})
MEASUREMENTS = frozenset({"ledyba-chain-v1", "live-observer-control-v1", "actor-binding-context-v1",
    HEIGHT_CONTROL, CHAIN_RETRY, MOUNT_CONTROL_STRESS, APPEAR_HOP}) | POOL_MEASUREMENTS | RAW_MEASUREMENTS \
    | PROFILE_FEATURE_MEASUREMENTS
RAW_MEASUREMENTS = RAW_MEASUREMENTS | {THROW_COMPETITION, THROW_RETARGET, THROW_MUTUAL_PICKUP, FOLLOWER_THROW, FOLLOWER_THROW_NON45, FOLLOWER_APPROACH, DAMAGE_FOLLOWER, FOLLOWER_PRIORITY, WARP_GATE, PLAYER_HEALTH_INITIAL, PLAYER_HEALTH_RAM_REST, PLAYER_HEALTH_RAM_LOW_SPEED, PLAYER_HEALTH_THROW, PLAYER_HEALTH_HOP, PLAYER_HEALTH_AMBUSH_JUMP, PLAYER_HEALTH_RUNNING_HIT, PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT, WILD_THROW_MOVING, PLAYER_HEALTH_MOUNTED_THROW, PLAYER_HEALTH_BAR, PLAYER_HEALTH_RAM_WARNING, PLAYER_HEALTH_SAVE_RELOAD, PLAYER_HEALTH_ZERO_LOAD}
MEASUREMENTS = MEASUREMENTS | {THROW_COMPETITION, THROW_RETARGET, THROW_MUTUAL_PICKUP, FOLLOWER_THROW, FOLLOWER_THROW_NON45, FOLLOWER_APPROACH, DAMAGE_FOLLOWER, FOLLOWER_PRIORITY, WARP_GATE, PLAYER_HEALTH_INITIAL, PLAYER_HEALTH_RAM_REST, PLAYER_HEALTH_RAM_LOW_SPEED, PLAYER_HEALTH_THROW, PLAYER_HEALTH_HOP, PLAYER_HEALTH_AMBUSH_JUMP, PLAYER_HEALTH_RUNNING_HIT, PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT, WILD_THROW_MOVING, PLAYER_HEALTH_MOUNTED_THROW, PLAYER_HEALTH_BAR, PLAYER_HEALTH_RAM_WARNING, PLAYER_HEALTH_SAVE_RELOAD, PLAYER_HEALTH_ZERO_LOAD}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | {THROW_CARGO_FLEE, HELD_THROW_SEARCH}
MEASUREMENTS = MEASUREMENTS | {THROW_CARGO_FLEE, HELD_THROW_SEARCH}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | BABY_FEAR_KINDS
MEASUREMENTS = MEASUREMENTS | BABY_FEAR_KINDS
RAW_MEASUREMENTS = RAW_MEASUREMENTS | {PLAYFUL_HOPS, STOMP_SLAM, STOMP_SLAM_MOUNTED, RATTATA_LEDGE}
MEASUREMENTS = MEASUREMENTS | {PLAYFUL_HOPS, STOMP_SLAM, STOMP_SLAM_MOUNTED, RATTATA_LEDGE}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | {WILD_THROW_SOAK}
MEASUREMENTS = MEASUREMENTS | {WILD_THROW_SOAK}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | DISTANCE_KINDS | CROSS_HEIGHT_KINDS
MEASUREMENTS = MEASUREMENTS | DISTANCE_KINDS | CROSS_HEIGHT_KINDS
RAW_MEASUREMENTS = RAW_MEASUREMENTS | TARGET_ACCESS_KINDS
MEASUREMENTS = MEASUREMENTS | TARGET_ACCESS_KINDS
RAW_MEASUREMENTS = RAW_MEASUREMENTS | {POKEMON_COMBAT, POKEMON_SKID_HIT, FOLLOWER_RAM, BASIC_ATTACK}
MEASUREMENTS = MEASUREMENTS | {POKEMON_COMBAT, POKEMON_SKID_HIT, FOLLOWER_RAM, BASIC_ATTACK}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | SURFACE_REBIND_KINDS
MEASUREMENTS = MEASUREMENTS | SURFACE_REBIND_KINDS
RAW_MEASUREMENTS = RAW_MEASUREMENTS | SPAWN_PRIORITY_KINDS | {SENTRET_THROW, POPULATION_HEADROOM}
MEASUREMENTS = MEASUREMENTS | SPAWN_PRIORITY_KINDS | {SENTRET_THROW, POPULATION_HEADROOM}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | APPEARANCE_KINDS
MEASUREMENTS = MEASUREMENTS | APPEARANCE_KINDS
RAW_MEASUREMENTS = RAW_MEASUREMENTS | {EMOTE_THREE}
MEASUREMENTS = MEASUREMENTS | {EMOTE_THREE}
RAW_MEASUREMENTS = RAW_MEASUREMENTS | PLAYER_HEALTH_MOVING_KINDS
MEASUREMENTS = MEASUREMENTS | PLAYER_HEALTH_MOVING_KINDS


def _shape(value, required, optional=(), label="value"):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f"{label} has missing or unknown fields")


def _same_mounted_reader_boundary(before, after):
    """Snapshot commands can expose a retained profile cache, not advance it.

    Dense queue samples omit this cache. Every native clock, watermark, coverage
    flag and error remains exact; profiles do not supply this pacing oracle.
    """
    if any(before.get(k) != after.get(k) for k in (
            "frame", "nativeCycle", "actorFrame", "context", "player", "actors")):
        return False
    return ({k: v for k, v in before.get("nativeObservation", {}).items() if k != "resolvedProfiles"}
            == {k: v for k, v in after.get("nativeObservation", {}).items() if k != "resolvedProfiles"})


def _mounted_input_boundary(before, after, events, subject, expected, first_sample):
    """Keep the already-polled queue at a key edge, without crediting a press.

    Stock main polls before its task queue. A new host mask can therefore reach
    one completed queue too late. Only that first queue may retain the prior
    exact memory mask; all pose, timing and lifecycle checks still consume it.
    """
    held = after["mountPacing"].get("latestCompletedPose", {}).get("input", {}).get("heldKeys")
    if type(held) is int and held == expected:
        return
    previous = before.get("mountPacing", {}).get("latestCompletedPose") or {}
    previous = previous.get("input", {}).get("heldKeys", before.get("selector", {}).get("heldKeys"))
    actor = next((a for a in before.get("actors", []) if a.get("handle") == subject["handle"]), {})
    starts = any(e.get("kind") == "native" and e.get("data", {}).get("actorHandle") == subject["handle"]["value"]
                 and e["data"].get("event") == "MOTION_STARTED" for e in events)
    if not (first_sample and type(held) is int and type(previous) is int
            and held == previous and held != expected and held in (0, 0x10) and not starts
            and ((expected == 0x10 and actor.get("motionPhase") == "IDLE")
                 or (expected == 0 and actor.get("motionKind") == "WALK"
                     and actor.get("motionPhase") != "IDLE"))):
        raise ValueError("mounted pacing live held input differs from its sealed action")


def _wild_spawn_setup(receipt, snapshot, species=19, locomotion=0):
    """Bind this command to its own finalized encounter and actual native site."""
    value = receipt.get("value", {})
    if value.get("species") != species or type(value.get("slot")) is not int or not 0 <= value["slot"] < 6 \
            or type(value.get("personality")) is not int or value["personality"] <= 0:
        raise ValueError("wild spawn lacks its command encounter identity")
    candidates = [e for e in receipt.get("events",[]) if e.get("kind") == "native-observation"
        and e.get("data",{}).get("observation") == "spawn-prepared"
        and e["data"].get("slot") == value["slot"] and e["data"].get("preparedEncounter",{}).get("personality") == value["personality"]]
    if len(candidates) != 1: raise ValueError("wild Walk spawn needs its exact native receipt")
    event = candidates[0]; spawn = event["data"]
    pair = spawn.get("finalization", {}); final = pair.get("receipt", {})
    if pair.get("status") != "matched" or final.get("pairEligible") is not True \
            or spawn.get("returnValue") != 1 or final.get("returnValue") != 1:
        raise ValueError("wild Walk spawn finalization is not matched")
    fields = ("slot","terrain","statePointer","fieldPointer","preparedPointer","worldContext","preparedPrefixHex","preparedEncounter","startup","position")
    if locomotion in (3, 9): fields += ("startupHex",)
    for key in fields:
        if key not in final or final[key] != spawn.get(key): raise ValueError("wild Walk spawn finalized data differs: " + key)
    world = spawn["worldContext"]
    if final.get("returnWorldContext") != world or any(world.get(k) != snapshot["context"].get(k) for k in ("mapId","fieldEpoch","mapGeneration")):
        raise ValueError("wild Walk spawn world differs")
    if type(final.get("sequence")) is not int or type(spawn.get("sequence")) is not int or not 0 < final["sequence"] < spawn["sequence"]:
        raise ValueError("wild Walk spawn finalization order differs")
    raw = bytes.fromhex(spawn["preparedPrefixHex"])
    if len(raw) != 30: raise ValueError("wild Walk spawn raw prefix size differs")
    encounter = dict(personality=int.from_bytes(raw[12:16],"little"),species=int.from_bytes(raw[16:18],"little"),form=raw[18],level=raw[19])
    position = [int.from_bytes(raw[n:n+4],"little",signed=True) for n in (0,4)]
    target = [int.from_bytes(raw[n:n+2],"little",signed=True) for n in (20,22)]
    origin = [int.from_bytes(raw[n:n+2],"little",signed=True) for n in (24,26)]
    expected_startup = dict(target=target,origin=origin,locomotion=raw[28],hopDirection=raw[29],targetBaseY=0)
    if locomotion in (3, 9):
        startup_raw = bytes.fromhex(spawn["startupHex"])
        if len(startup_raw) != 16 or startup_raw[:10] != raw[20:30] or startup_raw[10:12] != bytes(2):
            raise ValueError("wild Move/Fly In exact startup bytes differ")
        expected_startup["targetBaseY"] = int.from_bytes(startup_raw[12:16], "little", signed=True)
    if locomotion == 9:
        dx, dy = target[0] - origin[0], target[1] - origin[1]
        direction = int(origin[1] < target[1]) if dx == 0 else 2 + int(origin[0] < target[0])
        if (dx == 0) == (dy == 0) or max(abs(dx), abs(dy)) > 16 or raw[29] != direction:
            raise ValueError("wild Fly In offscreen origin/direction differs")
    # Move From Off Screen publishes its native start site in both position
    # and startup.origin. This binds setup only; the shared route witness and
    # each full START/END/control return own travel acceptance.
    if locomotion == 4:
        # Ordinary Hop From Off Screen keeps its destination in position and
        # publishes its distinct native airborne origin in the startup receipt.
        dx, dy = target[0] - origin[0], target[1] - origin[1]
        direction = int(origin[1] < target[1]) if dx == 0 else 2 + int(origin[0] < target[0])
        if (dx == 0) == (dy == 0) or max(abs(dx), abs(dy)) != 8 or raw[29] != direction:
            raise ValueError("wild Hop offscreen origin/direction differs")
    if locomotion == 3:
        if position != origin or target == origin or raw[29] != 0:
            raise ValueError("wild Walk spawn identity or own native destination differs")
    elif target != position:
        raise ValueError("wild Walk spawn identity or own native destination differs")
    if encounter != spawn["preparedEncounter"] or encounter["species"] != species or encounter["personality"] != value["personality"] \
            or position != spawn["position"] or (locomotion not in (3, 4, 9) and origin != target) \
            or spawn["startup"] != expected_startup \
            or raw[28] != locomotion:
        raise ValueError("wild Walk spawn identity or own native destination differs")
    public = spawn["publicSubject"]
    selected = select_current_actor(snapshot,public)
    actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
    if actor["handle"]["slot"] != value["slot"] or actor["subjectIdentity"] != encounter["personality"] \
            or any(actor[k] != encounter[k] for k in ("species","form","level")) \
            or [actor["logical" if actor["motionPhase"] == "IDLE" else "origin"][k] for k in ("x","y")] != (origin if locomotion in (4, 9) else position):
        raise ValueError("wild Walk spawned actor is not at its own native destination")
    if locomotion == 9:
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        matches = [a for a in snapshot.get("pokemonCombat", {}).get("targets", [])
                   if a.get("handle") == selected["handle"]]
        if len(matches) != 1:
            raise ValueError("wild Fly In lacks its full current motion owner")
        motion = matches[0].get("motion", {})
        if decode_motion(bytes.fromhex(motion.get("rawHex", ""))) != motion:
            raise ValueError("wild Fly In raw motion differs")
        plan = motion["plan"]
        if actor["motionKind"] != "FLY_IN" or actor["motionPhase"] != motion["phase"] \
                or motion["phase"] != "MOVING" or plan["version"] != 1 or plan["kind"] != 6 \
                or plan["fieldEpoch"] != selected["handle"]["fieldEpoch"] \
                or not actor["reservationId"] or plan["reservationId"] != actor["reservationId"] \
                or plan["origin"] != origin or plan["target"] != target \
                or plan["facing"] != raw[29] or plan["direction"] != raw[29] \
                or plan["targetBaseY"] != expected_startup["targetBaseY"] \
                or plan["startBaseY"] != plan["targetBaseY"] + 6 * 65536 \
                or plan["duration"] != 144 or actor["motionDuration"] != 144 \
                or actor["motionElapsed"] != motion["elapsed"] or not 0 <= motion["elapsed"] < 144 \
                or plan["distance"] != 16 or plan["commitPolicy"] != 2 or plan["flags"] != 0 \
                or [actor["logical"][k] for k in ("x","y")] != origin \
                or [actor["target"][k] for k in ("x","y")] != target:
            raise ValueError("wild Fly In accepted native plan differs from its startup")
    return dict(subject=selected, commandValue=deepcopy(value), nativeSpawn=deepcopy(event), destination=position)


def _int(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in {low}..{high}")
    return value


def _valid_requested_raw_rows(rows, requested):
    return len(rows) == requested or (len(rows) > requested
        and all(isinstance(row, tuple) and isinstance(row[0], dict) for row in rows)
        and any(row[0].get("fieldAvailable") is False for row in rows))


def _name(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", value) or ".." in value:
        raise ValueError(f"{label} must be a short identifier, not a path")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label} needs nonempty text of at most 4096 characters")
    return value


def _budget(value, *, overall=False):
    _shape(value, {"maxSeconds", "maxFrames", "noProgressFrames"},
           {"minObservedFrames"} if overall else (), "budget")
    result = deepcopy(value)
    _int(result["maxSeconds"], "maxSeconds", 1, 3600)
    _int(result["maxFrames"], "maxFrames", 1, 65535)
    _int(result["noProgressFrames"], "noProgressFrames", 1, result["maxFrames"])
    if overall:
        result.setdefault("minObservedFrames", 1)
        _int(result["minObservedFrames"], "minObservedFrames", 1, result["maxFrames"])
    return result


def validate_predicate(value, subject_ids):
    """Finite public assertions only. No JSONPath, Python, or private-memory path."""
    if not isinstance(value, dict):
        raise ValueError("predicate must be an object")
    kind = value.get("kind")
    if isinstance(kind, str) and kind in MOVEMENT_PREDICATE_KINDS:
        return validate_movement_predicate(value)
    if kind == "field-task-active":
        _shape(value, {"kind"}, {"when"}, "predicate")
    elif kind == "actor-present":
        _shape(value, {"kind", "subject"}, {"when"}, "predicate")
    elif kind == "acceleration-role-started":
        _shape(value, {"kind", "subject", "value"}, {"when"}, label="acceleration start predicate")
        _int(value["value"], "acceleration starts", 1, 7)
    elif kind == "acceleration-role-complete":
        _shape(value, {"kind", "subject"}, {"when"}, "predicate")
    elif kind == "measurement-complete":
        _shape(value, {"kind", "measurement"}, {"when"}, "predicate")
        if value["measurement"] not in MEASUREMENTS:
            raise ValueError("measurement has no implemented shared evaluator")
    elif kind == "measurement-stage":
        _shape(value, {"kind", "measurement", "stage"}, {"when"}, "predicate")
        stages = {"live-observer-control-v1": ("baseline", "render-detected", "complete"),
                  MOUNT_PACING: ("main-started", "main-complete", "recovery-started", "recovery-complete"),
                  MOUNT_SPEED_SLEW: ("main-started", "main-complete", "gait-settled"),
                  MATRIX: ("case-started", "case-complete", "gate-complete", "gate-released"),
                  MATRIX_CONTROL: ("case-started", "case-complete", "gate-complete", "gate-released"),
                  STOMP: ("case-started", "case-complete"),
                  STOMP_CONTROL: ("case-started", "case-complete"),
                  CORNER: ("blocked", "recovery-started", "recovery-complete"),
                  CORNER_CONTROL: ("blocked", "recovery-started", "recovery-complete"),
                  WILD_CLEAR_CONTROL: ("natural-walk-complete",),
                  WILD_TRANSITION: ("natural-motion-complete",),
                  FOLLOWER_TRANSITION: ("natural-motion-complete",),
                  SURFACE_REBIND_SIGN: ("settled-on-signpost",),
                  MOUNTED_STREAMING: ("two-complete",),
                  MOUNTED_CARDINAL_STREAMING: ("target-reached", "recovered"),
                  MOUNTED_WALK_TRANSITION: ("context-changed", "transition-motion-complete", "recovered"),
                  TURN_SKID: ("acceleration-complete", "recovery-started", "complete"),
                  WILD_BATTLE_HANDOFF: ("motion-started", "motion-complete", "request-complete"),
                  LAND_SURF: ("two-attempts",),
                  SPAWN_WORK_BUDGET: ("complete",),
                  POPULATION_FAST_TRAVEL: ("refilled",),
                  MOUNTED_TELEPORT_MATRIX: ("case-started", "case-complete"),
                  WARP_GATE: ("case-started", "case-complete", "teleports-complete", "walk-started", "arrived"),
                  CONDITION_CONTROLLER: ("stale-target-observed",),
                  "stalker-runtime-v1": ("unseen-motion-complete",),
                  "playful-runtime-v1": ("actor-play-complete",),
                  CHAIN_RETRY: ("baseline", "complete"),
                  ROUTE_CONTROL: ("baseline", "cpu-detected", "player-detected", "complete")}
        stages[PLAYER_HEALTH_ZERO_LOAD] = ("message-ready", "arrival-or-free", "field-free")
        stages[STOMP_SLAM] = ("contact", "finished")
        stages[STOMP_SLAM_MOUNTED] = ("contact", "finished")
        stages[RATTATA_LEDGE] = ("started", "finished")
        stages[PLAYER_HEALTH_HOP] = ("airborne-crossed",)
        stages[PLAYER_HEALTH_AMBUSH_JUMP] = ("airborne-crossed",)
        stages[PLAYER_HEALTH_RUNNING_HIT] = ("running-contact", "knockback-returned")
        stages["pokemon-damage-palette-v1"] = ("two-red-hits", "hits-settled")
        stages["pokemon-cooldown-palette-v1"] = ("attack-started", "attack-ended", "crashed", "blue-used")
        stages["pokemon-ambush-cooldown-palette-v1"] = ("attack-started", "attack-ended", "blue-used")
        for kind in DISTANCE_KINDS: stages[kind] = ("claim-bound", "first-far-sample")
        for kind in CROSS_HEIGHT_KINDS: stages[kind] = ("launched",)
        for kind in TARGET_ACCESS_KINDS: stages[kind] = ("target-settled", "rejected")
        stages[FOLLOWER_THROW] = ("launched", "resumed")
        stages[FOLLOWER_THROW_NON45] = ("launched", "resumed")
        stages[DAMAGE_FOLLOWER] = ("physical-hit", "landed", "resumed")
        stages[FOLLOWER_PRIORITY] = ("source-ready", "landed", "resumed")
        stages[WILD_THROW_SOAK] = ("window-complete",)
        stages[THROW_COMPETITION] = ("far-claimed",)
        stages[THROW_RETARGET] = ("first-pursuit",)
        stages[HELD_THROW_SEARCH] = ("carried", "held201", "launched")
        stages[PLAYER_HEALTH_THROW] = ("launched",)
        stages[PLAYER_HEALTH_MOUNTED_THROW] = ("trigger-bound", "launched")
        for kind in PLAYER_HEALTH_MOVING_KINDS: stages[kind] = ("contact-crossed",)
        stages[POKEMON_COMBAT] = ("landed",)
        stages[POKEMON_SKID_HIT] = ("landed",)
        stages[FOLLOWER_RAM] = ("landed",)
        stages[BASIC_ATTACK] = ("landed",)
        stages[RAM_UNTIL_CRASH] = ("charge-started",)
        stages[RAM_BEHIND] = ("charge-started",)
        stages[RAM_LEDGE] = ("charge-started",)
        stages[RAM_BRIEF_NOTICE] = ("ordinary-moving", "player-on-line", "player-off-line", "charge-started")
        stages[THROW_NOTICE_WALK_COMMIT] = ("ordinary-up-walk",)
        stages[PLAYER_HEALTH_RAM_WARNING] = ("ram-active", "charge-started")
        stages[PLAYER_HEALTH_RAM_LOW_SPEED] = ("ram-active",)
        if value["stage"] not in stages.get(value["measurement"], ()):
            raise ValueError("unsupported observer measurement stage")
    elif kind in ("actor-field", "player-field"):
        _shape(value, {"kind", "path", "operator", "value"} | ({"subject"} if kind == "actor-field" else set()),
               {"when"}, "predicate")
        if value["path"] not in (ACTOR_PATHS if kind == "actor-field" else PLAYER_PATHS):
            raise ValueError("predicate path is not an allowed public observation")
    elif kind == "actor-count":
        _shape(value, {"kind", "subject", "operator", "value"}, {"when", "motionPhase"}, "predicate")
        _int(value["value"], "actor count", 0, 10)
        if "motionPhase" in value and value["motionPhase"] != "IDLE":
            raise ValueError("actor count only supports the explicit IDLE phase filter")
    elif kind == "event-count":
        _shape(value, {"kind", "subject", "event", "operator", "value"}, {"when"}, "predicate")
        if value["event"] not in EVENTS:
            raise ValueError("predicate event is not in the public trace ABI")
        _int(value["value"], "event count", 0, 1000000)
    elif kind == "frame-count":
        _shape(value, {"kind", "operator", "value"}, {"when"}, "predicate")
        _int(value["value"], "frame count", 0, 120000)
    else:
        raise ValueError("unsupported predicate kind")
    if "subject" in value and value["subject"] not in subject_ids:
        raise ValueError("predicate names an undeclared subject")
    if "operator" in value:
        if value["operator"] not in OPERATORS:
            raise ValueError("unsupported predicate operator")
        if type(value["value"]) not in (bool, int, str):
            raise ValueError("predicate value must be a literal bool, integer, or string")
        if value["operator"] in ("gte", "lte") and type(value["value"]) is not int:
            raise ValueError("ordered comparison needs an integer literal")
    if value.get("when", "final") not in ("always", "final"):
        raise ValueError("predicate when must be always or final")
    return {**deepcopy(value), "when": value.get("when", "final")}


def validate_test(value):
    value = _copy_json(value, 262144)
    _shape(value, {"schemaVersion", "id", "title", "mode", "fixture", "expectationSource", "requirements",
                   "budgets", "subjects", "setup", "actions", "assertions"},
           {"measurements", "spawnObserverCost", "diagnosticContinueHostHitches"}, label="test")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise ValueError("unsupported test schemaVersion")
    _name(value["id"], "test id"); _text(value["title"], "test title")
    _text(value["expectationSource"], "expectationSource")
    if value["mode"] not in MODES:
        raise ValueError("invalid test mode")
    _shape(value["fixture"], {"rom", "save"}, label="fixture")
    for key, endings in (("rom", (".nds",)), ("save", (".sav", ".dsv"))):
        path = _text(value["fixture"][key], "fixture " + key)
        if path.startswith("/") or ".." in path.split("/") or not path.lower().endswith(endings):
            raise ValueError("fixture must name a repository-relative ROM/save")
    requirements = value["requirements"]
    if not isinstance(requirements, list) or len(requirements) > 256 \
            or any(not isinstance(item, str) for item in requirements) or len(set(requirements)) != len(requirements):
        raise ValueError("requirements must be a bounded list of distinct measurement IDs")
    for item in requirements: _text(item, "requirement")
    if "diagnosticContinueHostHitches" in value:
        if value["diagnosticContinueHostHitches"] is not True or requirements or value["mode"] != "prepared" \
                or [m.get("kind") for m in value.get("measurements", []) if isinstance(m, dict)] != ["unmounted-cadence-v1"]:
            raise ValueError("host-hitch continuation is diagnostic-only prepared cadence with no requirements")
    if "spawnObserverCost" in value:
        cost_mode = value["spawnObserverCost"]
        if cost_mode not in ("baseline", "omit-spawn-details") or requirements \
                or value["mode"] not in ("normal", "prepared") \
                or (cost_mode == "omit-spawn-details" and value["mode"] != "prepared"):
            raise ValueError("spawn observer cost is diagnostic-only work with no requirements; omission requires prepared mode")
    value["budgets"] = _budget(value["budgets"], overall=True)
    resolver_case = value.get("measurements") == [{"kind": RESOLVER_PARITY}]
    condition_case = value.get("measurements") == [{"kind": CONDITION_SERVICE}]
    emote_case = value.get("measurements") == [{"kind": EMOTE_THREE, "subject": "a"}]
    inspect_case = value.get("measurements") == [{"kind": ACTOR_INSPECT, "subject": "mankey"}]
    health_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_INITIAL}]
    damage_follower_case = value.get("measurements") == [{"kind": DAMAGE_FOLLOWER, "subject": "mankey"}]
    wild_throw_soak_case = value.get("measurements") == [{"kind": WILD_THROW_SOAK, "subject": "geodude-a"}]
    pokemon_combat_case = value.get("measurements") in ([{"kind": POKEMON_COMBAT, "subject": "cyndaquil"}],
                                                       [{"kind": POKEMON_SKID_HIT, "subject": "stantler"}],
                                                       [{"kind": FOLLOWER_RAM, "subject": "onix"}],
                                                       [{"kind": BASIC_ATTACK, "subject": "snorlax"}])
    appearance_damage_case = value.get("measurements") == [{"kind":"pokemon-damage-palette-v1","subject":"cyndaquil"}]
    health_moving_case = value.get("measurements") in ([{"kind":kind,"subject":"weepinbell"}] for kind in PLAYER_HEALTH_MOVING_KINDS)
    health_ram_rest_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_RAM_REST, "subject": "onix"}]
    health_ram_low_speed_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_RAM_LOW_SPEED, "subject": "onix"}]
    health_throw_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_THROW,
                                                         "subjects": ["weepinbell", "geodude"]}]
    health_hop_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_HOP,
                                                      "subject": "mankey"}]
    health_ambush_case = value.get("measurements") in ([{"kind": kind, "subject": "weepinbell"}]
                for kind in (PLAYER_HEALTH_AMBUSH_JUMP, PLAYER_HEALTH_RUNNING_HIT))
    health_mounted_ambush_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT,
                                                                  "subjects": ["cyndaquil", "weepinbell"]}]
    health_mounted_throw_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_MOUNTED_THROW,
                                                                 "subjects": ["cyndaquil", "bellsprout", "geodude"]}]
    health_bar_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_BAR,
                                                       "subject": "onix"}]
    health_ram_warning_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_RAM_WARNING,
                                                               "subject": "onix"}]
    health_save_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_SAVE_RELOAD,
                                                        "subject": "onix"}]
    health_zero_case = value.get("measurements") == [{"kind": PLAYER_HEALTH_ZERO_LOAD}]
    stomp_slam_case = value.get("measurements") in ([{"kind": STOMP_SLAM, "subject": "snorlax"}],
        [{"kind": STOMP_SLAM_MOUNTED, "subject": "snorlax"}])
    minimum_subjects = 1 if requirements and not (resolver_case or condition_case or health_case or health_zero_case) else 0
    if not isinstance(value["subjects"], list) or not minimum_subjects <= len(value["subjects"]) <= 10:
        raise ValueError("test needs 1..10 declared subjects when it claims requirements; tools-only tests may use none")
    subjects = set()
    for subject in value["subjects"]:
        _shape(subject, {"id", "species", "role", "acquire"}, label="subject")
        _name(subject["id"], "subject id")
        if subject["id"] in subjects: raise ValueError("duplicate subject id")
        subjects.add(subject["id"])
        _int(subject["species"], "species", 1, 1075)
        if subject["role"] not in ROLES or subject["acquire"] not in ("existing", "spawn"):
            raise ValueError("invalid subject role/acquisition")
    action_ids = set()
    for phase in ("setup", "actions"):
        if not isinstance(value[phase], list) or len(value[phase]) > 2000 or (phase == "actions" and not value[phase]):
            raise ValueError("test actions must be bounded and observation actions nonempty")
        for action in value[phase]:
            _shape(action, {"id", "op", "args", "budget"}, {"skipIf"}, label="action")
            _name(action["id"], "action id")
            if action["id"] in action_ids: raise ValueError("duplicate action id")
            action_ids.add(action["id"])
            action["budget"] = _budget(action["budget"])
            if action["budget"]["maxFrames"] > value["budgets"]["maxFrames"] \
                    or action["budget"]["maxSeconds"] > value["budgets"]["maxSeconds"]:
                raise ValueError("action budget exceeds the overall budget")
            op = action["op"]
            if "skipIf" in action:
                if phase != "setup" or op not in ("step", "wait"):
                    raise ValueError("conditional skipping is limited to normal setup input and waits")
                action["skipIf"] = validate_predicate(action["skipIf"], subjects)
            if op in ("crash.arm", "crash.close", "crash.calibrate"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="Crash args")
                if phase != "actions" or value["mode"] not in ("prepared", "observer-control") or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("Crash command requires its bound prepared window")
                if op.endswith("calibrate") and value["mode"] != "observer-control":
                    raise ValueError("Crash calibration requires a separate observer-control test")
            elif op in ("stomp.arm", "stomp.close", "stomp.calibrate"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="stomp args")
                if phase != "actions" or value["mode"] not in ("prepared", "observer-control") or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("stomp command requires its bound prepared window")
                if op.endswith("calibrate") and value["mode"] != "observer-control":
                    raise ValueError("stomp calibration requires a separate observer-control test")
            elif op in ("walk-matrix.arm", "walk-matrix.close", "walk-matrix.calibrate"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="matrix args")
                if phase != "actions" or value["mode"] not in ("prepared", "observer-control") or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("matrix command requires its bound prepared window")
                if op.endswith("calibrate") and value["mode"] != "observer-control":
                    raise ValueError("matrix calibration requires a separate observer-control test")
            elif op in ("walk-corner.probe", "walk-corner.arm", "walk-corner.recovery", "walk-corner.close", "walk-corner.calibrate"):
                needs_subject = op in ("walk-corner.probe", "walk-corner.arm")
                _shape(action["args"], {"subject"} if needs_subject else set(), label="corner args")
                if value["mode"] not in ("prepared", "observer-control") or phase != ("setup" if op.endswith("probe") else "actions") \
                        or (needs_subject and action["args"]["subject"] not in subjects):
                    raise ValueError("corner command requires its bound prepared window")
                if op.endswith("calibrate") and value["mode"] != "observer-control":
                    raise ValueError("corner calibration requires a separate observer-control test")
            elif op in ("wild-walk.arm", "wild-walk.close", "wild-walk.calibrate"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="wild Walk args")
                if phase != "actions" or value["mode"] not in ("prepared","observer-control") or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("wild Walk reader requires its bound prepared window")
            elif op in ("wild-ledge.arm", "wild-ledge.close"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="wild ledge args")
                if phase != "actions" or value["mode"] != "prepared" \
                        or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("wild ledge reader requires its bound prepared window")
            elif op in ("condition-controller.fixture", "condition-controller.arm",
                        "condition-controller.close"):
                needs_subject = op.endswith("arm")
                _shape(action["args"], {"subject"} if needs_subject else set(),
                       label="condition controller args")
                valid_phase = (op == "condition-controller.fixture" and phase == "setup"
                               or op != "condition-controller.fixture" and phase == "actions")
                if (not valid_phase or value["mode"] != "prepared"
                        or needs_subject and action["args"]["subject"] not in subjects):
                    raise ValueError(
                        "condition controller requires its bound prepared window")
            elif op in ("mount-pacing.arm", "mount-pacing.recovery", "mount-pacing.close", "mount-pacing.calibrate"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="mounted pacing args")
                if phase != "actions" or value["mode"] not in ("prepared", "observer-control") or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("mounted pacing requires a prepared bound observation window")
            elif op in ("walk-policy-control.arm", "walk-policy-control.close"):
                _shape(action["args"], {"subject"} if op.endswith("arm") else set(), label="Walk reader control args")
                if phase != "actions" or value["mode"] != "observer-control" or (op.endswith("arm") and action["args"]["subject"] not in subjects):
                    raise ValueError("Walk reader control requires its observer-control action")
            elif op == "mount-walk.configure":
                _shape(action["args"], {"subject", "directionMode"}, {"travelTime", "stompTime", "turning", "crashSound", "fastestTime", "timeToFullSpeed", "timeVariance"}, label="Mount Walk setup args")
                if (phase != "setup" and not any(m.get("kind") in (MATRIX_KINDS | STOMP_KINDS) for m in value.get("measurements", []))) or value["mode"] not in ("prepared", "observer-control") \
                        or action["args"]["subject"] not in subjects \
                        or next(s["role"] for s in value["subjects"]
                                if s["id"] == action["args"]["subject"]) != "MOUNTED":
                    raise ValueError("Mount Walk setup requires a declared Mounted subject in prepared setup")
                _int(action["args"]["directionMode"], "Mount Walk directions", 0, 2)
                if "travelTime" in action["args"]:
                    _int(action["args"]["travelTime"], "Mount Walk travel time", 1, 32)
                if "timeVariance" in action["args"]:
                    _int(action["args"]["timeVariance"], "Mount Walk time variance", 0, 32)
                args = action["args"]
                if ("fastestTime" in args) != ("timeToFullSpeed" in args):
                    raise ValueError("fastestTime and timeToFullSpeed must be supplied together")
                if "fastestTime" in args:
                    _int(args["fastestTime"], "Mount Walk fastest time", 1, 32)
                    _int(args["timeToFullSpeed"], "Mount Walk time to full speed", 1, 255)
                    if "travelTime" not in args or args["fastestTime"] > args["travelTime"]:
                        raise ValueError("Linear acceleration requires travelTime and fastestTime <= travelTime")
                if "stompTime" in action["args"]:
                    _int(action["args"]["stompTime"], "Mount Walk stomp threshold", 0, 32)
                for key, allowed in (("turning", ("free", "locked")), ("crashSound", ("none", "wall-hit"))):
                    if key in action["args"] and action["args"][key] not in allowed:
                        raise ValueError("Mount Walk " + key + " differs")
            elif op == "mount-teleport.restore":
                _shape(action["args"], {"subject"}, label="Mount Teleport restore args")
                if phase != "actions" or value["mode"] != "prepared" or not any(m.get("kind") == WARP_GATE for m in value.get("measurements", [])) or action["args"]["subject"] not in subjects:
                    raise ValueError("Mount Teleport restore requires its prepared warp gate")
            elif op == "mount-teleport.configure":
                _shape(action["args"], {"subject", "locomotion", "teleportTime", "teleportPause"},
                       label="Mount Teleport setup args")
                if phase != "actions" or value["mode"] != "prepared" \
                        or not any(m.get("kind") in (MOUNTED_TELEPORT_MATRIX, WARP_GATE)
                                   for m in value.get("measurements", [])) \
                        or action["args"]["subject"] not in subjects \
                        or next(s["role"] for s in value["subjects"]
                                if s["id"] == action["args"]["subject"]) != "MOUNTED":
                    raise ValueError("Mount Teleport setup requires its declared prepared matrix")
                _int(action["args"]["locomotion"], "Mount Teleport locomotion", 6, 11)
                if action["args"]["locomotion"] not in (6, 9, 10, 11):
                    raise ValueError("Mount Teleport locomotion differs")
                _int(action["args"]["teleportTime"], "Mount Teleport time", 1, 32)
                _int(action["args"]["teleportPause"], "Mount Teleport pause", 0, 255)
            elif op == "walk-policy.reset":
                _shape(action["args"], {"subject"}, label="Walk reset args")
                if phase != "setup" or value["mode"] != "prepared" \
                        or action["args"]["subject"] not in subjects \
                        or next(s["role"] for s in value["subjects"]
                                if s["id"] == action["args"]["subject"]) not in ("WILD", "MOUNTED"):
                    raise ValueError("Walk reset requires a declared Wild/Mounted subject in prepared setup")
            elif op == "walk-intent.arm":
                _shape(action["args"], {"subject", "direction", "maxFrames"}, label="Walk intent args")
                if phase != "setup" or value["mode"] != "prepared" or action["args"]["subject"] not in subjects:
                    raise ValueError("Walk intent requires a prepared declared setup subject")
                _int(action["args"]["direction"], "Walk intent direction", 0, 7)
                _int(action["args"]["maxFrames"], "Walk intent frames", 1, 600)
            elif op == "walk-intent.close":
                _shape(action["args"], set(), label="Walk intent close args")
                if phase != "setup" or value["mode"] != "prepared":
                    raise ValueError("Walk intent close requires prepared setup")
            elif op == "obstacle-intent.arm":
                _shape(action["args"], {"subject", "maxFrames"},
                       label="obstacle intent args")
                if (phase != "actions" or value["mode"] != "prepared"
                        or action["args"]["subject"] not in subjects):
                    raise ValueError("Obstacle intent requires a prepared bound subject")
                _int(action["args"]["maxFrames"], "obstacle intent frames", 1, 120)
            elif op == "obstacle-intent.close":
                _shape(action["args"], set(), label="obstacle intent close args")
                if phase != "actions" or value["mode"] != "prepared":
                    raise ValueError("Obstacle intent close requires prepared observation")
            elif op in ("emote-three.arm", "emote-three.close"):
                _shape(action["args"], set("abcd") if op.endswith("arm") else set(), label="emote burst args")
                if not emote_case or phase != "actions" or value["mode"] != "prepared" \
                        or op.endswith("arm") and action["args"] != {name:name for name in "abcd"}:
                    raise ValueError("emote burst requires its fixed four prepared subjects")
            elif op == "actor-inspect.probe":
                _shape(action["args"], {"subject"}, label="actor Inspect args")
                if not inspect_case or phase != "actions" or value["mode"] != "prepared" \
                        or action["args"]["subject"] not in subjects:
                    raise ValueError("actor Inspect requires its exact prepared subject measurement")
            elif op == "player-health.observe":
                _shape(action["args"], set(), label="player HP observation args")
                if not (phase == "actions" or health_bar_case and phase == "setup") or not (health_case and value["mode"] == "normal"
                        or health_ram_rest_case and value["mode"] == "prepared"
                        or health_moving_case and value["mode"] == "prepared"
                        or health_ram_low_speed_case and value["mode"] == "prepared"
                        or health_throw_case and value["mode"] == "prepared"
                        or health_hop_case and value["mode"] == "prepared"
                        or health_ambush_case and value["mode"] == "prepared"
                        or stomp_slam_case and value["mode"] == "prepared"
                        or damage_follower_case and value["mode"] == "prepared"
                        or wild_throw_soak_case and value["mode"] == "prepared"
                        or health_mounted_ambush_case and value["mode"] == "prepared"
                        or health_mounted_throw_case and value["mode"] == "prepared"
                        or pokemon_combat_case and value["mode"] == "prepared"
                        or health_bar_case and value["mode"] == "prepared"
                        or health_ram_warning_case and value["mode"] == "prepared"
                        or health_save_case and value["mode"] == "prepared"
                        or health_zero_case and value["mode"] == "normal"
                        or any(a.get("op") == "save.reload" for a in value["actions"])
                            and not value["subjects"] and not value["measurements"]):
                    raise ValueError("player HP observation requires its exact HP measurement")
            elif op == "save.reload":
                _shape(action["args"], set(), label="save reload args")
                if (phase != "actions" or not health_save_case
                        and (value["subjects"] or value["measurements"])
                        or sum(a.get("op") == "save.reload" for a in value["actions"]) != 1):
                    raise ValueError("save reload needs one subjectless diagnostic action")
                earlier = value["setup"] + value["actions"][:value["actions"].index(action)]
                if (not any(a.get("op") == "step" and "A" in a.get("args", {}).get("keys", [])
                            for a in earlier)
                        or not any(a.get("op") == "step" and set(a.get("args", {}).get("keys", []))
                                   & {"X", "START"} for a in earlier)):
                    raise ValueError("save reload needs prior normal menu and confirm input")
            elif op == "save.wait":
                _shape(action["args"], {"maxNativeCycles"}, label="stock Save wait args")
                if (not health_save_case or phase != "actions"
                        or action["args"] != {"maxNativeCycles": 2000}):
                    raise ValueError("stock Save wait needs its exact HP persistence scenario")
            elif op == "appearance-line.prepare":
                _shape(action["args"], {"subject"}, label="current appearance line args")
                onix = (value["id"] == "pokemon-appearance.cooldown-palette" and action["id"] == "approach-current-line"
                        and action["args"] == {"subject":"onix"} and action["budget"] == {"maxFrames":96,"noProgressFrames":96,"maxSeconds":90})
                ambush = (value["id"] == "pokemon-appearance.ambush-cooldown-palette" and action["args"] == {"subject":"weepinbell"}
                        and action["id"] in ("stage-outside-vision","approach-ambush")
                        and action["budget"] == {"maxFrames":32 if action["id"] == "stage-outside-vision" else 40,
                                               "noProgressFrames":32 if action["id"] == "stage-outside-vision" else 40,"maxSeconds":90})
                if phase != "actions" or value["mode"] != "prepared" or not (onix or ambush):
                    raise ValueError("current appearance line requires its exact bounded Blue action")
            elif op in ("held-throw-pocket.prepare", "held-throw-line.prepare"):
                _shape(action["args"], set(), label="held Throw normal input args")
                pocket = op == "held-throw-pocket.prepare"
                if (value["id"] != "wild.throw-held-search" or value["mode"] != "prepared"
                        or phase != ("setup" if pocket else "actions")
                        or action["id"] != ("normal-pocket-exit" if pocket else "open-current-line")
                        or action["budget"] != {"maxFrames":400 if pocket else 64,
                            "noProgressFrames":400 if pocket else 64,"maxSeconds":180 if pocket else 90}):
                    raise ValueError("held Throw requires its exact bounded normal input")
            elif op == "notice-hop.prepare":
                _shape(action["args"], {"subject"}, label="blocked Notice Hop prepare args")
                if phase != "setup" or value["mode"] != "prepared" \
                        or value["id"] != "profile.notice.blocked-hop" \
                        or action["args"] != {"subject": "flabebe"}:
                    raise ValueError("blocked Notice Hop preparation requires its exact setup")
            elif op == "terrain" and any(m["kind"] in DISTANCE_KINDS for m in value.get("measurements", [])):
                from tools.overworld.devtools_distance_despawn_measurement import setup
                kind = value["measurements"][0]["kind"]
                expected = {name:args for name,op,args in setup(kind) if op == "terrain"}
                if phase != "setup" or value["mode"] != "prepared" or expected.get(action["id"]) != action["args"]:
                    raise ValueError("distance fixture terrain differs from exact current setup")
                action["args"] = validate_command(op,action["args"])
            elif op == "terrain" and value["id"] in ("follower.target-access-signpost", "follower.target-access-ground"):
                if (phase != "setup" or value["mode"] != "prepared"
                        or action["id"] != "read-target-terrain"
                        or action["args"] != {"x": 581, "z": 398, "radius": 2}
                        or action["budget"] != {"maxSeconds": 60,
                            "maxFrames": 1, "noProgressFrames": 1}):
                    raise ValueError("target access requires its exact current target terrain read")
                action["args"] = validate_command(op, action["args"])
            elif op == "terrain" and value["id"] == "profile.ram.brief-notice":
                if (phase != "setup" or value["mode"] != "prepared"
                        or action["id"] != "read-current-line-terrain"
                        or action["args"] != {"x": 603, "z": 402, "radius": 3}
                        or action["budget"] != {"maxSeconds": 10,
                            "maxFrames": 1, "noProgressFrames": 1}):
                    raise ValueError("brief Ram requires its exact current line terrain read")
                action["args"] = validate_command(op, action["args"])
            elif op == "terrain":
                from tools.overworld.devtools_wild_surface_rebind_measurement import CONFIG as surface_config
                surface_case = next((c for c in surface_config.values() if c["id"] == value["id"]), None)
                if surface_case is not None:
                    if phase != "setup" or value["mode"] != "prepared" \
                            or action["id"] != "read-actual-target-surface" \
                            or action["args"] != surface_case["terrainArgs"]:
                        raise ValueError("retained surface terrain probe differs from its exact setup")
                    action["args"] = validate_command(op, action["args"])
                elif value["id"] != "world.streaming.stantler-mounted-route" \
                        or phase != "actions" or value["mode"] != "prepared" \
                        or action["id"] not in ("route-terrain", "recovery-terrain"):
                    raise ValueError("terrain probe requires the mounted Stantler route")
                else:
                    _shape(action["args"], {"radius"}, label="mounted route terrain args")
                    action["args"] = validate_command(op, action["args"])
                    if action["args"]["radius"] != (1 if action["id"] == "route-terrain" else 2):
                        raise ValueError("mounted route terrain radius differs")
            elif op in ("main-loop-pacing.arm", "cpu-work.start", "cpu-work.read"):
                headroom_arm = (op == "main-loop-pacing.arm" and value["id"] == "population.route30.saturated-headroom"
                                and value.get("measurements") == [{"kind": POPULATION_HEADROOM, "subject": "mankey"}])
                if not headroom_arm and (value["id"] != "world.route30.sentret-throw-pacing"
                                         or value.get("measurements") != [{"kind": SENTRET_THROW, "subject": "mankey"}]):
                    raise ValueError("native timing commands require the exact Sentret Throw case")
                action["args"] = validate_command(op, action["args"])
            elif op in {"step", *PREPARED_OPS}:
                raw_args = action["args"]
                until = None
                if op == "step" and isinstance(raw_args, dict) and "until" in raw_args:
                    until = validate_predicate(raw_args["until"], subjects)
                    raw_args = {key: item for key, item in raw_args.items() if key != "until"}
                action["args"] = validate_command(op, raw_args)
                if until is not None: action["args"]["until"] = until
                resolver_action = resolver_case and op == "resolver.probe" and phase == "actions" and value["mode"] == "prepared"
                condition_action = condition_case and op == "condition.probe" and phase == "actions" and value["mode"] == "prepared"
                health_rest_teleport = health_ram_rest_case and phase == "actions" and op == "teleport" \
                    and action["id"] == "safe-rest-tile" and value["mode"] == "prepared"
                appearance_restore = appearance_damage_case and phase == "actions" and value["mode"] == "prepared"                     and (op == "teleport" and action["id"] in ("normal-center", "normal-outdoor")
                         or op == "spawn" and action["id"] == "same-party-follower")
                priority_warp = phase == "actions" and op == "teleport" and action["id"] == "route29-window" \
                    and value["mode"] == "prepared" and value.get("measurements") == [{"kind": "natural-refill-retry-v1", "subject": "mankey"}]
                if op in PREPARED_OPS and not (resolver_action or condition_action or health_rest_teleport or appearance_restore or priority_warp or (
                    value["id"] == "world.route30.sentret-throw-pacing" and phase == "actions"
                    and action["id"] == "spawn-cargo" and op == "spawn"
                    and value.get("measurements") == [{"kind": SENTRET_THROW, "subject": "mankey"}]
                )) and (phase != "setup" or value["mode"] == "normal"):
                    raise ValueError("prepared operations are allowed only in declared non-normal setup")
                if op == "step" and action["args"]["frames"] > action["budget"]["maxFrames"]:
                    raise ValueError("step exceeds its frame budget")
            elif op in ("wait", "assert"):
                _shape(action["args"], {"predicate"}, label=op + " args")
                action["args"]["predicate"] = validate_predicate(action["args"]["predicate"], subjects)
            elif op == "bind":
                _shape(action["args"], {"subject"}, label="bind args")
                if action["args"]["subject"] not in subjects: raise ValueError("bind names an undeclared subject")
            elif op in ("acceleration.begin", "acceleration.end"):
                _shape(action["args"], {"subject"}, label="acceleration window args")
                if value["mode"] != "prepared" or phase != "setup" or action["args"]["subject"] not in subjects:
                    raise ValueError("acceleration windows require a declared prepared setup subject")
            elif op == "chain-retry":
                _shape(action["args"], {"subject"}, label="chain-retry args")
                if value["mode"] != "prepared" or phase != "actions" \
                        or action["args"]["subject"] not in subjects:
                    raise ValueError("chain retry requires a bound subject in a prepared test")
            elif op == "observer-control":
                _shape(action["args"], {"subject", "fault"}, label="observer-control args")
                if value["mode"] != "observer-control" or phase != "actions" \
                        or action["args"]["subject"] not in subjects \
                        or action["args"]["fault"] not in ("render-stall", "inactive-object", "cpu-hitch", "player-start-stall"):
                    raise ValueError("native faults require the exact observer-control action")
            else:
                raise ValueError("unsupported test action")
    if not isinstance(value["assertions"], list) or not 1 <= len(value["assertions"]) <= 128:
        raise ValueError("test needs 1..128 typed assertions")
    value["assertions"] = [validate_predicate(item, subjects) for item in value["assertions"]]
    measurements = value.get("measurements", [])
    if not isinstance(measurements, list) or len(measurements) > 1:
        raise ValueError("test permits at most one implemented measurement")
    for measurement in measurements:
        if (isinstance(measurement, dict)
                and measurement.get("kind") == CONDITION_CONTROLLER):
            _shape(measurement, {"kind", "subject"},
                   label="condition controller measurement")
            subject = measurement["subject"]
            expected_wait = {
                "kind": "measurement-stage",
                "measurement": CONDITION_CONTROLLER,
                "stage": "stale-target-observed",
                "when": "final",
            }
            if (value["mode"] != "prepared"
                    or value["requirements"] != ["current.live-condition-controller"]
                    or value["subjects"] != [{
                        "id": subject, "species": 70,
                        "role": "WILD", "acquire": "spawn",
                    }]
                    or value["budgets"]["maxFrames"] > 600
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "spawn", "spawn", "bind",
                        "condition-controller.fixture",
                    ]
                    or [action["op"] for action in value["actions"]] != [
                        "condition-controller.arm", "wait",
                        "condition-controller.close",
                    ]
                    or value["actions"][0]["args"] != {"subject": subject}
                    or value["actions"][1]["args"] != {"predicate": expected_wait}
                    or value["actions"][2]["args"] != {}
                    or value["assertions"] != [{
                        "kind": "measurement-complete",
                        "measurement": CONDITION_CONTROLLER,
                        "when": "final",
                    }]):
                raise ValueError(
                    "condition controller requires its exact Wild caller fixture")
            follower = value["setup"][1]["args"]
            wild = value["setup"][2]["args"]
            if (value["setup"][4]["args"] != {}
                    or follower.get("species") != 174
                    or follower.get("role") != "follower"
                    or wild.get("species") != 70
                    or wild.get("role") != "wild"
                    or value["setup"][3]["args"] != {"subject": subject}):
                raise ValueError("condition controller actor setup differs")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WARP_GATE:
            from tools.overworld.devtools_warp_gate_recipe import validate_recipe
            validate_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == TURN_SKID:
            from tools.overworld.devtools_turn_skid_recipe import validate_recipe
            validate_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WILD_BATTLE_HANDOFF:
            from tools.overworld.devtools_wild_battle_handoff_recipe import validate_recipe
            validate_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNTED_TELEPORT_MATRIX:
            from tools.overworld.devtools_mounted_teleport_recipe import validate_recipe
            validate_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in CRASH_KINDS:
            from tools.overworld.devtools_crash_recipe import validate_crash_recipe
            validate_crash_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in STOMP_KINDS:
            from tools.overworld.devtools_stomp_recipe import validate_stomp_recipe
            validate_stomp_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in MATRIX_KINDS:
            from tools.overworld.devtools_walk_matrix_recipe import validate_matrix_recipe
            validate_matrix_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in CORNER_KINDS:
            _shape(measurement, {"kind", "subject"}, label="corner measurement")
            subject = measurement["subject"]
            corner_kind = measurement["kind"]
            control = corner_kind == CORNER_CONTROL
            if value["mode"] != ("observer-control" if control else "prepared") or value["subjects"] != [{"id": subject, "species": 155, "role": "MOUNTED", "acquire": "existing"}] or value["budgets"]["maxFrames"] > 600:
                raise ValueError("corner requires one bound mounted Cyndaquil and at most 600 frames")
            if [a["op"] for a in value["setup"]] != ["teleport", "party", "spawn", "bind", "mount-walk.configure", "walk-corner.probe"] \
                    or [a["op"] for a in value["actions"]] != ["walk-corner.arm", "step", "step", "walk-corner.recovery", "step", "wait", *(["walk-corner.calibrate"] if control else []), "walk-corner.close"]:
                raise ValueError("corner requires exact prepared setup and two normal input decisions")
            for index, keys, stage in ((1, ["DOWN", "LEFT"], "blocked"), (4, ["LEFT"], "recovery-started")):
                args = value["actions"][index]["args"]
                if args.get("keys") != keys or args.get("until") != {"kind": "measurement-stage", "measurement": corner_kind, "stage": stage, "when": "final"}:
                    raise ValueError("corner input must stop at its native decision boundary")
            if value["actions"][2]["args"] != {"frames": 1, "keys": []} \
                    or value["actions"][5]["args"] != {"predicate": {"kind": "measurement-stage", "measurement": corner_kind, "stage": "recovery-complete", "when": "final"}}:
                raise ValueError("corner requires released input and complete recovery")
            if any(a["args"].get("subject", subject) != subject for a in value["setup"] + value["actions"]):
                raise ValueError("corner setup and reader must bind the same subject")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in (WILD_WALK,WILD_CLEAR_CONTROL):
            _shape(measurement, {"kind","subject"}, label="wild Walk measurement")
            control = measurement["kind"] == WILD_CLEAR_CONTROL
            if value["mode"] != ("observer-control" if control else "prepared") or value["subjects"] != [{"id":measurement["subject"],"species":19,"role":"WILD","acquire":"spawn"}] or value["budgets"]["maxFrames"] > 1200:
                raise ValueError("wild Walk requires one newly spawned wild Rattata")
            if [a["op"] for a in value["actions"]] != ["wild-walk.arm","wait",*(["wild-walk.calibrate"] if control else []),"wild-walk.close"] \
                    or any(a["op"] not in ("teleport","spawn","bind","wait") or "skipIf" in a for a in value["setup"]):
                raise ValueError("wild Walk requires neutral natural motion without setup changes inside its window")
            expected = {"kind":"measurement-stage","measurement":WILD_CLEAR_CONTROL,"stage":"natural-walk-complete","when":"final"} if control else {"kind":"measurement-complete","measurement":WILD_WALK,"when":"final"}
            if value["actions"][0]["args"]["subject"] != measurement["subject"] \
                    or value["actions"][1]["args"]["predicate"] != expected:
                raise ValueError("wild Walk must wait for its exact complete motion")
            spawns = [a for a in value["setup"] if a["op"] == "spawn"]
            if len(spawns) != 1 or spawns[0]["args"].get("species") != 19 or spawns[0]["args"].get("role") != "wild":
                raise ValueError("wild Walk setup must spawn its own Rattata")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WILD_LEDGE:
            _shape(measurement, {"kind", "subject"}, label="wild ledge measurement")
            subject = measurement["subject"]
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.wild-ledge-hop"] \
                    or value["subjects"] != [{"id": subject, "species": 35, "role": "WILD", "acquire": "spawn"}] \
                    or value["budgets"]["maxFrames"] > 1200 \
                    or [action["op"] for action in value["setup"]] != ["teleport", "spawn", "bind", "wait"] \
                    or [action["op"] for action in value["actions"]] != ["wild-ledge.arm", "wait", "wild-ledge.close"] \
                    or value["assertions"] != [{"kind": "measurement-complete", "measurement": WILD_LEDGE, "when": "final"}]:
                raise ValueError("wild ledge requires its exact two-direction Clefairy fixture")
            spawn = value["setup"][1]["args"]
            teleport = value["setup"][0]["args"]
            if teleport != {"map": 33, "x": 585, "z": 400, "facing": 0} \
                    or spawn != {"species": 35, "form": 0, "role": "wild", "level": 5, "x": 590, "z": 395} \
                    or value["actions"][1]["args"] != {"predicate": {"kind": "measurement-complete", "measurement": WILD_LEDGE, "when": "final"}}:
                raise ValueError("wild ledge Route 29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WILD_TELEPORT:
            _shape(measurement, {"kind", "subject"}, label="wild Teleport measurement")
            subject = measurement["subject"]
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.wild-teleport"] \
                    or value["subjects"] != [{"id": subject, "species": 92, "role": "WILD", "acquire": "spawn"}] \
                    or value["budgets"]["maxFrames"] > 600 \
                    or [action["op"] for action in value["setup"]] != ["teleport", "spawn", "bind", "wait"] \
                    or [action["op"] for action in value["actions"]] != ["wait"] \
                    or value["assertions"] != [{"kind": "measurement-complete", "measurement": WILD_TELEPORT, "when": "final"}]:
                raise ValueError("wild Teleport requires its exact neutral Gastly fixture")
            spawn = value["setup"][1]["args"]
            teleport = value["setup"][0]["args"]
            expected = {"kind": "measurement-complete", "measurement": WILD_TELEPORT, "when": "final"}
            if teleport != {"map": 33, "x": 585, "z": 408, "facing": 1} \
                    or spawn != {"species": 92, "form": 0, "role": "wild", "level": 5, "x": 583, "z": 406} \
                    or value["actions"][0]["args"] != {"predicate": expected}:
                raise ValueError("wild Teleport Route 29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == RUNNER_STOP_SKID:
            _shape(measurement, {"kind", "subject"}, label="Runner stop-skid measurement")
            subject = measurement["subject"]
            expected = {"kind": "measurement-complete", "measurement": RUNNER_STOP_SKID,
                        "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.runner-stop-skid"] \
                    or value["subjects"] != [{"id": subject, "species": 234,
                                               "role": "WILD", "acquire": "spawn"}] \
                    or value["budgets"]["maxFrames"] > 600 \
                    or [action["op"] for action in value["setup"]] != ["teleport", "spawn", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["wait"] \
                    or value["assertions"] != [expected]:
                raise ValueError("Runner stop skid requires its exact neutral Stantler fixture")
            spawn = value["setup"][1]["args"]
            if value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 406,
                                                "facing": 3} \
                    or spawn != {"species": 234, "form": 0, "role": "wild", "level": 10,
                         "x": 584, "z": 406} \
                    or value["actions"][0]["args"] != {"predicate": expected}:
                raise ValueError("Runner stop-skid Route 29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == RUNNER_TURN_RUNWAY:
            _shape(measurement, {"kind", "subject"}, label="Runner turn-runway measurement")
            subject = measurement["subject"]
            expected = {"kind": "measurement-complete", "measurement": RUNNER_TURN_RUNWAY,
                        "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["current.runner-turn-runway"] \
                    or value["subjects"] != [{"id": subject, "species": 234,
                                               "role": "WILD", "acquire": "spawn"}] \
                    or value["budgets"] != {"maxSeconds": 120, "maxFrames": 300,
                                             "noProgressFrames": 240,
                                             "minObservedFrames": 22} \
                    or [action["op"] for action in value["setup"]] != ["teleport", "spawn", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["wait"] \
                    or value["assertions"] != [expected]:
                raise ValueError("Runner turn runway requires its exact neutral Stantler fixture")
            if value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 406,
                                                "facing": 3} \
                    or value["setup"][1]["args"] != {
                    "species": 234, "form": 0, "role": "wild", "level": 10,
                    "x": 586, "z": 404} \
                    or value["actions"][0]["args"] != {"predicate": expected}:
                raise ValueError("Runner turn-runway Route 29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == APPEAR_HOP:
            _shape(measurement, {"kind", "subject"}, label="Appear Hop measurement")
            subject = measurement["subject"]
            expected = {"kind": "measurement-complete", "measurement": APPEAR_HOP,
                        "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["shared.appear-hop-timing-v1"] \
                    or value["subjects"] != [{"id": subject, "species": 35,
                                               "role": "WILD", "acquire": "spawn"}] \
                    or value["budgets"] != {"maxSeconds": 60, "maxFrames": 30,
                                             "noProgressFrames": 30,
                                             "minObservedFrames": 14} \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "spawn", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["wait"] \
                    or value["assertions"] != [expected]:
                raise ValueError("Appear Hop requires one exact prepared Clefairy spawn")
            if value["setup"][0]["args"] != {
                    "map": 33, "x": 585, "z": 406, "facing": 1} \
                    or value["setup"][1]["args"] != {
                        "species": 35, "form": 0, "role": "wild", "level": 5,
                        "x": 587, "z": 406} \
                    or value["setup"][2]["args"] != {"subject": subject} \
                    or value["actions"][0]["args"] != {"predicate": expected}:
                raise ValueError("Appear Hop Route 29 fixture differs")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in SURFACE_REBIND_KINDS:
            _shape(measurement, {"kind", "subject"}, label="retained surface measurement")
            from tools.overworld.devtools_wild_surface_rebind_measurement import CONFIG
            config = CONFIG[measurement["kind"]]
            if value["id"] != config["id"] or value["mode"] != "prepared" \
                    or value["subjects"] != [dict(id=config["subject"], species=config["species"], role="WILD", acquire="spawn")] \
                    or measurement["subject"] != config["subject"]:
                raise ValueError("retained surface requires its exact prepared Wild subject")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WILD_TRANSITION:
            _shape(measurement, {"kind", "subject"}, label="Wild transition measurement")
            subject = measurement["subject"]
            if value["mode"] != "prepared" \
                    or value["subjects"] != [{"id": subject, "species": 19,
                                               "role": "WILD", "acquire": "spawn"}] \
                    or [action["op"] for action in value["setup"]] != ["spawn", "bind"] \
                    or [action["op"] for action in value["actions"]] != [
                        "wait", "step", "wait", "step", "wait", "step", "wait",
                        "step", "wait", "step", "wait"]:
                raise ValueError("Wild transition requires one spawned Rattata and the short Route29 boundary")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == FOLLOWER_TRANSITION:
            _shape(measurement, {"kind", "subject"}, label="Follower transition measurement")
            subject = measurement["subject"]
            if value["mode"] != "prepared" \
                    or value["subjects"] != [{"id": subject, "species": 155,
                                               "role": "FOLLOWER", "acquire": "existing"}] \
                    or [action["op"] for action in value["setup"]] != ["teleport", "party", "spawn", "bind"] \
                    or [action["op"] for action in value["actions"]] != [
                        "step", "wait", "wait", "step", "wait", "step", "wait",
                        "step", "wait", "step", "wait", "wait"]:
                raise ValueError("Follower transition requires one Cyndaquil and the short Route29 boundary")
            if value["setup"][0]["id"] != "route-start" \
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 406, "facing": 1} \
                    or value["setup"][1]["args"] != {"slot": 1, "hp": 21, "status": 0} \
                    or value["setup"][2]["args"] != {"species": 155, "form": 0,
                                                       "role": "follower", "slot": 1, "level": 5}:
                raise ValueError("Follower transition prepared setup differs")
            if value["actions"][-1]["id"] != "rebound-follower-walk" \
                    or value["actions"][-1]["args"] != {"predicate": {
                        "kind": "measurement-complete", "measurement": FOLLOWER_TRANSITION, "when": "final"}} \
                    or value["actions"][-1]["budget"] != {
                        "maxSeconds": 20, "maxFrames": 64, "noProgressFrames": 64}:
                raise ValueError("Follower transition fresh rebound Walk wait differs")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNTED_STREAMING:
            _shape(measurement, {"kind", "subject"}, label="mounted streaming measurement")
            subject = measurement["subject"]
            expected_stage = {"kind": "measurement-stage", "measurement": MOUNTED_STREAMING,
                              "stage": "two-complete", "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.mounted-streaming-path"] \
                    or value["subjects"] != [{"id": subject, "species": 165,
                                               "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 120 \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "party", "spawn", "step", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["step"] \
                    or value["assertions"] != [{"kind": "measurement-complete",
                                                 "measurement": MOUNTED_STREAMING,
                                                 "when": "final"}]:
                raise ValueError("mounted streaming requires one short Ledyba diagonal path")
            if value["setup"][0]["args"] != {"map": 33, "x": 594, "z": 403, "facing": 3} \
                    or value["setup"][1]["args"] != {
                        "slot": 0, "species": 165, "level": 10, "hp": 1, "status": 0} \
                    or value["setup"][2]["args"] != {
                        "species": 165, "form": 0, "role": "mounted", "slot": 0, "level": 10} \
                    or value["setup"][3]["args"] != {"frames": 16, "keys": []} \
                    or value["actions"][0]["args"] != {
                        "frames": 24, "keys": ["UP", "RIGHT"], "until": expected_stage}:
                raise ValueError("mounted streaming Route29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNTED_CARDINAL_STREAMING:
            _shape(measurement, {"kind", "subject"}, label="cardinal streaming measurement")
            subject = measurement["subject"]
            target_stage = {"kind": "measurement-stage",
                            "measurement": MOUNTED_CARDINAL_STREAMING,
                            "stage": "target-reached", "when": "final"}
            recovery_stage = {"kind": "measurement-stage",
                              "measurement": MOUNTED_CARDINAL_STREAMING,
                              "stage": "recovered", "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.cyndaquil-streaming-stress"] \
                    or value["subjects"] != [{"id": subject, "species": 155,
                                               "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 320 \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "party", "spawn", "step", "bind"] \
                    or [action["op"] for action in value["actions"]] != [
                        "step", "step", "step", "step"] \
                    or value["assertions"] != [{"kind": "measurement-complete",
                                                 "measurement": MOUNTED_CARDINAL_STREAMING,
                                                 "when": "final"}]:
                raise ValueError("cardinal streaming requires one finite Cyndaquil held route")
            if value["setup"][0]["args"] != {
                    "map": 33, "x": 584, "z": 403, "facing": 3} \
                    or value["setup"][1]["args"] != {
                        "slot": 0, "species": 155, "level": 10, "hp": 1, "status": 0} \
                    or value["setup"][2]["args"] != {
                        "species": 155, "form": 0, "role": "mounted",
                        "slot": 0, "level": 10} \
                    or value["setup"][3]["args"] != {"frames": 16, "keys": []} \
                    or value["setup"][4]["args"] != {"subject": subject} \
                    or value["actions"][0]["args"] != {
                        "frames": 240, "keys": ["RIGHT"], "until": target_stage} \
                    or value["actions"][1]["args"] != {"frames": 16, "keys": []} \
                    or value["actions"][2]["args"] != {"frames": 1, "keys": ["LEFT"]} \
                    or value["actions"][3]["args"] != {
                        "frames": 24, "keys": [], "until": recovery_stage}:
                raise ValueError("cardinal streaming Route29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNTED_WALK_TRANSITION:
            _shape(measurement, {"kind", "subject"}, label="mounted Walk transition measurement")
            subject = measurement["subject"]
            stage = lambda name: {"kind": "measurement-stage",
                                  "measurement": MOUNTED_WALK_TRANSITION,
                                  "stage": name, "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.mounted-walk-transition"] \
                    or value["subjects"] != [{"id": subject, "species": 155,
                                               "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 120 \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "party", "spawn", "step", "bind"] \
                    or [action["op"] for action in value["actions"]] != [
                        "step", "wait", "step", "wait"] \
                    or value["assertions"] != [
                        {"kind": "measurement-complete",
                         "measurement": MOUNTED_WALK_TRANSITION, "when": "final"},
                        {"kind": "player-settled-at", "map": 60,
                         "x": 674, "z": 402, "when": "final"}]:
                raise ValueError("mounted Walk transition requires one bounded Route29 crossing")
            if value["setup"][0]["args"] != {
                    "map": 33, "x": 671, "z": 402, "facing": 3} \
                    or value["setup"][1]["args"] != {
                        "slot": 0, "species": 155, "level": 10, "hp": 1, "status": 0} \
                    or value["setup"][2]["args"] != {
                        "species": 155, "form": 0, "role": "mounted",
                        "slot": 0, "level": 10} \
                    or value["setup"][3]["args"] != {"frames": 16, "keys": []} \
                    or value["setup"][4]["args"] != {"subject": subject} \
                    or value["actions"][0]["args"] != {
                        "frames": 32, "keys": ["RIGHT"],
                        "until": stage("context-changed")} \
                    or value["actions"][1]["args"] != {
                        "predicate": stage("transition-motion-complete")} \
                    or value["actions"][2]["args"] != {"frames": 1, "keys": ["RIGHT"]} \
                    or value["actions"][3]["args"] != {"predicate": stage("recovered")}:
                raise ValueError("mounted Walk transition Route29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == SENTRET_THROW:
            from tools.overworld.devtools_sentret_throw_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == POPULATION_HEADROOM:
            from tools.overworld.devtools_population_headroom_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in SPAWN_PRIORITY_KINDS:
            _shape(measurement, {"kind", "subject"}, label="natural spawn measurement")
            from tools.overworld.devtools_spawn_priority_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == LAND_SURF:
            _shape(measurement, {"kind", "subject"}, label="land/surf measurement")
            subject = measurement["subject"]
            expected_stage = {"kind": "measurement-stage", "measurement": LAND_SURF,
                              "stage": "two-attempts", "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.cherrygrove-surf-spawn-terrain"] \
                    or value["subjects"] != [{"id": subject, "species": 56,
                                               "role": "FOLLOWER", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 320 \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "wait", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["wait"] \
                    or value["assertions"] != [{"kind": "measurement-complete",
                                                 "measurement": LAND_SURF,
                                                 "when": "final"}]:
                raise ValueError("land/surf separation requires one short Cherrygrove wait")
            if value["setup"][0]["args"] != {
                    "map": 67, "x": 543, "z": 393, "facing": 1} \
                    or value["setup"][1]["args"] != {"predicate": {
                        "kind": "actor-present", "subject": subject,
                        "when": "final"}} \
                    or value["setup"][2]["args"] != {"subject": subject} \
                    or value["actions"][0]["args"] != {"predicate": expected_stage}:
                raise ValueError("land/surf Cherrygrove inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == SPAWN_WORK_BUDGET:
            _shape(measurement, {"kind", "subject"}, label="spawn-work measurement")
            subject = measurement["subject"]
            expected_stage = {"kind": "measurement-stage", "measurement": SPAWN_WORK_BUDGET,
                              "stage": "complete", "when": "final"}
            route = [
                ("route-up", "UP", 33, 585, 398, 64),
                ("route-left-city", "LEFT", 67, 565, 398, 128),
                ("route-up-city", "UP", 67, 565, 393, 64),
                ("route-left-window", "LEFT", 67, 543, 393, 128),
                ("route-down-window", "DOWN", 67, 543, 402, 64),
            ]
            if value["mode"] != "normal" \
                    or value["requirements"] != ["shared.spawn-work-budget-v1"] \
                    or value["subjects"] != [{"id": subject, "species": 56,
                                               "role": "FOLLOWER", "acquire": "existing"}] \
                    or value["budgets"] != {"maxSeconds": 180, "maxFrames": 720,
                                             "noProgressFrames": 320,
                                             "minObservedFrames": 120} \
                    or value["setup"][:-2] != _d1_warmup_setup() \
                    or [action["op"] for action in value["setup"][-2:]] != ["wait", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["step", "wait", "step"] + ["step", "wait"] * (len(route) - 1) + ["wait"] \
                    or value["assertions"] != [{"kind": "measurement-complete",
                                                 "measurement": SPAWN_WORK_BUDGET,
                                                 "when": "final"}]:
                raise ValueError("spawn-work budget requires the normal warm-up and short moving route")
            if value["setup"][-2]["args"] != {"predicate": {
                        "kind": "actor-present", "subject": subject,
                        "when": "final"}} \
                    or value["setup"][-1]["args"] != {"subject": subject}:
                raise ValueError("spawn-work Route 30 inputs differ")
            if value["actions"][2] != {
                    "id": "route-up-scan-idle", "op": "step",
                    "args": {"frames": 36, "keys": []},
                    "budget": {"maxSeconds": 10, "maxFrames": 36,
                               "noProgressFrames": 36}}:
                raise ValueError("spawn-work pre-crossing idle differs")
            route_actions = value["actions"][:2] + value["actions"][3:]
            for index, (action_id, key, map_id, x, z, frames) in enumerate(route):
                move, settle = route_actions[index * 2:index * 2 + 2]
                if move["id"] != action_id \
                        or move["args"] != {"frames": frames, "keys": [key], "until": {
                            "kind": "player-field", "path": "y" if key in ("UP", "DOWN") else "x",
                            "operator": "eq", "value": z if key in ("UP", "DOWN") else x,
                            "when": "final"}} \
                        or settle["id"] != action_id + "-settle" \
                        or settle["args"] != {"predicate": {
                            "kind": "player-settled-at", "map": map_id,
                            "x": x, "z": z, "when": "final"}} \
                        or settle["budget"] != {"maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 8} \
                        or "skipIf" in move or "skipIf" in settle:
                    raise ValueError("spawn-work Route 30 inputs differ")
            if value["actions"][-1] != {
                    "id": "finish-natural-entry", "op": "wait",
                    "args": {"predicate": expected_stage},
                    "budget": {"maxSeconds": 60, "maxFrames": 256,
                               "noProgressFrames": 32}}:
                raise ValueError("spawn-work final entry wait differs")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == UNMOUNTED_ZERO_STUTTER:
            _shape(measurement, {"kind", "subject"}, label="zero-stutter measurement")
            subject = measurement["subject"]
            expected_assertions = [
                {"kind": "measurement-complete", "measurement": UNMOUNTED_ZERO_STUTTER,
                 "when": "final"},
                {"kind": "player-settled-at", "map": 67, "x": 555, "z": 393,
                 "when": "final"},
            ]
            if value["mode"] != "normal" \
                    or value["requirements"] != ["current.unmounted-zero-stutter"] \
                    or value["subjects"] != [{"id": subject, "species": 56,
                                               "role": "FOLLOWER", "acquire": "existing"}] \
                    or value["budgets"] != {"maxSeconds": 900, "maxFrames": 4000,
                                             "noProgressFrames": 600,
                                             "minObservedFrames": 2600} \
                    or value["setup"][:-2] != _d1_warmup_setup() \
                    or [(action["id"], action["op"]) for action in value["setup"][-2:]] != [
                        ("follower-present", "wait"), ("bind-mankey", "bind"),
                    ] \
                    or len(value["actions"]) != 127 \
                    or value["assertions"] != expected_assertions:
                raise ValueError("zero-stutter test requires the sealed 673-step route")
            if value["setup"][-2]["args"] != {"predicate": {
                        "kind": "actor-present", "subject": subject, "when": "final"}} \
                    or value["setup"][-1]["args"] != {"subject": subject}:
                raise ValueError("zero-stutter normal save setup differs")
            routes = [
                ("UP", 8, 33, 585, 398),
                ("LEFT", 28, 67, 565, 398),
                ("UP", 33, 67, 565, 393),
                ("LEFT", 55, 67, 543, 393),
                ("DOWN", 64, 67, 543, 402),
            ]
            count = 64
            for _ in range(14):
                count += 12; routes.append(("RIGHT", count, 67, 555, 402))
                count += 9; routes.append(("UP", count, 67, 555, 393))
                count += 12; routes.append(("LEFT", count, 67, 543, 393))
                count += 9; routes.append(("DOWN", count, 67, 543, 402))
            count += 12; routes.append(("RIGHT", count, 67, 555, 402))
            count += 9; routes.append(("UP", count, 67, 555, 393))
            for index, (direction, step_count, map_id, x, z) in enumerate(routes, 1):
                move, settle = value["actions"][(index - 1) * 2:index * 2]
                if move["id"] != f"route-{index:03d}" or move["op"] != "step" \
                        or move["args"] != {"frames": 256, "keys": [direction], "until": {
                            "kind": "player-field", "path": "y" if direction in ("UP", "DOWN") else "x",
                            "operator": "eq", "value": z if direction in ("UP", "DOWN") else x,
                            "when": "final"}} \
                        or settle["id"] != f"route-{index:03d}-settle" \
                        or settle["op"] != "wait" \
                        or settle["args"] != {"predicate": {
                            "kind": "player-settled-at", "map": map_id,
                            "x": x, "z": z, "when": "final"}} \
                        or settle["budget"] != {"maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 8} \
                        or "skipIf" in move or "skipIf" in settle:
                    raise ValueError("zero-stutter route inputs differ")
            final_wait = value["actions"][-1]
            if final_wait["id"] != "complete-zero-stutter-window" \
                    or final_wait["op"] != "wait" \
                    or final_wait["args"] != {"predicate": {
                        "kind": "measurement-complete",
                        "measurement": UNMOUNTED_ZERO_STUTTER,
                        "when": "final"}} \
                    or final_wait["budget"] != {
                        "maxSeconds": 15, "maxFrames": 80,
                        "noProgressFrames": 80}:
                raise ValueError("zero-stutter completion window differs")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == POPULATION_FAST_TRAVEL:
            _shape(measurement, {"kind", "subject"}, label="population fast-travel measurement")
            subject = measurement["subject"]
            expected_stage = {"kind": "measurement-stage",
                              "measurement": POPULATION_FAST_TRAVEL,
                              "stage": "refilled", "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["legacy.population-after-fast-travel"] \
                    or value["subjects"] != [{"id": subject, "species": 56,
                                               "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 480 \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "party", "spawn", "step", "bind"] \
                    or [action["op"] for action in value["actions"]] != [
                        "step", "wait", "step", "wait"] \
                    or value["assertions"] != [{"kind": "measurement-complete",
                                                 "measurement": POPULATION_FAST_TRAVEL,
                                                 "when": "final"}]:
                raise ValueError("population fast travel requires one short mounted boundary route")
            if value["setup"][0]["args"] != {
                    "map": 33, "x": 576, "z": 402, "facing": 0} \
                    or value["setup"][1]["args"] != {
                        "slot": 0, "species": 56, "level": 10, "hp": 1, "status": 0} \
                    or value["setup"][2]["args"] != {
                        "species": 56, "form": 0, "role": "mounted",
                        "slot": 0, "level": 10} \
                    or value["setup"][3]["args"] != {"frames": 16, "keys": []} \
                    or value["setup"][4]["args"] != {"subject": subject} \
                    or value["actions"][0]["args"] != {"frames": 1, "keys": ["UP"]} \
                    or value["actions"][1]["args"] != {"predicate": {
                        "kind": "player-settled-at", "map": 33,
                        "x": 576, "z": 396, "when": "final"}} \
                    or value["actions"][2]["args"] != {
                        "frames": 30, "keys": ["LEFT"], "until": {
                            "kind": "event-count", "subject": subject,
                            "event": "MOTION_STARTED", "operator": "gte",
                            "value": 2, "when": "final"}} \
                    or value["actions"][3]["args"] != {"predicate": expected_stage}:
                raise ValueError("population fast-travel Route29 inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNT_DETACH_FOLLOWER_RESUME:
            _shape(measurement, {"kind", "subject"},
                   label="mount detach follower resume measurement")
            subject = measurement["subject"]
            expected = {"kind": "measurement-complete",
                        "measurement": MOUNT_DETACH_FOLLOWER_RESUME,
                        "when": "final"}
            if value["mode"] != "prepared" \
                    or value["requirements"] != ["current.mount-detach-follower-resume"] \
                    or value["subjects"] != [{"id": subject, "species": 155,
                                               "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"] != {"maxSeconds": 120, "maxFrames": 240,
                                             "noProgressFrames": 48,
                                             "minObservedFrames": 1} \
                    or [action["op"] for action in value["setup"]] != [
                        "teleport", "party", "spawn", "step", "bind"] \
                    or [action["op"] for action in value["actions"]] != ["step", "step"] \
                    or value["assertions"] != [expected]:
                raise ValueError("mount detach follower resume requires its exact short route")
            if [action["args"] for action in value["setup"]] != [
                    {"map": 33, "x": 584, "z": 403, "facing": 3},
                    {"slot": 0, "species": 155, "level": 10, "hp": 1, "status": 0},
                    {"species": 155, "form": 0, "role": "mounted", "slot": 0, "level": 5},
                    {"frames": 16, "keys": []},
                    {"subject": subject}] \
                    or [action["args"] for action in value["actions"]] != [
                        {"frames": 1, "keys": ["SELECT"]},
                        {"frames": 32, "keys": ["RIGHT"]}]:
                raise ValueError("mount detach follower resume inputs differ")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNT_CONTROL_STRESS:
            _shape(measurement, {"kind", "subject", "contract"}, label="mounted control stress measurement")
            subject = measurement["subject"]
            configurations = {
                "walk": {"species": 155, "motions": 1200, "frames": 20,
                         "budgets": {"maxSeconds": 1200, "maxFrames": 30000,
                                     "noProgressFrames": 120, "minObservedFrames": 5000},
                         "settle": 32, "recoveryFrames": 32, "motion": "WALK"},
                "hop": {"species": 56, "motions": 100, "frames": 100,
                        "budgets": {"maxSeconds": 1200, "maxFrames": 24000,
                                    "noProgressFrames": 120, "minObservedFrames": 5001},
                        "settle": 64, "recoveryFrames": 64, "motion": "HOP"},
            }
            configuration = configurations.get(measurement["contract"])
            if configuration is None or value["mode"] != "prepared" \
                    or value["subjects"] != [{"id": subject, "species": configuration["species"],
                                               "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"] != configuration["budgets"]:
                raise ValueError("mounted control stress requires its exact current species contract")
            if [action["op"] for action in value["setup"]] != ["teleport", "party", "spawn", "step", "bind"] \
                    or any("skipIf" in action for action in value["setup"]):
                raise ValueError("mounted Walk stress requires exact prepared own-party setup")
            setup_args = [action["args"] for action in value["setup"]]
            if setup_args != [
                    {"map": 33, "x": 584, "z": 403, "facing": 3},
                    {"slot": 0, "species": configuration["species"], "level": 10, "hp": 1, "status": 0},
                    {"species": configuration["species"], "form": 0, "role": "mounted", "slot": 0, "level": 5},
                    {"frames": 16, "keys": []},
                    {"subject": subject}]:
                raise ValueError("mounted control stress prepared setup changed")
            stress, tail = value["actions"][:-9], value["actions"][-9:]
            if len(stress) != configuration["motions"] or any(action["op"] != "step" or action["args"] != {
                    "frames": configuration["frames"], "keys": ["RIGHT" if index % 2 == 0 else "LEFT"]}
                    for index, action in enumerate(stress)):
                raise ValueError("mounted control stress needs its alternating normal-input holds")
            tail_args = [action["args"] for action in tail]
            recovery = {"kind": "actor-field", "subject": subject, "path": "motionKind",
                        "operator": "eq", "value": configuration["motion"], "when": "final"}
            if [action["op"] for action in tail] != ["step"] * 9 or tail_args != [
                    {"frames": configuration["settle"], "keys": []}, {"frames": 1, "keys": ["SELECT"]},
                    {"frames": 60, "keys": []}, {"frames": 32, "keys": ["RIGHT"]},
                    {"frames": 32, "keys": []}, {"frames": 1, "keys": ["SELECT"]},
                    {"frames": 60, "keys": []}, {"frames": configuration["recoveryFrames"],
                                                   "keys": ["RIGHT"], "until": recovery},
                    {"frames": configuration["settle"], "keys": []}]:
                raise ValueError("mounted control stress detach/remount route changed")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNT_POSE_CONTROL:
            _shape(measurement, {"kind", "subject"}, label="mounted pose control measurement")
            if value["mode"] != "observer-control" or value["subjects"] != [{"id": measurement["subject"], "species": 155, "role": "MOUNTED", "acquire": "existing"}] or value["budgets"]["maxFrames"] > 1200:
                raise ValueError("mounted pose control requires one current mounted Cyndaquil")
            if [a["op"] for a in value["actions"]] != ["mount-pacing.arm", "wait", "mount-pacing.calibrate", "mount-pacing.close"] or any(a["op"] not in ("teleport", "party", "spawn", "bind", "step", "wait") or "skipIf" in a for a in value["setup"]):
                raise ValueError("mounted pose control requires arm, coherent wait, calibrate and close")
            if value["actions"][0]["args"]["subject"] != measurement["subject"]:
                raise ValueError("mounted pose control arm subject differs")
            if value["actions"][1]["args"] != {"predicate": {"kind": "frame-count", "operator": "gte", "value": 1, "when": "final"}}:
                raise ValueError("mounted pose control needs one completed sample before calibration")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNT_PACING:
            _shape(measurement, {"kind", "subject"}, label="mounted pacing measurement")
            if value["mode"] != "prepared" or value["subjects"] != [{"id": measurement["subject"], "species": 155, "role": "MOUNTED", "acquire": "existing"}] or value["budgets"]["maxFrames"] > 1200:
                raise ValueError("mounted pacing requires one current mounted Cyndaquil and bounded frames")
            operations = [a["op"] for a in value["actions"] if a["op"] not in ("step", "wait", "assert")]
            if operations != ["mount-pacing.arm", "mount-pacing.recovery", "mount-pacing.close"] or any(a["op"] not in ("teleport", "party", "spawn", "bind", "step", "wait") or "skipIf" in a for a in value["setup"]):
                raise ValueError("mounted pacing requires one arm, separate recovery, and close without setup mutations during motion")
            arm = next(a for a in value["actions"] if a["op"] == "mount-pacing.arm")
            if arm["args"]["subject"] != measurement["subject"]:
                raise ValueError("mounted pacing arm subject differs")
            if [a["op"] for a in value["actions"]] != ["mount-pacing.arm", "step", "wait",
                    "mount-pacing.recovery", "step", "wait", "mount-pacing.close"]:
                raise ValueError("mounted pacing requires one held Right run and a separate recovery run")
            for index, stage, predicate_key in ((1, "main-started", "until"), (2, "main-complete", "predicate"),
                                                (4, "recovery-started", "until"), (5, "recovery-complete", "predicate")):
                args = value["actions"][index]["args"]
                expected = {"kind": "measurement-stage", "measurement": MOUNT_PACING, "stage": stage, "when": "final"}
                if args.get(predicate_key) != expected or (predicate_key == "until" and args.get("keys") != ["RIGHT"]):
                    raise ValueError("mounted pacing input must stop at its exact semantic boundary")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == MOUNT_SPEED_SLEW:
            _shape(measurement, {"kind", "subject"}, {"linearRamp"}, label="mounted speed measurement")
            linear = measurement.get("linearRamp")
            if linear is not None:
                from tools.overworld.devtools_mount_speed_slew_measurement import linear_tuning
                base, fastest = linear_tuning(linear)
            if linear is not None:
                configured = [a for a in value["setup"] if a["op"] == "mount-walk.configure"]
                if len(configured) != 1 or configured[0] != value["setup"][-1] or configured[0]["args"] != dict(
                        subject=measurement["subject"], directionMode=0, travelTime=base,
                        fastestTime=fastest, timeToFullSpeed=linear, timeVariance=2):
                    raise ValueError("mounted Linear needs its exact idle setup lane")
            if value["mode"] != "prepared" or value["subjects"] != [
                    {"id": measurement["subject"], "species": 234,
                     "role": "MOUNTED", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 1200:
                raise ValueError("mounted speed requires one current bounded Stantler")
            if any(a["op"] not in ("teleport", "party", "spawn", "bind", "step", "wait",
                                      *(("mount-walk.configure",) if linear is not None else ()))
                   or "skipIf" in a for a in value["setup"]):
                raise ValueError("mounted speed setup must end before its input window")
            if [a["op"] for a in value["actions"]] != [
                    "mount-pacing.arm", "step", "wait", "wait", "mount-pacing.close"]:
                raise ValueError("mounted speed needs one held Right run and close")
            if value["actions"][0]["args"]["subject"] != measurement["subject"]:
                raise ValueError("mounted speed arm subject differs")
            for index, stage, key in ((1, "main-started", "until"),
                                      (2, "main-complete", "predicate"),
                                      (3, "gait-settled", "predicate")):
                args = value["actions"][index]["args"]
                expected = {"kind": "measurement-stage", "measurement": MOUNT_SPEED_SLEW,
                            "stage": stage, "when": "final"}
                if args.get(key) != expected or (key == "until" and args.get("keys") != ["RIGHT"]):
                    raise ValueError("mounted speed input must stop at its exact motion boundary")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WALK_POLICY_CONTROL:
            _shape(measurement, {"kind", "subject"}, label="Walk reader control measurement")
            if value["mode"] != "observer-control" or len(value["subjects"]) != 1 or value["subjects"][0]["id"] != measurement["subject"] or value["subjects"][0]["role"] not in ("WILD", "MOUNTED") or value["subjects"][0]["acquire"] != "existing" or value["budgets"]["maxFrames"] > 1200:
                raise ValueError("Walk reader control requires one existing Wild or Mounted subject")
            operations = [a["op"] for a in value["actions"] if a["op"] not in ("step", "wait", "assert")]
            if operations != ["walk-policy-control.arm", "walk-policy-control.close"] or any(a["op"] not in ("teleport", "party", "spawn", "bind", "step", "wait") or "skipIf" in a for a in value["setup"]):
                raise ValueError("Walk reader control requires one arm/close window and bounded excluded setup")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == ACCELERATION:
            _shape(measurement, {"kind", "subjects"}, label="acceleration measurement")
            _shape(measurement["subjects"], {"WILD", "MOUNTED"}, label="acceleration roles")
            if value["mode"] != "prepared" or len(value["subjects"]) != 2 or any(
                    len([s for s in value["subjects"] if s["id"] == subject and s["role"] == role
                         and s["acquire"] == "existing"]) != 1
                    for role, subject in measurement["subjects"].items()):
                raise ValueError("acceleration requires exact existing Wild and Mounted subjects")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == EMOTE_THREE:
            _shape(measurement, {"kind", "subject"}, label="emote burst measurement")
            from tools.overworld.devtools_emote_three_measurement import SUBJECTS, SETUP, ACTIONS
            if measurement["subject"] != "a" or value["id"] != "presentation.emote-three-slots" or value["subjects"] != SUBJECTS \
                    or value["mode"] != "prepared" or [a["op"] for a in value["actions"]] \
                    != ["emote-three.arm", "step", "emote-three.close"] \
                    or value["actions"][1]["args"] != {"frames":240,"keys":[]} \
                    or [(a["id"], a["op"], a["args"]) for a in value["setup"]] != SETUP \
                    or [(a["id"], a["op"], a["args"]) for a in value["actions"]] != ACTIONS:
                raise ValueError("emote burst requires one fixed six-request arm/240 ordinary updates/close")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == ACTOR_INSPECT:
            _shape(measurement, {"kind", "subject"}, label="actor Inspect measurement")
            subject = measurement["subject"]
            if not inspect_case or value["subjects"] != [{"id": subject, "species": 56,
                    "role": "FOLLOWER", "acquire": "existing"}] or value["mode"] != "prepared" \
                    or len(value["setup"]) != 1 or value["setup"][0]["op"] != "bind" \
                    or value["setup"][0]["args"] != {"subject": subject} \
                    or len(value["actions"]) != 1 or value["actions"][0]["op"] != "actor-inspect.probe" \
                    or value["actions"][0]["args"] != {"subject": subject} \
                    or value["budgets"]["maxFrames"] > 120:
                raise ValueError("actor Inspect requires one existing Mankey bind and one fixed probe")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_INITIAL:
            _shape(measurement, {"kind"}, label="player HP initial measurement")
            if (value["id"] != "player-hp.initial-state"
                    or value["mode"] != "normal" or value["subjects"]
                    or value["setup"] or len(value["actions"]) != 1
                    or value["actions"][0]["op"] != "player-health.observe"
                    or value["actions"][0]["args"] != {}
                    or value["budgets"]["maxFrames"] > 120):
                raise ValueError("initial HP needs one normal-save read-only observation")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_RAM_REST:
            _shape(measurement, {"kind", "subject"}, label="player HP Ram/rest measurement")
            from tools.overworld.devtools_player_health_ram_rest_measurement import ORDER, STEPS
            if (value["id"] != "player-hp.ram-rest" or value["mode"] != "prepared"
                    or measurement["subject"] != "onix"
                    or value["subjects"] != [{"id": "onix", "species": 95,
                                              "role": "WILD", "acquire": "spawn"}]
                    or [(a["id"], a["op"]) for a in value["setup"]]
                    != [("ram-tile", "teleport"), ("spawn-onix", "spawn"),
                        ("bind-onix", "bind")]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 3}
                    or value["setup"][1]["args"] != {"species": 95, "form": 0,
                                                        "role": "wild", "level": 5,
                                                        "x": 585, "z": 411}
                    or value["setup"][2]["args"] != {"subject": "onix"}
                    or value["actions"][3]["args"] != {"map": 34, "x": 550,
                                                          "z": 381, "facing": 1}
                    or any(a["args"].get("keys") != (["RIGHT"] if a["id"] == "move-again" else [])
                           for a in value["actions"] if a["id"] in STEPS)
                    or any(a["args"] != {} for a in value["actions"]
                           if a["op"] == "player-health.observe")
                    or any(a["args"].get("frames") != STEPS[a["id"]]
                           for a in value["actions"] if a["id"] in STEPS)
                    or value["budgets"]["minObservedFrames"] != sum(STEPS.values())
                    or value["budgets"]["maxFrames"] > 910):
                raise ValueError("Ram/rest needs its exact Onix and bounded frame contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_RAM_LOW_SPEED:
            _shape(measurement, {"kind", "subject"}, label="player HP low-speed Ram measurement")
            from tools.overworld.devtools_player_health_ram_low_speed_measurement import ORDER, SETUP
            if (value["id"] != "player-hp.ram-low-speed" or value["mode"] != "prepared"
                    or measurement["subject"] != "onix"
                    or value["subjects"] != [{"id": "onix", "species": 95,
                                              "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 95, "form": 0,
                                                        "role": "wild", "level": 5,
                                                        "x": 585, "z": 408}
                    or value["setup"][2]["args"] != {"subject": "onix"}
                    or value["actions"][1]["args"] != {
                        "frames": 120, "keys": [], "until": {"kind": "measurement-stage",
                        "measurement": PLAYER_HEALTH_RAM_LOW_SPEED,
                        "stage": "ram-active", "when": "final"}}
                    or value["actions"][2]["args"] != {"frames": 80, "keys": []}
                    or value["actions"][0]["args"] != {}
                    or value["actions"][3]["args"] != {}
                    or value["budgets"]["minObservedFrames"] != 81
                    or value["budgets"]["maxFrames"] > 360):
                raise ValueError("low-speed Ram needs its exact adjacent Onix frame contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_THROW:
            _shape(measurement, {"kind", "subjects"}, label="player HP Throw measurement")
            from tools.overworld.devtools_player_health_throw_contact_measurement import (
                CROSS_FRAMES, LAUNCH_LIMIT, MIN_FRAMES, ORDER, SETUP,
            )
            if (value["id"] != "player-hp.throw-contact" or value["mode"] != "prepared"
                    or measurement["subjects"] != ["weepinbell", "geodude"]
                    or value["subjects"] != [
                        {"id": "weepinbell", "species": 70, "role": "WILD", "acquire": "spawn"},
                        {"id": "geodude", "species": 74, "role": "WILD", "acquire": "spawn"},
                    ]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "spawn", "bind", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != [
                        "player-health.observe", "step", "player-health.observe", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 70, "form": 0, "role": "wild", "level": 5,
                                                        "x": 585, "z": 400}
                    or value["setup"][2]["args"] != {"subject": "weepinbell"}
                    or value["setup"][3]["args"] != {"species": 74, "form": 0, "role": "wild", "level": 5,
                                                        "x": 585, "z": 402}
                    or value["setup"][4]["args"] != {"subject": "geodude"}
                    or any(a["args"] != {} for a in value["actions"]
                           if a["op"] == "player-health.observe")
                    or value["actions"][1]["args"] != {"frames": LAUNCH_LIMIT, "keys": [],
                        "until": {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_THROW,
                                  "stage": "launched", "when": "final"}}
                    or value["actions"][3]["args"] != {"frames": CROSS_FRAMES, "keys": []}
                    or value["budgets"]["minObservedFrames"] != MIN_FRAMES
                    or value["budgets"]["maxFrames"] > 900):
                raise ValueError("Throw contact needs its exact two actors and bounded flight contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_HOP:
            _shape(measurement, {"kind", "subject"}, label="player HP Hop measurement")
            from tools.overworld.devtools_player_health_hop_contact_measurement import ORDER, SETUP, WAIT_LIMIT
            if (value["id"] != "player-hp.hop-contact" or value["mode"] != "prepared"
                    or measurement["subject"] != "mankey"
                    or value["subjects"] != [{"id": "mankey", "species": 56,
                                              "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != [
                        "step", "player-health.observe", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 56, "form": 0,
                        "role": "wild", "level": 5, "x": 586, "z": 406}
                    or value["setup"][2]["args"] != {"subject": "mankey"}
                    or value["actions"][0]["args"] != {"frames": 80, "keys": [],
                        "until": {"kind": "actor-field", "subject": "mankey",
                                  "path": "motionKind", "operator": "eq", "value": "NONE", "when": "final"}}
                    or value["actions"][2]["args"] != {"frames": WAIT_LIMIT, "keys": [],
                        "until": {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_HOP,
                                  "stage": "airborne-crossed", "when": "final"}}
                    or any(a["args"] != {} for a in value["actions"]
                           if a["op"] == "player-health.observe")
                    or value["budgets"]["minObservedFrames"] != 1
                    or value["budgets"]["maxFrames"] > 700):
                raise ValueError("ordinary Hop contact needs its exact Mankey and frame contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in APPEARANCE_KINDS:
            _shape(measurement, {"kind", "subject"}, label="Pokémon palette measurement")
            from tools.overworld.devtools_appearance_measurement import validate_recipe
            validate_recipe(value, measurement)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == BASIC_ATTACK:
            _shape(measurement, {"kind", "subject"}, label="Basic attack measurement")
            from tools.overworld.devtools_basic_attack_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == FOLLOWER_RAM:
            _shape(measurement, {"kind", "subject"}, label="Follower Ram measurement")
            from tools.overworld.devtools_follower_ram_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == POKEMON_SKID_HIT:
            _shape(measurement, {"kind", "subject"}, label="Pokémon skid-hit measurement")
            from tools.overworld.devtools_pokemon_skid_hit_measurement import (
                MIN_FRAMES, ORDER, SETUP, SETUP_SPEC, SUBJECTS, INPUTS, SCENARIO, REQUIREMENT)
            if (value["id"] != SCENARIO or value["mode"] != "prepared"
                    or measurement["subject"] != "stantler" or value["requirements"] != [REQUIREMENT]
                    or value["subjects"] != [dict(id=n, species=s, role=r, acquire=a) for n,s,r,a in SUBJECTS]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [(a["op"], a["args"]) for a in value["setup"]] != list(SETUP_SPEC)
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != ["player-health.observe", "step", "step", "step", "player-health.observe"]
                    or any(a["args"] != dict(frames=INPUTS[a["id"]][0], keys=INPUTS[a["id"]][1])
                           for a in value["actions"][1:4])
                    or value["budgets"]["minObservedFrames"] != MIN_FRAMES
                    or value["budgets"]["maxFrames"] > 900):
                raise ValueError("Pokémon skid-hit needs the exact natural head2 Ambush fixture and input order")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == POKEMON_COMBAT:
            _shape(measurement, {"kind", "subject"}, label="Pokémon combat measurement")
            from tools.overworld.devtools_pokemon_combat_measurement import (
                MIN_FRAMES, ORDER, SETUP, SUBJECTS, WAIT_LIMIT, TAIL_FRAMES)
            if (value["id"] != "pokemon-hp.collision-knockback" or value["mode"] != "prepared"
                    or measurement["subject"] != "cyndaquil"
                    or value["subjects"] != [dict(id=n, species=s, role=r, acquire=a) for n,s,r,a in SUBJECTS]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "party", "spawn", "step", "bind", "spawn", "bind", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != ["player-health.observe", "step", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map":33,"x":585,"z":407,"facing":1}
                    or value["setup"][1]["args"] != {"slot":0,"species":155,"level":50}
                    or value["setup"][2]["args"] != {"species":155,"form":0,"role":"mounted","slot":0,"level":50}
                    or value["setup"][3]["args"] != {"frames":16,"keys":[]}
                    or value["setup"][5]["args"] != {"species":143,"form":0,"role":"wild","level":50,"x":585,"z":405}
                    or value["setup"][7]["args"] != {"species":70,"form":0,"role":"wild","level":10,"x":585,"z":404}
                    or value["actions"][1]["args"] != {"frames":WAIT_LIMIT,"keys":[],"until":{
                        "kind":"measurement-stage","measurement":POKEMON_COMBAT,"stage":"landed","when":"final"}}
                    or value["actions"][2]["args"] != {"frames":TAIL_FRAMES,"keys":[]}
                    or value["budgets"]["minObservedFrames"] != MIN_FRAMES
                    or value["budgets"]["maxFrames"] > 600):
                raise ValueError("Pokémon combat needs its exact ordinary Ambush collision and shared knockback fixture")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_RUNNING_HIT:
            _shape(measurement, {"kind", "subject"}, label="player HP running-hit measurement")
            from tools.overworld.devtools_player_health_running_hit_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_AMBUSH_JUMP:
            _shape(measurement, {"kind", "subject"}, label="player HP Ambush jump measurement")
            from tools.overworld.devtools_player_health_ambush_jump_measurement import (
                JUMP_FRAMES, MIN_FRAMES, ORDER, SETUP, WAIT_LIMIT)
            if (value["id"] != "player-hp.ambush-jump" or value["mode"] != "prepared"
                    or measurement["subject"] != "weepinbell"
                    or value["subjects"] != [{"id": "weepinbell", "species": 70,
                                               "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != [
                        "player-health.observe", "step", "player-health.observe",
                        "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 70, "form": 0,
                        "role": "wild", "level": 5, "x": 585, "z": 404}
                    or value["setup"][2]["args"] != {"subject": "weepinbell"}
                    or value["actions"][1]["args"] != {"frames": WAIT_LIMIT, "keys": [],
                        "until": {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_AMBUSH_JUMP,
                                  "stage": "airborne-crossed", "when": "final"}}
                    or value["actions"][3]["args"] != {"frames": JUMP_FRAMES, "keys": []}
                    or any(a["args"] != {} for a in value["actions"]
                           if a["op"] == "player-health.observe")
                    or value["budgets"]["minObservedFrames"] != MIN_FRAMES
                    or value["budgets"]["maxFrames"] > 450):
                raise ValueError("Ambush jump needs its exact Wild actor and frame contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT:
            _shape(measurement, {"kind", "subjects"}, label="mounted Ambush height measurement")
            from tools.overworld.devtools_player_health_mounted_ambush_height_measurement import (
                MIN_FRAMES, OBSERVE_FRAMES, ORDER, SETUP)
            if (value["id"] != "player-hp.mounted-ambush-height" or value["mode"] != "prepared"
                    or measurement["subjects"] != ["cyndaquil", "weepinbell"]
                    or value["subjects"] != [
                        {"id": "cyndaquil", "species": 155, "role": "MOUNTED", "acquire": "existing"},
                        {"id": "weepinbell", "species": 70, "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "party", "spawn", "step", "bind", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != [
                        "player-health.observe", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"slot": 0, "species": 155, "level": 50}
                    or value["setup"][2]["args"] != {"species": 155, "form": 0,
                        "role": "mounted", "slot": 0, "level": 50}
                    or value["setup"][3]["args"] != {"frames": 16, "keys": []}
                    or value["setup"][4]["args"] != {"subject": "cyndaquil"}
                    or value["setup"][5]["args"] != {"species": 70, "form": 0,
                        "role": "wild", "level": 5, "x": 585, "z": 404}
                    or value["setup"][6]["args"] != {"subject": "weepinbell"}
                    or value["actions"][1]["args"] != {"frames": OBSERVE_FRAMES, "keys": []}
                    or any(a["args"] != {} for a in value["actions"]
                           if a["op"] == "player-health.observe")
                    or value["budgets"]["minObservedFrames"] != MIN_FRAMES
                    or value["budgets"]["maxFrames"] > 500):
                raise ValueError("mounted Ambush needs exact actor, hit, and stable-height contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in PLAYER_HEALTH_MOVING_KINDS:
            _shape(measurement, {"kind", "subject"}, label="moving Player HP measurement")
            from tools.overworld.devtools_player_health_moving_heal_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in TARGET_ACCESS_KINDS:
            _shape(measurement, {"kind", "subject"}, label="target access measurement")
            from tools.overworld.devtools_target_access_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in CROSS_HEIGHT_KINDS:
            _shape(measurement, {"kind", "subject"}, label="signed-height Throw measurement")
            from tools.overworld.devtools_cross_height_throw_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in DISTANCE_KINDS:
            _shape(measurement, {"kind", "subject"}, label="distance despawn measurement")
            from tools.overworld.devtools_distance_despawn_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == HELD_THROW_SEARCH:
            _shape(measurement, {"kind", "subject"}, label="held Throw measurement")
            from tools.overworld.devtools_held_throw_search_measurement import validate_recipe
            if measurement["subject"] != "geodude":
                raise ValueError("held Throw needs its exact current Geodude")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == THROW_CARGO_FLEE:
            _shape(measurement, {"kind", "subject"}, label="Cargo Flee measurement")
            from tools.overworld.devtools_throw_cargo_flee_measurement import validate_recipe
            if measurement["subject"] != "cargo":
                raise ValueError("Cargo Flee needs its exact baby Cargo")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in BABY_FEAR_KINDS:
            _shape(measurement, {"kind", "subject"}, label="baby fear measurement")
            from tools.overworld.devtools_baby_fear_measurement import CASES, validate_recipe
            if measurement["subject"] != CASES[measurement["kind"]].get("subject", "baby"):
                raise ValueError("fear needs the exact current subject")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in (STOMP_SLAM, STOMP_SLAM_MOUNTED):
            _shape(measurement, {"kind", "subject"}, label="Stomp Slam measurement")
            from tools.overworld.devtools_stomp_slam_measurement import validate_recipe
            if measurement["subject"] != "snorlax":
                raise ValueError("Stomp Slam needs the exact current Snorlax")
            validate_recipe(value, measurement["kind"], "MOUNTED" if measurement["kind"] == STOMP_SLAM_MOUNTED else "FOLLOWER")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == RATTATA_LEDGE:
            _shape(measurement, {"kind", "subject"}, label="Rattata ledge measurement")
            from tools.overworld.devtools_mounted_rattata_ledge_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYFUL_HOPS:
            _shape(measurement, {"kind", "subject"}, label="Playful hop measurement")
            from tools.overworld.devtools_playful_hop_measurement import validate_recipe
            if measurement["subject"] != "clefairy":
                raise ValueError("Playful hops need the exact current Clefairy")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == THROW_COMPETITION:
            _shape(measurement, {"kind", "subject"}, label="Cargo competition measurement")
            from tools.overworld.devtools_throw_cargo_competition_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == THROW_RETARGET:
            _shape(measurement, {"kind", "subject"}, label="Cargo retarget measurement")
            from tools.overworld.devtools_throw_cargo_retarget_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == THROW_MUTUAL_PICKUP:
            _shape(measurement, {"kind", "subject"}, label="mutual pickup measurement")
            from tools.overworld.devtools_throw_mutual_pickup_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WILD_THROW_SOAK:
            _shape(measurement, {"kind", "subject"}, label="Wild Throw soak measurement")
            from tools.overworld.devtools_wild_throw_soak_measurement import validate_recipe
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == FOLLOWER_PRIORITY:
            _shape(measurement, {"kind", "subject"}, label="Follower priority measurement")
            from tools.overworld.devtools_follower_query_priority_measurement import validate_recipe
            if measurement["subject"] != "mankey":
                raise ValueError("Follower priority needs unchanged saved Mankey")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == DAMAGE_FOLLOWER:
            _shape(measurement, {"kind", "subject"}, label="Damage Follower measurement")
            from tools.overworld.devtools_damage_follower_measurement import validate_recipe
            if measurement["subject"] != "mankey":
                raise ValueError("Damage Follower subject differs")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == FOLLOWER_APPROACH:
            _shape(measurement, {"kind", "subject"}, label="Follower approach measurement")
            from tools.overworld.devtools_follower_throw_approach_measurement import validate_recipe
            if measurement["subject"] != "mankey":
                raise ValueError("Follower approach needs unchanged saved Mankey")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in (FOLLOWER_THROW, FOLLOWER_THROW_NON45):
            _shape(measurement, {"kind", "subject"}, label="Follower Throw measurement")
            from tools.overworld.devtools_follower_throw_measurement import validate_recipe
            if measurement["subject"] != "mankey":
                raise ValueError("Follower Throw needs current Mankey")
            validate_recipe(value)
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == WILD_THROW_MOVING:
            _shape(measurement, {"kind", "subjects"}, label="moving Wild Throw measurement")
            from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
                LIMIT, ORDER, PRE_WALK_LIMIT, SETUP,
            )
            if (value["id"] != "wild.throw-moving-candidate"
                    or value["mode"] != "prepared"
                    or measurement["subjects"] != ["stantler", "geodude"]
                    or value["subjects"] != [
                        {"id": "stantler", "species": 234, "role": "WILD", "acquire": "spawn"},
                        {"id": "geodude", "species": 74, "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "party", "spawn", "spawn", "bind", "spawn", "bind", "step"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != ["step"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"slot": 0, "species": 155, "level": 20}
                    or value["setup"][2]["args"] != {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20}
                    or value["setup"][3]["args"] != {"species": 234, "form": 0, "role": "wild", "level": 5,
                                                        "x": 585, "z": 403}
                    or value["setup"][4]["args"] != {"subject": "stantler"}
                    or value["setup"][7]["args"] != {"frames": PRE_WALK_LIMIT, "keys": [],
                        "until": {"kind": "actor-field", "subject": "stantler",
                                  "path": "motionKind", "operator": "eq", "value": "WALK", "when": "final"}}
                    or value["setup"][5]["args"] != {"species": 74, "form": 0, "role": "wild", "level": 5,
                                                        "x": 583, "z": 404}
                    or value["setup"][6]["args"] != {"subject": "geodude"}
                    or value["actions"][0]["args"] != {"frames": LIMIT, "keys": [],
                        "until": {"kind": "measurement-complete", "measurement": WILD_THROW_MOVING,
                                  "when": "final"}}
                    or value["budgets"]["minObservedFrames"] != 2
                    or value["budgets"]["maxFrames"] > 700):
                raise ValueError("moving Wild Throw needs its exact two actors and bounded Walk-to-Hop contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_MOUNTED_THROW:
            _shape(measurement, {"kind", "subjects"}, label="mounted Throw measurement")
            from tools.overworld.devtools_player_health_mounted_throw_measurement import (
                CROSS_FRAMES, LAUNCH_LIMIT, MIN_FRAMES, ORDER, SETUP, TRIGGER_LIMIT,
            )
            if (value["id"] != "player-hp.mounted-throw" or value["mode"] != "prepared"
                    or measurement["subjects"] != ["cyndaquil", "bellsprout", "geodude"]
                    or value["subjects"] != [
                        {"id": "cyndaquil", "species": 155, "role": "MOUNTED", "acquire": "existing"},
                        {"id": "bellsprout", "species": 69, "role": "WILD", "acquire": "spawn"},
                        {"id": "geodude", "species": 74, "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "party", "spawn", "step", "bind", "spawn", "bind", "step", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != [
                        "player-health.observe", "step", "player-health.observe", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 0}
                    or value["setup"][1]["args"] != {"slot": 0, "species": 155, "level": 10}
                    or value["setup"][2]["args"] != {"species": 155, "form": 0, "role": "mounted", "slot": 0, "level": 10}
                    or value["setup"][3]["args"] != {"frames": 16, "keys": []}
                    or value["setup"][4]["args"] != {"subject": "cyndaquil"}
                    or value["setup"][5]["args"] != {"species": 74, "form": 0, "role": "wild", "level": 5, "x": 585, "z": 404}
                    or value["setup"][6]["args"] != {"subject": "geodude"}
                    or value["setup"][7]["args"] != {"frames": TRIGGER_LIMIT, "keys": [],
                        "until": {"kind":"measurement-stage", "measurement":PLAYER_HEALTH_MOUNTED_THROW,
                                  "stage":"trigger-bound", "when":"final"}}
                    or value["setup"][8]["args"] != {"species": 69, "form": 0, "role": "wild", "level": 5, "x": 585, "z": 403}
                    or value["setup"][9]["args"] != {"subject": "bellsprout"}
                    or any(a["args"] != {} for a in value["actions"] if a["op"] == "player-health.observe")
                    or value["actions"][1]["args"] != {"frames": LAUNCH_LIMIT, "keys": [],
                        "until": {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_MOUNTED_THROW,
                                  "stage": "launched", "when": "final"}}
                    or value["actions"][3]["args"] != {"frames": CROSS_FRAMES, "keys": []}
                    or value["budgets"]["minObservedFrames"] != MIN_FRAMES
                    or value["budgets"]["maxFrames"] > 900):
                raise ValueError("mounted Throw needs its exact north rider and bounded flight contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_BAR:
            _shape(measurement, {"kind", "subject"}, label="player HP bar measurement")
            from tools.overworld.devtools_player_health_bar_measurement import (
                OBSERVED_FRAMES, ORDER, SETUP, STEPS,
            )
            if (value["id"] != "player-hp.bar" or value["mode"] != "prepared"
                    or measurement["subject"] != "onix"
                    or value["subjects"] != [{"id": "onix", "species": 95,
                                              "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != ["player-health.observe", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 95, "form": 0, "role": "wild",
                                                       "level": 5, "x": 585, "z": 412}
                    or value["setup"][2]["args"] != {"subject": "onix"}
                    or any(a["args"] != {} for a in value["setup"] + value["actions"]
                           if a["op"] == "player-health.observe")
                    or any(a["args"] != {"frames": STEPS[a["id"]],
                                           "keys": []}
                           for a in value["setup"] + value["actions"] if a["op"] == "step")
                    or value["budgets"]["minObservedFrames"] != OBSERVED_FRAMES
                    or value["budgets"]["maxFrames"] > 180):
                raise ValueError("HP bar needs its exact Onix and bounded Ram contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_RAM_WARNING:
            _shape(measurement, {"kind", "subject"}, label="player HP Ram warning measurement")
            from tools.overworld.devtools_player_health_ram_warning_measurement import (
                LIMITS, ORDER, SETUP,
            )
            if (value["id"] != "player-hp.ram-warning" or value["mode"] != "prepared"
                    or measurement["subject"] != "onix"
                    or value["subjects"] != [{"id": "onix", "species": 95,
                                              "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "spawn", "bind"]
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [a["op"] for a in value["actions"]] != ["step", "step", "player-health.observe"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 95, "form": 0, "role": "wild",
                                                       "level": 5, "x": 585, "z": 412}
                    or value["setup"][2]["args"] != {"subject": "onix"}
                    or value["actions"][0]["args"] != {"frames": LIMITS[ORDER[0]], "keys": [],
                        "until": {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_RAM_WARNING,
                                  "stage": "ram-active", "when": "final"}}
                    or value["actions"][1]["args"] != {"frames": LIMITS[ORDER[1]], "keys": [],
                        "until": {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_RAM_WARNING,
                                  "stage": "charge-started", "when": "final"}}
                    or value["actions"][2]["args"] != {}
                    or value["budgets"]["minObservedFrames"] != 2
                    or value["budgets"]["maxFrames"] > 360):
                raise ValueError("Ram warning needs its exact active Onix charge contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_SAVE_RELOAD:
            _shape(measurement, {"kind", "subject"}, label="player HP save/reload measurement")
            from tools.overworld.devtools_player_health_save_reload_measurement import (
                OBSERVED_FRAMES, ORDER, SETUP, STEPS,
            )
            expected_ops = {"before-save": "player-health.observe",
                            "before-reload": "player-health.observe",
                            "after-reload": "player-health.observe",
                            "wait-flash": "save.wait", "reload": "save.reload"}
            if (value["id"] != "player-hp.save-reload" or value["mode"] != "prepared"
                    or measurement["subject"] != "onix"
                    or value["subjects"] != [{"id": "onix", "species": 95,
                                               "role": "WILD", "acquire": "spawn"}]
                    or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["op"] for a in value["setup"]] != ["teleport", "spawn", "bind"]
                    or value["setup"][0]["args"] != {"map": 33, "x": 585, "z": 407, "facing": 1}
                    or value["setup"][1]["args"] != {"species": 95, "form": 0,
                                                       "role": "wild", "level": 5,
                                                       "x": 585, "z": 412}
                    or value["setup"][2]["args"] != {"subject": "onix"}
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or any(a["op"] != ("step" if a["id"] in STEPS else expected_ops[a["id"]])
                           for a in value["actions"])
                    or any(a["args"] != {"frames": STEPS[a["id"]][0],
                                           "keys": STEPS[a["id"]][1]}
                           for a in value["actions"] if a["id"] in STEPS)
                    or any(a["args"] != {} for a in value["actions"]
                           if a["op"] in ("player-health.observe", "save.reload"))
                    or value["budgets"]["minObservedFrames"] != OBSERVED_FRAMES
                    or value["budgets"]["maxFrames"] > 1800):
                raise ValueError("HP save/reload needs its exact Onix, Save, and bounded load contract")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == PLAYER_HEALTH_ZERO_LOAD:
            _shape(measurement, {"kind"}, label="zero-load HP measurement")
            from tools.overworld.devtools_player_health_zero_load_complete_measurement import SETUP, ORDER
            stage = lambda name: {"kind": "measurement-stage", "measurement": PLAYER_HEALTH_ZERO_LOAD,
                                  "stage": name, "when": "final"}
            free = stage("field-free")
            expected_setup = [
                ("wait", {"predicate": stage("message-ready")}, None),
                ("step", {"frames": 1, "keys": ["A"]}, None),
                ("step", {"frames": 12, "keys": []}, None),
                ("wait", {"predicate": stage("arrival-or-free")}, None),
                ("step", {"frames": 1, "keys": ["A"]}, free),
                ("step", {"frames": 12, "keys": []}, free),
                ("wait", {"predicate": stage("arrival-or-free")}, None),
                ("step", {"frames": 1, "keys": ["A"]}, free),
                ("step", {"frames": 12, "keys": []}, free),
                ("wait", {"predicate": free}, None),
            ]
            expected_actions = [("player-health.observe", {}),
                                ("step", {"frames": 16, "keys": ["UP"]}),
                                ("step", {"frames": 24, "keys": []}),
                                ("player-health.observe", {})]
            if (value["id"] != "player-hp.zero-load" or value["mode"] != "normal"
                    or value["fixture"] != {"rom": "test.nds", "save": "test.sav"}
                    or value["subjects"] or [a["id"] for a in value["setup"]] != list(SETUP)
                    or [a["id"] for a in value["actions"]] != list(ORDER)
                    or [(a["op"], a["args"], a.get("skipIf")) for a in value["setup"]] != expected_setup
                    or [(a["op"], a["args"]) for a in value["actions"]] != expected_actions
                    or any("skipIf" in a for a in value["actions"])
                    or value["budgets"]["maxFrames"] > 3000
                    or value["budgets"]["minObservedFrames"] < 53):
                raise ValueError("zero-load HP requires one private normal Continue and fixed input points")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == "actor-binding-context-v1":
            _shape(measurement, {"kind", "subject"}, label="binding measurement")
            if value["mode"] != "normal" or value["subjects"] != [{
                    "id": measurement["subject"], "species": 19, "role": "WILD", "acquire": "existing"}] \
                    or value["budgets"]["maxFrames"] > 900:
                raise ValueError("binding requires normal Wild Rattata and at most900 post-boot frames")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == RESOLVER_PARITY:
            _shape(measurement, {"kind"}, label="resolver measurement")
            if value["subjects"] or value["setup"] or value["mode"] != "prepared" \
                    or len(value["actions"]) != 1 or value["actions"][0]["op"] != "resolver.probe":
                raise ValueError("resolver parity requires one fixed prepared probe and no actor/setup detour")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == CONDITION_SERVICE:
            _shape(measurement, {"kind"}, label="condition service measurement")
            if value["subjects"] or value["setup"] or value["mode"] != "prepared" \
                    or len(value["actions"]) != 1 or value["actions"][0]["op"] != "condition.probe":
                raise ValueError("condition service requires one fixed prepared probe and no actor/setup detour")
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == ROUTE_CONTROL:
            _shape(measurement, {"kind", "subject", "setupTransitions"}, label="route control measurement")
            from tools.overworld.devtools_route_control_measurement import LiveRouteControlMeasurement
            if len(value["subjects"]) != 1 or value["subjects"][0]["id"] != measurement["subject"] \
                    or value["mode"] != "observer-control" or measurement["setupTransitions"] != []:
                raise ValueError("route control requires one observer subject and direct prepared setup")
            subject = value["subjects"][0]
            if (subject["species"], subject["role"], subject["acquire"]) != (155, "FOLLOWER", "existing") \
                    or [a["args"]["fault"] for a in value["actions"] if a["op"] == "observer-control"] \
                        != ["cpu-hitch", "player-start-stall"]:
                raise ValueError("route control requires the saved follower and one CPU/player fault pair")
            LiveRouteControlMeasurement(value, max_frames=value["budgets"]["maxFrames"], setup_transitions=[])
            continue
        if isinstance(measurement, dict) and measurement.get("kind") == "center-entry-exit-v1":
            _shape(measurement, {"kind", "setupTransitions"}, label="Center measurement")
            from tools.overworld.devtools_center_measurement import CenterEntryExitMeasurement
            CenterEntryExitMeasurement(value, max_frames=value["budgets"]["maxFrames"],
                                       setup_transitions=measurement["setupTransitions"])
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in ("unmounted-cadence-v1", "unmounted-game-cadence-v1", "cyndaquil-normal-setup-v1"):
            _shape(measurement, {"kind", "subject", "setupTransitions"}, label="cadence measurement")
            subject = next((item for item in value["subjects"] if item["id"] == measurement["subject"]), None)
            allowed_modes = ("normal", "prepared") if measurement["kind"] in ("unmounted-cadence-v1", "unmounted-game-cadence-v1") else ("normal",)
            if len(value["subjects"]) != 1 or subject is None or value["mode"] not in allowed_modes \
                    or (subject["species"], subject["role"], subject["acquire"]) != (155, "FOLLOWER", "existing"):
                raise ValueError("cadence requires one existing FOLLOWER Cyndaquil in the allowed setup mode")
            transitions = measurement["setupTransitions"]
            if not isinstance(transitions, list) or len(transitions) > 8:
                raise ValueError("cadence setup transitions must be a bounded list")
            from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
            from tools.overworld.devtools_cyndaquil_setup_measurement import CyndaquilNormalSetupMeasurement
            cls = (CyndaquilNormalSetupMeasurement if measurement["kind"] == "cyndaquil-normal-setup-v1"
                   else UnmountedCadenceMeasurement)
            cls(value, max_frames=value["budgets"]["maxFrames"], setup_transitions=transitions,
                **({"diagnostic_continue_host_hitches": (value.get("diagnosticContinueHostHitches", False)
                                                           or measurement["kind"] == "unmounted-game-cadence-v1"),
                    "accept_host_cpu_hitches": measurement["kind"] == "unmounted-game-cadence-v1"}
                   if measurement["kind"] in ("unmounted-cadence-v1", "unmounted-game-cadence-v1") else {}))
            continue
        if isinstance(measurement, dict) and measurement.get("kind") in PROFILE_FEATURE_MEASUREMENTS:
            _shape(measurement, {"kind", "subject"}, label="profile feature measurement")
            from tools.overworld.devtools_profile_feature_measurement import FEATURES
            config = FEATURES[measurement["kind"]]
            expected_subjects = [
                {"id": name, "species": species, "role": config.get("roles", {}).get(name, config.get("role", "WILD")),
                 "acquire": config.get("acquires", {}).get(name, config.get("acquire", "spawn"))}
                for name, species in config["subjects"]
            ]
            if value["mode"] != "prepared" or value["subjects"] != expected_subjects \
                    or measurement["subject"] != expected_subjects[0]["id"]:
                raise ValueError(
                    "profile feature measurement requires its exact prepared subjects")
            if measurement["kind"] == FOLLOWER_STOP:
                from tools.overworld.devtools_follower_stop_measurement import validate_recipe
                validate_recipe(value)
            elif measurement["kind"] == RAM_LEDGE:
                from tools.overworld.devtools_ram_ledge_measurement import validate_recipe
                validate_recipe(value)
            elif measurement["kind"] in (RAM_UNTIL_CRASH,RAM_BEHIND):
                from tools.overworld.devtools_ram_until_crash_measurement import validate_recipe
                validate_recipe(value)
            elif measurement["kind"] == RAM_BRIEF_NOTICE:
                from tools.overworld.devtools_ram_brief_notice_measurement import validate_recipe
                validate_recipe(value)
            elif measurement["kind"] == THROW_NOTICE_WALK_COMMIT:
                from tools.overworld.devtools_throw_notice_walk_commit_measurement import validate_recipe
                validate_recipe(value)
            elif measurement["kind"] == FOLLOWER_THROW_HIT_ABORT:
                from tools.overworld.devtools_follower_throw_hit_abort_measurement import validate_recipe
                validate_recipe(value)
            elif measurement["kind"] == BLOCKED_NOTICE_HOP:
                from tools.overworld.devtools_blocked_notice_hop_measurement import validate_recipe
                validate_recipe(value)
            continue
        _shape(measurement, {"kind", "subject"}, label="measurement")
        subject = next((item for item in value["subjects"] if item["id"] == measurement["subject"]), None)
        expected_mode = {"ledyba-chain-v1": "normal", "live-observer-control-v1": "observer-control",
                         CHAIN_RETRY: "prepared",
                         HEIGHT_CONTROL: "observer-control",
                         **dict.fromkeys(POOL_MEASUREMENTS, "normal")}.get(measurement["kind"])
        expected_species = 179 if measurement["kind"] == HEIGHT_CONTROL else 165
        if expected_mode is None or value["mode"] != expected_mode or not subject \
                or (subject["species"], subject["role"], subject["acquire"]) \
                    != (expected_species, "WILD", "spawn"):
            raise ValueError(
                "measurement requires its exact naturally acquired Wild subject and mode")
    predicates = value["assertions"] + [predicate for action in value["setup"] + value["actions"]
        for key in ("predicate", "until") if (predicate := action["args"].get(key)) is not None]
    predicates += [action["skipIf"] for action in value["setup"] if "skipIf" in action]
    declared = {item["kind"] for item in measurements}
    acceleration = next((m for m in measurements if m["kind"] == ACCELERATION), None)
    window, completed, intent_subject, intent_closed = None, set(), None, False
    for action in value["setup"] + value["actions"]:
        op = action["op"]
        if op.startswith("crash.") and not CRASH_KINDS.intersection(declared):
            raise ValueError("Crash action needs its exact measurement")
        if op.startswith("stomp.") and not ({TURN_SKID} | STOMP_KINDS).intersection(declared):
            raise ValueError("stomp action needs its exact measurement")
        if op.startswith("walk-matrix.") and not ({TURN_SKID} | MATRIX_KINDS).intersection(declared):
            raise ValueError("matrix action needs its exact measurement")
        if op.startswith("walk-corner.") and not CORNER_KINDS.intersection(declared):
            raise ValueError("corner action needs its exact measurement")
        if op.startswith("wild-walk.") and not {WILD_WALK,WILD_CLEAR_CONTROL}.intersection(declared):
            raise ValueError("wild Walk action needs its exact measurement")
        if op.startswith("wild-ledge.") and WILD_LEDGE not in declared:
            raise ValueError("wild ledge action needs its exact measurement")
        if (op.startswith("condition-controller.")
                and CONDITION_CONTROLLER not in declared):
            raise ValueError(
                "condition controller action needs its exact measurement")
        if op.startswith("mount-pacing.") and not {MOUNT_PACING, MOUNT_SPEED_SLEW, MOUNT_POSE_CONTROL}.intersection(declared):
            raise ValueError("mounted pacing action needs its exact measurement")
        if op.startswith("walk-policy-control.") and WALK_POLICY_CONTROL not in declared:
            raise ValueError("Walk reader control action needs its exact measurement")
        if op.startswith("acceleration."):
            if acceleration is None:
                raise ValueError("acceleration action needs its exact measurement")
            subject = action["args"]["subject"]
            if subject not in acceleration["subjects"].values():
                raise ValueError("acceleration action subject differs")
            if op == "acceleration.begin":
                if window is not None or subject in completed:
                    raise ValueError("acceleration windows overlap or repeat")
                window = subject
            else:
                if subject != window:
                    raise ValueError("acceleration end lacks its matching begin")
                completed.add(subject)
                window = None
        elif op == "walk-intent.arm":
            if acceleration is None or intent_subject is not None \
                    or action["args"]["subject"] != acceleration["subjects"]["WILD"] \
                    or window not in (None, action["args"]["subject"]):
                raise ValueError("Walk intent requires the acceleration Wild window")
            intent_subject = action["args"]["subject"]
        elif op == "walk-intent.close":
            if acceleration is None or intent_subject is None or intent_closed:
                raise ValueError("Walk intent close lacks its unique arm")
            intent_closed = True
        elif acceleration and window and op not in ("step", "wait", "assert"):
            raise ValueError("prepared mutation or bind inside acceleration window")
        if acceleration and ("skipIf" in action or op not in (
                "teleport", "party", "spawn", "bind", "step", "wait", "assert", "acceleration.begin", "acceleration.end",
                "walk-intent.arm", "walk-intent.close")):
            raise ValueError("unsupported acceleration setup action")
    if acceleration and (window is not None or completed != set(acceleration["subjects"].values())):
        raise ValueError("acceleration requires exactly two complete declared windows")
    if intent_subject is not None and not intent_closed:
        raise ValueError("Walk intent must have one authored close")
    if any(p["kind"] in ("acceleration-role-complete", "acceleration-role-started") and (acceleration is None
           or p["subject"] not in acceleration["subjects"].values()) for p in predicates):
        raise ValueError("role completion requires its acceleration measurement")
    if CHAIN_RETRY in declared:
        if measurements != [{"kind": CHAIN_RETRY, "subject": "ledyba"}] \
                or value["subjects"] != [{"id": "ledyba", "species": 165, "role": "WILD", "acquire": "spawn"}] \
                or [a["op"] for a in value["actions"]] != ["bind", "wait", "chain-retry", "wait"] \
                or any(a["op"] not in ("assert", "step", "wait") for a in value["setup"]) \
                or value["budgets"]["maxFrames"] > 6000:
            raise ValueError("chain retry requires natural acquisition and exactly one controlled start")
    if any(item["kind"] in ("measurement-complete", "measurement-stage") and item["measurement"] not in declared for item in predicates):
        raise ValueError("predicate requires a declared measurement")
    for action in value["actions"]:
        if action["op"] == "chain-retry" and CHAIN_RETRY not in declared:
            raise ValueError("chain retry requires its exact measurement")
        if action["op"] == "observer-control":
            required = ROUTE_CONTROL if action["args"]["fault"] in ("cpu-hitch", "player-start-stall") else "live-observer-control-v1"
            if required not in declared:
                raise ValueError("native fault action requires its exact control measurement")
    return value


def _handle(value):
    return tuple(value[key] for key in HANDLE_FIELDS)


def _actor_identity(value):
    return (value.get("species"), value.get("role"), value.get("subjectIdentity"))


class TestEvaluator:
    """Incremental checks; failures are append-only, success requires finish()."""
    def __init__(self, test):
        self.test = validate_test(test)
        self.specs = {item["id"]: item for item in self.test["subjects"]}
        self.subjects, self.failures = {}, []
        self.latest = None
        self.frames = 0
        self.sampled_frames = 0
        self.first_handles = None
        self.first_subjects = None
        self.events = Counter()
        self._prepared_attached = set()
        self.spawn_setup = None
        self.last_sequence = {}
        self.closed = False
        self._passed = False
        self.measurements = {}
        self.measurements_installed = False
        self._raw_frame = None
        self._raw_commands = set()
        self._raw_action_frames = Counter()
        self._acceleration_active = None
        self._acceleration_closed = set()
        self._acceleration_native_sequence = 0
        self._acceleration_intent = None
        self._acceleration_intent_direction = None
        self._acceleration_intent_subject = None
        self._acceleration_intent_closed = False
        self._unmounted_zero_stutter_profiles = []

    def install_measurements(self, inputs):
        if self.latest is not None or self.closed or self.measurements_installed:
            raise ValueError("measurement inputs can be installed only once before observation")
        from tools.overworld.devtools_chain_measurement import LedybaChainMeasurement
        from tools.overworld.devtools_chain_retry_measurement import ChainRetryMeasurement
        from tools.overworld.devtools_observer_control_measurement import LiveObserverControlMeasurement
        from tools.overworld.devtools_spawn_measurement import PoolSpawnMeasurement, PoolSpawnSurfaceMeasurement
        from tools.overworld.devtools_spawn_height_control_measurement import LiveSpawnHeightControlMeasurement
        for specification in self.test.get("measurements", []):
            kind = specification["kind"]
            source = inputs.get(kind)
            if kind == WARP_GATE:
                if source != {"contractVersion": 1}:
                    raise ValueError("warp gate contract input is missing")
                from tools.overworld.devtools_warp_gate_measurement import WarpGateMeasurement
                self.measurements[kind] = WarpGateMeasurement(self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNTED_TELEPORT_MATRIX:
                if source != {"contractVersion": 1}:
                    raise ValueError("Teleport matrix contract input is missing")
                from tools.overworld.devtools_mounted_teleport_matrix import MountedTeleportMatrixMeasurement
                self.measurements[kind] = MountedTeleportMatrixMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in CRASH_KINDS:
                from tools.overworld.devtools_crash_test_support import create_meter
                natural = create_meter(source, self.test["budgets"]["maxFrames"])
                if kind == CRASH:
                    self.measurements[kind] = natural
                else:
                    from tools.overworld.devtools_mounted_crash_control_measurement import MountedCrashControlMeasurement
                    self.measurements[kind] = MountedCrashControlMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in STOMP_KINDS:
                if source != {"contractVersion": 1}:
                    raise ValueError("stomp contract input is missing")
                if kind == STOMP:
                    from tools.overworld.devtools_stomp_measurement import StompMeasurement as Meter
                else:
                    from tools.overworld.devtools_stomp_control_measurement import StompControlMeasurement as Meter
                self.measurements[kind] = Meter(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == TURN_SKID:
                if source != {"contractVersion": 1}:
                    raise ValueError("turn-skid contract input is missing")
                from tools.overworld.devtools_turn_skid_measurement import TurnSkidMeasurement
                self.measurements[kind] = TurnSkidMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == WILD_BATTLE_HANDOFF:
                if source != {"contractVersion": 1}:
                    raise ValueError("Wild battle handoff contract input is missing")
                from tools.overworld.devtools_wild_battle_handoff_measurement import WildBattleHandoffMeasurement
                self.measurements[kind] = WildBattleHandoffMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in MATRIX_KINDS:
                if source != {"contractVersion": 1}:
                    raise ValueError("matrix contract input is missing")
                if kind == MATRIX:
                    from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement as Meter
                else:
                    from tools.overworld.devtools_walk_matrix_control_measurement import MatrixControlMeasurement as Meter
                self.measurements[kind] = Meter(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in CORNER_KINDS:
                if source != {"contractVersion": 1}:
                    raise ValueError("corner contract input is missing")
                if kind == CORNER:
                    from tools.overworld.devtools_corner_measurement import CornerMeasurement as Meter
                else:
                    from tools.overworld.devtools_corner_control_measurement import CornerControlMeasurement as Meter
                self.measurements[kind] = Meter(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in (WILD_WALK,WILD_CLEAR_CONTROL):
                if source != {"contractVersion": 1}:
                    raise ValueError("wild Walk contract input is missing")
                if kind == WILD_WALK:
                    from tools.overworld.devtools_wild_walk_measurement import WildWalkMeasurement as Meter
                else:
                    from tools.overworld.devtools_wild_clear_control_measurement import WildClearControlMeasurement as Meter
                self.measurements[kind] = Meter(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == WILD_LEDGE:
                if source != {"contractVersion": 1}:
                    raise ValueError("wild ledge contract input is missing")
                from tools.overworld.devtools_wild_ledge_measurement import WildLedgeMeasurement
                self.measurements[kind] = WildLedgeMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == CONDITION_CONTROLLER:
                if source != {"contractVersion": 1}:
                    raise ValueError(
                        "condition controller contract input is missing")
                from tools.overworld.devtools_condition_controller_measurement import (
                    ConditionControllerMeasurement,
                )
                self.measurements[kind] = ConditionControllerMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == WILD_TELEPORT:
                if source != {"contractVersion": 1}:
                    raise ValueError("wild Teleport contract input is missing")
                from tools.overworld.devtools_wild_teleport_measurement import WildTeleportMeasurement
                self.measurements[kind] = WildTeleportMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == RUNNER_STOP_SKID:
                if source != {"contractVersion": 1}:
                    raise ValueError("Runner stop-skid contract input is missing")
                from tools.overworld.devtools_runner_stop_skid_measurement import RunnerStopSkidMeasurement
                self.measurements[kind] = RunnerStopSkidMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == RUNNER_TURN_RUNWAY:
                if source != {"contractVersion": 1}:
                    raise ValueError("Runner turn-runway contract input is missing")
                from tools.overworld.devtools_runner_turn_runway_measurement import RunnerTurnRunwayMeasurement
                self.measurements[kind] = RunnerTurnRunwayMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == APPEAR_HOP:
                if source != {"contractVersion": 1}:
                    raise ValueError("Appear Hop contract input is missing")
                from tools.overworld.devtools_appear_hop_measurement import AppearHopMeasurement
                self.measurements[kind] = AppearHopMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in PROFILE_FEATURE_MEASUREMENTS:
                if source != {"contractVersion": 1}:
                    raise ValueError("profile feature contract input is missing")
                from tools.overworld.devtools_profile_feature_measurement import (
                    make_measurement,
                )
                self.measurements[kind] = make_measurement(
                    kind, self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind in SURFACE_REBIND_KINDS:
                if source != {"contractVersion": 1}:
                    raise ValueError("retained surface contract input is missing")
                from tools.overworld.devtools_wild_surface_rebind_measurement import WildSurfaceRebindMeasurement
                self.measurements[kind] = WildSurfaceRebindMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == WILD_TRANSITION:
                if source != {"contractVersion": 1}:
                    raise ValueError("Wild transition contract input is missing")
                from tools.overworld.devtools_wild_transition_measurement import WildTransitionMeasurement
                self.measurements[kind] = WildTransitionMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == FOLLOWER_TRANSITION:
                if source != {"contractVersion": 1}:
                    raise ValueError("Follower transition contract input is missing")
                from tools.overworld.devtools_follower_transition_measurement import FollowerTransitionMeasurement
                self.measurements[kind] = FollowerTransitionMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNTED_STREAMING:
                if source != {"contractVersion": 1}:
                    raise ValueError("mounted streaming contract input is missing")
                from tools.overworld.devtools_mounted_streaming_measurement import MountedStreamingMeasurement
                self.measurements[kind] = MountedStreamingMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNTED_CARDINAL_STREAMING:
                if source != {"contractVersion": 1}:
                    raise ValueError("cardinal streaming contract input is missing")
                from tools.overworld.devtools_mounted_cardinal_streaming_measurement import MountedCardinalStreamingMeasurement
                self.measurements[kind] = MountedCardinalStreamingMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNTED_WALK_TRANSITION:
                if source != {"contractVersion": 1}:
                    raise ValueError("mounted Walk transition contract input is missing")
                from tools.overworld.devtools_mounted_walk_transition_measurement import MountedWalkTransitionMeasurement
                self.measurements[kind] = MountedWalkTransitionMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == SENTRET_THROW:
                from tools.overworld.devtools_sentret_throw_measurement import SentretThrowMeasurement
                self.measurements[kind] = SentretThrowMeasurement(self.test, source)
                continue
            if kind == POPULATION_HEADROOM:
                from tools.overworld.devtools_population_headroom_measurement import PopulationHeadroomMeasurement
                self.measurements[kind] = PopulationHeadroomMeasurement(self.test, source)
                continue
            if kind in SPAWN_PRIORITY_KINDS:
                from tools.overworld.devtools_spawn_priority_measurement import SpawnPriorityMeasurement
                self.measurements[kind] = SpawnPriorityMeasurement(self.test, source)
                continue
            if kind == LAND_SURF:
                if source != {"contractVersion": 1}:
                    raise ValueError("land/surf contract input is missing")
                from tools.overworld.devtools_land_surf_measurement import LandSurfMeasurement
                self.measurements[kind] = LandSurfMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == SPAWN_WORK_BUDGET:
                _shape(source, {"schema", "sourceSha256"}, label="spawn-work source inputs")
                from tools.overworld.devtools_spawn_work_budget_measurement import SpawnWorkBudgetMeasurement
                self.measurements[kind] = SpawnWorkBudgetMeasurement(
                    self.test, source, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == UNMOUNTED_ZERO_STUTTER:
                _shape(source, {"schema", "sourceSha256"},
                       label="zero-stutter source inputs")
                from tools.overworld.devtools_unmounted_zero_stutter_measurement import UnmountedZeroStutterMeasurement
                self.measurements[kind] = UnmountedZeroStutterMeasurement(
                    self.test, source,
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == POPULATION_FAST_TRAVEL:
                if source != {"contractVersion": 1}:
                    raise ValueError("population fast-travel contract input is missing")
                from tools.overworld.devtools_population_fast_travel_measurement import PopulationFastTravelMeasurement
                self.measurements[kind] = PopulationFastTravelMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNT_POSE_CONTROL:
                if source != {"contractVersion": 1}:
                    raise ValueError("mounted pose control contract input is missing")
                from tools.overworld.devtools_mount_pose_control_measurement import MountedPoseControlMeasurement
                self.measurements[kind] = MountedPoseControlMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNT_PACING:
                if source != {"contractVersion": 1}:
                    raise ValueError("mounted pacing contract input is missing")
                from tools.overworld.devtools_mount_pacing_measurement import MountedPacingMeasurement
                self.measurements[kind] = MountedPacingMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNT_SPEED_SLEW:
                if source != {"contractVersion": 1}:
                    raise ValueError("mounted speed contract input is missing")
                from tools.overworld.devtools_mount_speed_slew_measurement import MountedSpeedSlewMeasurement
                self.measurements[kind] = MountedSpeedSlewMeasurement(
                    max_frames=self.test["budgets"]["maxFrames"], linear_ramp=specification.get("linearRamp"))
                continue
            if kind == MOUNT_CONTROL_STRESS:
                if source != {"contractVersion": 1}:
                    raise ValueError("mounted control stress contract input is missing")
                from tools.overworld.devtools_mount_control_stress import MountControlStressMeasurement
                self.measurements[kind] = MountControlStressMeasurement(
                    specification["contract"], max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == MOUNT_DETACH_FOLLOWER_RESUME:
                if source != {"contractVersion": 1}:
                    raise ValueError("mount detach follower resume contract input is missing")
                from tools.overworld.devtools_mount_detach_follower_resume import (
                    MountDetachFollowerResumeMeasurement,
                )
                self.measurements[kind] = MountDetachFollowerResumeMeasurement(
                    self.test, max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == WALK_POLICY_CONTROL:
                if source != {"contractVersion": 1}:
                    raise ValueError("Walk reader control contract input is missing")
                from tools.overworld.devtools_walk_policy_control_measurement import WalkPolicyControlMeasurement
                self.measurements[kind] = WalkPolicyControlMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == ACCELERATION:
                _shape(source, {"schema", "sourceSha256"}, label="acceleration source inputs")
                from tools.overworld.devtools_acceleration_measurement import AccelerationMeasurement
                self.measurements[kind] = AccelerationMeasurement(source["schema"], source["sourceSha256"],
                    max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == "actor-binding-context-v1":
                if source != {"contractVersion": 1}:
                    raise ValueError("binding context contract input is missing")
                from tools.overworld.devtools_binding_measurement import BindingMeasurement
                self.measurements[kind] = BindingMeasurement(max_frames=self.test["budgets"]["maxFrames"])
                continue
            if kind == RESOLVER_PARITY:
                if source != {"contractVersion": 1}:
                    raise ValueError("resolver raw-record contract input is missing")
                from tools.overworld.devtools_resolver_measurement import ResolverMeasurement
                self.measurements[kind] = ResolverMeasurement(self.test)
                continue
            if kind == CONDITION_SERVICE:
                if source != {"contractVersion": 1}:
                    raise ValueError("condition service raw-record contract input is missing")
                from tools.overworld.devtools_condition_measurement import ConditionMeasurement
                self.measurements[kind] = ConditionMeasurement(self.test)
                continue
            if kind == EMOTE_THREE:
                if source != {"contractVersion": 1}:
                    raise ValueError("emote burst raw-record contract input is missing")
                from tools.overworld.devtools_emote_three_measurement import EmoteThreeMeasurement
                self.measurements[kind] = EmoteThreeMeasurement(self.test)
                continue
            if kind == ACTOR_INSPECT:
                if source != {"contractVersion": 1}:
                    raise ValueError("actor Inspect raw-record contract input is missing")
                from tools.overworld.devtools_actor_inspect_measurement import ActorInspectMeasurement
                self.measurements[kind] = ActorInspectMeasurement(self.test)
                continue
            if kind in APPEARANCE_KINDS:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "romSha256", "overlaySha256", "profileSha256",
                        "capsuleElfSha256", "behaviorBlobSha256"} or source["contractVersion"] != 1:
                    raise ValueError("Pokémon palette source identity is missing")
                from tools.overworld.devtools_appearance_measurement import AppearanceMeasurement
                self.measurements[kind] = AppearanceMeasurement(kind, self.test, source)
                continue
            if kind in (POKEMON_COMBAT, POKEMON_SKID_HIT, FOLLOWER_RAM, BASIC_ATTACK):
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256", "profileSha256"} or source["contractVersion"] != 1:
                    raise ValueError("Pokémon combat source identity is missing")
                from tools.overworld.devtools_pokemon_combat_measurement import PokemonCombatMeasurement
                if kind == BASIC_ATTACK:
                    from tools.overworld.devtools_basic_attack_measurement import BasicAttackMeasurement
                    self.measurements[kind] = BasicAttackMeasurement(source, self.test)
                elif kind == FOLLOWER_RAM:
                    from tools.overworld.devtools_follower_ram_measurement import FollowerRamMeasurement
                    self.measurements[kind] = FollowerRamMeasurement(source, self.test)
                elif kind == POKEMON_SKID_HIT:
                    from tools.overworld.devtools_pokemon_skid_hit_measurement import PokemonSkidHitMeasurement
                    self.measurements[kind] = PokemonSkidHitMeasurement(source)
                else:
                    self.measurements[kind] = PokemonCombatMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_INITIAL:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP source identity is missing")
                from tools.overworld.devtools_player_health_initial_measurement import PlayerHealthInitialMeasurement
                self.measurements[kind] = PlayerHealthInitialMeasurement(self.test, source)
                continue
            if kind == PLAYER_HEALTH_RAM_REST:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP Ram/rest source identity is missing")
                from tools.overworld.devtools_player_health_ram_rest_measurement import PlayerHealthRamRestMeasurement
                self.measurements[kind] = PlayerHealthRamRestMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_RAM_LOW_SPEED:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP low-speed Ram source identity is missing")
                from tools.overworld.devtools_player_health_ram_low_speed_measurement import PlayerHealthRamLowSpeedMeasurement
                self.measurements[kind] = PlayerHealthRamLowSpeedMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_THROW:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP Throw source identity is missing")
                from tools.overworld.devtools_player_health_throw_contact_measurement import PlayerHealthThrowContactMeasurement
                self.measurements[kind] = PlayerHealthThrowContactMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_HOP:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256", "profileSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP Hop source identity is missing")
                from tools.overworld.devtools_player_health_hop_contact_measurement import PlayerHealthHopContactMeasurement
                self.measurements[kind] = PlayerHealthHopContactMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_RUNNING_HIT:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256", "profileSha256"} or source["contractVersion"] != 1:
                    raise ValueError("player HP running-hit source identity is missing")
                from tools.overworld.devtools_player_health_running_hit_measurement import PlayerHealthRunningHitMeasurement
                self.measurements[kind] = PlayerHealthRunningHitMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_AMBUSH_JUMP:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256", "profileSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP Ambush source identity is missing")
                from tools.overworld.devtools_player_health_ambush_jump_measurement import PlayerHealthAmbushJumpMeasurement
                self.measurements[kind] = PlayerHealthAmbushJumpMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256", "profileSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("mounted Ambush source identity is missing")
                from tools.overworld.devtools_player_health_mounted_ambush_height_measurement import PlayerHealthMountedAmbushHeightMeasurement
                self.measurements[kind] = PlayerHealthMountedAmbushHeightMeasurement(source)
                continue
            if kind in PLAYER_HEALTH_MOVING_KINDS:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="moving Player HP source")
                if source["contractVersion"] != 1: raise ValueError("moving Player HP source identity differs")
                from tools.overworld.devtools_player_health_moving_heal_measurement import PlayerHealthMovingHealMeasurement, MODES
                self.measurements[kind] = PlayerHealthMovingHealMeasurement(source, MODES[kind])
                continue
            if kind in TARGET_ACCESS_KINDS:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="target access source")
                from tools.overworld.devtools_target_access_measurement import TargetAccessMeasurement
                self.measurements[kind] = TargetAccessMeasurement(source, kind)
                continue
            if kind in CROSS_HEIGHT_KINDS:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="signed-height Throw source")
                from tools.overworld.devtools_cross_height_throw_measurement import CrossHeightThrowMeasurement
                self.measurements[kind] = CrossHeightThrowMeasurement(source, kind)
                continue
            if kind in DISTANCE_KINDS:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "helperAddress", "helperEntrySha256"}, label="distance source")
                if source["contractVersion"] != 1: raise ValueError("distance source version differs")
                from tools.overworld.devtools_distance_despawn_measurement import DistanceDespawnMeasurement
                self.measurements[kind] = DistanceDespawnMeasurement(self.test,source)
                continue
            if kind == HELD_THROW_SEARCH:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="held Throw source")
                from tools.overworld.devtools_held_throw_search_measurement import HeldThrowSearchMeasurement
                self.measurements[kind] = HeldThrowSearchMeasurement(source)
                continue
            if kind == THROW_CARGO_FLEE:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="Cargo Flee source")
                if source["contractVersion"] != 1:
                    raise ValueError("Cargo Flee source identity differs")
                from tools.overworld.devtools_throw_cargo_flee_measurement import ThrowCargoFleeMeasurement
                self.measurements[kind] = ThrowCargoFleeMeasurement(source)
                continue
            if kind in BABY_FEAR_KINDS:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="baby fear source")
                if source["contractVersion"] != 1:
                    raise ValueError("baby fear source identity differs")
                from tools.overworld.devtools_baby_fear_measurement import BabyFearMeasurement
                self.measurements[kind] = BabyFearMeasurement(kind, source)
                continue
            if kind in (STOMP_SLAM, STOMP_SLAM_MOUNTED, RATTATA_LEDGE):
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="mounted contact/ledge source")
                if source["contractVersion"] != 1:
                    raise ValueError("mounted contact/ledge source identity differs")
                if kind == RATTATA_LEDGE:
                    from tools.overworld.devtools_mounted_rattata_ledge_measurement import MountedRattataLedgeMeasurement
                    self.measurements[kind] = MountedRattataLedgeMeasurement(source)
                else:
                    from tools.overworld.devtools_stomp_slam_measurement import StompSlamMeasurement
                    self.measurements[kind] = StompSlamMeasurement(source, kind=kind,
                        passive_role="MOUNTED" if kind == STOMP_SLAM_MOUNTED else "FOLLOWER")
                continue
            if kind == PLAYFUL_HOPS:
                _shape(source, {"contractVersion", "romSha256", "overlaySha256", "profileSha256"}, label="Playful hop source")
                if source["contractVersion"] != 1:
                    raise ValueError("Playful hop source identity differs")
                from tools.overworld.devtools_playful_hop_measurement import PlayfulHopMeasurement
                self.measurements[kind] = PlayfulHopMeasurement(source)
                continue
            if kind in (FOLLOWER_THROW, FOLLOWER_THROW_NON45, FOLLOWER_APPROACH, DAMAGE_FOLLOWER, FOLLOWER_PRIORITY, WILD_THROW_MOVING, WILD_THROW_SOAK, THROW_COMPETITION, THROW_RETARGET, THROW_MUTUAL_PICKUP):
                fields = {"contractVersion", "romSha256", "overlaySha256", "profileSha256", "queryImage"}
                if kind == WILD_THROW_SOAK: fields |= {"helperAddress", "helperEntrySha256"}
                _shape(source, fields,
                       label="Throw route source")
                _shape(source["queryImage"], {"elfSha256", "packageSha256"}, label="Throw route image")
                if source["contractVersion"] != 2 or any(not isinstance(value, str) or len(value) != 64
                        or any(c not in "0123456789abcdef" for c in value)
                        for value in source["queryImage"].values()):
                    raise ValueError("Throw route source identity differs")
                if kind == THROW_COMPETITION:
                    from tools.overworld.devtools_throw_cargo_competition_measurement import ThrowCargoCompetitionMeasurement
                    self.measurements[kind] = ThrowCargoCompetitionMeasurement(source)
                elif kind == THROW_RETARGET:
                    from tools.overworld.devtools_throw_cargo_retarget_measurement import ThrowCargoRetargetMeasurement
                    self.measurements[kind] = ThrowCargoRetargetMeasurement(source)
                elif kind == THROW_MUTUAL_PICKUP:
                    from tools.overworld.devtools_throw_mutual_pickup_measurement import ThrowMutualPickupMeasurement
                    self.measurements[kind] = ThrowMutualPickupMeasurement(source)
                elif kind == WILD_THROW_SOAK:
                    from tools.overworld.devtools_wild_throw_soak_measurement import WildThrowSoakMeasurement
                    self.measurements[kind] = WildThrowSoakMeasurement(source)
                elif kind == FOLLOWER_PRIORITY:
                    from tools.overworld.devtools_follower_query_priority_measurement import FollowerQueryPriorityMeasurement
                    self.measurements[kind] = FollowerQueryPriorityMeasurement(source)
                elif kind == DAMAGE_FOLLOWER:
                    from tools.overworld.devtools_damage_follower_measurement import DamageFollowerMeasurement
                    self.measurements[kind] = DamageFollowerMeasurement(source)
                elif kind == FOLLOWER_APPROACH:
                    from tools.overworld.devtools_follower_throw_approach_measurement import FollowerThrowApproachMeasurement
                    self.measurements[kind] = FollowerThrowApproachMeasurement(source)
                elif kind in (FOLLOWER_THROW, FOLLOWER_THROW_NON45):
                    from tools.overworld.devtools_follower_throw_measurement import FollowerThrowMeasurement
                    self.measurements[kind] = FollowerThrowMeasurement(source, feature=kind)
                else:
                    from tools.overworld.devtools_wild_throw_moving_candidate_measurement import WildThrowMovingCandidateMeasurement
                    self.measurements[kind] = WildThrowMovingCandidateMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_MOUNTED_THROW:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("mounted player HP Throw source identity is missing")
                from tools.overworld.devtools_player_health_mounted_throw_measurement import PlayerHealthMountedThrowMeasurement
                self.measurements[kind] = PlayerHealthMountedThrowMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_BAR:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP bar source identity is missing")
                from tools.overworld.devtools_player_health_bar_measurement import PlayerHealthBarMeasurement
                self.measurements[kind] = PlayerHealthBarMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_RAM_WARNING:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("Ram warning source identity is missing")
                from tools.overworld.devtools_player_health_ram_warning_measurement import PlayerHealthRamWarningMeasurement
                self.measurements[kind] = PlayerHealthRamWarningMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_SAVE_RELOAD:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("player HP save/reload source identity is missing")
                from tools.overworld.devtools_player_health_save_reload_measurement import PlayerHealthSaveReloadMeasurement
                self.measurements[kind] = PlayerHealthSaveReloadMeasurement(source)
                continue
            if kind == PLAYER_HEALTH_ZERO_LOAD:
                if not isinstance(source, dict) or set(source) != {
                        "contractVersion", "overlaySha256", "romSha256", "sourceSaveSha256"} \
                        or source["contractVersion"] != 1:
                    raise ValueError("zero-load HP source identity is missing")
                from tools.overworld.devtools_player_health_zero_load_complete_measurement import PlayerHealthZeroLoadMeasurement
                self.measurements[kind] = PlayerHealthZeroLoadMeasurement(source)
                continue
            if kind in RAW_MEASUREMENTS:
                if source != {"contractVersion": 1}:
                    raise ValueError("cadence raw-record contract input is missing")
                from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
                from tools.overworld.devtools_center_measurement import CenterEntryExitMeasurement
                from tools.overworld.devtools_cyndaquil_setup_measurement import CyndaquilNormalSetupMeasurement
                from tools.overworld.devtools_route_control_measurement import LiveRouteControlMeasurement
                cls = {"unmounted-cadence-v1": UnmountedCadenceMeasurement,
                       "unmounted-game-cadence-v1": UnmountedCadenceMeasurement,
                       "center-entry-exit-v1": CenterEntryExitMeasurement,
                       "cyndaquil-normal-setup-v1": CyndaquilNormalSetupMeasurement,
                       ROUTE_CONTROL: LiveRouteControlMeasurement}[kind]
                self.measurements[kind] = cls(self.test,
                    max_frames=self.test["budgets"]["maxFrames"], setup_transitions=specification["setupTransitions"],
                    **({"diagnostic_continue_host_hitches": (self.test.get("diagnosticContinueHostHitches", False)
                                                               or kind == "unmounted-game-cadence-v1"),
                        "accept_host_cpu_hitches": kind == "unmounted-game-cadence-v1"}
                       if kind in ("unmounted-cadence-v1", "unmounted-game-cadence-v1") else {}))
                continue
            required = {"schema", "sourceSha256"} | ({"authoredProfiles"} if kind in PROFILE_MEASUREMENTS else set())
            if not isinstance(source, dict) or set(source) != required \
                    or (kind in PROFILE_MEASUREMENTS and not isinstance(source["authoredProfiles"], dict)):
                raise ValueError("current measurement source inputs are missing")
            cls = {"ledyba-chain-v1": LedybaChainMeasurement,
                   CHAIN_RETRY: ChainRetryMeasurement,
                   "live-observer-control-v1": LiveObserverControlMeasurement,
                   HEIGHT_CONTROL: LiveSpawnHeightControlMeasurement,
                   "pool-spawn-v1": PoolSpawnMeasurement,
                   "pool-spawn-surface-v1": PoolSpawnSurfaceMeasurement}[kind]
            self.measurements[kind] = cls(source["schema"], source["sourceSha256"],
                max_frames=self.test["budgets"]["maxFrames"] + 1,
                **({"authored_profiles": source["authoredProfiles"]} if kind in PROFILE_MEASUREMENTS else {}))
        self.measurements_installed = True

    @property
    def uses_raw_records(self):
        return bool(RAW_MEASUREMENTS.intersection(self.measurements))

    def observe_record(self, record, *, frame_callback=None, full_report=True):
        """One shared live/replay path. Meter and assertions advance one frame at a time.

        The meter validates the physical chunk before invoking a callback at
        each exact frame. Later readiness must never rescue an earlier failure.
        """
        if not self.uses_raw_records:
            raise ValueError("raw records require the installed cadence measurement")
        if self.closed or self.failures:
            return self.result(full_report=full_report)
        meter_kind = next(kind for kind in self.measurements if kind in RAW_MEASUREMENTS)
        meter = self.measurements[meter_kind]
        try:
            if meter_kind in (SENTRET_THROW, POPULATION_HEADROOM):
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted, on_events=self._events)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                else:
                    self._prepared_attached.update(_handle(v["handle"]) for n,v in meter.subjects.items()
                                                   if n != "mankey")
                    if record.get("command") == "bind":
                        action = next(a for a in self.test["setup"] + self.test["actions"] if a["id"] == record["action"])
                        if self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                            self.fail("subject-binding-differs", "full current subject binding differs")
                if record.get("snapshot") is not None:
                    self.latest = deepcopy(record["snapshot"])
                elif record.get("initialSnapshot") is not None:
                    self.latest = deepcopy(record["initialSnapshot"])
                return self.result(full_report=full_report)
            if meter_kind in SPAWN_PRIORITY_KINDS:
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "bind":
                    if self.bind("mankey", record["snapshot"]) != record["receipt"]:
                        raise ValueError("natural spawn current follower binding differs")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                elif (record.get("command") == "teleport" and (
                        record.get("phase") == "setup" and record.get("action") == "natural-window"
                        or meter_kind == "natural-refill-retry-v1" and record.get("phase") == "observe"
                        and record.get("action") == "route29-window")):
                    old = self.subjects.get("mankey")
                    warmup = (meter.warmup_boundary if record.get("phase") == "setup"
                              else meter.window_transition)["subject"]
                    if (old is None or old["handle"] != warmup["handle"]
                            or old["subjectIdentity"] != meter.warmup_identity
                            or (old["species"], old["role"]) != (56, "FOLLOWER")):
                        raise ValueError("natural spawn warp lacks its exact old follower binding")
                    # The meter accepted this one declared different-field warp.
                    # The next bind must select the same saved follower afresh.
                    del self.subjects["mankey"]
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                return self.result(full_report=full_report)
            if meter_kind in (THROW_COMPETITION, THROW_RETARGET, THROW_MUTUAL_PICKUP):
                if meter_kind == THROW_COMPETITION:
                    from tools.overworld.devtools_throw_cargo_competition_measurement import SETUP
                elif meter_kind == THROW_MUTUAL_PICKUP:
                    from tools.overworld.devtools_throw_mutual_pickup_measurement import SETUP
                else:
                    from tools.overworld.devtools_throw_cargo_retarget_measurement import SETUP
                if "initialSnapshot" in record:
                    snapshot=record["initialSnapshot"]
                    self.first_handles={_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects={_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command")=="spawn" and record.get("action")!="create-passive-follower":
                    args=next(args for name,op,args in SETUP if name==record["action"] and op=="spawn")
                    prepared=_wild_spawn_setup(record["receipt"],record["snapshot"],species=args["species"],
                                               locomotion=0 if args["species"]==70 else 7)
                    self.spawn_setup = prepared
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command")=="bind":
                    name=next(args["subject"] for name,op,args in SETUP if name==record["action"] and op=="bind")
                    if self.bind(name,record["snapshot"]) != record["receipt"]:
                        raise ValueError("Cargo selection bind differs from current full actor")
                def accepted(sample,frames):
                    self.latest=deepcopy(sample);self.frames=self.sampled_frames=frames
                    if frame_callback is not None:frame_callback(sample,self)
                measured=meter.observe_record(record,on_sample=accepted)
                if measured["failures"]:self.fail("measurement-failed",meter_kind,measured["failures"])
                snapshot=record.get("snapshot",record.get("initialSnapshot"))
                if snapshot is not None:self.latest=deepcopy(snapshot)
                self.frames=self.sampled_frames=measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == WILD_THROW_SOAK:
                from tools.overworld.devtools_wild_throw_soak_measurement import SETUP
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") != "create-passive":
                    args = next(args for name,op,args in SETUP if name == record["action"] and op == "spawn")
                    self.spawn_setup = _wild_spawn_setup(record["receipt"], record["snapshot"],
                        species=args["species"], locomotion=0 if args["species"] == 70 else 7)
                    self._prepared_attached.add(_handle(self.spawn_setup["subject"]["handle"]))
                elif record.get("command") == "bind":
                    name = next(args["subject"] for name,op,args in SETUP if name == record["action"] and op == "bind")
                    if self.bind(name, record["snapshot"]) != record["receipt"]:
                        raise ValueError("Wild Throw soak bind differs from exact native spawn")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample); self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in SURFACE_REBIND_KINDS:
                self._observe_surface_rebind_record(record, meter, frame_callback)
                return self.result(full_report=full_report)
            if meter_kind == WARP_GATE:
                self._observe_walk_policy_control_record(record, frame_callback=frame_callback, meter_kind=meter_kind)
                return self.result(full_report=full_report)
            if meter_kind in RAW_BOUNDARY_MEASUREMENTS:
                self._observe_walk_policy_control_record(record, frame_callback=frame_callback, meter_kind=meter_kind)
                return self.result(full_report=full_report)
            if meter_kind == ACCELERATION:
                self._observe_acceleration_record(record, frame_callback=frame_callback)
                return self.result(full_report=full_report)
            if meter_kind == ACTOR_INSPECT:
                if not isinstance(record, dict):
                    raise ValueError("actor Inspect raw record must be an object")
                if "initialSnapshot" in record and self.latest is not None:
                    raise ValueError("duplicate actor Inspect initial boundary")
                if record.get("command") == "bind":
                    if self.latest is None or record.get("snapshot") != self.latest:
                        raise ValueError("actor Inspect bind is not the current boundary")
                    subject = self.test["measurements"][0]["subject"]
                    bound = self.bind(subject, record["snapshot"])
                    if record.get("receipt") != bound:
                        raise ValueError("actor Inspect bind differs from the exact subject")
                measured = meter.observe_record(record)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("boundarySnapshot", record.get("initialSnapshot")))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == PLAYER_HEALTH_INITIAL:
                if not isinstance(record, dict):
                    raise ValueError("player HP raw record must be an object")
                measured = meter.observe_record(record)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("boundarySnapshot",
                                                      record.get("initialSnapshot")))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in (PLAYER_HEALTH_RAM_REST, PLAYER_HEALTH_RAM_LOW_SPEED):
                if not isinstance(record, dict):
                    raise ValueError("player HP Ram/rest raw record must be an object")
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"]
                                          if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"]
                                           if a.get("active") is True}
                elif record.get("command") == "spawn":
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                 species=95, locomotion=7)
                    self.spawn_setup = prepared
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    if self.bind("onix", record["snapshot"]) != record["receipt"]:
                        raise ValueError("Ram Onix bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = frames
                    self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("boundarySnapshot",
                                                      record.get("initialSnapshot")))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in APPEARANCE_KINDS:
                if not isinstance(record, dict):
                    raise ValueError("Pokémon palette raw record must be an object")
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") in (
                        "spawn-snorlax", "spawn-weepinbell", "spawn-onix"):
                    expected = {"spawn-snorlax":(143,7), "spawn-weepinbell":(70,0), "spawn-onix":(95,7)}[record["action"]]
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                 species=expected[0], locomotion=expected[1])
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next((a for a in self.test["setup"]+self.test["actions"]
                                   if a["id"] == record.get("action") and a["op"] == "bind"), None)
                    if action is None or self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("Pokémon palette bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in PLAYER_HEALTH_MOVING_KINDS:
                if "initialSnapshot" in record:
                    snapshot=record["initialSnapshot"]
                    self.first_handles={_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects={_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command")=="spawn" and record.get("action") not in ("create-mounted", "create-follower"):
                    species=70 if record["action"]=="spawn-weepinbell" else int(record["action"].rsplit("-",1)[1])
                    prepared=_wild_spawn_setup(record["receipt"],record["snapshot"],species=species,locomotion=0 if species==70 else 7)
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command")=="bind":
                    name=next(a["args"]["subject"] for a in self.test["setup"] if a["id"]==record["action"] and a["op"]=="bind")
                    if self.bind(name,record["snapshot"]) != record["receipt"]: raise ValueError("moving-heal bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest=deepcopy(sample);self.frames=self.sampled_frames=frames
                    if frame_callback is not None: frame_callback(sample,self)
                measured=meter.observe_record(record,on_sample=accepted)
                if measured["failures"]:self.fail("measurement-failed",meter_kind,measured["failures"])
                snapshot=record.get("snapshot",record.get("initialSnapshot"))
                if snapshot is not None:self.latest=deepcopy(snapshot)
                self.frames=self.sampled_frames=measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in TARGET_ACCESS_KINDS:
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") == "spawn-target":
                    from tools.overworld.devtools_target_access_measurement import CASES
                    species = CASES[meter_kind]["species"]
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                        species=species, locomotion=9 if species == 16 else 7)
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    if self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("target access bind differs from exact current actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in BABY_FEAR_KINDS:
                from tools.overworld.devtools_baby_fear_measurement import CASES
                case = CASES[meter_kind]
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") in ("spawn-baby", "spawn-snorlax", "spawn-threat"):
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    if action["args"]["role"] == "wild":
                        prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                            species=action["args"]["species"], locomotion=0 if action["args"]["species"] == 70
                            else 4 if meter_kind == "baby-wild-igglybuff-cry-v1" else 7)
                        self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    if self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("baby fear bind differs from the current actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in (STOMP_SLAM, STOMP_SLAM_MOUNTED, RATTATA_LEDGE):
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") in ("spawn-snorlax",):
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                        species=action["args"]["species"], locomotion=7)
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    if self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("Stomp Slam bind differs from the current actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == PLAYFUL_HOPS:
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") in ("spawn-clefairy", "spawn-clefable"):
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                        species=action["args"]["species"], locomotion=7)
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next(a for a in self.test["setup"] if a["id"] == record["action"])
                    if self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("Playful hop bind differs from the current actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in (FOLLOWER_THROW, FOLLOWER_THROW_NON45, FOLLOWER_APPROACH, DAMAGE_FOLLOWER, FOLLOWER_PRIORITY, THROW_CARGO_FLEE, HELD_THROW_SEARCH, *DISTANCE_KINDS, *CROSS_HEIGHT_KINDS):
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") in ("spawn-trigger", "spawn-cargo", "spawn-alternative", "spawn-geodude", "spawn-mareep", "spawn-carrier", "spawn-unrelated", "spawn-source", "spawn-old-geodude"):
                    if meter_kind in CROSS_HEIGHT_KINDS:
                        from tools.overworld.devtools_cross_height_throw_measurement import CASES
                        signed_case = CASES[meter_kind]
                    species = ({"spawn-trigger":signed_case["trigger"],"spawn-cargo":signed_case["cargo"]} if meter_kind in CROSS_HEIGHT_KINDS
                               else {"spawn-cargo":179,"spawn-carrier":74,"spawn-unrelated":143} if meter_kind in DISTANCE_KINDS
                               else {"spawn-geodude":74,"spawn-mareep":179} if meter_kind == HELD_THROW_SEARCH
                               else {"spawn-cargo":173,"spawn-geodude":74} if meter_kind == THROW_CARGO_FLEE
                               else {"spawn-cargo":69,"spawn-alternative":43} if meter_kind == FOLLOWER_APPROACH
                               else {"spawn-source":74,"spawn-old-geodude":74} if meter_kind == FOLLOWER_PRIORITY
                               else {"spawn-source":70} if meter_kind == DAMAGE_FOLLOWER
                               else {"spawn-trigger":69} if meter_kind in (FOLLOWER_THROW, FOLLOWER_THROW_NON45)
                               else {"spawn-trigger":69,"spawn-cargo":43})[record["action"]]
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                        species=species, locomotion=(0 if species==70 else 3 if species==161 else 7)
                        if meter_kind in CROSS_HEIGHT_KINDS else 0 if meter_kind == DAMAGE_FOLLOWER else 7)
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                    if meter_kind == FOLLOWER_PRIORITY:
                        # Both registered subjects are Geodude. Bind to this
                        # command's matched full encounter, not every new one.
                        self.spawn_setup = prepared
                elif record.get("command") == "bind":
                    action = next((a for a in self.test["setup"] if a["id"] == record.get("action") and a["op"] == "bind"), None)
                    if action is None or self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("Follower Throw bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = self.sampled_frames = frames
                    if frame_callback is not None: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if (meter_kind == HELD_THROW_SEARCH and record.get("command") == "held-throw-pocket.prepare"
                        and not measured["failures"]):
                    # The leaf proved the same handle/PID through normal Select
                    # and completed Hop; use its current returned Follower owner.
                    self.subjects["stantler"] = deepcopy(measured["subjects"]["stantler"])
                if measured["failures"]: self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None: self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in (POKEMON_COMBAT, POKEMON_SKID_HIT, FOLLOWER_RAM, BASIC_ATTACK):
                if not isinstance(record, dict):
                    raise ValueError("Pokémon combat raw record must be an object")
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"]
                                          if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"]
                                           if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") not in ("mount-cyndaquil", "mount-stantler", "spawn-onix") \
                        and not (meter_kind == BASIC_ATTACK and record.get("action") == "spawn-passive"):
                    expected_spawns = {"spawn-snorlax": (143, 7), "spawn-weepinbell": (70, 0)}
                    if meter_kind == BASIC_ATTACK:
                        expected_spawns = {"spawn-snorlax": (143, 7), "spawn-cyndaquil": (155, 7)}
                    elif meter_kind == POKEMON_SKID_HIT:
                        from tools.overworld.devtools_pokemon_skid_hit_measurement import FILLERS
                        # These Meander/Waddle fillers inherit default Appear
                        # Hop7. Ambush explicitly starts Weepinbell at None0.
                        expected_spawns = {"spawn-filler-"+str(s): (s, 7) for s in FILLERS}
                        expected_spawns["spawn-weepinbell"] = (70, 0)
                    expected = expected_spawns.get(record.get("action"))
                    if expected is None:
                        raise ValueError("Pokémon combat spawn action differs")
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                 species=expected[0], locomotion=expected[1])
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next((a for a in self.test["setup"]
                                   if a["id"] == record.get("action") and a["op"] == "bind"), None)
                    if action is None or self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("Pokémon combat bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = frames
                    self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in (PLAYER_HEALTH_THROW, PLAYER_HEALTH_HOP, PLAYER_HEALTH_AMBUSH_JUMP, PLAYER_HEALTH_RUNNING_HIT, PLAYER_HEALTH_MOUNTED_AMBUSH_HEIGHT, PLAYER_HEALTH_MOUNTED_THROW,
                              WILD_THROW_MOVING):
                if not isinstance(record, dict):
                    raise ValueError("player HP Throw raw record must be an object")
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"]
                                          if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"]
                                           if a.get("active") is True}
                elif record.get("command") == "spawn" and record.get("action") != "mount-cyndaquil" \
                        and not (meter_kind == WILD_THROW_MOVING and record.get("action") == "create-passive-follower"):
                    if meter_kind == PLAYER_HEALTH_HOP:
                        prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                     species=56, locomotion=7)
                    elif meter_kind == WILD_THROW_MOVING \
                            and record.get("action") == "spawn-stantler":
                        from tools.overworld.devtools_wild_throw_moving_candidate_measurement import verify_wander_spawn
                        prepared = verify_wander_spawn(
                            record["receipt"], record["snapshot"])
                    else:
                        if meter_kind == PLAYER_HEALTH_MOUNTED_THROW and record.get("action") == "spawn-bellsprout":
                            species, locomotion = 69, 7
                        else:
                            species, locomotion = ((70, 0) if record.get("action") == "spawn-weepinbell"
                                                   else (74, 7))
                        prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                     species=species, locomotion=locomotion)
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    subject = {"bind-mankey": "mankey", "bind-cyndaquil": "cyndaquil", "bind-mareep": "mareep",
                               "bind-weepinbell": "weepinbell",
                               "bind-geodude": "geodude"}.get(record.get("action"))
                    if meter_kind == PLAYER_HEALTH_MOUNTED_THROW and record.get("action") == "bind-bellsprout":
                        subject = "bellsprout"
                    if meter_kind == WILD_THROW_MOVING and record.get("action") == "bind-stantler":
                        subject = "stantler"
                    if subject is None:
                        raise ValueError("Throw actor bind action differs")
                    if self.bind(subject, record["snapshot"]) != record["receipt"]:
                        raise ValueError("Throw actor bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = frames
                    self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("boundarySnapshot",
                                                      record.get("initialSnapshot")))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind in (PLAYER_HEALTH_BAR, PLAYER_HEALTH_RAM_WARNING):
                if not isinstance(record, dict):
                    raise ValueError("player HP bar raw record must be an object")
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"]
                                          if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"]
                                           if a.get("active") is True}
                elif record.get("command") == "spawn":
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                 species=95, locomotion=7)
                    self.spawn_setup = prepared
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    if self.bind("onix", record["snapshot"]) != record["receipt"]:
                        raise ValueError("bar Onix bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = frames
                    self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("boundarySnapshot",
                                                      record.get("initialSnapshot")))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == PLAYER_HEALTH_SAVE_RELOAD:
                if not isinstance(record, dict):
                    raise ValueError("player HP save/reload raw record must be an object")
                if "initialSnapshot" in record:
                    snapshot = record["initialSnapshot"]
                    self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"]
                                          if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in snapshot["actors"]
                                           if a.get("active") is True}
                elif record.get("command") == "spawn":
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"],
                                                 species=95, locomotion=7)
                    self.spawn_setup = prepared
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    if self.bind("onix", record["snapshot"]) != record["receipt"]:
                        raise ValueError("save Onix bind differs from current live actor")
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = frames
                    self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                if record.get("command") == "save.reload" and not self.failures:
                    self.save_reloads = getattr(self, "save_reloads", 0) + 1
                return self.result(full_report=full_report)
            if meter_kind == PLAYER_HEALTH_ZERO_LOAD:
                def accepted(sample, frames):
                    self.latest = deepcopy(sample)
                    self.frames = frames
                    self.sampled_frames = frames
                    if frame_callback is not None:
                        frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == RESOLVER_PARITY:
                if not isinstance(record, dict):
                    raise ValueError("resolver raw record must be an object")
                if record.get("command") is not None:
                    action = self.test["actions"][0]
                    if record.get("command") != "resolver.probe" or record.get("phase") != "observe" \
                            or record.get("action") != action["id"] or self.latest is None:
                        raise ValueError("resolver receipt must name its exact declared action")
                elif "initialSnapshot" in record:
                    if self.latest is not None:
                        raise ValueError("duplicate resolver initial boundary")
                elif "boundarySnapshot" not in record:
                    raise ValueError("unexpected resolver raw record")
                measured = meter.observe_record(record)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("boundarySnapshot", record.get("initialSnapshot")))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                # This controlled service contract measures native cycles that
                # contain its seven calls, not rendered frames or boot padding.
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == EMOTE_THREE:
                if "initialSnapshot" in record:
                    self.first_handles = {_handle(a["handle"]) for a in record["initialSnapshot"]["actors"] if a.get("active") is True}
                    self.first_subjects = {_actor_identity(a) for a in record["initialSnapshot"]["actors"] if a.get("active") is True}
                elif record.get("command") == "spawn":
                    prepared = _wild_spawn_setup(record["receipt"], record["snapshot"], species=155, locomotion=7)
                    self.spawn_setup = prepared
                    self._prepared_attached.add(_handle(prepared["subject"]["handle"]))
                elif record.get("command") == "bind":
                    action = next(a for a in self.test["setup"] if a["id"] == record.get("action"))
                    if self.bind(action["args"]["subject"], record["snapshot"]) != record["receipt"]:
                        raise ValueError("emote exact actor bind differs")
                def accepted(sample, frames):
                    self.frames = self.sampled_frames = frames
                    self.latest = deepcopy(sample)
                    if frame_callback: frame_callback(sample, self)
                measured = meter.observe_record(record, on_sample=accepted)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None:self.latest = deepcopy(snapshot)
                self.frames = self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if meter_kind == CONDITION_SERVICE:
                if not isinstance(record, dict):
                    raise ValueError("condition service raw record must be an object")
                if record.get("command") is not None:
                    action = self.test["actions"][0]
                    if record.get("command") != "condition.probe" \
                            or record.get("phase") != "observe" \
                            or record.get("action") != action["id"] \
                            or self.latest is None:
                        raise ValueError(
                            "condition receipt must name its exact declared action")
                elif "initialSnapshot" in record:
                    if self.latest is not None:
                        raise ValueError("duplicate condition initial boundary")
                else:
                    raise ValueError("unexpected condition service raw record")
                measured = meter.observe_record(record)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind,
                              measured["failures"])
                snapshot = record.get("snapshot", record.get("initialSnapshot"))
                if snapshot is not None:
                    self.latest = deepcopy(snapshot)
                # This subjectless service contract measures only native
                # cycles occupied by its fixed prepare/evaluate calls.
                self.frames = measured["observedFrames"]
                self.sampled_frames = measured["observedFrames"]
                return self.result(full_report=full_report)
            if not isinstance(record, dict): raise ValueError("raw record must be an object")
            prepared_transition_command = record.get("command") in ("party", "spawn") or (
                meter_kind == FOLLOWER_TRANSITION and record.get("command") == "teleport")
            if "initialSnapshot" in record:
                if self.latest is not None: raise ValueError("duplicate initial raw record")
            elif record.get("command") == "observer-control" and meter_kind == ROUTE_CONTROL:
                measured = meter.observe_record(record, full_report=False)
                if measured["failures"]:
                    self.fail("measurement-failed", meter_kind, measured["failures"])
                return self.result(full_report=full_report)
            elif prepared_transition_command:
                key = (record.get("phase"), record.get("action"))
                action = meter.actions.get(key)
                if (self.test["mode"] != "prepared" and meter_kind != ROUTE_CONTROL) or record.get("phase") != "setup" \
                        or self.subjects or key in self._raw_commands or action is None \
                        or action["op"] != record["command"]:
                    raise ValueError("prepared raw receipt must name one unbound setup command")
                self._raw_commands.add(key)
                if meter_kind in (WILD_TRANSITION, FOLLOWER_TRANSITION):
                    receipt, snapshot = record.get("receipt", {}), record.get("snapshot", {})
                    if meter_kind == WILD_TRANSITION and record["command"] == "spawn":
                        self.spawn_setup = _wild_spawn_setup(receipt, snapshot, species=19)
                    old_sequences, old_events = deepcopy(self.last_sequence), self.events.copy()
                    try:
                        for event in receipt.get("events", []):
                            if event.get("kind") == "native-observation":
                                continue
                            event_frame = _int(event.get("frame"), "field transition setup event frame",
                                               self.latest["frame"], snapshot["frame"])
                            self._events([event], event_frame)
                        traces = receipt.get("setupBoundary", {}).get("traceSequences")
                        if not isinstance(traces, dict):
                            raise ValueError("field transition setup trace watermark is missing")
                        checked = {_int(int(stream), "field transition setup trace stream", 1, 1000000):
                                   _int(sequence, "field transition setup trace sequence", 0, 0xFFFFFFFF)
                                   for stream, sequence in traces.items()
                                   if isinstance(stream, str) and stream.isdecimal()
                                   and str(int(stream)) == stream}
                        if len(checked) != len(traces) or checked != self.last_sequence:
                            raise ValueError("field transition setup trace watermark differs")
                        # The sealed prefix proves attachment identity without
                        # granting setup event credit to gameplay assertions.
                        if self.spawn_setup is not None:
                            self._prepared_attached.add(_handle(self.spawn_setup["subject"]["handle"]))
                    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
                        self.last_sequence = old_sequences
                        raise
                    finally:
                        self.events = old_events
            elif record.get("command") in ("bind", "skip"):
                command_key = (record.get("phase"), record.get("action"))
                if command_key in self._raw_commands: raise ValueError("duplicate raw command record")
                action = next((a for a in self.test["setup" if record.get("phase") == "setup" else "actions"]
                               if a["id"] == record.get("action")), None)
                snapshot = record.get("snapshot")
                if action is None or not isinstance(snapshot, dict) or self.latest is None \
                        or any(snapshot.get(key) != self.latest.get(key) for key in (
                            "frame", "nativeCycle", "context", "player", "actors", "party", "partyObservation", "selector", "fieldAvailable")):
                    raise ValueError("raw command requires the exact current snapshot and declared action")
                if record["command"] == "bind":
                    if action["op"] != "bind": raise ValueError("raw bind does not name a binding action")
                    selected = select_current_actor(snapshot, record["receipt"])
                    measured = meter.observe_record(record)
                    if measured["failures"]: raise ValueError(str(measured["failures"]))
                    bound = self.bind(action["args"]["subject"], snapshot)
                    if selected != bound or record["receipt"] != bound:
                        raise ValueError("raw binding receipt differs from current full subject")
                else:
                    if not action.get("skipIf") or not self.check(action["skipIf"], snapshot):
                        raise ValueError("raw skip lacks its declared true condition")
                    measured = meter.observe_record(record)
                    if measured["failures"]: raise ValueError(str(measured["failures"]))
                self._raw_commands.add(command_key)
                return self.result(full_report=full_report)
            else:
                samples, intervals, events = record.get("samples"), record.get("cycleIntervals"), record.get("events")
                if self.latest is None or not isinstance(samples, list) or not 1 <= len(samples) <= 600 \
                        or any(not isinstance(s, dict) or type(s.get("fieldAvailable")) is not bool for s in samples) \
                        or type(record.get("completedGameFrames")) is not int or len(samples) != record["completedGameFrames"] \
                        or not isinstance(intervals, list) or not 1 <= len(intervals) <= 3720 \
                        or any(not isinstance(i, dict) for i in intervals) \
                        or type(record.get("nativeCycles")) is not int or len(intervals) != record["nativeCycles"] \
                        or not isinstance(events, list) or len(events) > 4096 or type(record.get("observedFieldFrames")) is not int \
                        or record.get("observedFieldFrames") != sum(s.get("fieldAvailable") is not False for s in samples):
                    raise ValueError("raw chunk has missing samples, cycle intervals or field counts")
                action_key = (record.get("phase"), record.get("action"))
                action = meter.actions.get(action_key)
                if action is None or action["op"] not in ("step", "wait"):
                    raise ValueError("raw chunk must name its sealed step/wait action")
                # Current workers always declare the requested transport count.
                # Older synthetic rows omitted it and represented exact counts.
                requested = _int(record.get("requestedGameFrames", record["completedGameFrames"]),
                                 "requested game frames", 1, 600)
                completed = record["completedGameFrames"]
                if completed < requested or (completed > requested and not (
                        record.get("phase") == "setup" and action["op"] == "wait")):
                    raise ValueError("raw requested/completed frame counts differ outside neutral setup wait")
                self._raw_action_frames[action_key] += len(samples)
                bound = action["budget"]["maxFrames"]
                if action["op"] == "step": bound = min(bound, action["args"]["frames"])
                if self._raw_action_frames[action_key] > bound:
                    raise ValueError("raw action exceeds its frame budget")
            def measured_frame(sample, sample_events, current_meter):
                selected = current_meter.subject if meter_kind in ("unmounted-cadence-v1", "unmounted-game-cadence-v1", ROUTE_CONTROL) else current_meter.result().get("subject")
                if selected and meter.subject_id in self.subjects and self.subjects[meter.subject_id] != selected:
                    # Rebinding is visible only after its exact native frame.
                    self.subjects[meter.subject_id] = deepcopy(selected)
                self._raw_frame = sample["frame"]
                try:
                    if prepared_transition_command:
                        # Only the meter's successful unbound prepared-command
                        # callback reaches here. It has validated the drained
                        # receipt, endpoint and monotonic setup watermarks.
                        # Excluded setup events earn no assertion event credit.
                        traces = current_meter.trace_sequences
                        if any(traces.get(stream, -1) < sequence
                               for stream, sequence in self.last_sequence.items()):
                            raise ValueError("prepared trace watermark rolled back evaluator sequence")
                        self.last_sequence = deepcopy(traces)
                    self._raw_prepared_refresh_frame = None
                    if prepared_transition_command and self.latest is not None \
                            and sample["frame"] == self.latest["frame"]:
                        # The meter has validated this retained setup command
                        # and readback before invoking this callback. No queue
                        # completed, so context/clock/player cannot advance.
                        if (self.test["mode"] != "prepared" and meter_kind != ROUTE_CONTROL) or record.get("phase") != "setup" or self.subjects \
                                or sample_events or any(sample.get(key) != self.latest.get(key) for key in
                                    ("nativeCycle", "context", "player", "fieldControl", "fieldAvailable")):
                            raise ValueError("same-frame prepared endpoint changed its completed field boundary")
                        self._raw_prepared_refresh_frame = sample["frame"]
                    self.observe(sample, sample_events,
                                 count_frame="initialSnapshot" not in record and record.get("phase") == "observe",
                                 full_report=False)
                    if self.failures:
                        raise ValueError("per-frame evaluator rejected raw observation")
                    if frame_callback:
                        frame_callback(sample, self)
                finally:
                    self._raw_prepared_refresh_frame = None
                    self._raw_frame = None
            measured = meter.observe_record(record, frame_callback=measured_frame,
                **({"full_report": False} if meter_kind in ("unmounted-cadence-v1", "unmounted-game-cadence-v1", ROUTE_CONTROL) else {}))
            if measured["failures"]:
                self.fail("measurement-failed", meter_kind, measured["failures"])
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
            self.fail("raw-observation-invalid", str(error))
        return self.result(full_report=full_report)

    def _observe_surface_rebind_record(self, record, meter, frame_callback):
        """Use existing setup watermarks and exact native queue validation."""
        if not isinstance(record, dict):
            raise ValueError("retained surface raw record must be an object")
        def accepted(sample, events=(), current_meter=None):
            if current_meter is not None and current_meter.subject is not None:
                self.subjects[meter.config["subject"]] = deepcopy(current_meter.subject)
            self._raw_frame = sample["frame"]
            try:
                self.observe(sample, events, count_frame=record.get("phase") == "observe", full_report=False)
                if self.failures:
                    raise ValueError("per-frame evaluator rejected retained surface observation")
                if frame_callback is not None:
                    frame_callback(sample, self)
            finally:
                self._raw_frame = None
        if "initialSnapshot" in record:
            if self.latest is not None:
                raise ValueError("duplicate retained surface initial boundary")
            accepted(record["initialSnapshot"])
        elif record.get("command") is not None:
            key = (record.get("phase"), record.get("action"))
            action = meter.actions.get(key)
            if key in self._raw_commands or action is None or key[0] != "setup" \
                    or action["op"] != record["command"] or self.latest is None:
                raise ValueError("retained surface command differs from its sealed setup")
            snapshot = record["snapshot"]
            if record["command"] in ("teleport", "spawn"):
                if meter.initial is not None:
                    raise ValueError("retained surface mutation after binding")
                if record["command"] == "spawn":
                    found = [e["data"] for e in record["receipt"].get("events", [])
                             if e.get("kind") == "native-observation"
                             and e.get("data", {}).get("observation") == "spawn-prepared"]
                    if len(found) != 1:
                        raise ValueError("retained surface needs one native prepared spawn")
                    spawn = found[0]
                    final = spawn.get("finalization", {}).get("receipt", {})
                    fields = ("slot", "terrain", "statePointer", "fieldPointer", "preparedPointer",
                              "worldContext", "preparedPrefixHex", "preparedEncounter", "startup", "position")
                    if spawn.get("finalization", {}).get("status") != "matched" \
                            or final.get("pairEligible") is not True or final.get("returnValue") != 1 \
                            or any(k not in final or final[k] != spawn.get(k) for k in fields) \
                            or final.get("returnWorldContext") != spawn.get("worldContext") \
                            or not 0 < final.get("sequence", 0) < spawn.get("sequence", 0):
                        raise ValueError("retained surface finalized spawn binding differs")
                    selected = select_current_actor(snapshot, spawn["publicSubject"])
                    value = record["receipt"].get("value", {})
                    if (value.get("slot"), value.get("species"), value.get("personality")) != \
                            (selected["handle"]["slot"], meter.config["species"], selected["subjectIdentity"]):
                        raise ValueError("retained surface command encounter differs")
                    raw = bytes.fromhex(spawn["preparedPrefixHex"])
                    if len(raw) != 30:
                        raise ValueError("retained surface prepared prefix size differs")
                    encounter = dict(personality=int.from_bytes(raw[12:16], "little"),
                                     species=int.from_bytes(raw[16:18], "little"), form=raw[18], level=raw[19])
                    target = [int.from_bytes(raw[n:n+2], "little", signed=True) for n in (20,22)]
                    origin = [int.from_bytes(raw[n:n+2], "little", signed=True) for n in (24,26)]
                    if encounter != spawn["preparedEncounter"] \
                            or any(spawn["publicSubject"][k] != v for k,v in encounter.items()
                                   if k != "personality") \
                            or encounter["personality"] != selected["subjectIdentity"] \
                            or spawn["position"] != [int.from_bytes(raw[n:n+4], "little", signed=True) for n in (0,4)] \
                            or spawn["position"] != target or target != spawn["startup"]["target"] \
                            or origin != spawn["startup"]["origin"] or raw[28] != 9 \
                            or raw[29] != spawn["startup"]["hopDirection"]:
                        raise ValueError("retained surface prepared encounter or native target differs")
                    self._prepared_attached.add(_handle(selected["handle"]))
                self._raw_frame = self._raw_prepared_refresh_frame = snapshot["frame"]
                try:
                    self.observe_prepared_command(record)
                finally:
                    self._raw_frame = self._raw_prepared_refresh_frame = None
                if self.failures:
                    raise ValueError("retained surface prepared boundary failed")
            else:
                if any(snapshot.get(k) != self.latest.get(k) for k in
                       ("frame", "nativeCycle", "context", "player", "actors", "party", "fieldControl", "fieldAvailable")):
                    raise ValueError("retained surface read/bind is not the current boundary")
                if record["command"] == "bind" and self.bind(action["args"]["subject"], snapshot) != record["receipt"]:
                    raise ValueError("retained surface bind differs from its full live subject")
            self._raw_commands.add(key)
        else:
            key = (record.get("phase"), record.get("action"))
            action = meter.actions.get(key)
            if action is None or action["op"] not in ("step", "wait"):
                raise ValueError("retained surface chunk must name its sealed input/wait")
            completed = _int(record.get("completedGameFrames"), "retained surface completed frames", 1, 600)
            requested = _int(record.get("requestedGameFrames", completed), "retained surface requested frames", 1, 600)
            if completed < requested or (completed > requested and not (key[0] == "setup" and action["op"] == "wait")):
                raise ValueError("retained surface requested/completed frame counts differ")
            self._raw_action_frames[key] += completed
            bound = min(action["budget"]["maxFrames"], action["args"]["frames"]) if action["op"] == "step" else action["budget"]["maxFrames"]
            if self._raw_action_frames[key] > bound:
                raise ValueError("retained surface action exceeds its frame budget")
        measured = meter.observe_record(record, frame_callback=accepted)
        if measured["failures"]:
            self.fail("measurement-failed", meter.kind, measured["failures"])

    def _acceleration_role(self, subject):
        specification = self.test["measurements"][0]
        matches = [role for role, selected in specification["subjects"].items() if selected == subject]
        if len(matches) != 1:
            raise ValueError("unknown acceleration subject")
        return matches[0]

    def acceleration_role_complete(self, subject):
        meter = self.measurements.get(ACCELERATION)
        if meter is None or meter.failures or self.failures:
            return False
        state = meter.roles.get(self._acceleration_role(subject))
        return bool(state and len(state["motions"]) == 7 and len(state["policies"]) == 7
                    and state["recorder"].current is None)

    def acceleration_begin_args(self, subject, snapshot):
        if ACCELERATION not in self.measurements or self._acceleration_active is not None \
                or subject in self._acceleration_closed or snapshot != self.latest:
            raise ValueError("acceleration begin requires an unused current setup boundary")
        self._acceleration_role(subject)
        return self.walk_reset_args(subject, snapshot)

    def acceleration_end_receipt(self, subject, snapshot):
        if self._acceleration_active != subject or snapshot != self.latest \
                or not self.acceleration_role_complete(subject):
            raise ValueError("acceleration end requires exactly seven completed Walks")
        return {"subject": deepcopy(self.subjects[subject]), "role": self._acceleration_role(subject),
                "frame": snapshot["frame"], "nativeCycle": snapshot["nativeCycle"],
                "completedWalks": 7, "advancedFrames": 0, "acceptedProof": False}

    def walk_intent_args(self, args, snapshot):
        if ACCELERATION not in self.measurements or self._acceleration_intent is not None \
                or snapshot != self.latest or self._acceleration_role(args["subject"]) != "WILD":
            raise ValueError("Walk intent requires its exact unused Wild boundary")
        subject = select_current_actor(snapshot, self.subjects[args["subject"]])
        return validate_command("walk-intent.arm", {**args, "subject": subject})

    def obstacle_intent_args(self, args, snapshot):
        if snapshot != self.latest or args["subject"] not in self.subjects:
            raise ValueError("Obstacle intent needs the current bound subject")
        subject = select_current_actor(snapshot, self.subjects[args["subject"]])
        return validate_command("obstacle-intent.arm", {**args, "subject": subject})

    def _acceleration_prefix(self, snapshot, events, *, start_frame, boundary=None, allow_normal=False):
        """Consume complete excluded setup data; never grant event/frame credit."""
        frame = _int(snapshot.get("frame"), "setup frame", start_frame, 0xFFFFFFFF)
        cycle = _int(snapshot.get("nativeCycle"), "setup native cycle", 0, 0xFFFFFFFF)
        if (type(snapshot.get("prepared")) is not bool or (not allow_normal and snapshot["prepared"] is not True)) or snapshot.get("fieldAvailable") is not True \
                or snapshot.get("observationBoundary") != "main-task-queue-completion":
            raise ValueError("acceleration setup endpoint is not a coherent prepared field")
        if not isinstance(events, list) or len(events) > 65536:
            raise ValueError("acceleration setup lacks bounded retained events")
        old_events = self.events.copy()
        attached = set()
        try:
            for event in events:
                lower = 0 if event.get("kind") == "native-observation" else start_frame
                event_frame = _int(event.get("frame"), "setup event frame", lower, frame)
                self._events([event], event_frame)
                if event.get("kind") == "native" and event["data"].get("event") == "ACTOR_ATTACHED":
                    attached.add((event["data"]["actorHandle"], *[event["data"]["actor"][k] for k in HANDLE_FIELDS if k != "value"]))
                if event.get("kind") == "native-observation":
                    sequence = _int(event["data"].get("sequence"), "setup native sequence", 1, 0xFFFFFFFF)
                    if sequence != self._acceleration_native_sequence + 1:
                        raise ValueError("acceleration setup native sequence gap")
                    self._acceleration_native_sequence = sequence
                elif event.get("kind") not in ("native", "trace-status"):
                    raise ValueError("unknown acceleration setup event")
            if self.failures:
                raise ValueError("acceleration setup trace coverage failed")
            if snapshot.get("nativeObservation", {}).get("sequence") != self._acceleration_native_sequence:
                raise ValueError("acceleration setup native watermark differs")
            if boundary is not None:
                if boundary.get("eventsDrained") is not True or boundary.get("frame") != frame \
                        or boundary.get("nativeCycle") != cycle:
                    raise ValueError("acceleration setup drained boundary differs")
                _int(boundary.get("endpointNativeCycle"), "setup endpoint cycle", cycle, 0xFFFFFFFF)
                watermarks = boundary.get("traceSequences")
                if not isinstance(watermarks, dict):
                    raise ValueError("acceleration setup trace watermark lacks contiguous receipts")
                for stream, sequence in watermarks.items():
                    if not isinstance(stream, str) or not stream.isascii() or not stream.isdecimal() \
                            or not 0 < int(stream) <= 1000000 or str(int(stream)) != stream:
                        raise ValueError("acceleration setup trace stream is invalid")
                    _int(sequence, "setup trace sequence", 0, 0xFFFFFFFF)
                # An announced stream at zero has not emitted an event. It does
                # not require a receipt, unlike every positive watermark.
                if {k: v for k, v in watermarks.items() if v > 0} != \
                        {str(k): v for k, v in self.last_sequence.items() if v > 0}:
                    raise ValueError("acceleration setup trace watermark lacks contiguous receipts")
            # Keep only validated setup identity provenance. These receipts
            # never earn motion or generic event-count credit.
            self._prepared_attached.update(attached)
        finally:
            self.events = old_events

    def walk_policy_control_args(self, subject, snapshot):
        if WALK_POLICY_CONTROL not in self.measurements or subject not in self.subjects:
            raise ValueError("Walk control requires its bound subject")
        return {"subject": select_current_actor(snapshot, self.subjects[subject])}

    def mount_pacing_args(self, subject, snapshot):
        if not {MOUNT_PACING, MOUNT_SPEED_SLEW, MOUNT_POSE_CONTROL}.intersection(self.measurements) or subject not in self.subjects:
            raise ValueError("mounted pacing requires its bound subject")
        return {"subject": select_current_actor(snapshot, self.subjects[subject]),
                "maxFrames": self.test["budgets"]["maxFrames"]}

    def wild_walk_args(self, subject, snapshot):
        if not {WILD_WALK,WILD_CLEAR_CONTROL}.intersection(self.measurements) or subject not in self.subjects:
            raise ValueError("wild Walk requires its bound subject")
        return {"subject": select_current_actor(snapshot,self.subjects[subject]),
                "maxFrames":self.test["budgets"]["maxFrames"]}

    def wild_ledge_args(self, subject, snapshot):
        if WILD_LEDGE not in self.measurements or subject not in self.subjects:
            raise ValueError("wild ledge requires its bound subject")
        return validate_command("wild-ledge.arm", {
            "subject": select_current_actor(snapshot, self.subjects[subject]),
            "maxFrames": self.test["budgets"]["maxFrames"]})

    def condition_controller_args(self, subject, snapshot):
        if CONDITION_CONTROLLER not in self.measurements or subject not in self.subjects:
            raise ValueError("condition controller requires its bound subject")
        return validate_command("condition-controller.arm", {
            "subject": select_current_actor(snapshot, self.subjects[subject]),
            "maxFrames": self.test["budgets"]["maxFrames"],
        })

    def crash_args(self, subject, snapshot):
        if not CRASH_KINDS.intersection(self.measurements) or subject not in self.subjects:
            raise ValueError("Crash requires its bound subject")
        return validate_command("crash.arm", {
            "subject": select_current_actor(snapshot, self.subjects[subject]),
            "maxFrames": self.test["budgets"]["maxFrames"]})

    def stomp_args(self, subject, snapshot):
        if not (STOMP_KINDS.intersection(self.measurements)
                or TURN_SKID in self.measurements) or subject not in self.subjects:
            raise ValueError("stomp requires its bound subject")
        return validate_command("stomp.arm", {
            "subject": select_current_actor(snapshot, self.subjects[subject]),
            "maxFrames": self.test["budgets"]["maxFrames"]})

    def matrix_args(self, subject, snapshot):
        if not MATRIX_KINDS.intersection(self.measurements) or subject not in self.subjects:
            raise ValueError("matrix requires its bound subject")
        return validate_command("walk-matrix.arm", {
            "subject": select_current_actor(snapshot, self.subjects[subject]),
            "maxFrames": self.test["budgets"]["maxFrames"]})

    def turn_skid_args(self, subject, snapshot):
        if TURN_SKID not in self.measurements or subject not in self.subjects:
            raise ValueError("turn-skid requires its bound subject")
        return validate_command("walk-matrix.arm", {
            "subject": select_current_actor(snapshot, self.subjects[subject]),
            "maxFrames": self.test["budgets"]["maxFrames"]})

    def corner_args(self, subject, snapshot, *, probe=False):
        if not CORNER_KINDS.intersection(self.measurements) or subject not in self.subjects:
            raise ValueError("corner requires its bound subject")
        args = {"subject": select_current_actor(snapshot, self.subjects[subject])}
        if not probe:
            args["maxFrames"] = self.test["budgets"]["maxFrames"]
        return validate_command("walk-corner.probe" if probe else "walk-corner.arm", args)

    def _observe_walk_policy_control_record(self, record, *, frame_callback=None, meter_kind=WALK_POLICY_CONTROL):
        from tools.overworld.devtools_raw_chunk import validate_raw_chunk
        meter = self.measurements[meter_kind]
        if "initialSnapshot" in record:
            if self.latest is not None or record.get("phase") != "setup":
                raise ValueError("duplicate Walk control initial boundary")
            snapshot = record["initialSnapshot"]
            initial_events = record.get("initialEvents", [])
            if meter_kind in (SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER):
                self._d1_warmup = _d1_warmup_initial(snapshot)
            if meter_kind == UNMOUNTED_ZERO_STUTTER:
                profiles = snapshot.get("nativeObservation", {}).get(
                    "resolvedProfiles", [])
                if not isinstance(profiles, list) or len(profiles) > 64:
                    raise ValueError("zero-stutter initial profile cache is invalid")
                self._unmounted_zero_stutter_profiles = deepcopy(profiles)
            if meter_kind in (MOUNTED_STREAMING, MOUNTED_CARDINAL_STREAMING,
                              MOUNTED_WALK_TRANSITION,
                              LAND_SURF, SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER,
                              POPULATION_FAST_TRAVEL, WARP_GATE) and initial_events == []:
                # This public-only meter installs no private callback reader.
                # Its initial row can therefore carry only the current native
                # watermark.  Seed that excluded setup boundary without
                # granting an event, frame, path or streaming observation.
                self._acceleration_native_sequence = _int(
                    snapshot.get("nativeObservation", {}).get("sequence"),
                    "initial native sequence", 0, 0xFFFFFFFF)
            else:
                self._acceleration_prefix(snapshot, initial_events,
                    start_frame=_int(record.get("initialEventStartFrame", snapshot["frame"]),
                                     "initial frame", 0, snapshot["frame"]), allow_normal=True)
            self.latest = deepcopy(snapshot)
            self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
            self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
            return
        if self.latest is None or record.get("phase") not in ("setup", "observe"):
            raise ValueError("Walk control initial boundary or phase missing")
        phase = record["phase"]
        action = next((a for a in self.test["setup" if phase == "setup" else "actions"] if a["id"] == record.get("action")), None)
        if action is None:
            raise ValueError("Walk control record lacks a sealed action")
        command = record.get("command")
        if command:
            key = (phase, action["id"])
            if command != action["op"] or key in self._raw_commands:
                raise ValueError("duplicate or wrong Walk control command")
            snapshot, receipt = record["snapshot"], record["receipt"]
            if command == "bind":
                same_boundary = snapshot == self.latest or (
                    meter_kind in (MOUNTED_STREAMING, MOUNTED_CARDINAL_STREAMING,
                                   MOUNTED_WALK_TRANSITION,
                                   MOUNT_DETACH_FOLLOWER_RESUME,
                                   LAND_SURF, SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER,
                                   POPULATION_FAST_TRAVEL, WARP_GATE)
                    and _same_mounted_reader_boundary(self.latest, snapshot))
                if phase != "setup" or (meter.initial is not None and meter_kind not in (
                        MOUNT_CONTROL_STRESS, MOUNT_DETACH_FOLLOWER_RESUME)) \
                        or not same_boundary or self.bind(action["args"]["subject"], snapshot) != receipt:
                    raise ValueError("Walk control binding differs")
                if meter_kind == MOUNTED_STREAMING:
                    meter.arm(receipt, snapshot)
                if meter_kind == MOUNTED_CARDINAL_STREAMING:
                    meter.arm(receipt, snapshot)
                if meter_kind == MOUNTED_WALK_TRANSITION:
                    meter.arm(receipt, snapshot)
                if meter_kind == LAND_SURF:
                    meter.arm(receipt, snapshot)
                if meter_kind == SPAWN_WORK_BUDGET:
                    _d1_warmup_arm(self._d1_warmup, snapshot, receipt)
                    setup_frames = sum(count for (phase, _), count
                        in self._raw_action_frames.items() if phase == "setup")
                    meter.max_frames = _d1_spawn_remaining_frames(
                        self._d1_warmup, snapshot, setup_frames,
                        self.test["budgets"]["maxFrames"])
                    meter.arm(receipt, snapshot)
                if meter_kind == UNMOUNTED_ZERO_STUTTER:
                    _d1_warmup_arm(self._d1_warmup, snapshot, receipt)
                    meter.arm(receipt, snapshot, resolved_profiles=
                              self._unmounted_zero_stutter_profiles)
                if meter_kind == POPULATION_FAST_TRAVEL:
                    meter.arm(receipt, snapshot)
                if meter_kind == WILD_BATTLE_HANDOFF:
                    meter.arm(receipt, snapshot, trace_sequences=self.last_sequence)
                if meter_kind == WARP_GATE:
                    meter.arm(receipt, snapshot, trace_sequences=self.last_sequence, door=[555, 391])
            elif command in ("teleport", "party", "spawn"):
                if phase != "setup" or meter.initial is not None or receipt.get("preparedOnly") is not True or receipt.get("snapshot") != snapshot or snapshot["nativeCycle"] < self.latest["nativeCycle"] or not isinstance(receipt.get("setupBoundary"), dict):
                    raise ValueError("Walk control prepared endpoint differs")
                self._acceleration_prefix(snapshot, receipt.get("events"), start_frame=self.latest["frame"], boundary=receipt["setupBoundary"])
                if command == "spawn" and meter_kind in (
                        WILD_WALK, WILD_LEDGE, WILD_TELEPORT, RUNNER_STOP_SKID,
                        RUNNER_TURN_RUNWAY,
                        WILD_CLEAR_CONTROL, WILD_BATTLE_HANDOFF):
                    species = {
                        WILD_LEDGE: 35, WILD_TELEPORT: 92, RUNNER_STOP_SKID: 234,
                        RUNNER_TURN_RUNWAY: 234,
                    }.get(meter_kind, 19)
                    self.spawn_setup = _wild_spawn_setup(
                        receipt, snapshot, species=species,
                        locomotion=3 if meter_kind in (WILD_WALK, WILD_CLEAR_CONTROL)
                        else 7 if meter_kind in (
                            WILD_LEDGE, WILD_TELEPORT, RUNNER_STOP_SKID,
                            RUNNER_TURN_RUNWAY) else 0)
            elif command == "mount-walk.configure" and meter_kind == MOUNT_SPEED_SLEW:
                if phase != "setup" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("mounted Linear fixture changed its idle boundary")
                expected = self.mount_walk_fixture_args(action["args"], snapshot)
                meter.configure(receipt, snapshot, expected["subject"])
            elif command == "mount-walk.configure" and meter_kind in CRASH_KINDS:
                if phase != "setup" or meter.initial is not None or receipt.get("completed") is not True or receipt.get("guestAdvanced") is not False:
                    raise ValueError("Crash lane fixture is not completed idle setup")
                expected = self.mount_walk_fixture_args(action["args"], snapshot)
                from tools.overworld.devtools_crash_test_support import feed_configuration
                natural = meter.natural if meter_kind == CRASH_CONTROL else meter
                feed_configuration(natural, receipt, snapshot, expected["subject"])
            elif command.startswith("crash.") and meter_kind in CRASH_KINDS:
                from tools.overworld.devtools_crash_test_support import feed_command
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("Crash command changed its completed boundary")
                if command == "crash.arm":
                    expected = self.crash_args(action["args"]["subject"], snapshot)
                    natural = meter.natural if meter_kind == CRASH_CONTROL else meter
                    if getattr(natural, "_typed_configuration", None) is None:
                        raise ValueError("Crash arm requires its fixed lane fixture")
                    feed_command(natural, command, receipt, snapshot, subject=expected["subject"], trace_sequences=self.last_sequence)
                elif command == "crash.calibrate":
                    if meter_kind != CRASH_CONTROL:
                        raise ValueError("Crash calibration cannot run in gameplay proof")
                    meter.calibrate(receipt, snapshot)
                elif meter_kind == CRASH_CONTROL:
                    meter.close(receipt, snapshot)
                else:
                    feed_command(meter, command, receipt, snapshot)
            elif command == "mount-walk.configure" and meter_kind in STOMP_KINDS:
                if receipt.get("completed") is not True or receipt.get("guestAdvanced") is not False:
                    raise ValueError("stomp lane fixture must not advance the guest")
                self.mount_walk_fixture_args(action["args"], snapshot)
                meter.configure(receipt, snapshot)
            elif command == "mount-walk.configure" and meter_kind == TURN_SKID:
                if phase != "setup" or meter.initial is not None \
                        or receipt.get("completed") is not True \
                        or receipt.get("guestAdvanced") is not False:
                    raise ValueError("turn-skid lane fixture is not completed idle setup")
                self.mount_walk_fixture_args(action["args"], snapshot)
            elif command.startswith("stomp.") and meter_kind in STOMP_KINDS:
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("stomp command changed its completed boundary")
                if command.endswith("arm"):
                    expected = self.stomp_args(action["args"]["subject"], snapshot)
                    meter.arm(expected["subject"], snapshot, receipt, trace_sequences=self.last_sequence)
                elif command.endswith("calibrate"):
                    if meter_kind != STOMP_CONTROL:
                        raise ValueError("stomp calibration cannot run in gameplay proof")
                    meter.calibrate(receipt, snapshot)
                else:
                    meter.close(receipt, snapshot)
            elif command.startswith("stomp.") and meter_kind == TURN_SKID:
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("turn-skid dust command changed its completed boundary")
                feedback = receipt.get("stompFeedback", {})
                if command == "stomp.arm":
                    self.stomp_args(action["args"]["subject"], snapshot)
                    if feedback.get("armed") is not True or feedback.get("closed") is not False \
                            or feedback.get("failure") is not None:
                        raise ValueError("turn-skid dust reader did not arm")
                elif command == "stomp.close":
                    counts = feedback.get("counts", {})
                    if feedback.get("closed") is not True or feedback.get("failure") is not None \
                            or feedback.get("pending") != 0 \
                            or [counts.get(name) for name in
                                ("dust", "allocate", "init", "sound", "soundStart")] \
                                != [1, 1, 1, 0, 0]:
                        raise ValueError("turn-skid dust reader did not close with skid dust")
                else:
                    raise ValueError("turn-skid does not use stomp calibration")
            elif command == "mount-teleport.restore" and meter_kind == WARP_GATE:
                self.mount_teleport_restore_args(action["args"], snapshot)
                meter.restore(receipt, snapshot)
            elif command == "mount-teleport.configure" and meter_kind in (MOUNTED_TELEPORT_MATRIX, WARP_GATE):
                if receipt.get("completed") is not True or receipt.get("guestAdvanced") is not False:
                    raise ValueError("Teleport matrix lane fixture must not advance the guest")
                expected = self.mount_teleport_fixture_args(action["args"], snapshot)
                if meter.initial is None:
                    meter.arm(expected["subject"], snapshot,
                              trace_sequences=self.last_sequence)
                meter.configure(receipt, snapshot)
            elif command == "mount-walk.configure" and meter_kind in MATRIX_KINDS:
                if receipt.get("completed") is not True or receipt.get("guestAdvanced") is not False:
                    raise ValueError("matrix lane fixture must not advance the guest")
                self.mount_walk_fixture_args(action["args"], snapshot)
                meter.configure(receipt, snapshot)
            elif command.startswith("walk-matrix.") and meter_kind in ({TURN_SKID} | MATRIX_KINDS):
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("matrix command changed its completed boundary")
                if command.endswith("arm"):
                    expected = (self.turn_skid_args(action["args"]["subject"], snapshot)
                                if meter_kind == TURN_SKID else
                                self.matrix_args(action["args"]["subject"], snapshot))
                    meter.arm(expected["subject"], snapshot, receipt, trace_sequences=self.last_sequence)
                elif command.endswith("calibrate"):
                    if meter_kind != MATRIX_CONTROL:
                        raise ValueError("matrix calibration cannot run in gameplay proof")
                    meter.calibrate(receipt, snapshot)
                else:
                    meter.close(receipt, snapshot)
            elif command == "mount-walk.configure" and meter_kind in CORNER_KINDS:
                if phase != "setup" or meter.initial is not None or receipt.get("completed") is not True or receipt.get("guestAdvanced") is not False:
                    raise ValueError("corner lane fixture is not completed idle setup")
                self.mount_walk_fixture_args(action["args"], snapshot)
            elif command == "walk-corner.probe" and meter_kind in CORNER_KINDS:
                if phase != "setup" or meter.initial is not None:
                    raise ValueError("corner probe is outside setup")
                self._acceleration_prefix(snapshot, receipt.get("events"), start_frame=self.latest["frame"], boundary=receipt["setupBoundary"])
                meter.probe(receipt, snapshot)
            elif command in ("walk-corner.arm", "walk-corner.recovery", "walk-corner.close", "walk-corner.calibrate") and meter_kind in CORNER_KINDS:
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("corner command changed its completed boundary")
                if command.endswith("arm"):
                    expected = self.corner_args(action["args"]["subject"], snapshot)
                    meter.arm(expected["subject"], snapshot, receipt, trace_sequences=self.last_sequence)
                elif command.endswith("calibrate"):
                    if meter_kind != CORNER_CONTROL:
                        raise ValueError("calibration cannot run in a gameplay proof window")
                    meter.calibrate(receipt, snapshot)
                elif command.endswith("recovery"):
                    if receipt != {"snapshot": snapshot, "advancedFrames": 0, "acceptedProof": False}:
                        raise ValueError("corner recovery boundary differs")
                    meter.begin_recovery(snapshot)
                else:
                    meter.close(receipt, snapshot)
            elif command in ("wild-walk.arm","wild-walk.close","wild-walk.calibrate") and meter_kind in (WILD_WALK,WILD_CLEAR_CONTROL):
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest,snapshot):
                    raise ValueError("wild Walk command changed its completed boundary")
                if command.endswith("arm"):
                    if self.spawn_setup is None:
                        raise ValueError("wild Walk arm lacks its own native spawn setup")
                    expected = self.wild_walk_args(action["args"]["subject"],snapshot)
                    meter.arm(expected["subject"],snapshot,receipt,trace_sequences=self.last_sequence)
                elif command == "wild-walk.calibrate" and meter_kind == WILD_CLEAR_CONTROL:
                    meter.calibrate(receipt,snapshot)
                else:
                    meter.close(receipt,snapshot)
            elif command in ("wild-ledge.arm", "wild-ledge.close") and meter_kind == WILD_LEDGE:
                if phase != "observe" or not _same_mounted_reader_boundary(self.latest, snapshot):
                    raise ValueError("wild ledge command changed its completed boundary")
                if command.endswith("arm"):
                    if self.spawn_setup is None:
                        raise ValueError("wild ledge arm lacks its own native spawn setup")
                    expected = self.wild_ledge_args(action["args"]["subject"], snapshot)
                    reader = receipt.get("wildLedge", {})
                    if receipt.get("armed") is not True or reader.get("subject") != expected["subject"] \
                            or reader.get("maxFrames") != expected["maxFrames"]:
                        raise ValueError("wild ledge reader arm differs")
                    meter.arm(expected["subject"], snapshot, receipt, trace_sequences=self.last_sequence)
                else:
                    meter.close(receipt, snapshot)
            elif command == "condition-controller.fixture" \
                    and meter_kind == CONDITION_CONTROLLER:
                if (phase != "setup" or meter.initial is not None
                        or not _same_mounted_reader_boundary(self.latest, snapshot)):
                    raise ValueError(
                        "condition controller fixture changed its completed boundary")
                fixture = receipt.get("conditionController", {})
                if (receipt.get("prepared") is not True
                        or receipt.get("advancedFrames") != 0
                        or receipt.get("acceptedProof") is not False
                        or fixture.get("catalogPatch", {}).get("applied") is not True
                        or fixture["catalogPatch"].get("restored") is not False
                        or fixture.get("guestMemoryWriteBytes") != 5
                        or fixture.get("guestMemoryWriteOperations") != 5):
                    raise ValueError("condition controller fixture receipt differs")
            elif command in ("condition-controller.arm",
                              "condition-controller.close") \
                    and meter_kind == CONDITION_CONTROLLER:
                if (phase != "observe"
                        or not _same_mounted_reader_boundary(self.latest, snapshot)):
                    raise ValueError(
                        "condition controller command changed its completed boundary")
                if command.endswith("arm"):
                    expected = self.condition_controller_args(
                        action["args"]["subject"], snapshot)
                    reader = receipt.get("conditionController", {})
                    if (receipt.get("armed") is not True
                            or receipt.get("advancedFrames") != 0
                            or reader.get("subject") != expected["subject"]
                            or reader.get("maxFrames") != expected["maxFrames"]):
                        raise ValueError("condition controller arm receipt differs")
                    meter.arm(expected["subject"], snapshot, receipt)
                else:
                    meter.close(snapshot, receipt)
            elif command.startswith("mount-pacing.") and meter_kind in (MOUNT_PACING, MOUNT_SPEED_SLEW, MOUNT_POSE_CONTROL):
                if phase != "observe" or not _same_mounted_reader_boundary(snapshot, self.latest):
                    raise ValueError("mounted pacing command advanced or changed the boundary")
                if command == "mount-pacing.arm":
                    expected = self.mount_pacing_args(action["args"]["subject"], snapshot)
                    meter.arm(expected["subject"], snapshot, receipt, trace_sequences=self.last_sequence)
                elif command == "mount-pacing.calibrate" and meter_kind == MOUNT_POSE_CONTROL:
                    meter.calibrate(receipt, snapshot)
                elif command == "mount-pacing.recovery":
                    if receipt != {"snapshot": snapshot, "advancedFrames": 0, "acceptedProof": False}:
                        raise ValueError("mounted pacing recovery boundary differs")
                    meter.begin_recovery(snapshot)
                else:
                    meter.close(receipt, snapshot)
            elif command in ("walk-policy-control.arm", "walk-policy-control.close") and meter_kind == WALK_POLICY_CONTROL:
                if phase != "observe" or any(snapshot.get(k) != self.latest.get(k) for k in (
                        "frame", "nativeCycle", "actorFrame", "context", "player", "actors", "nativeObservation")):
                    raise ValueError("Walk control command advanced or changed the boundary")
                if command.endswith("arm"):
                    expected = self.walk_policy_control_args(action["args"]["subject"], snapshot)
                    if receipt.get("walkPolicyControl", {}).get("subject") != expected["subject"]:
                        raise ValueError("Walk control arm subject differs")
                    meter.arm(receipt, snapshot, trace_sequences=self.last_sequence)
                else:
                    meter.close(receipt)
            else:
                raise ValueError("unsupported Walk control command")
            self.latest = deepcopy(snapshot)
            self._raw_commands.add(key)
            return
        if action["op"] not in ("step", "wait") or meter.closed:
            raise ValueError("Walk control samples are outside a step/wait window")
        rows = validate_raw_chunk(record, self.latest)
        requested = _int(record.get("requestedGameFrames"), "requested frames", 1, 600)
        if not _valid_requested_raw_rows(rows, requested):
            raise ValueError("Walk control requested sample count differs")
        key = (phase, action["id"])
        self._raw_action_frames[key] += len(rows)
        maximum = action["budget"]["maxFrames"]
        if action["op"] == "step": maximum = min(maximum, action["args"]["frames"])
        if self._raw_action_frames[key] > maximum:
            raise ValueError("Walk control action frame budget exceeded")
        bootstrap = False
        if meter_kind in CRASH_KINDS:
            natural = meter.natural if meter_kind == CRASH_CONTROL else meter
            if getattr(natural, "_typed_pending_arm", None) is not None:
                from tools.overworld.devtools_crash_test_support import feed_chunk
                feed_chunk(natural, {"op": "step", "args": {"frames": requested,
                    "keys": action["args"].get("keys", [])}, "startFrame": self.latest["frame"]},
                    record, [row[0] for row in rows], [event for row in rows for event in row[1]])
                bootstrap = True
        if meter_kind in (WILD_TELEPORT, RUNNER_STOP_SKID, RUNNER_TURN_RUNWAY) \
                and meter.initial is None:
            if phase != "observe" or self.spawn_setup is None:
                raise ValueError("natural Wild observation lacks its own native spawn setup")
            subject = self.test["measurements"][0]["subject"]
            if subject not in self.subjects:
                raise ValueError("natural Wild observation lacks its bound subject")
            meter.arm(select_current_actor(self.latest, self.subjects[subject]), self.latest,
                      trace_sequences=self.last_sequence)
        if meter_kind in ({TURN_SKID} | CORNER_KINDS | MATRIX_KINDS | STOMP_KINDS | CRASH_KINDS) and meter.initial is not None and not bootstrap:
            meter.command({"op": "step", "args": {"frames": requested,
                "keys": action["args"].get("keys", [])}, "startFrame": self.latest["frame"]}, record)
        for row_index, (snapshot, events, _) in enumerate(rows):
            if meter.initial is None:
                if phase != "setup": raise ValueError("Walk control observation preceded arm")
                if meter_kind in (SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER):
                    _d1_warmup_observe(self._d1_warmup, snapshot, events)
                if meter_kind == SPAWN_WORK_BUDGET:
                    meter.observe_setup(snapshot, events)
                self._acceleration_prefix(snapshot, events, start_frame=self.latest["frame"], allow_normal=True)
            else:
                self._events(events, snapshot["frame"])
                if self.failures: return
                if meter_kind in (MOUNT_PACING, MOUNT_SPEED_SLEW):
                    _mounted_input_boundary(self.latest, snapshot, events, meter.subject,
                        0x10 if action["op"] == "step" else 0,
                        self._raw_action_frames[key] - len(rows) + row_index == 0)
                report = meter.result() if bootstrap else meter.observe(snapshot, events)
                self.frames = meter.frames
                if report["failures"]:
                    self.latest = deepcopy(snapshot)
                    self.fail("measurement-failed", meter_kind, report["failures"])
                    return
                if meter_kind == MOUNTED_TELEPORT_MATRIX and report.get("subject"):
                    # The matrix verifies each visibility detach/reattach and
                    # owns its presentation-generation changes. Keep later
                    # fixture commands bound to that verified current value.
                    subject_id = self.test["measurements"][0]["subject"]
                    self.subjects[subject_id] = deepcopy(report["subject"])
                if meter_kind == WARP_GATE and meter.subject:
                    subject_id = self.test["measurements"][0]["subject"]
                    self.subjects[subject_id] = deepcopy(meter.subject)
                if meter_kind == MOUNTED_WALK_TRANSITION and report.get("subject"):
                    subject_id = self.test["measurements"][0]["subject"]
                    self.subjects[subject_id] = deepcopy(report["subject"])
                if meter_kind == UNMOUNTED_ZERO_STUTTER and report.get("subject"):
                    # The zero-stutter meter checks that this is the same
                    # saved follower and permits only an exact next-field
                    # rebind. Publish that current canonical selection before
                    # the shared replay callback verifies engine membership.
                    subject_id = self.test["measurements"][0]["subject"]
                    self.subjects[subject_id] = select_current_actor(
                        snapshot, report["subject"])
                if meter_kind == SPAWN_WORK_BUDGET and report.get("subject"):
                    # This meter owns the reviewed Route 30 -> Cherrygrove
                    # crossing and proves the same follower identity on both
                    # sides. Publish its current handle before the independent
                    # replay callback checks field and engine membership.
                    subject_id = self.test["measurements"][0]["subject"]
                    self.subjects[subject_id] = select_current_actor(
                        snapshot, report["subject"])
            self.latest = deepcopy(snapshot)
            self.sampled_frames += 1
            if self.sampled_frames > self.test["budgets"]["maxFrames"]:
                raise ValueError("Walk control overall frame budget exceeded")
            if meter.initial is not None:
                for predicate in self.test["assertions"]:
                    if predicate["when"] == "always" and not self.check(predicate):
                        self.fail("assertion-failed", "always assertion failed", predicate)
                        return
            if frame_callback: frame_callback(snapshot, self)

    def _observe_acceleration_record(self, record, *, frame_callback=None):
        from tools.overworld.devtools_raw_chunk import validate_raw_chunk
        if not isinstance(record, dict):
            raise ValueError("acceleration raw record must be an object")
        meter = self.measurements[ACCELERATION]
        if "initialSnapshot" in record:
            if self.latest is not None or record.get("phase") != "setup":
                raise ValueError("duplicate or wrong acceleration initial boundary")
            snapshot = record["initialSnapshot"]
            start = _int(record.get("initialEventStartFrame"), "initial start frame", 0, snapshot["frame"])
            self._acceleration_prefix(snapshot, record.get("initialEvents"), start_frame=start, allow_normal=True)
            self.latest = deepcopy(snapshot)
            self.first_handles = {_handle(a["handle"]) for a in snapshot["actors"] if a.get("active") is True}
            self.first_subjects = {_actor_identity(a) for a in snapshot["actors"] if a.get("active") is True}
            return
        if self.latest is None:
            raise ValueError("acceleration initial boundary is missing")
        phase = record.get("phase")
        if phase not in ("setup", "observe"):
            raise ValueError("acceleration record phase differs")
        action = next((a for a in self.test["setup" if phase == "setup" else "actions"]
                       if a["id"] == record.get("action")), None)
        if action is None:
            raise ValueError("acceleration record does not name a sealed action")
        command = record.get("command")
        if command:
            key = (phase, action["id"])
            if key in self._raw_commands or command != action["op"]:
                raise ValueError("duplicate or wrong acceleration command")
            snapshot, receipt = record["snapshot"], record["receipt"]
            if command in ("bind", "acceleration.end"):
                if snapshot != self.latest:
                    raise ValueError("acceleration command is not the exact current boundary")
                subject = action["args"]["subject"]
                if command == "bind":
                    if self._acceleration_active is not None:
                        raise ValueError("binding inside acceleration window")
                    if self.bind(subject, snapshot) != receipt:
                        raise ValueError("acceleration binding receipt differs")
                else:
                    if receipt != self.acceleration_end_receipt(subject, snapshot):
                        raise ValueError("acceleration end receipt differs")
                    self._acceleration_closed.add(subject)
                    self._acceleration_active = None
            elif command in ("teleport", "party", "spawn", "acceleration.begin"):
                if phase != "setup" or self._acceleration_active is not None \
                        or receipt.get("preparedOnly") is not True or receipt.get("snapshot") != snapshot:
                    raise ValueError("acceleration prepared command is not excluded setup")
                if snapshot["frame"] < self.latest["frame"] or snapshot["nativeCycle"] < self.latest["nativeCycle"]:
                    raise ValueError("acceleration prepared endpoint moved backwards")
                self._acceleration_prefix(snapshot, receipt.get("events"), start_frame=self.latest["frame"],
                                          boundary=receipt.get("setupBoundary"))
                if command == "acceleration.begin":
                    subject = action["args"]["subject"]
                    if subject not in self.subjects or subject in self._acceleration_closed:
                        raise ValueError("acceleration begin lacks its unused bound subject")
                    if receipt.get("boundary") != "native-field-command-trampoline" \
                            or receipt.get("acceptedProof") is not False or receipt.get("fatal") \
                            or receipt.get("error") or receipt.get("firstBadCheckpoint") is not None \
                            or receipt.get("firstInvalidThreadSwitch") is not None \
                            or receipt.get("nativeHeapAdaptation") != []:
                        raise ValueError("acceleration RESET native bridge failed")
                    calls = receipt.get("calls")
                    address = receipt["trampoline"]["address"]
                    if not isinstance(calls, list) or len(calls) != 1 or calls[0].get("routine") != "reduce_walk" \
                            or calls[0].get("requestedArguments") != [address + 0x210] \
                            or calls[0].get("returnValue") != 1:
                        raise ValueError("acceleration RESET contains other native work")
                    value = receipt["value"]
                    meter.bind(self._acceleration_role(subject), self.subjects[subject],
                               value["after"]["snapshot"], value,
                               resolved_profiles=snapshot["nativeObservation"].get("resolvedProfiles", []))
                    meter.seed_window_boundary(snapshot, receipt["events"], self.last_sequence)
                    self._acceleration_active = subject
                self.latest = deepcopy(snapshot)
            elif command in ("walk-intent.arm", "walk-intent.close"):
                if any(snapshot.get(k) != self.latest.get(k) for k in (
                        "frame", "nativeCycle", "actorFrame", "context", "player", "actors", "nativeObservation")):
                    raise ValueError("Walk intent command advanced or changed the current boundary")
                control = receipt.get("walkIntent")
                if not isinstance(control, dict) or control.get("failure") is not None \
                        or control.get("guestMemoryWrites") != 0 or control.get("acceptedProof") is not False:
                    raise ValueError("Walk intent receipt failed")
                if command == "walk-intent.arm":
                    args = self.walk_intent_args(action["args"], self.latest)
                    if receipt.get("armed") is not True or receipt.get("prepared") is not True \
                            or receipt.get("snapshot") != snapshot or control.get("subject") != args["subject"] \
                            or control.get("direction") != args["direction"] or control.get("armed") is not True \
                            or control.get("closed") is not False or control.get("acceptedStarts") != 0 \
                            or control.get("terminal") is not False or control.get("calls") != []:
                        raise ValueError("Walk intent arm identity or baseline differs")
                    self._acceleration_intent = action["args"]["subject"]
                    self._acceleration_intent_direction = args["direction"]
                    self._acceleration_intent_subject = deepcopy(args["subject"])
                else:
                    if self._acceleration_intent is None or self._acceleration_intent_closed \
                            or not self.acceleration_role_complete(self._acceleration_intent) \
                            or receipt.get("closed") is not True or receipt.get("advancedFrames") != 0 \
                            or control.get("subject") != self._acceleration_intent_subject \
                            or control.get("closed") is not True or control.get("terminal") is not True \
                            or control.get("acceptedStarts") != 7 \
                            or control.get("direction") != self._acceleration_intent_direction \
                            or meter.roles["WILD"]["direction"] != self._acceleration_intent_direction:
                        raise ValueError("Walk intent close lacks seven complete starts")
                    self._acceleration_intent_closed = True
                self.latest = deepcopy(snapshot)
            else:
                raise ValueError("unsupported acceleration raw command")
            self._raw_commands.add(key)
            return
        if action["op"] not in ("step", "wait"):
            raise ValueError("acceleration samples do not name a step or wait")
        rows = validate_raw_chunk(record, self.latest)
        requested = _int(record.get("requestedGameFrames"), "requested game frames", 1, 600)
        if len(rows) < requested or (len(rows) != requested and not (phase == "setup" and action["op"] == "wait")):
            raise ValueError("acceleration requested sample count differs")
        key = (phase, action["id"])
        self._raw_action_frames[key] += len(rows)
        maximum = action["budget"]["maxFrames"]
        if action["op"] == "step": maximum = min(maximum, action["args"]["frames"])
        if self._raw_action_frames[key] > maximum:
            raise ValueError("acceleration action frame budget exceeded")
        for sample, events, _ in rows:
            if self._acceleration_active is None:
                self._acceleration_prefix(sample, events, start_frame=self.latest["frame"])
            else:
                self._events(events, sample["frame"])
                if self.failures: return
                measured = meter.observe(sample, events)
                if measured["failures"]:
                    self.latest = deepcopy(sample)
                    self.fail("measurement-failed", ACCELERATION, measured["failures"])
                    return
                self._acceleration_native_sequence = sample["nativeObservation"]["sequence"]
                self.frames = meter.frames
            self.sampled_frames += 1
            if self.sampled_frames > self.test["budgets"]["maxFrames"]:
                raise ValueError("acceleration overall frame budget exceeded")
            self.latest = deepcopy(sample)
            if self._acceleration_active is not None:
                for predicate in self.test["assertions"]:
                    if predicate["when"] == "always" and ("subject" not in predicate or predicate["subject"] in self.subjects):
                        if not self.check(predicate):
                            self.fail("assertion-failed", "always assertion failed", predicate)
                            return
            if frame_callback:
                frame_callback(sample, self)

    def chain_retry_args(self, subject):
        if self.test["mode"] != "prepared" or subject not in self.subjects:
            raise ValueError("chain retry requires its bound prepared-test subject")
        measurement = self.measurements.get(CHAIN_RETRY)
        if measurement is None:
            raise ValueError("chain retry measurement is missing")
        return measurement.arm_args(self.subjects[subject])

    def observer_control_args(self, subject, fault):
        if self.test["mode"] != "observer-control" or subject not in self.subjects:
            raise ValueError("native control requires its bound observer-test subject")
        kind = ROUTE_CONTROL if fault in ("cpu-hitch", "player-start-stall") else "live-observer-control-v1"
        measurement = self.measurements.get(kind)
        if measurement is None: raise ValueError("native control measurement is missing")
        return measurement.arm_args(self.subjects[subject], fault)

    def observe_brief_terrain(self, record):
        """Keep one same-frame native terrain read with the brief Ram meter."""
        try:
            if (self.test["id"] != "profile.ram.brief-notice"
                    or RAM_BRIEF_NOTICE not in self.measurements
                    or record.get("phase") != "setup"
                    or record.get("action") != "read-current-line-terrain"
                    or record.get("command") != "terrain"
                    or self.latest is None or "onix" not in self.subjects):
                raise ValueError("brief Ram terrain is outside its bound setup")
            snapshot, receipt = record["snapshot"], record["receipt"]
            keys = ("frame", "nativeCycle", "actorFrame", "context", "player",
                    "actors", "fieldControl", "fieldAvailable", "romSha256",
                    "pokemonCombat", "pokemonAppearance")
            if (any(snapshot.get(key) != self.latest.get(key) for key in keys)
                    or receipt != {"terrain": snapshot.get("terrain")}):
                raise ValueError("brief Ram terrain changed its completed actor boundary")
            self.measurements[RAM_BRIEF_NOTICE].observe_terrain(snapshot)
        except (ValueError, KeyError, TypeError) as error:
            self.fail("brief-ram-terrain-invalid", str(error))
        return self.result()

    def observe_prepared_command(self, record):
        """Consume retained setup trace continuity without proof/event credit."""
        if self.closed or self.failures:
            return self.result()
        old_sequences, old_events = deepcopy(self.last_sequence), self.events.copy()
        try:
            surface_raw = set(self.measurements) <= SURFACE_REBIND_KINDS and bool(self.measurements)
            notice_hop = record.get("command") == "notice-hop.prepare" and BLOCKED_NOTICE_HOP in self.measurements
            if (self.uses_raw_records and not surface_raw) or (self.subjects and not notice_hop) or self.latest is None \
                    or self.test["mode"] not in ("prepared", "observer-control"):
                raise ValueError("prepared handoff requires unbound nonraw setup")
            action = next((a for a in self.test["setup"] if a["id"] == record.get("action")), None)
            throw_teleport = (record.get("command") == "teleport"
                and bool({THROW_NOTICE_WALK_COMMIT, FOLLOWER_THROW_HIT_ABORT} & self.measurements.keys()))
            allowed = (("teleport", "spawn") if surface_raw else
                       ("party", "spawn", "notice-hop.prepare") if notice_hop else
                       ("teleport", "party", "spawn") if throw_teleport else ("party", "spawn"))
            if record.get("phase") != "setup" or record.get("command") not in allowed \
                    or action is None or action["op"] != record["command"]:
                raise ValueError("prepared handoff differs from sealed setup action")
            consumed = getattr(self, "_prepared_commands", set())
            if action["id"] in consumed:
                raise ValueError("prepared handoff action was already consumed")
            receipt, snapshot = record["receipt"], record["snapshot"]
            if notice_hop:
                admission = receipt["noticeHopAdmission"]
                if set(self.subjects) != {"flabebe"} or admission["selected"] != self.subjects["flabebe"] \
                        or any(admission["snapshot"].get(k) != self.latest.get(k) for k in
                               ("frame", "nativeCycle", "context", "player", "actors", "fieldControl", "fieldAvailable")):
                    raise ValueError("blocked Notice Hop admission is not the current bound setup")
            boundary = receipt["setupBoundary"]
            if (not notice_hop and (receipt.get("preparedOnly") is not True or snapshot.get("prepared") is not True)) \
                    or receipt.get("snapshot") != snapshot or boundary.get("eventsDrained") is not True:
                raise ValueError("prepared handoff endpoint or drained receipt differs")
            frame = _int(snapshot.get("frame"), "prepared frame", self.latest["frame"], 0xFFFFFFFF)
            cycle = _int(snapshot.get("nativeCycle"), "prepared native cycle", self.latest["nativeCycle"], 0xFFFFFFFF)
            if snapshot.get("fieldAvailable") is not True \
                    or snapshot.get("observationBoundary") != "main-task-queue-completion":
                raise ValueError("prepared handoff requires a coherent field endpoint")
            if frame == self.latest["frame"] and any(snapshot.get(key) != self.latest.get(key) for key in
                    ("nativeCycle", "context", "player", "fieldControl", "fieldAvailable")):
                raise ValueError("same-frame prepared endpoint changed its completed field boundary")
            if boundary.get("frame") != frame or boundary.get("nativeCycle") != cycle:
                raise ValueError("prepared handoff boundary clocks differ")
            if "endpointNativeCycle" in boundary:
                _int(boundary["endpointNativeCycle"], "prepared endpoint cycle", cycle, 0xFFFFFFFF)
            events = receipt.get("events")
            if not isinstance(events,list) or len(events)>65536:
                raise ValueError("prepared handoff lacks bounded retained events")
            previous = self.latest["frame"]
            for event in events:
                if event.get("kind") == "native-observation":
                    # Prepared receipts can retain boot diagnostics before a
                    # trace window starts. They are not native ring events and
                    # cannot set its watermark or earn generic event credit.
                    # Their claim-specific reader validates them separately.
                    _int(event.get("frame"), "diagnostic event frame", 0, frame)
                    if not isinstance(event.get("data"), dict):
                        raise ValueError("prepared diagnostic event lacks data")
                    continue
                event_frame = _int(event.get("frame"), "prepared event frame", previous, frame)
                self._events([event], event_frame)
                if event.get("kind") == "native" \
                        and event.get("data", {}).get("event") == "ACTOR_ATTACHED":
                    data = event["data"]
                    self._prepared_attached.add((data["actorHandle"], *[
                        data["actor"][key] for key in HANDLE_FIELDS if key != "value"]))
                previous = event_frame
                if self.failures:
                    raise ValueError("prepared handoff trace status failed")
            traces = boundary.get("traceSequences")
            if not isinstance(traces,dict) or len(traces)>1000:
                raise ValueError("prepared handoff lacks bounded trace watermarks")
            checked = {}
            for stream, sequence in traces.items():
                if not isinstance(stream,str) or not stream.isdecimal() or str(int(stream)) != stream:
                    raise ValueError("prepared handoff trace stream differs")
                stream_id = _int(int(stream), "prepared trace stream", 1, 1000000)
                checked[stream_id] = _int(sequence, "prepared trace watermark", 0, 0xFFFFFFFF)
            if any(checked.get(k) != v for k,v in self.last_sequence.items()) \
                    or any(self.last_sequence.get(k,0) != v for k,v in checked.items()):
                raise ValueError("prepared handoff watermark lacks contiguous retained events")
            self.events = old_events
            if record["command"] == "spawn":
                prepared_subjects = [
                    event.get("data", {}).get("publicSubject")
                    for event in events
                    if event.get("kind") == "native-observation"
                    and event.get("data", {}).get("observation") == "spawn-prepared"
                ]
                if len(prepared_subjects) == 1 and isinstance(prepared_subjects[0], dict):
                    selected = select_current_actor(snapshot, prepared_subjects[0])
                    self._prepared_attached.add(_handle(selected["handle"]))
            if record["command"] == "spawn" and APPEAR_HOP in self.measurements:
                self.spawn_setup = _wild_spawn_setup(
                    receipt, snapshot, species=35, locomotion=7)
                self._prepared_attached.add(
                    _handle(self.spawn_setup["subject"]["handle"]))
            if record["command"] == "spawn" and any(
                    action["op"] == "obstacle-intent.arm" for action in self.test["actions"]):
                obstacle_spawn = _wild_spawn_setup(
                    receipt, snapshot, species=234, locomotion=7)
                self._prepared_attached.add(
                    _handle(obstacle_spawn["subject"]["handle"]))
            if record["command"] == "spawn":
                profile_spawn_measurements = PROFILE_FEATURE_MEASUREMENTS.intersection(self.measurements) - {FOLLOWER_STOP}
                auxiliary_follower = bool({RAM_LEDGE, RAM_BEHIND, RAM_BRIEF_NOTICE,
                    THROW_NOTICE_WALK_COMMIT, FOLLOWER_THROW_HIT_ABORT} & profile_spawn_measurements) \
                    and action["args"].get("role") == "follower"
                if auxiliary_follower:
                    requested = receipt["requestedSubject"]
                    _shape(requested, {"slot", "role", "species", "personality", "form", "level"}, label="auxiliary Follower")
                    if receipt.get("lifecycle") != "prepared-native-follower-lifecycle" or any(
                            requested.get(k) != ("FOLLOWER" if k == "role" else action["args"][k])
                            for k in ("slot", "role", "species", "form", "level")):
                        raise ValueError("auxiliary Follower differs from sealed spawn")
                    candidates = [a for a in snapshot["actors"] if a.get("active") is True
                        and a.get("role") == "FOLLOWER" and a.get("species") == requested["species"]
                        and a.get("subjectIdentity") == requested["personality"]
                        and a.get("form") == requested["form"] and a.get("level") == requested["level"]]
                    if len(candidates) != 1:
                        raise ValueError("auxiliary Follower lacks one current subject")
                    selected = select_current_actor(snapshot, candidates[0])
                    selector = snapshot["selector"]
                    if selector.get("activeFollowerPartySlot") != requested["slot"] or selector.get("followerReleaseState") != 0 \
                            or selector.get("captureTargetMask", 1 << 7) & (1 << 7) \
                            or selector["queue"].get("count") != 0 or selector["queue"].get("request") != 0 \
                            or candidates[0].get("motionPhase") != "IDLE" or candidates[0].get("reservationId") != 0:
                        raise ValueError("auxiliary Follower release is not settled")
                    self._prepared_attached.add(_handle(selected["handle"]))
                else:
                    for kind in profile_spawn_measurements:
                        self.measurements[kind].observe_prepared(receipt, snapshot)
                    if profile_spawn_measurements:
                        prepared_subjects = [
                            event.get("data", {}).get("publicSubject")
                            for event in events
                            if event.get("kind") == "native-observation"
                            and event.get("data", {}).get("observation") == "spawn-prepared"
                        ]
                        if len(prepared_subjects) != 1 or not isinstance(prepared_subjects[0], dict):
                            raise ValueError("profile feature spawn lacks one prepared public subject")
                        selected = select_current_actor(snapshot, prepared_subjects[0])
                        self._prepared_attached.add(_handle(selected["handle"]))
            if notice_hop:
                measured = self.measurements[BLOCKED_NOTICE_HOP].observe_admission(receipt, snapshot)
                if measured["failures"]:
                    self.fail("measurement-failed", BLOCKED_NOTICE_HOP, measured["failures"])
                    raise ValueError("blocked Notice Hop admission failed")
            self._prepared_command_refresh_frame = frame
            try:
                result = self.observe(snapshot,count_frame=False)
            finally:
                self._prepared_command_refresh_frame = None
            if self.failures:
                self.last_sequence = old_sequences
                return result
            self._prepared_commands = consumed | {action["id"]}
        except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
            self.last_sequence, self.events = old_sequences, old_events
            self.fail("prepared-handoff-invalid",str(error))
        return self.result()

    def expected_control_identity_failure(self, snapshot, subject):
        measurement = self.measurements.get("live-observer-control-v1")
        return self.test["mode"] == "observer-control" and measurement is not None \
            and measurement.expected_identity_failure(snapshot, subject)

    def observer_control_cleanup(self, receipt):
        kind = ROUTE_CONTROL if ROUTE_CONTROL in self.measurements else "live-observer-control-v1"
        if self.test["mode"] != "observer-control" or kind not in self.measurements:
            raise ValueError("cleanup belongs only to a live observer-control test")
        self.measurements[kind].observe_cleanup(receipt)

    def fail(self, code, message, details=None):
        if self.closed and self._passed:
            self._passed = False
        try:
            detail_copy = _copy_json(details, 65536)
        except (ValueError, TypeError, RecursionError) as error:
            detail_copy = {"omitted": True, "captureError": str(error)[:1000],
                           "scope": "full command failure belongs to the job-owned artifact"}
        self.failures.append({"code": str(code)[:512], "message": str(message)[:4096],
                              "frame": self.latest.get("frame") if self.latest else None,
                              "details": detail_copy})
        return self.result()

    def _actor(self, subject_id, snapshot):
        if subject_id not in self.subjects:
            raise ValueError("required subject has not been bound: " + subject_id)
        selected_subject = self.subjects[subject_id]
        stress = self.measurements.get(MOUNT_CONTROL_STRESS)
        specification = next((item for item in self.test.get("measurements", [])
                              if item.get("kind") == MOUNT_CONTROL_STRESS), None)
        if specification is not None and specification.get("subject") == subject_id \
                and stress is not None and stress.phase != "unarmed":
            if stress.failures or stress.last.get("frame") != snapshot.get("frame"):
                raise ValueError("mounted control stress subject is not current at this boundary")
            selected_subject = stress.actor
        selected = select_current_actor(snapshot, selected_subject)
        return next(actor for actor in snapshot["actors"] if actor.get("handle") == selected["handle"])

    def _candidates(self, subject_id, snapshot):
        spec = self.specs[subject_id]
        if SENTRET_THROW in self.measurements and subject_id in self.measurements[SENTRET_THROW].subjects:
            exact = self.measurements[SENTRET_THROW].subjects[subject_id]
            selected = select_current_actor(snapshot, exact)
            return [a for a in snapshot["actors"] if a["handle"] == selected["handle"]]
        height_subject = self.measurements.get(HEIGHT_CONTROL)
        height_subject = height_subject.result().get("subject") \
            if height_subject is not None else None
        candidates = []
        for actor in snapshot.get("actors", []):
            if actor.get("species") == spec["species"] and actor.get("role") == spec["role"] and actor.get("active") is True:
                measured_height_actor = bool(height_subject) \
                    and actor.get("handle") == height_subject.get("handle")
                if subject_id in self.subjects and actor.get("handle") != self.subjects[subject_id]["handle"]:
                    continue
                if spec["acquire"] == "spawn" and not measured_height_actor \
                        and self.first_handles is not None \
                        and _handle(actor["handle"]) in self.first_handles:
                    continue
                if spec["acquire"] == "spawn" and not measured_height_actor \
                        and self.first_subjects is not None \
                        and _actor_identity(actor) in self.first_subjects:
                    continue
                if spec["acquire"] == "spawn" and self.spawn_setup is not None and actor.get("handle") != self.spawn_setup["subject"]["handle"]:
                    continue
                select_current_actor(snapshot, actor)
                candidates.append(actor)
        return candidates

    def actor_inspect_args(self, subject_id, snapshot):
        """Resolve one already bound subject; recipes cannot supply raw handles."""
        if self.closed or ACTOR_INSPECT not in self.measurements or subject_id not in self.subjects:
            raise ValueError("actor Inspect requires its bound measured subject")
        if snapshot != self.latest:
            raise ValueError("actor Inspect requires the current measured boundary")
        selected = select_current_actor(snapshot, self.subjects[subject_id])
        return {"handle": selected["handle"]["value"]}

    def walk_reset_args(self, subject_id, snapshot):
        """Resolve prepared setup from the bound actor, not recipe-stored addresses."""
        if self.closed or self.test["mode"] != "prepared" or subject_id not in self.subjects:
            raise ValueError("Walk reset requires a bound prepared subject")
        selected = select_current_actor(snapshot, self.subjects[subject_id])
        return validate_command("walk-policy.reset", {"subject": selected})

    def mount_walk_fixture_args(self, args, snapshot):
        if self.closed or self.test["mode"] not in ("prepared", "observer-control") or args.get("subject") not in self.subjects:
            raise ValueError("Mount Walk setup requires a bound prepared subject")
        selected = select_current_actor(snapshot, self.subjects[args["subject"]])
        return validate_command("mount-walk.configure", {**args, "subject": selected})

    def mount_teleport_fixture_args(self, args, snapshot):
        if self.closed or not {MOUNTED_TELEPORT_MATRIX, WARP_GATE}.intersection(self.measurements) \
                or self.test["mode"] != "prepared" \
                or args.get("subject") not in self.subjects:
            raise ValueError("Mount Teleport setup requires its bound matrix subject")
        selected = select_current_actor(snapshot, self.subjects[args["subject"]])
        return validate_command("mount-teleport.configure", {**args, "subject": selected})

    def mount_teleport_restore_args(self, args, snapshot):
        if self.closed or WARP_GATE not in self.measurements or self.test["mode"] != "prepared" or args.get("subject") not in self.subjects:
            raise ValueError("Mount Teleport restore requires the bound warp subject")
        selected = select_current_actor(snapshot, self.subjects[args["subject"]])
        return validate_command("mount-teleport.restore", {"subject": selected})

    def bind(self, subject_id, snapshot):
        if self.closed: raise ValueError("test evaluator is closed")
        if subject_id not in self.specs: raise ValueError("undeclared subject")
        candidates = self._candidates(subject_id, snapshot)
        if "actor-binding-context-v1" in self.measurements:
            measured = self.measurements["actor-binding-context-v1"].result().get("subject")
            candidates = [actor for actor in candidates if measured and actor["handle"] == measured["handle"]]
        if HEIGHT_CONTROL in self.measurements:
            measured = self.measurements[HEIGHT_CONTROL].result().get("subject")
            candidates = [actor for actor in candidates if measured and actor["handle"] == measured["handle"]]
        if len(candidates) != 1: raise ValueError("subject must name exactly one verified live actor")
        actor = candidates[0]
        selected = select_current_actor(snapshot, actor)
        if BLOCKED_NOTICE_HOP in self.measurements:
            from tools.overworld.devtools_blocked_notice_hop_measurement import validate_bound
            selected = validate_bound(snapshot, selected)
        if subject_id in self.subjects:
            select_current_actor(snapshot, self.subjects[subject_id])
            if selected != self.subjects[subject_id] and selected["handle"] != self.subjects[subject_id]["handle"]:
                raise ValueError("cannot rebind a test subject to a replacement")
            return deepcopy(self.subjects[subject_id])
        if self.specs[subject_id]["acquire"] == "spawn":
            key = _handle(selected["handle"])
            measured = self.measurements.get(HEIGHT_CONTROL)
            measured = measured.result().get("subject") if measured is not None else None
            measured_height_actor = bool(measured) and selected["handle"] == measured.get("handle")
            if self.first_handles is None or (not measured_height_actor and (
                    key in self.first_handles or
                    (self.events[(key, "ACTOR_ATTACHED")] < 1
                     and key not in self._prepared_attached))):
                raise ValueError("spawn acquisition needs a new full handle and observed native attachment")
        self.subjects[subject_id] = selected
        if MOUNT_CONTROL_STRESS in self.measurements:
            specification = next(item for item in self.test["measurements"]
                                 if item["kind"] == MOUNT_CONTROL_STRESS)
            if specification["subject"] != subject_id:
                raise ValueError("mounted control stress bind subject differs")
            self.measurements[MOUNT_CONTROL_STRESS].arm(
                selected, snapshot, trace_sequences=self.last_sequence)
        if MOUNT_DETACH_FOLLOWER_RESUME in self.measurements:
            specification = next(item for item in self.test["measurements"]
                                 if item["kind"] == MOUNT_DETACH_FOLLOWER_RESUME)
            if specification["subject"] != subject_id:
                raise ValueError("mount detach follower resume bind subject differs")
            self.measurements[MOUNT_DETACH_FOLLOWER_RESUME].arm(
                selected, snapshot, trace_sequences=self.last_sequence)
        if self.latest is not None and not self.sampled_frames and snapshot["frame"] > self.latest["frame"]:
            # Prepared native setup can advance many unmeasured frames. Bind
            # establishes its retained current boundary, not gameplay credit.
            self.latest = deepcopy(snapshot)
        return deepcopy(selected)

    def check(self, predicate, snapshot=None):
        predicate = validate_predicate(predicate, self.specs)
        snapshot = snapshot if snapshot is not None else self.latest
        if snapshot is None: raise ValueError("predicate has no coherent snapshot")
        if self.uses_raw_records and (self.latest is None or snapshot.get("frame") != self.latest["frame"]):
            raise ValueError("cadence predicate requires the current measured frame")
        if self.uses_raw_records and snapshot.get("fieldAvailable") is False \
                and PLAYER_HEALTH_ZERO_LOAD not in self.measurements:
            # A loading interval is retained but has no player or actor facts.
            # Continue the bounded action; never satisfy its end condition.
            return False
        kind = predicate["kind"]
        if kind == "field-task-active":
            if snapshot.get("observationBoundary") != "main-task-queue-completion":
                raise ValueError("field task needs a completed queue")
            task = _int(snapshot.get("fieldControl", {}).get("taskPointer"), "field task", 0, 0xFFFFFFFF)
            if task and (task % 4 or not 0x02000000 <= task <= 0x023FFFFF):
                raise ValueError("invalid field task pointer")
            return bool(task)
        if kind in MOVEMENT_PREDICATE_KINDS:
            return check_movement_predicate(predicate, snapshot)
        if kind == "measurement-complete":
            measurement = self.measurements.get(predicate["measurement"])
            if measurement is None: raise ValueError("measurement has no current source inputs")
            if predicate["measurement"] == ACCELERATION:
                return measurement.ready and self._acceleration_closed == set(self.specs) \
                    and self.frames >= self.test["budgets"]["minObservedFrames"]
            # A previously completed behavior is not permission to end a
            # longer same-subject witness before its declared frame floor.
            report = measurement.progress_result() if predicate["measurement"] in ("unmounted-cadence-v1", "unmounted-game-cadence-v1", ROUTE_CONTROL) else measurement.result()
            return report["ready"] is True \
                and self.frames >= self.test["budgets"]["minObservedFrames"]
        if kind == "measurement-stage":
            measurement = self.measurements.get(predicate["measurement"])
            if measurement is None: raise ValueError("measurement has no current source inputs")
            return measurement.stage(predicate["stage"])
        if kind == "acceleration-role-started":
            subject = predicate["subject"]
            if subject not in self.subjects or subject != self._acceleration_active:
                return False
            state = self.measurements[ACCELERATION].roles.get(self._acceleration_role(subject))
            return bool(state and len(state["motions"]) + int(state["recorder"].current is not None) >= predicate["value"])
        if kind == "acceleration-role-complete":
            return self.acceleration_role_complete(predicate["subject"])
        if kind == "actor-present":
            subject = predicate["subject"]
            if subject in self.subjects:
                self._actor(subject, snapshot)
                return True
            candidates = self._candidates(subject, snapshot)
            if "actor-binding-context-v1" in self.measurements:
                measured = self.measurements["actor-binding-context-v1"].result().get("subject")
                return bool(measured and any(actor["handle"] == measured["handle"] for actor in candidates))
            if HEIGHT_CONTROL in self.measurements:
                measured = self.measurements[HEIGHT_CONTROL].result().get("subject")
                return bool(measured and any(actor["handle"] == measured["handle"] for actor in candidates))
            if len(candidates) > 1: raise ValueError("subject acquisition is ambiguous")
            if not candidates: return False
            if self.specs[subject]["acquire"] == "spawn":
                key = _handle(candidates[0]["handle"])
                return self.first_handles is not None and key not in self.first_handles and self.events[(key, "ACTOR_ATTACHED")] > 0
            return True
        if kind == "actor-count":
            candidates = self._candidates(predicate["subject"], snapshot)
            if "motionPhase" in predicate:
                if any(not isinstance(actor.get("motionPhase"), str) for actor in candidates):
                    raise ValueError("current actor motion phase is missing")
                candidates = [actor for actor in candidates if actor["motionPhase"] == predicate["motionPhase"]]
            actual = len(candidates)
        elif kind == "event-count":
            self._actor(predicate["subject"], snapshot)
            actual = self.events[(_handle(self.subjects[predicate["subject"]]["handle"]), predicate["event"])]
        elif kind == "frame-count":
            actual = self.frames
        else:
            actual = self._actor(predicate["subject"], snapshot) if kind == "actor-field" else snapshot.get("player")
            for part in predicate["path"].split("."):
                if not isinstance(actual, dict) or part not in actual:
                    raise ValueError("required observed field is missing: " + predicate["path"])
                actual = actual[part]
        expected = predicate["value"]
        if type(actual) is not type(expected): raise ValueError("observed predicate value has the wrong type")
        return {"eq": lambda: actual == expected, "ne": lambda: actual != expected,
                "gte": lambda: actual >= expected, "lte": lambda: actual <= expected}[predicate["operator"]]()

    def _events(self, events, frame):
        if not isinstance(events, (list, tuple)) or len(events) > 2048:
            raise ValueError("frame events must be a bounded list")
        for event in events:
            if not isinstance(event, dict) or event.get("frame") != frame or not isinstance(event.get("data"), dict):
                raise ValueError("event must belong to this coherent game frame")
            data = event["data"]
            if event.get("kind") == "trace-status":
                if data.get("coverageComplete") is False or data.get("code") in {
                    "sequence-reset", "invalid-native-ring", "window-rearmed-externally", "read-recovered",
                    "unread-events-lost", "trace-filter-changed", "field-samples-unavailable"}:
                    self.fail("trace-incomplete", "native trace coverage is incomplete", data)
                elif data.get("code") == "window-ended" and data.get("reason") != "stopped":
                    self.fail("trace-ended", "native trace expired before test completion", data)
                continue
            if event.get("kind") != "native": continue
            stream = _int(data.get("traceStream"), "trace stream", 1, 1000000)
            sequence = _int(data.get("sequence"), "native sequence", 1, 0xFFFFFFFF)
            if sequence != self.last_sequence.get(stream, 0) + 1:
                raise ValueError("native event sequence is missing, duplicated, or reordered")
            self.last_sequence[stream] = sequence
            actor = data.get("actor")
            if not isinstance(actor, dict) or set(actor) != set(HANDLE_FIELDS) - {"value"}:
                raise ValueError("native event lacks a full actor handle")
            handle = {"value": data.get("actorHandle"), **actor}
            for field in HANDLE_FIELDS:
                _int(handle[field], "event handle " + field, 0 if field == "slot" else 1, 0xFFFFFFFF)
            if handle["value"] != (handle["generation"] << 16) | handle["slot"]:
                raise ValueError("native event actorHandle differs")
            if data.get("event") not in EVENTS: raise ValueError("unknown native trace event")
            self.events[(_handle(handle), data["event"])] += 1
            if len(self.events) > 8192: raise ValueError("native identity/event capacity exceeded")

    def observe_start_boundary(self, snapshot, events, start_frame):
        """Retain a prepared record-start prefix, with no gameplay credit.

        Semantic records belong to the actual start interval. Older native
        diagnostics may be drained here for the first time. Neither supplies
        event assertions, subject acquisition or measured frame counts.
        """
        if self.closed or self.subjects or self.sampled_frames or self.uses_raw_records \
                or self.measurements or self.test["mode"] != "prepared":
            raise ValueError("start boundary requires unbound prepared setup without measurements")
        if getattr(self, "_start_boundary_observed", False):
            raise ValueError("record-start boundary was already observed")
        old_sequences, old_events = deepcopy(self.last_sequence), self.events.copy()
        try:
            end = _int(snapshot.get("frame"), "start endpoint frame", 0, 0xFFFFFFFF)
            start = _int(start_frame, "record-start frame", 0, end)
            if self.latest is not None and (start < self.latest["frame"] or end <= self.latest["frame"]):
                raise ValueError("record-start boundary moved backwards or did not advance")
            if snapshot.get("prepared") is not True or snapshot.get("fieldAvailable") is not True \
                    or snapshot.get("observationBoundary") != "main-task-queue-completion":
                raise ValueError("record-start endpoint is not a prepared complete field queue")
            cycle = _int(snapshot.get("nativeCycle"), "record-start native cycle", 0, 0xFFFFFFFF)
            if self.latest is not None and cycle < self.latest.get("nativeCycle", 0):
                raise ValueError("record-start native clock moved backwards")
            if not isinstance(events, list) or len(events) > 8192:
                raise ValueError("record-start prefix exceeds its bound")
            native_sequence = None
            for event in events:
                if not isinstance(event, dict) or event.get("kind") not in ("native", "native-observation", "trace-status"):
                    raise ValueError("unknown record-start event")
                lower = 0 if event["kind"] == "native-observation" else start
                frame = _int(event.get("frame"), "record-start event frame", lower, end)
                self._events([event], frame)
                if event["kind"] == "native-observation":
                    sequence = _int(event["data"].get("sequence"), "record-start native sequence", 1, 0xFFFFFFFF)
                    if native_sequence is not None and sequence != native_sequence + 1:
                        raise ValueError("record-start native prefix has a sequence gap")
                    native_sequence = sequence
            if native_sequence is not None and native_sequence != snapshot.get("nativeObservation", {}).get("sequence"):
                raise ValueError("record-start native prefix does not reach its endpoint")
            if self.failures:
                self.last_sequence = old_sequences
                return self.result()
            self._start_boundary_observed = True
            return self.observe(snapshot, count_frame=False)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            self.last_sequence = old_sequences
            return self.fail("start-boundary-invalid", str(error))
        finally:
            self.events = old_events

    def observe_initial(self, snapshot, events=(), *, start_frame=None):
        """Consume an exact record-start prefix without assertion/motion credit."""
        if self.latest is not None or self.subjects or self.closed:
            raise ValueError("initial prefix is only valid before observation")
        kinds = set(self.measurements)
        if self.uses_raw_records or kinds not in (
                {"actor-binding-context-v1"}, {HEIGHT_CONTROL}):
            raise ValueError("initial prefix requires the binding or height measurement")
        height_control = kinds == {HEIGHT_CONTROL}
        try:
            end = _int(snapshot.get("frame"), "initial frame", 0, 0xFFFFFFFF)
            start = _int(end if start_frame is None else start_frame, "initial start frame", 0, end)
            if not isinstance(events, list) or len(events) > 8192:
                raise ValueError("initial event prefix exceeds its bound")
            if height_control and not events:
                # Older retained host fixtures begin their natural spawn on
                # the next sampled frame. They still must complete the same
                # meter; an empty prefix grants no boot evidence.
                return self.observe(snapshot, count_frame=False)
            native_sequence = None
            for event in events:
                # Native diagnostics are installed before boot and first drain
                # here. Semantic trace coverage begins only at record.start.
                lower = 0 if event.get("kind") == "native-observation" else start
                frame = _int(event.get("frame"), "initial event frame", lower, end)
                self._events([event], frame)
                if event.get("kind") == "native-observation":
                    data = event["data"]
                    sequence = _int(data.get("sequence"), "initial native sequence", 1, 0xFFFFFFFF)
                    if native_sequence is not None and sequence != native_sequence + 1:
                        raise ValueError("initial native prefix has a sequence gap")
                    native_sequence = sequence
                    if data.get("setupMode") != "normal" \
                            or (not height_control
                                and data.get("observation") == "actor-binding-context"):
                        raise ValueError("initial native capture started outside its declared boundary")
            if native_sequence is not None and native_sequence != snapshot.get("nativeObservation", {}).get("sequence"):
                raise ValueError("initial native prefix does not reach the endpoint")
            if self.failures:
                return self.result()
            if height_control:
                measured = self.measurements[HEIGHT_CONTROL].observe_initial(snapshot, events)
                if measured["failures"]:
                    return self.fail("measurement-failed", HEIGHT_CONTROL,
                                     measured["failures"])
                self.first_handles = {_handle(actor["handle"])
                                      for actor in snapshot.get("actors", [])
                                      if actor.get("active") is True}
                self.first_subjects = {_actor_identity(actor)
                                       for actor in snapshot.get("actors", [])
                                       if actor.get("active") is True}
                self.latest = deepcopy(snapshot)
                return self.result()
            # _events checks identities and sequences but its meaning counts
            # belong outside this proof window. Preserve only stream counters.
            self.events.clear()
            self.measurements["actor-binding-context-v1"].seed_trace_prefix(self.last_sequence)
            return self.observe(snapshot, count_frame=False)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            return self.fail("initial-prefix-invalid", str(error))

    def observe(self, snapshot, events=(), count_frame=True, *, full_report=True):
        if self.closed: raise ValueError("test evaluator is closed")
        try:
            if type(count_frame) is not bool: raise ValueError("count_frame must be boolean")
            if not isinstance(snapshot, dict): raise ValueError("snapshot must be an object")
            frame = _int(snapshot.get("frame"), "game frame", 0, 0xFFFFFFFF)
            if self.uses_raw_records and self._raw_frame != frame:
                raise ValueError("cadence observations require the raw-record path")
            prepared_refresh = self.uses_raw_records and not count_frame and not self.subjects \
                and self.test["mode"] == "prepared" and snapshot.get("prepared") is True \
                and getattr(self, "_raw_prepared_refresh_frame", None) == frame
            prepared_refresh = prepared_refresh or (not self.uses_raw_records and not count_frame and not self.subjects
                and getattr(self, "_prepared_command_refresh_frame", None) == frame)
            if self.latest is not None and ((frame <= self.latest["frame"] and not prepared_refresh) or
                    (count_frame and frame != self.latest["frame"] + 1)):
                raise ValueError("coherent game frame is missing, duplicated, or reordered")
            if type(snapshot.get("prepared")) is not bool:
                raise ValueError("snapshot must declare prepared state")
            if self.test["mode"] == "normal" and snapshot["prepared"]:
                raise ValueError("normal test was changed by prepared setup")
            absent_setup = self.uses_raw_records and snapshot.get("fieldAvailable") is False and not self.subjects and not count_frame
            if not isinstance(snapshot.get("actors"), list) and not absent_setup: raise ValueError("snapshot has no actor list")
            if self.first_handles is None and not absent_setup:
                self.first_handles = {_handle(actor["handle"]) for actor in snapshot["actors"] if actor.get("active") is True}
                self.first_subjects = {_actor_identity(actor) for actor in snapshot["actors"] if actor.get("active") is True}
            self.latest = deepcopy(snapshot)
            self.sampled_frames += bool(count_frame)
            if self.sampled_frames > self.test["budgets"]["maxFrames"]: raise ValueError("overall observation frame budget exceeded")
            self._events(events, frame)
            if self.test.get("measurements") and not self.measurements_installed:
                raise ValueError("measurement has no current source inputs")
            stress_subject = None
            teleport_subject = next((item["subject"] for item in self.test.get("measurements", [])
                                     if item.get("kind") == MOUNTED_TELEPORT_MATRIX), None)
            transition_subject = next((item["subject"] for item in self.test.get("measurements", [])
                                       if item.get("kind") in (WILD_TRANSITION, FOLLOWER_TRANSITION)), None)
            for kind, measurement in self.measurements.items():
                if kind in RAW_MEASUREMENTS: continue  # already advanced at this exact raw boundary
                specification = next(item for item in self.test["measurements"] if item["kind"] == kind)
                if kind in (FOLLOWER_STOP, RAM_UNTIL_CRASH, RAM_BEHIND, RAM_LEDGE, RAM_BRIEF_NOTICE, BLOCKED_NOTICE_HOP) and specification["subject"] not in self.subjects:
                    continue
                if kind == APPEAR_HOP and self.spawn_setup is None:
                    continue
                if kind == MOUNT_CONTROL_STRESS:
                    stress_subject = specification["subject"]
                    # Prepared setup is outside the stress window. Binding arms
                    # the exact actor at the retained completed-frame boundary.
                    if stress_subject not in self.subjects:
                        continue
                measured = measurement.observe(snapshot, events)
                if measured["failures"]:
                    self.fail("measurement-failed", kind, measured["failures"])
                bound = self.subjects.get(specification["subject"])
                identity_fields = ("handle", "species", "subjectIdentity") if kind == MOUNT_CONTROL_STRESS \
                    else ("handle", "species", "role", "subjectIdentity")
                if bound and measured["subject"] and any(bound.get(key) != measured["subject"].get(key)
                        for key in identity_fields):
                    raise ValueError("measurement and bound subject identities differ")
            for subject, bound in self.subjects.items():
                if subject in (stress_subject, teleport_subject, transition_subject):
                    # This meter owns the exact Mounted -> Follower -> Mounted
                    # role transfer or Teleport visibility identity transition.
                    # The generic binding requires one fixed role/presentation.
                    continue
                if not self.expected_control_identity_failure(snapshot, bound):
                    self._actor(subject, snapshot)
            # Acquisition waits and setup samples are retained, not credited as
            # continuous live-subject observation toward a proof frame floor.
            if count_frame and set(self.subjects) == set(self.specs): self.frames += 1
            for predicate in self.test["assertions"]:
                if count_frame and predicate["when"] == "always" and ("subject" not in predicate or predicate["subject"] in self.subjects):
                    if not self.check(predicate): self.fail("assertion-failed", "always assertion failed", predicate)
        except (ValueError, KeyError, TypeError) as error:
            self.fail("observation-invalid", str(error))
        return self.result(full_report=full_report)

    def observe_save_reload(self, receipt):
        """Accept one checked private-session boundary without frame credit."""
        if self.closed or self.uses_raw_records or self.subjects or self.latest is None:
            return self.fail("save-reload-invalid", "reload needs an active subjectless observation")
        try:
            boundary, snapshot = receipt["saveReload"], receipt["snapshot"]
            export, loaded = boundary["export"], boundary["loaded"]
            if (boundary["state"] != "loaded"
                    or boundary["sourceSessionId"] == boundary["newSessionId"]
                    or boundary["sourceFrame"] != self.latest["frame"]
                    or boundary["sourceSaveSha256"] != self.latest["sourceSaveSha256"]
                    or boundary["sourceRomSha256"] != self.latest["romSha256"]
                    or not isinstance(export["sha256"], str) or len(export["sha256"]) != 64
                    or export["sha256"] == boundary["sourceSaveSha256"]
                    or export["sha256"] != loaded["sha256"]
                    or export["sha256"] != boundary["loadedSaveSha256"]
                    or export["size"] != loaded["size"]
                    or snapshot["romSha256"] != boundary["sourceRomSha256"]
                    or snapshot["sourceSaveSha256"] != export["sha256"]
                    or snapshot.get("prepared") is not False):
                raise ValueError("exported and loaded private cartridge identity differs")
            _int(snapshot.get("frame"), "reload boot frame", 0, 0xFFFFFFFF)
            self.latest = deepcopy(snapshot)
            self.last_sequence = {}
            self.events.clear()
            self.first_handles = None
            self.first_subjects = None
            self.save_reloads = getattr(self, "save_reloads", 0) + 1
        except (KeyError, TypeError, ValueError) as error:
            return self.fail("save-reload-invalid", str(error))
        return self.result()

    def finish(self):
        if self.closed: return self.result()
        if ACCELERATION in self.measurements and (self._acceleration_active is not None
                or self._acceleration_closed != set(self.specs)):
            self.fail("acceleration-window-open", "both exact windows must be sealed")
        if ACCELERATION in self.measurements and self._acceleration_intent is not None and not self._acceleration_intent_closed:
            self.fail("acceleration-intent-open", "Walk intent must be closed")
        for kind, measurement in self.measurements.items():
            measured = measurement.finish()
            if not measured["passed"]:
                self.fail("measurement-incomplete", kind, {"failures": measured["failures"],
                    "measurementErrors": measured.get("measurementErrors"), "completeMotions": measured.get("completeMotions")})
        if set(self.subjects) != set(self.specs): self.fail("subject-unbound", "not all required live subjects were bound")
        if self.frames < self.test["budgets"]["minObservedFrames"]:
            self.fail("observation-short", "minimum observed frame count was not reached")
        for predicate in self.test["assertions"]:
            try:
                if not self.check(predicate): self.fail("assertion-failed", "final assertion failed", predicate)
            except (ValueError, KeyError, TypeError) as error:
                self.fail("assertion-unavailable", str(error), predicate)
        self.closed = True
        self._passed = not self.failures
        return self.result()

    def result(self, *, full_report=True):
        return deepcopy({"state": "failed" if self.failures else "passed" if self._passed else "running",
            "passed": self._passed and not self.failures, "acceptedProof": False,
            "observedFrames": self.frames, "sampledFrames": self.sampled_frames,
            "saveReloads": getattr(self, "save_reloads", 0),
            "lastFrame": self.latest.get("frame") if self.latest else None,
            "subjects": self.subjects, "failures": self.failures,
            "spawnSetup": deepcopy(self.spawn_setup),
            "assertions": self.test["assertions"], "requirements": self.test["requirements"],
            **({"measurements": {key: value.result() for key, value in self.measurements.items()}}
               if full_report and self.test.get("measurements") else {}),
            "scope": "typed shared-tool observations only; registration and claim proof remain controller gates"})
