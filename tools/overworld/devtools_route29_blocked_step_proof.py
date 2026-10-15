"""Exact retained-stream proof for the saved Route 29 blocked-step freeze."""

from copy import copy


KIND = "route29-blocked-step-live-v1"
REQUIREMENT = "current.route29-blocked-step-live"
CLAIMS = ["live-actor-identity", "natural-input", "frame-pacing"]
NAMES = ("current-mankey-follower", "route29-held-left-to-wall",
         "blocked-step-continuous-progress")
FAULTS = ("wrong-blocked-tile", "missing-completed-frame")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in zip(CLAIMS, NAMES)}


def _windows(rows):
    windows = {"held-left-to-wall": [], "held-left-after-block": []}
    for row in rows:
        if row.get("samples") is None:
            continue
        action = row.get("action")
        if action not in windows or row.get("phase") != "observe" \
                or row.get("command") is not None \
                or row.get("completedGameFrames") != len(row["samples"]) \
                or row.get("requestedGameFrames") != len(row["samples"]):
            raise ValueError("Route 29 retained input window differs from the two LEFT actions")
        windows[action].extend(row["samples"])
    if len(windows["held-left-to-wall"]) != 120 \
            or len(windows["held-left-after-block"]) != 240:
        raise ValueError("Route 29 LEFT actions lack 120 plus 240 completed frames")
    return windows


def measurements(rows, replay):
    windows = _windows(rows)
    samples = windows["held-left-to-wall"] + windows["held-left-after-block"]
    frames = [sample.get("frame") for sample in samples]
    if any(type(frame) is not int for frame in frames) \
            or any(right != left + 1 for left, right in zip(frames, frames[1:])) \
            or replay.get("passed") is not True or replay.get("observedFrames") != 360:
        raise ValueError("Route 29 main loop did not complete 360 continuous frames")
    bound = replay.get("subjects", {}).get("mankey", {})
    if bound.get("species") != 56 or bound.get("role") != "FOLLOWER" \
            or bound.get("identityVerified") is not True:
        raise ValueError("Route 29 saved Mankey follower identity differs")
    handle = bound.get("handle")
    for sample in samples:
        current = [actor for actor in sample.get("actors", [])
                   if actor.get("handle") == handle and actor.get("active") is True]
        if len(current) != 1 or current[0].get("identityVerified") is not True \
                or current[0].get("presentationAttached") is not True \
                or current[0].get("species") != 56 \
                or current[0].get("role") != "FOLLOWER":
            raise ValueError("Route 29 Mankey ceased to be the current visible follower")
    for sample in windows["held-left-after-block"]:
        player = sample.get("player", {})
        if sample.get("context", {}).get("mapId") != 67 \
                or (player.get("x"), player.get("y")) != (538, 392):
            raise ValueError("Route 29 player left the blocked tile during the held LEFT window")
    return {"observedFrames": 360, "observedFrameUnit": "completed-main-loop-frames",
            "measurements": [{"claim": claim, "name": name, "value": 1,
                              "operator": "eq", "expected": 1}
                             for claim, name in zip(CLAIMS, NAMES)]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Route 29 copied-data control")
    changed = list(rows)
    for index, row in enumerate(changed):
        if row.get("action") != "held-left-after-block" or not row.get("samples"):
            continue
        row = copy(row)
        row["samples"] = list(row["samples"])
        sample = copy(row["samples"][0])
        if fault == "wrong-blocked-tile":
            sample["player"] = {**sample["player"], "x": 537}
        else:
            sample["frame"] += 1
        row["samples"][0] = sample
        changed[index] = row
        return changed
    raise ValueError("Route 29 blocked-step control has no completed frame")
