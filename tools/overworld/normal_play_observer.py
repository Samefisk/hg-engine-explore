"""Read-only normal-play observations, independent of emulator setup.

Expected chain ranges come from the authored field contract, not the game's
variance generator or private remaining-move counter. These evaluators retain
raw motion samples so a failed visible movement cannot become an endpoint pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from tools.overworld.spawn_identity import live_spawn_flags


CHAIN_KEYS = (
    "ramAccelerationSteps", "chainMovementVariance", "ramMaxSpeed",
    "chainPauseVariance", "chainPauseAction", "chainPauseActionChance",
    "chainRepositionJumpCount", "chainRepositionSpeed", "chainRepositionDistance",
    "chainRepositionAllowCardinal", "chainRepositionAllowDiagonal", "walkPause",
    "walkPauseVariance", "hopPause",
)


def decode_lane(data: bytes, schema: dict[str, Any]) -> dict[str, int]:
    """Use the authored schema for the public resolver's immutable lane value."""
    if len(data) != schema["compactSize"]:
        raise ValueError("resolved lane has the wrong byte count")
    fields = {item["key"]: item for item in schema["fields"]}
    result = {}
    for key in CHAIN_KEYS:
        field = fields[key]
        size = {"u8": 1, "u16": 2, "u32": 4}[field["cType"]]
        value = int.from_bytes(
            data[field["offset"]:field["offset"] + size],
            "little",
        )
        if "bitOffset" in field:
            value = (value >> field["bitOffset"]) \
                & ((1 << field["bitWidth"]) - 1)
        result[key] = value
    return result


def live_identity(actor, source, engine, *, species, role, current_epoch) -> bool:
    """Require the public actor and live manager object to name the same subject."""
    handle = actor.get("handle", {})
    pointer = source.get("object", 0)
    return (
        actor.get("active") is True and actor.get("species") == species
        and actor.get("role") == role and actor.get("presentationAttached") is True
        and actor.get("subjectIdentity", 0) > 0
        and actor.get("subjectIdentity") == source.get("personality")
        and ((role == "WILD" and 0 <= handle.get("slot", -1) < 6)
             or (role == "FOLLOWER" and handle.get("slot") == 7))
        and handle.get("fieldEpoch") == current_epoch and current_epoch > 0
        and all(handle.get(key, 0) > 0 for key in
                ("generation", "mapGeneration", "encounterGeneration"))
        and live_spawn_flags(source.get("active")) and source.get("species") == species
        and pointer > 0 and engine.get("pointer") == pointer
        and engine.get("in_manager") is True and engine.get("active") is True
        and engine.get("object_manager") == engine.get("current_manager")
        and engine.get("current_manager", 0) > 0
        and engine.get("object_id") == source.get("object_id")
        and source.get("object_id") == 0xE0 + handle.get("slot", -1)
        and engine.get("spawn_object_id") == source.get("object_id")
        and engine.get("object_map_id") == source.get("map_id")
        and engine.get("spawn_map_id") == source.get("map_id")
        and engine.get("current_map_id") == source.get("map_id")
        and engine.get("encounter_generation") == source.get("encounter_generation")
        and handle.get("encounterGeneration") == source.get("encounter_generation")
        and engine.get("script_id") == 2074
    )


def motion_key(actor):
    return (
        actor["handle"]["value"], actor["motionKind"],
        actor["origin"]["x"], actor["origin"]["y"],
        actor["target"]["x"], actor["target"]["y"],
    )


def complete_travel(motion):
    """A sampled terminal pose can supply the last travel frame, not missing frames."""
    samples = motion["samples"]
    end = motion.get("travelEnd")
    if not samples or end is None or motion["duration"] <= 0:
        return False
    elapsed = [sample["elapsed"] for sample in samples]
    frames = [sample["frame"] for sample in samples]
    if end["elapsed"] != motion["duration"]:
        return False
    if elapsed[-1] != motion["duration"]:
        dx = motion["target"][0] - motion["origin"][0]
        dz = motion["target"][1] - motion["origin"][1]
        progress = (end["render"][0] - samples[-1]["render"][0]) * dx \
            + (end["render"][1] - samples[-1]["render"][2]) * dz
        if (dx or dz) and progress <= 0:
            return False
        elapsed.append(end["elapsed"])
        frames.append(end["frame"])
    return elapsed[0] in (0, 1) \
        and elapsed == list(range(elapsed[0], motion["duration"] + 1)) \
        and all(second == first + 1 for first, second in zip(frames, frames[1:]))


