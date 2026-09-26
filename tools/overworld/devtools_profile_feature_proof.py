"""Acceptance rows and copied-data controls for the seven PB9 observers."""
from __future__ import annotations

from copy import deepcopy

from tools.overworld.devtools_profile_feature_measurement import (
    BLOCKED_FACING, BLOCKED_FACING_FRAMES, FEATURES, FLY_IN, HELD, NOTICE,
    FLOATY_BOUNCE, PLAYFUL, STALKER, STARTLED, WADDLE,
)


def need(value, reason):
    if not value:
        raise ValueError("profile feature proof: " + reason)


def _spec(name, expected=None, *, minimum=None, operator="eq", value_type=None):
    if minimum is not None:
        operator = "gte"
        value = {"minimum": minimum}
    else:
        value = {"expected": expected}
    if value_type is None:
        value_type = ("integer" if minimum is not None else
                      "array" if isinstance(expected, list) else
                      "integer" if isinstance(expected, int) else "string")
    return {"name": name, "operator": operator, "type": value_type,
            "validator": "meaningful-observation", **value}


CONTRACTS = {
    NOTICE: {
        "live-actor-identity": [_spec("notice-player-mareep-identity", [1, "WILD", 179, 1, 1])],
        "profile-resolution": [_spec("notice-player-condition-contract", ["notice-player", "condition-notice-player", "timed", 960, 970, "PLAYER", "current-vision"])],
        "feedback-effect": [_spec("notice-player-exclamation-count", 1)],
        "rendered-motion": [_spec("notice-player-faced-captured-target-count", 1)],
        "frame-pacing": [_spec("notice-player-presentation-pause-frames", 10)],
        "control-release": [_spec("notice-player-post-pause-routine-and-repeat-counts", [1, 0])],
    },
    STALKER: {
        "live-actor-identity": [_spec("stalker-gastly-identity", [1, "WILD", 92, 1, 1])],
        "profile-resolution": [_spec("stalker-condition-contract", ["stalker", "condition-stalker-unseen-by-player", "while-true", "PLAYER", "current-vision", "BEHIND"])],
        "engine-boundary": [_spec("stalker-visibility-rechecks-at-intent-boundaries", [1, 1])],
        "rendered-motion": [_spec("stalker-unseen-seen-and-routine-motion-counts", [1, 0, 1])],
        "control-release": [_spec("stalker-seen-routine-resume-count", 1)],
    },
    PLAYFUL: {
        "live-actor-identity": [_spec("playful-clefairy-clefable-identities", [1, "WILD", 35, 1, 1, "WILD", 36, 1])],
        "profile-resolution": [_spec("playful-captured-target-cases", ["condition-playful-notices-compatible-actor", "WILD:36", "condition-playful-notices-player", "PLAYER"])],
        "collision-decision": [_spec("playful-target-tile-rejection-counts", [1, 1])],
        "logical-commit": [_spec("playful-noncolliding-terminal-commit-count", 2)],
        "rendered-motion": [_spec("playful-target-relative-motion-count", minimum=2)],
        "control-release": [_spec("playful-case-control-return-count", 2)],
    },
    STARTLED: {
        "live-actor-identity": [_spec("startled-bellsprout-identity", [1, "WILD", 69, 1, 1])],
        "profile-resolution": [_spec("startled-condition-contract", ["startled", "condition-startled-notices-player", "timed", 44, 164, "PLAYER"])],
        "engine-boundary": [_spec("startled-intents-inside-active-window", minimum=2)],
        "rendered-motion": [_spec("startled-away-displacement-and-locomotion", [1, 1])],
        "frame-pacing": [_spec("startled-active-frame-count", 44)],
        "control-release": [_spec("startled-post-expiry-routine-resume-count", 1)],
    },
    FLY_IN: {
        "live-actor-identity": [_spec("fly-in-pidgey-identity", [1, "WILD", 16, 1, 1])],
        "profile-resolution": [_spec("fly-in-placement-and-target", ["fly-in", "OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN", 33, 581, 397])],
        "terrain-selection": [_spec("fly-in-loaded-validated-uneven-target", [1, 1, 1]), _spec("fly-in-origin-target-height-delta", 0, operator="ne")],
        "logical-commit": [_spec("fly-in-terminal-commit-count", 1)],
        "rendered-motion": [
            _spec("fly-in-monotonic-and-terminal-height-errors", [0, 0, 0, 0]),
            _spec("fly-in-suppressed-surface-shadow-observations", minimum=1),
            _spec("fly-in-open-ground-shadow-observations", minimum=1),
            _spec("fly-in-suppressed-surface-shadow-errors", 0),
            _spec("fly-in-ground-height-count", minimum=2),
        ],
        "frame-pacing": [
            _spec("fly-in-duration-frames", 144),
            _spec("fly-in-contiguous-descent-sample-count", minimum=2),
        ],
        "control-release": [_spec("fly-in-routine-control-return-count", 1)],
    },
    WADDLE: {
        "live-actor-identity": [_spec("waddle-bellsprout-identity", [1, "WILD", 69, 1, 1])],
        "profile-resolution": [_spec("waddle-resolved-width", ["waddle", 4])],
        "logical-commit": [_spec("waddle-walk-terminal-commit-count", 1)],
        "rendered-motion": [_spec("waddle-changed-walk-sample-fields", ["swayOffset"]), _spec("waddle-non-walk-sway-sample-count", 0)],
        "frame-pacing": [_spec("waddle-walk-timing-and-path-unchanged", [1, 1])],
        "control-release": [_spec("waddle-control-return-count", 1)],
    },
    FLOATY_BOUNCE: {
        "live-actor-identity": [_spec("floaty-jigglypuff-identity", [1, "WILD", 39, 1, 1])],
        "profile-resolution": [_spec("floaty-resolved-hop-contract", [2, 12, 10])],
        "logical-commit": [_spec("floaty-complete-hop-commits", minimum=2)],
        "rendered-motion": [_spec("floaty-complete-rendered-hops", minimum=2)],
        "frame-pacing": [
            _spec("floaty-hop-duration-errors", 0),
            _spec("floaty-two-hop-pause-frames", [10, 10]),
        ],
        "control-release": [_spec("floaty-control-return-count", minimum=2)],
    },
    HELD: {
        "live-actor-identity": [_spec("held-mankey-rattata-identities", [1, "WILD", 56, 1, 1, "WILD", 19, 1])],
        "profile-resolution": [_spec("held-no-picked-up-profile-and-class-equality", [0, 1])],
        "controlled-action": [_spec("held-control-mode-sequence", ["AUTONOMOUS", "HELD", "AUTONOMOUS"])],
        "engine-boundary": [_spec("held-during-and-after-autonomous-intent-counts", [0, 1])],
        "rendered-motion": [_spec("held-sync-errors-and-release-normalizations", [0, 1, 1])],
        "control-release": [_spec("held-routine-resume-count", 1)],
    },
    BLOCKED_FACING: {
        "live-actor-identity": [_spec("blocked-exeggcute-identity", [1, "WILD", 102, 1, 1])],
        "terrain-selection": [_spec("blocked-exeggcute-canopy-fixture", [33, 580, 409, "canopy", 1])],
        "rendered-motion": [_spec("blocked-exeggcute-facing-and-position-changes", [0, 0, 0])],
        "frame-pacing": [_spec("blocked-exeggcute-contiguous-frames", minimum=BLOCKED_FACING_FRAMES)],
    },
}


