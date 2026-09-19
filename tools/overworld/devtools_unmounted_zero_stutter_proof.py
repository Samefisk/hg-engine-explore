"""Acceptance rows and copied-data controls for unmounted zero stutter."""
from copy import deepcopy

from tools.overworld.devtools_main_loop_probe import (
    MAX_ZERO_STUTTER_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
)
from tools.overworld.devtools_unmounted_zero_stutter_measurement import (
    KIND,
    MAX_DESTINATION_SCAN_FRAME_SPAN,
    MINIMUM_FRAMES,
    MINIMUM_MOVING_FRAMES,
    REQUIREMENT,
    START,
    require,
)


CLAIMS = (
    "live-actor-identity",
    "natural-input",
    "population-bounds",
    "frame-pacing",
)
FAULTS = (
    "zero-stutter-extra-game-frame",
    "zero-stutter-missing-pacing-sample",
    "zero-stutter-player-render-stall",
    "zero-stutter-missing-spawn-work",
    "zero-stutter-slow-spawn-scan",
)


def contract():
    return {
        "live-actor-identity": [{
            "name": "zero-stutter-follower-identity", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [56, "FOLLOWER", 1],
        }],
        "natural-input": [{
            "name": "zero-stutter-moving-frame-count", "operator": "gte",
            "type": "integer", "validator": "meaningful-observation",
            "minimum": MINIMUM_MOVING_FRAMES,
        }, {
            "name": "zero-stutter-source-profile-binding", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [5, 6, 1],
        }],
        "population-bounds": [
            {
                "name": "zero-stutter-spawn-work-witness-count", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": 1,
            },
            {
                "name": "zero-stutter-spawn-attempt-frame-span", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": MAX_DESTINATION_SCAN_FRAME_SPAN,
            },
        ],
        "frame-pacing": [
            {
                "name": "zero-stutter-observed-frame-count", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": MINIMUM_FRAMES,
            },
            {
                "name": "zero-stutter-late-main-loop-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 0,
            },
            {
                "name": "zero-stutter-maximum-native-cycles", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            },
            {
                "name": "zero-stutter-maximum-frame-sequence", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            },
            {
                "name": "zero-stutter-maximum-arm9-ticks", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": MAX_ZERO_STUTTER_ARM9_TICKS,
            },
            {
                "name": "zero-stutter-player-render-stall-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 0,
            },
        ],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    pacing = meter.get("pacing") or {}
    spawn = meter.get("spawnWork") or {}
    hop = meter.get("hopRhythm") or {}
    subject = meter.get("subject") or {}
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT]
            and meter.get("started", {}).get("mapId") == START["mapId"]
            and meter.get("frames", 0) >= MINIMUM_FRAMES
            and subject.get("species") == 56
            and subject.get("role") == "FOLLOWER"
            and subject.get("identityVerified") is True
            and spawn.get("destinationSearchCount", 0) >= 1
            and spawn.get("finalizerCount", 0) >= 1
            and spawn.get("joinedWitnessCount", 0) >= 1
            and spawn.get("maximumAttemptFrameSpan", 0)
                <= MAX_DESTINATION_SCAN_FRAME_SPAN
            and hop.get("profilePauseFrames") == 5
            and hop.get("profileMaxDistance") == 6
            and hop.get("profileFingerprint") == subject.get("behaviorFingerprint")
            and hop.get("profileMask") == subject.get("matchedLayerMask")
            and pacing.get("sampleCount") == pacing.get("intervalCount") == meter.get("frames")
            and pacing.get("movingFrameCount", 0) >= MINIMUM_MOVING_FRAMES
            and pacing.get("lateMainLoopCount") == 0
            and pacing.get("maximumNativeCycles") <= NORMAL_MAIN_LOOP_NATIVE_CYCLES
            and pacing.get("maximumFrameSequence") <= NORMAL_MAIN_LOOP_NATIVE_CYCLES
            and pacing.get("maximumArm9Ticks") <= MAX_ZERO_STUTTER_ARM9_TICKS
            and pacing.get("renderStallCount") == 0,
            "zero-stutter proof is not one complete hitch-free spawn-work route")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "zero-stutter private session did not close cleanly")
    rows = [
        ("live-actor-identity", "zero-stutter-follower-identity",
         [subject["species"], subject["role"], int(subject["identityVerified"])],
         "eq", [56, "FOLLOWER", 1]),
        ("natural-input", "zero-stutter-moving-frame-count",
         pacing["movingFrameCount"], "gte", MINIMUM_MOVING_FRAMES),
        ("natural-input", "zero-stutter-source-profile-binding",
         [hop["profilePauseFrames"], hop["profileMaxDistance"],
          int(hop["profileFingerprint"] == subject["behaviorFingerprint"]
              and hop["profileMask"] == subject["matchedLayerMask"])],
         "eq", [5, 6, 1]),
        ("population-bounds", "zero-stutter-spawn-work-witness-count",
         spawn["joinedWitnessCount"], "gte", 1),
        ("population-bounds", "zero-stutter-spawn-attempt-frame-span",
         spawn["maximumAttemptFrameSpan"], "lte", MAX_DESTINATION_SCAN_FRAME_SPAN),
        ("frame-pacing", "zero-stutter-observed-frame-count",
         meter["frames"], "gte", MINIMUM_FRAMES),
        ("frame-pacing", "zero-stutter-late-main-loop-count",
         pacing["lateMainLoopCount"], "eq", 0),
        ("frame-pacing", "zero-stutter-maximum-native-cycles",
         pacing["maximumNativeCycles"], "lte", NORMAL_MAIN_LOOP_NATIVE_CYCLES),
        ("frame-pacing", "zero-stutter-maximum-frame-sequence",
         pacing["maximumFrameSequence"], "lte", NORMAL_MAIN_LOOP_NATIVE_CYCLES),
        ("frame-pacing", "zero-stutter-maximum-arm9-ticks",
         pacing["maximumArm9Ticks"], "lte", MAX_ZERO_STUTTER_ARM9_TICKS),
        ("frame-pacing", "zero-stutter-player-render-stall-count",
         pacing["renderStallCount"], "eq", 0),
    ]
    output = []
    for claim, name, value, operator, expected in rows:
        key = "expected" if operator == "eq" else ("minimum" if operator == "gte" else "maximum")
        passed = value == expected if operator == "eq" else (
            value >= expected if operator == "gte" else value <= expected)
        output.append({"claim": claim, "name": name, "value": value,
                       "operator": operator, key: expected, "passed": passed})
    return output


class UnmountedZeroStutterNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown zero-stutter copied fault")
        self.fault = fault
        self.applied = False
        self.active = False
        self.previous_pose = None
        self.spawn_attempt_id = None
        self.spawn_attempt_frame = None

    @staticmethod
    def _anchor(sample):
        player = sample.get("player", {})
        return (sample.get("fieldAvailable") is True
                and sample.get("context", {}).get("mapId") == START["mapId"]
                and player.get("x") == player.get("x_prev") == START["x"]
                and player.get("y") == player.get("y_prev") == START["y"])

    def mutate(self, row, subjects):
        if row.get("phase") != "observe":
            return row
        changed = deepcopy(row)
        samples = changed.get("samples", [])
        events = changed.get("events", [])
        activated_now = False
        if not self.active and any(self._anchor(sample) for sample in samples):
            self.active = True
            activated_now = True
        if not self.active:
            return row
        if self.fault == "zero-stutter-missing-spawn-work":
            kept = [event for event in events
                    if event.get("data", {}).get("observation") not in
                    ("spawn-finalized", "spawn-destination-search")]
            if len(kept) != len(events):
                changed["events"] = kept
                self.applied = True
            return changed
        if activated_now:
            return row
        if self.applied:
            return row
        if self.fault == "zero-stutter-slow-spawn-scan":
            for event in events:
                if event.get("data", {}).get("observation") \
                        == "spawn-destination-search":
                    if self.spawn_attempt_id is None:
                        self.spawn_attempt_id = event["data"].get("spawnAttemptId")
                        self.spawn_attempt_frame = event.get("frame")
                    elif event.get("frame", 0) - self.spawn_attempt_frame \
                            >= MAX_DESTINATION_SCAN_FRAME_SPAN:
                        event["data"]["spawnAttemptId"] = self.spawn_attempt_id
                        self.applied = True
                        return changed
        if self.fault in ("zero-stutter-extra-game-frame",
                          "zero-stutter-missing-pacing-sample"):
            for event in events:
                data = event.get("data", {})
                if data.get("observation") != "stock-main-loop-pacing" \
                        or not isinstance(data.get("intervalFromPrevious"), dict):
                    continue
                if self.fault == "zero-stutter-missing-pacing-sample":
                    changed["events"] = [item for item in events if item is not event]
                else:
                    data["frameCounter"] = NORMAL_MAIN_LOOP_NATIVE_CYCLES + 3
                    data["intervalFromPrevious"].update(
                        arm9Ticks=5601900,
                        nativeCycles=NORMAL_MAIN_LOOP_NATIVE_CYCLES + 3,
                        frameSequence=NORMAL_MAIN_LOOP_NATIVE_CYCLES + 3)
                self.applied = True
                return changed
        if self.fault == "zero-stutter-player-render-stall":
            for sample in samples:
                player = sample.get("player", {})
                pose = [player.get("pos_x"), player.get("pos_z")]
                moving = player.get("x") != player.get("x_prev") or player.get("y") != player.get("y_prev")
                if self.previous_pose is not None and moving:
                    player["pos_x"], player["pos_z"] = self.previous_pose
                    self.applied = True
                    return changed
                if all(type(value) is int for value in pose):
                    self.previous_pose = pose
        return changed


Negative = UnmountedZeroStutterNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "zero-stutter copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "zero-stutter-extra-game-frame": "observed an extra game frame",
        "zero-stutter-missing-pacing-sample": "lacks one main-loop pacing sample",
        "zero-stutter-player-render-stall": "player render froze during movement",
        "zero-stutter-missing-spawn-work": "ended before its full spawn-work witness",
        "zero-stutter-slow-spawn-scan": "spawn destination scan exceeded its frame budget",
    }[fault]
    require(expected in text,
            "zero-stutter copied control failed for an unrelated reason: " + fault)