@dataclass
class MotionRecorder:
    """One actor's live samples; exact duplicate hooks alone are deduplicated."""

    current: dict | None = None
    completed: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    last_sample_key: tuple | None = None
    expected_pause_by_kind: dict = field(default_factory=dict)

    def _fail(self, reason, **details):
        self.failures.append({"reason": reason, **details})

    def observe(self, frame, actor, engine):
        moving = actor["motionKind"] in ("WALK", "HOP", "TELEPORT", "REPOSITION") \
            and actor["motionPhase"] in ("PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING")
        # Motion records cross JSON storage before independent acceptance.
        # Keep their key in that native wire type, not a tuple that reloads
        # as a list and makes an otherwise identical replay differ.
        key = list(motion_key(actor)) if moving else None
        current = self.current
        if current is not None:
            target_render = [(coordinate << 16) + 0x8000 for coordinate in current["target"]]
            if current.get("travelEnd") is None and actor["motionElapsed"] == current["duration"] \
                    and [engine["pos_x"], engine["pos_z"]] == target_render:
                current["travelEnd"] = {"frame": frame, "elapsed": actor["motionElapsed"],
                                        "render": [engine["pos_x"], engine["pos_z"]]}
                current["travelEndRender"] = [engine["pos_x"], engine["pos_y"], engine["pos_z"]]
                current["travelEndLogical"] = [actor["logical"]["x"], actor["logical"]["y"]]
            elif current.get("travelEnd") is None and moving and key != current["key"] \
                    and actor["handle"] == current["handle"] \
                    and actor["motionPhase"] in ("PLANNED", "MOVING") \
                    and actor["motionElapsed"] == 0 \
                    and [actor["origin"]["x"], actor["origin"]["y"]] == current["target"] \
                    and [actor["logical"]["x"], actor["logical"]["y"]] == current["target"] \
                    and [engine["pos_x"], engine["pos_z"]] == target_render \
                    and engine.get("unk88_y", 0) == 0 \
                    and actor["commitSequence"] == ((current["commitBefore"] + 1) & 0xFFFFFFFF) \
                    and current["samples"] \
                    and current["samples"][-1]["elapsed"] == current["duration"] - 1 \
                    and frame == current["samples"][-1]["frame"] + 1 \
                    and frame == current["startFrame"] + current["duration"] \
                        - current["samples"][0]["elapsed"]:
                # A zero-pause successor can replace the old elapsed value
                # before the completed-queue observation. Its exact origin
                # pose is also the observed final pose of the previous motion.
                # Keep it separate from raw samples; complete_travel still
                # requires every earlier elapsed value and adjacent frame.
                current["travelEnd"] = {"frame": frame, "elapsed": current["duration"],
                                        "render": [engine["pos_x"], engine["pos_z"]],
                                        "observedBy": "successor-origin", "successorElapsed": 0}
            if current.get("commitFrame") is None \
                    and actor["commitSequence"] == ((current["commitBefore"] + 1) & 0xFFFFFFFF):
                current["commitFrame"] = frame
        if current is not None and (key != current["key"] or not moving):
            # The old endpoint can be observed before a zero-pause successor
            # advances. Use that real pose, never the successor's moving pose.
            end = current.get("travelEnd")
            successor_pose = []
            if type(actor["motionDuration"]) is int and actor["motionDuration"] > 0:
                for axis in ("x", "y"):
                    delta = (actor["target"][axis] - actor["origin"][axis]) << 16
                    step = abs(delta) // actor["motionDuration"]
                    successor_pose.append((actor["origin"][axis] << 16) + 0x8000
                                          + (step if delta >= 0 else -step))
            # At elapsed1 of a two-frame tile, the new motion has already
            # crossed its tile boundary. Its logical target is not the old
            # motion's endpoint. Keep the endpoint actually read last frame.
            fast_tile = (actor["motionDuration"] == 2 and max(
                abs(actor["target"][axis] - actor["origin"][axis]) for axis in ("x", "y")) == 1)
            successor_logical = [actor["target" if fast_tile else "origin"][axis] for axis in ("x", "y")]
            observed_successor = (
                current["kind"] == "WALK" and moving and actor["motionKind"] == "WALK"
                and actor["motionPhase"] == "MOVING"
                and type(actor["motionElapsed"]) is int and actor["motionElapsed"] == 1
                and actor["handle"] == current["handle"]
                and actor["behaviorFingerprint"] == current["fingerprint"]
                and [actor["origin"]["x"], actor["origin"]["y"]] == current["target"]
                and [actor["logical"]["x"], actor["logical"]["y"]] == successor_logical
                and (not fast_tile or current.get("travelEndLogical") == current["target"])
                and end is not None and end["frame"] == frame - 1
                and current.get("travelEndRender") is not None
                and complete_travel(current)
                and [engine["pos_x"], engine["pos_z"]] == successor_pose
                and engine.get("unk88_y", 0) == 0
            )
            commit = actor["commitSequence"]
            if commit != (current["commitBefore"] + 1) & 0xFFFFFFFF:
                self._fail("missing-terminal-commit", expected=current["commitBefore"] + 1,
                           actual=commit)
            else:
                current["finishFrame"] = frame
                current["commitAfter"] = commit
                current["terminalLogical"] = (list(current["travelEndLogical"])
                    if observed_successor and fast_tile
                    else [actor["logical"]["x"], actor["logical"]["y"]])
                current["terminalRender"] = (list(current["travelEndRender"]) if observed_successor
                                             else [engine["pos_x"], engine["pos_y"], engine["pos_z"]])
                if not complete_travel(current):
                    self._fail("incomplete-travel", motion=current["kind"], duration=current["duration"],
                               elapsed=[sample["elapsed"] for sample in current["samples"]])
                current["pauseFrames"] = frame - current["commitFrame"]
                if current["expectedPauseFrames"] is not None \
                        and current["pauseFrames"] != current["expectedPauseFrames"]:
                    self._fail("settle-pause-time", motion=current["kind"], actual=current["pauseFrames"],
                               expected=current["expectedPauseFrames"])
                if current["terminalLogical"] != current["target"]:
                    self._fail("terminal-logical-target", motion=current["kind"])
                expected_render = [(coordinate << 16) + 0x8000 for coordinate in current["target"]]
                if [current["terminalRender"][0], current["terminalRender"][2]] != expected_render:
                    self._fail("terminal-render-target", actual=[engine["pos_x"], engine["pos_z"]],
                               expected=expected_render)
                self.completed.append(current)
            self.current = None
        if moving and self.current is None:
            self.current = {
                "key": key, "kind": actor["motionKind"], "startFrame": frame,
                "handle": dict(actor["handle"]),
                "origin": [actor["origin"]["x"], actor["origin"]["y"]],
                "target": [actor["target"]["x"], actor["target"]["y"]],
                "commitBefore": actor["commitSequence"], "duration": actor["motionDuration"],
                "fingerprint": actor["behaviorFingerprint"], "samples": [],
                "expectedPauseFrames": self.expected_pause_by_kind.get(actor["motionKind"]),
                "travelEnd": None, "commitFrame": None,
            }
        current = self.current
        if current is None or actor["motionPhase"] != "MOVING":
            return
        elapsed = actor["motionElapsed"]
        sample_key = (frame, key, elapsed)
        if sample_key == self.last_sample_key:
            return
        self.last_sample_key = sample_key
        sample = {"frame": frame, "elapsed": elapsed,
                  "render": [engine["pos_x"], engine["pos_y"], engine["pos_z"]],
                  "jumpOffset": engine.get("unk88_y", 0),
                  "facing": engine["facing"], "flags": engine["flags"]}
        previous = current["samples"][-1] if current["samples"] else None
        if previous is not None:
            if elapsed != previous["elapsed"] + 1:
                self._fail("elapsed-gap", previous=previous["elapsed"], actual=elapsed)
            dx = current["target"][0] - current["origin"][0]
            dz = current["target"][1] - current["origin"][1]
            # Teleport intentionally alternates its presentation between the
            # origin and target while the logical path advances. Its exact
            # elapsed, commit, and endpoint checks still apply below.
            if (dx or dz) and current["kind"] != "TELEPORT":
                progress = (sample["render"][0] - previous["render"][0]) * dx \
                    + (sample["render"][2] - previous["render"][2]) * dz
                if progress <= 0:
                    self._fail("render-stall" if progress == 0 else "render-reversal",
                               motion=current["kind"], samples=[previous, sample])
        elif elapsed not in (0, 1):
            self._fail("missed-motion-start", elapsed=elapsed)
        current["samples"].append(sample)