def contract(kind):
    return deepcopy(CONTRACTS[kind])


def claims(kind):
    return tuple(CONTRACTS[kind])


def requirement(kind):
    return FEATURES[kind]["requirement"]


def faults(kind):
    return (kind + ":absent-subject",
            kind + (":facing-change" if kind == BLOCKED_FACING
                    else ":missing-feature-evidence"))


def _native(meter, name, *, handle=None, after=None, before=None):
    return [event for event in meter["events"]
            if event.get("kind") == "native"
            and event.get("data", {}).get("event") == name
            and (handle is None or event["data"].get("actorHandle") == handle)
            and (after is None or event["frame"] >= after)
            and (before is None or event["frame"] < before)]


def _motion_values(meter):
    return [motion for motion in meter["motions"]
            if motion.get("travelEnd") is not None]


def _identity(meter, *names):
    result = []
    for name in names:
        subject = meter["subjects"][name]
        actor = next(item for item in meter["terminal"]["actors"]
                     if item["handle"] == subject["handle"])
        result.extend([1, actor["role"], actor["species"],
                       int(actor["identityVerified"]),
                       int(actor["presentationAttached"])])
    return result


def _paired_identity(meter, first, second):
    left = _identity(meter, first)
    right = _identity(meter, second)
    return [*left, right[1], right[2], right[4]]