def observed_chain_reset(request: bytes, response: bytes, returned: bool):
    """Recognize only public results that actually reset the chain owner.

    WalkPolicy RESET always resets. INPUT's newly raised CLEAR_PRESENTATION
    comes from ResetState, as do failed-skid START_RESULT and non-POST_SKID
    COMMIT clears. A turn/acceleration reset or a lane label alone is not one.
    No private counter or variance generator supplies this observation.
    """
    if not returned or len(request) != 28 or len(response) != 28 \
            or request[:4] != b"\x01\x00\x1c\x00" \
            or response[:4] != request[:4] or response[8:10] != request[8:10]:
        return None
    operation, flags = response[9], response[20]
    if operation == 0:
        return "explicit-policy-reset"
    if request[20] & 0x08 or not flags & 0x08:
        return None
    if operation == 1:
        return "walk-input-reset"
    if operation == 2 and response[15] != 1 and flags & 0x02:
        return "blocked-skid-reset"
    if operation == 3 and not flags & 0x20:
        return "walk-commit-reset"
    return None


def evaluate_chain_intervals(boundaries, motions, *, resets=(), aborts=()):
    """Use sampled chance boundaries, never a private remaining-move counter."""
    errors = []
    intervals = []
    interrupted = []
    previous_eligible = 0
    resets_by_boundary = [[] for _ in range(len(boundaries) + 1)]
    previous_reset_index = 0
    for reset in resets:
        try:
            index = reset["boundaryIndex"]
            reason = observed_chain_reset(bytes.fromhex(reset["requestHex"]),
                                          bytes.fromhex(reset["responseHex"]),
                                          reset["returned"] is True)
            valid = reason is not None and reset["reason"] == reason \
                and type(index) is int and previous_reset_index <= index <= len(boundaries) \
                and type(reset["eligibleMoves"]) is int and reset["eligibleMoves"] >= 0
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            errors.append({"reason": "invalid-chain-reset", "reset": reset})
            continue
        previous_reset_index = index
        resets_by_boundary[index].append(reset)
    for index in range(len(boundaries) + 1):
        boundary = boundaries[index] if index < len(boundaries) else None
        for reset in resets_by_boundary[index]:
            count = reset["eligibleMoves"] - previous_eligible
            lane = reset.get("lane") or (boundary or (boundaries[-1] if boundaries else {})).get("lane")
            transition = reset.get("laneTransition", {})
            # An observed clear is not, by itself, permission to excuse a
            # partial chain. Only a real AI lane handoff (or first-input
            # initialization before any counted move) starts this new window.
            allowed_reason = reset["reason"] in ("explicit-policy-reset", "walk-input-reset")
            initial = allowed_reason and reset["eligibleMoves"] == 0 and index == 0
            lane_change = allowed_reason and transition.get("fromLaneState") in (0, 2, 3) \
                and transition.get("toLaneState") in (0, 2, 3) \
                and transition.get("fromLaneState") != transition.get("toLaneState") \
                and transition.get("eligibleMoves") == reset["eligibleMoves"] \
                and transition.get("boundaryIndex") == index \
                and type(transition.get("beforeFrame")) is int \
                and type(transition.get("frame")) is int \
                and type(reset.get("frame")) is int \
                and transition["beforeFrame"] <= reset["frame"] <= transition["frame"]
            if not (initial or lane_change):
                errors.append({"reason": "unexplained-chain-reset", "reset": reset})
                interrupted.append({"count": count, "startEligibleMoves": previous_eligible,
                                    "acceptedBoundary": False, "reset": reset})
                continue
            if count < 0 or (boundary and reset["eligibleMoves"] > boundary["eligibleMoves"]):
                errors.append({"reason": "invalid-chain-reset-order", "reset": reset})
                continue
            if lane and count > lane["ramAccelerationSteps"] + lane["chainMovementVariance"]:
                errors.append({"reason": "chain-reset-after-range", "count": count, "reset": reset})
            interrupted.append({"count": count, "startEligibleMoves": previous_eligible,
                                "acceptedBoundary": True, "reset": reset})
            previous_eligible = reset["eligibleMoves"]
        if boundary is None:
            break
        lane = boundary["lane"]
        eligible = boundary["eligibleMoves"] - previous_eligible
        previous_eligible = boundary["eligibleMoves"]
        minimum = lane["ramAccelerationSteps"]
        maximum = minimum + lane["chainMovementVariance"]
        if minimum <= 0 or not minimum <= eligible <= maximum:
            errors.append({"reason": "chain-move-count", "actual": eligible,
                           "expectedRange": [minimum, maximum]})
        chance = lane["chainPauseActionChance"] or 100
        selected = boundary["roll"] % 100 < chance if chance < 100 else True
        if boundary["selected"] != selected:
            errors.append({"reason": "chance-selection", "boundary": boundary})
        intervals.append({**boundary, "count": eligible,
                          "expectedRange": [minimum, maximum]})
    actions, aborted_actions = [], []
    selected_boundaries = [item for item in boundaries if item["selected"]]
    for index, boundary in enumerate(selected_boundaries):
        end = selected_boundaries[index + 1]["frame"] \
            if index + 1 < len(selected_boundaries) else 0x7FFFFFFF
        lane = boundary["lane"]
        action = [motion for motion in motions if motion["kind"] == "REPOSITION"
                  and boundary["frame"] <= motion["startFrame"] < end]
        expected_count = lane["chainRepositionJumpCount"]
        # Only the native-observation meter supplies these authenticated
        # aborts. They close an action without pretending its missing legs ran.
        matching_aborts = [item for item in aborts if item["decisionFrame"] == boundary["frame"]]
        abort = matching_aborts[0] if len(matching_aborts) == 1 else None
        if len(matching_aborts) > 1:
            errors.append({"reason": "duplicate-chain-abort", "decisionFrame": boundary["frame"]})
        if abort is not None and (not boundary["frame"] <= abort["frame"] < end
                or len(action) >= expected_count or any(motion["finishFrame"] > abort["frame"] for motion in action)):
            errors.append({"reason": "invalid-chain-abort-window", "decisionFrame": boundary["frame"]})
            abort = None
        resumed = next((motion for motion in motions if motion["kind"] in ("WALK", "HOP", "TELEPORT")
                        and not motion.get("spawn") and not motion.get("skid")
                        and boundary["frame"] <= motion["startFrame"] < end), None)
        if resumed is not None:
            completed_before_resume = sum(motion["finishFrame"] <= resumed["startFrame"] for motion in action)
            if abort is not None and resumed["startFrame"] < abort["frame"]:
                errors.append({"reason": "chain-resumed-before-abort", "decisionFrame": boundary["frame"]})
                abort = None
            if completed_before_resume < expected_count and abort is None:
                errors.append({"reason": "reposition-action-truncated",
                    "decisionFrame": boundary["frame"], "resumeFrame": resumed["startFrame"],
                    "actual": completed_before_resume, "expected": expected_count})
        if len(action) != expected_count and abort is None:
            errors.append({"reason": "reposition-count", "actual": len(action),
                           "expected": expected_count})
        for motion in action:
            elapsed = [sample["elapsed"] for sample in motion["samples"]]
            expected_duration = lane["chainRepositionSpeed"]
            if motion["duration"] != expected_duration or not complete_travel(motion):
                errors.append({"reason": "reposition-time", "duration": motion["duration"],
                               "elapsed": elapsed, "expected": expected_duration})
            dx = abs(motion["target"][0] - motion["origin"][0])
            dz = abs(motion["target"][1] - motion["origin"][1])
            cardinal = (dx == 0) != (dz == 0)
            diagonal = dx > 0 and dx == dz
            if max(dx, dz) != lane["chainRepositionDistance"] or not (
                cardinal and lane["chainRepositionAllowCardinal"]
                or diagonal and lane["chainRepositionAllowDiagonal"]
            ):
                errors.append({"reason": "reposition-distance-direction", "delta": [dx, dz]})
            if len({sample["facing"] for sample in motion["samples"]}) != 1:
                errors.append({"reason": "reposition-facing"})
        if abort is not None:
            aborted_actions.append({**abort, "motions": len(action), "expectedMotions": expected_count,
                "startFrame": action[0]["startFrame"] if action else None,
                "lastMotionFrame": action[-1]["finishFrame"] if action else None,
                "countsAsCompleteAction": False})
        elif action:
            actions.append({"decisionFrame": boundary["frame"],
                            "startFrame": action[0]["startFrame"],
                            "finishFrame": action[-1]["finishFrame"],
                            "motions": len(action), "travelFrames": lane["chainRepositionSpeed"]})
    return {"passed": bool(intervals) and not errors,
            "intervals": intervals, "interruptedIntervals": interrupted,
            "actions": actions, "abortedActions": aborted_actions, "errors": errors}