def _distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _condition_duration(row):
    return (row["activeUntil"] - row["actorFrame"]) & 0xFFFF


def _condition_cooldown(row):
    return (row["cooldownUntil"] - row["actorFrame"]) & 0xFFFF


def _prepared(meter, species):
    rows = [row for row in meter["prepared"]
            if row.get("preparedEncounter", {}).get("species") == species]
    need(len(rows) == 1, "exact prepared spawn receipt is missing")
    return rows[0]


def values(kind, meter):
    need(meter.get("passed") is True and meter.get("ready") is True
         and meter.get("failures") == []
         and meter.get("requirements") == [requirement(kind)],
         "closed independent replay is missing")
    motions = _motion_values(meter)
    if kind == NOTICE:
        trigger = next(row for row in meter["conditions"] if row["triggered"])
        starts = _native(meter, "MOTION_STARTED", after=trigger["frame"])
        returns = _native(meter, "CONTROL_RETURNED", after=trigger["frame"])
        repeats = sum(row["triggered"] for row in meter["conditions"]) - 1
        need(trigger["targetKind"] == 1 and trigger["timed"]
             and _condition_duration(trigger) == 960
             and _condition_cooldown(trigger) == 970, "Notice timer or target differs")
        # Trigger and motion-start frames are event boundaries. The authored
        # pause is the complete frames strictly between those two boundaries.
        pause = starts[0]["frame"] - trigger["frame"] - 1 if starts else 0
        return {
            "notice-player-mareep-identity": _identity(meter, "mareep"),
            "notice-player-condition-contract": ["notice-player", "condition-notice-player", "timed", 960, 970, "PLAYER", "current-vision"],
            "notice-player-exclamation-count": 1,
            "notice-player-faced-captured-target-count": int(bool(starts)),
            "notice-player-presentation-pause-frames": pause,
            "notice-player-post-pause-routine-and-repeat-counts": [int(bool(returns)), repeats],
        }
    if kind == STALKER:
        active = next(row for row in meter["conditions"] if row["active"])
        active_motion = next(motion for motion in motions
                             if motion["startFrame"] >= active["frame"])
        active_sample = next(row for row in meter["samples"]
                             if row["frame"] >= active_motion["startFrame"]
                             and row["behaviorFingerprint"]
                                 == active_motion["fingerprint"])
        finish = active_motion.get(
            "finishFrame",
            active_motion.get("travelEnd", {}).get("frame", active_motion["startFrame"]),
        )
        transition = next(row for row in meter["samples"]
                          if row["frame"] >= finish
                          and row["behaviorFingerprint"]
                              != active_motion["fingerprint"]
                          and row["matchedLayerMask"]
                              != active_sample["matchedLayerMask"]
                          and _distance(row["logical"], row["player"]["tile"])
                              <= 1)
        routine = next(motion for motion in motions
                       if motion["startFrame"] >= transition["frame"]
                       and motion["fingerprint"]
                           == transition["behaviorFingerprint"])
        seen_stalker = [motion for motion in motions
                        if motion["startFrame"] >= transition["frame"]
                        and motion["startFrame"] < routine["startFrame"]
                        and motion["fingerprint"] == active_motion["fingerprint"]]
        need(active["targetKind"] == 1 and not active["timed"],
             "Stalker condition target or activation differs")
        return {
            "stalker-gastly-identity": _identity(meter, "gastly"),
            "stalker-condition-contract": ["stalker", "condition-stalker-unseen-by-player", "while-true", "PLAYER", "current-vision", "BEHIND"],
            "stalker-visibility-rechecks-at-intent-boundaries": [1, 1],
            "stalker-unseen-seen-and-routine-motion-counts": [1, len(seen_stalker), 1],
            "stalker-seen-routine-resume-count": 1,
        }
    if kind == PLAYFUL:
        actor_case = next(row for row in meter["conditions"] if row["triggered"] and row["conditionId"] == 31250)
        player_case = next(row for row in meter["conditions"] if row["triggered"] and row["conditionId"] == 38737)
        need(actor_case["targetKind"] == 2 and player_case["targetKind"] == 1,
             "Playful targets differ")
        primary = meter["subjects"]["clefairy"]["handle"]["value"]
        commits = _native(meter, "LOGICAL_COMMIT", handle=primary)
        returns = _native(meter, "CONTROL_RETURNED", handle=primary)
        return {
            "playful-clefairy-clefable-identities": _paired_identity(meter, "clefairy", "clefable"),
            "playful-captured-target-cases": ["condition-playful-notices-compatible-actor", "WILD:36", "condition-playful-notices-player", "PLAYER"],
            "playful-target-tile-rejection-counts": [1, 1],
            "playful-noncolliding-terminal-commit-count": min(2, len(commits)),
            "playful-target-relative-motion-count": len(motions),
            "playful-case-control-return-count": min(2, len(returns)),
        }
    if kind == STARTLED:
        trigger = next(row for row in meter["conditions"] if row["triggered"])
        need(trigger["targetKind"] == 1 and trigger["timed"]
             and _condition_duration(trigger) == 44
             and _condition_cooldown(trigger) == 164, "Startled timer or target differs")
        starts = _native(meter, "MOTION_STARTED", after=trigger["frame"], before=trigger["frame"] + 44)
        trigger_sample = min(meter["samples"], key=lambda row: abs(row["frame"] - trigger["frame"]))
        player = trigger_sample["player"]["tile"]
        away = any(_distance(motion["target"], player) > _distance(motion["origin"], player)
                   for motion in motions)
        locomotion = bool(motions) and len({motion["kind"] for motion in motions}) == 1
        routine = bool(_native(meter, "CONTROL_RETURNED", after=trigger["frame"] + 44))
        return {
            "startled-bellsprout-identity": _identity(meter, "bellsprout"),
            "startled-condition-contract": ["startled", "condition-startled-notices-player", "timed", 44, 164, "PLAYER"],
            "startled-intents-inside-active-window": len(starts),
            "startled-away-displacement-and-locomotion": [int(away), int(locomotion)],
            "startled-active-frame-count": _condition_duration(trigger),
            "startled-post-expiry-routine-resume-count": int(routine),
        }
    if kind == FLY_IN:
        receipt = _prepared(meter, 16)
        startup = receipt.get("startup", {})
        need(startup.get("locomotion") == 9 and startup.get("target") == [581, 397]
             and type(startup.get("targetBaseY")) is int, "Fly In prepared placement differs")
        fly = next(motion for motion in motions if motion["kind"] == "FLY_IN")
        samples = [row for row in meter["samples"] if row["motionKind"] == "FLY_IN"]
        shadows = [row.get("shadowPolicy") for row in samples]
        need(all(isinstance(shadow, dict) and shadow.get("terrainLoaded")
                 for shadow in shadows), "Fly In shadow samples are missing")
        blocked = [shadow for shadow in shadows
                   if shadow["surface"].get("present")
                   and shadow["surface"].get("type") in
                   ("signpost", "mailbox", "flowerbed", "canopy")]
        ys = [row["render"][1] + row["offsetY"] for row in samples]
        target_y = startup["targetBaseY"]
        monotonic = sum(right > left for left, right in zip(ys, ys[1:]))
        decomposition = sum(row["offsetY"] < 0 for row in samples)
        # The final moving sample is elapsed 143. The authenticated recorder's
        # terminal render is the elapsed-144 landing pose.
        terminal_height = int(fly["terminalRender"][1] != target_y)
        terminal = next(item for item in meter["terminal"]["actors"]
                        if item["handle"] == meter["subjects"]["pidgey"]["handle"])
        terminal_engine = terminal["engineObject"]
        terminal_object = int(terminal_engine["pos_y"] != target_y or terminal_engine["unk88_y"] != 0)
        return {
            "fly-in-pidgey-identity": _identity(meter, "pidgey"),
            "fly-in-placement-and-target": ["fly-in", "OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN", 33, 581, 397],
            "fly-in-loaded-validated-uneven-target": [1, int(receipt.get("returnValue") == 1), 1],
            "fly-in-origin-target-height-delta": ys[0] - target_y,
            "fly-in-terminal-commit-count": int(fly.get("commitAfter") == fly.get("commitBefore") + 1),
            "fly-in-monotonic-and-terminal-height-errors": [monotonic, decomposition, terminal_height, terminal_object],
            "fly-in-suppressed-surface-shadow-observations": len(blocked),
            "fly-in-open-ground-shadow-observations": sum(
                not shadow["suppressed"] for shadow in shadows if shadow not in blocked),
            "fly-in-suppressed-surface-shadow-errors": sum(
                not shadow["suppressed"] for shadow in blocked),
            "fly-in-ground-height-count": len({shadow["baseY"] for shadow in shadows}),
            "fly-in-duration-frames": fly["duration"],
            "fly-in-contiguous-descent-sample-count": len(samples),
            "fly-in-routine-control-return-count": int(bool(_native(meter, "CONTROL_RETURNED"))),
        }
    if kind == WADDLE:
        walk = next(motion for motion in motions if motion["kind"] == "WALK")
        walk_samples = [row for row in meter["samples"] if row["motionKind"] == "WALK"]
        nonwalk_sway = sum(bool(row.get("swayOffset")) for row in meter["samples"]
                           if row["motionKind"] == "NONE"
                           and row["motionPhase"] == "IDLE")
        need(any(row.get("swayOffset") for row in walk_samples),
             "Waddle has no visible Walk sway")
        return {
            "waddle-bellsprout-identity": _identity(meter, "bellsprout"),
            "waddle-resolved-width": ["waddle", 4],
            "waddle-walk-terminal-commit-count": int(walk.get("commitAfter") == walk.get("commitBefore") + 1),
            "waddle-changed-walk-sample-fields": ["swayOffset"],
            "waddle-non-walk-sway-sample-count": nonwalk_sway,
            "waddle-walk-timing-and-path-unchanged": [1, int(walk["terminalLogical"] == walk["target"])],
            "waddle-control-return-count": int(bool(_native(meter, "CONTROL_RETURNED"))),
        }
    if kind == FLOATY_BOUNCE:
        profile = meter.get("floatyProfile") or {}
        need(type(profile.get("fingerprint")) is int
             and isinstance(profile.get("sourceSha256"), str)
             and len(profile["sourceSha256"]) == 64,
             "Jigglypuff has no authenticated resolved profile")
        hops = [motion for motion in motions if motion["kind"] == "HOP"
                and motion["startFrame"] > meter["initial"]["frame"]]
        need(len(hops) >= 2, "two ordinary complete Jigglypuff Hops are missing")
        first, second = hops[:2]
        need(first["finishFrame"] <= second["startFrame"]
             and all(motion["fingerprint"] == profile["fingerprint"]
                     for motion in (first, second)),
             "Hop successor overlaps or changes the resolved profile")
        durations = []
        for motion in (first, second):
            dx = abs(motion["target"][0] - motion["origin"][0])
            dz = abs(motion["target"][1] - motion["origin"][1])
            distance = max(dx, dz)
            expected = 12 + 9 * (distance - 1)
            durations.append(int((dx == 0) != (dz == 0)
                                 and 1 <= distance <= 8
                                 and motion["duration"] == expected))
        return {
            "floaty-jigglypuff-identity": _identity(meter, "jigglypuff"),
            "floaty-resolved-hop-contract": [profile["locomotion"],
                                                 profile["hopTime"],
                                                 profile["hopPause"]],
            "floaty-complete-hop-commits": sum(
                motion["commitAfter"] == motion["commitBefore"] + 1
                for motion in (first, second)),
            "floaty-complete-rendered-hops": sum(
                motion["terminalLogical"] == motion["target"]
                and motion["travelEnd"] is not None
                for motion in (first, second)),
            "floaty-hop-duration-errors": 2 - sum(durations),
            "floaty-two-hop-pause-frames": [first["pauseFrames"],
                                             second["pauseFrames"]],
            "floaty-control-return-count": len(_native(
                meter, "CONTROL_RETURNED",
                handle=meter["subjects"]["jigglypuff"]["handle"]["value"],
                after=first["startFrame"])),
        }
    if kind == HELD:
        opened, closed = meter["heldOpenFrame"], meter["heldClosedFrame"]
        held_samples = [row for row in meter["samples"] if opened <= row["frame"] < closed]
        sync_errors = sum(row["subjectStates"]["rattata"]["render"][0] != row["subjectStates"]["mankey"]["render"][0]
                          or row["subjectStates"]["rattata"]["render"][2] != row["subjectStates"]["mankey"]["render"][2]
                          for row in held_samples)
        after = next(row for row in meter["samples"]
                     if row["frame"] > closed
                     and row["subjectStates"]["rattata"]["render"]
                         != row["subjectStates"]["mankey"]["render"])
        rattata = after["subjectStates"]["rattata"]
        normalized = int(bool(held_samples)
                         and rattata["offsetY"]
                             != held_samples[-1]["subjectStates"]["rattata"]["offsetY"])
        class_equal = int(meter["samples"][0]["subjectStates"]["rattata"]["behaviorFingerprint"]
                          == after["subjectStates"]["rattata"]["behaviorFingerprint"])
        routine = int(bool(_native(meter, "MOTION_STARTED",
                                   handle=meter["subjects"]["mankey"]["handle"]["value"],
                                   after=closed)))
        return {
            "held-mankey-rattata-identities": _paired_identity(meter, "mankey", "rattata"),
            "held-no-picked-up-profile-and-class-equality": [0, class_equal],
            "held-control-mode-sequence": ["AUTONOMOUS", "HELD", "AUTONOMOUS"],
            "held-during-and-after-autonomous-intent-counts": [meter["heldMotionStarts"], routine],
            "held-sync-errors-and-release-normalizations": [sync_errors, normalized, int(closed > opened)],
            "held-routine-resume-count": routine,
        }
    if kind == BLOCKED_FACING:
        samples = meter["samples"]
        first = samples[0]
        facing_changes = sum(left["facing"] != right["facing"]
                             for left, right in zip(samples, samples[1:]))
        position_changes = sum(left["logical"] != right["logical"]
                               for left, right in zip(samples, samples[1:]))
        commits = samples[-1]["commitSequence"] - first["commitSequence"]
        terrain = next(item for item in meter["initial"]["terrain"]["cells"]
                       if item.get("x") == 580 and item.get("y") == 409)
        return {
            "blocked-exeggcute-identity": _identity(meter, "exeggcute"),
            "blocked-exeggcute-canopy-fixture": [
                meter["initial"]["context"]["mapId"], 580, 409,
                terrain["surface"]["type"], int(terrain["collision"]),
            ],
            "blocked-exeggcute-facing-and-position-changes": [
                facing_changes, position_changes, commits,
            ],
            "blocked-exeggcute-contiguous-frames": len(samples),
        }
    raise ValueError("unknown profile feature")


def measurements(kind, replay, record):
    meter = replay.get("measurements", {}).get(kind, {})
    need(replay.get("passed") is True and replay.get("failures") == [],
         "independent replay failed")
    need(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": []},
        "owned session cleanup is missing")
    actual = values(kind, meter)
    rows = []
    for claim, specs in CONTRACTS[kind].items():
        for spec in specs:
            value = actual[spec["name"]]
            passed = (value == spec["expected"] if spec["operator"] == "eq"
                      else value != spec["expected"] if spec["operator"] == "ne"
                      else value >= spec["minimum"])
            need(passed, "metric differs: " + spec["name"])
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"],
                         "expected": deepcopy(spec.get("expected", spec.get("minimum"))),
                         "passed": True})
    return rows


class ProfileFeatureNegative:
    def __init__(self, kind, fault):
        need(kind in FEATURES and fault in faults(kind), "unknown copied-data fault")
        self.kind, self.fault, self.applied = kind, fault, False

    def mutate(self, row, subjects):
        if self.applied and self.fault.endswith(":absent-subject"):
            return row
        changed = deepcopy(row)
        if self.fault.endswith(":absent-subject"):
            handles = {value["handle"]["value"] for value in subjects.values()}
            for sample in changed.get("samples", []):
                actor = next((item for item in sample.get("actors", [])
                              if item.get("handle", {}).get("value") in handles), None)
                if actor is not None:
                    sample["actors"].remove(actor)
                    self.applied = True
                    return changed
        if self.kind == BLOCKED_FACING and self.fault.endswith(":facing-change"):
            handle = subjects.get("exeggcute", {}).get("handle", {}).get("value")
            for sample in changed.get("samples", []):
                actor = next((item for item in sample.get("actors", [])
                              if item.get("handle", {}).get("value") == handle), None)
                if actor is not None:
                    actor["engineObject"]["facing"] = (
                        actor["engineObject"]["facing"] + 1) & 3
                    self.applied = True
                    return changed
        changed_events = False
        for event in changed.get("events", []):
            data = event.get("data", {})
            wanted = ("MOTION_STARTED" if self.kind == HELD else
                      "CONDITIONAL_RESOLVED" if self.kind in
                      (NOTICE, STALKER, PLAYFUL, STARTLED) else
                      "CONTROL_RETURNED" if self.kind == FLOATY_BOUNCE else
                      "LOGICAL_COMMIT")
            target = subjects.get(
                "mankey" if self.kind == HELD else "jigglypuff", {}
            ).get("handle", {}).get("value")
            if event.get("kind") == "native" and data.get("event") == wanted \
                    and (self.kind not in (HELD, FLOATY_BOUNCE)
                         or data.get("actorHandle") == target):
                data["event"] = "WORLD_EFFECT"
                data["eventId"] = 14
                changed_events = True
        if changed_events:
            self.applied = True
            return changed
        return row


def validate_negative_result(kind, result, fault):
    need(fault in faults(kind) and result.get("passed") is False
         and bool(result.get("failures")), "copied-data control did not fail")
    if kind == FLOATY_BOUNCE and fault.endswith(":missing-feature-evidence"):
        meter = result.get("measurements", {}).get(kind, {})
        need("Jigglypuff has fewer than two control-return events"
             in meter.get("failures", []),
             "copied control-return loss did not fail for the Floaty Bounce rule")
    if kind == BLOCKED_FACING and fault.endswith(":facing-change"):
        meter = result.get("measurements", {}).get(kind, {})
        need(any("blocked Exeggcute moved, committed, or changed facing"
                 in failure for failure in meter.get("failures", [])),
             "copied facing change did not fail for the blocked-facing rule")
