"""Exact retained-stream proof for the Route 29 Weepinbell blocked-step freeze."""

from copy import copy


KIND = "weepinbell-blocked-step-live-v1"
REQUIREMENT = "current.weepinbell-blocked-step-live"
CLAIMS = ["live-actor-identity", "natural-input", "frame-pacing"]
NAMES = ("current-mankey-and-weepinbell", "held-left-against-weepinbell",
         "weepinbell-blocked-step-continuous-progress")
FAULTS = ("wrong-blocked-tile", "missing-completed-frame", "wrong-weepinbell")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in zip(CLAIMS, NAMES)}


def _samples(rows):
    samples = []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        chunk = row["samples"]
        if (row.get("action") != "held-left-against-weepinbell"
                or row.get("command") is not None or not isinstance(chunk, list)
                or row.get("completedGameFrames") != len(chunk)
                or row.get("requestedGameFrames") != len(chunk)):
            raise ValueError("Weepinbell retained input differs from the 180-frame LEFT action")
        samples.extend(chunk)
    if len(samples) != 180:
        raise ValueError("Weepinbell LEFT action lacks 180 completed frames")
    return samples


def measurements(rows, replay):
    samples = _samples(rows)
    frames = [sample.get("frame") for sample in samples]
    if (any(type(frame) is not int for frame in frames)
            or any(right != left + 1 for left, right in zip(frames, frames[1:]))
            or replay.get("passed") is not True or replay.get("observedFrames") != 180):
        raise ValueError("Weepinbell blocked step did not complete 180 continuous frames")
    subjects = replay.get("subjects", {})
    for name, species, role in (("mankey", 56, "FOLLOWER"),
                                ("weepinbell", 70, "WILD")):
        bound = subjects.get(name, {})
        if (bound.get("species") != species or bound.get("role") != role
                or bound.get("identityVerified") is not True):
            raise ValueError("Weepinbell blocked-step subject identity differs: " + name)
        handle = bound.get("handle")
        for sample in samples:
            current = [actor for actor in sample.get("actors", [])
                       if actor.get("handle") == handle and actor.get("active") is True]
            if (len(current) != 1 or current[0].get("identityVerified") is not True
                    or current[0].get("presentationAttached") is not True
                    or current[0].get("species") != species
                    or current[0].get("role") != role):
                raise ValueError("Weepinbell blocked-step actor ceased to be current: " + name)
    reached = False
    for sample in samples:
        player = sample.get("player", {})
        if sample.get("context", {}).get("mapId") != 67 or player.get("y") != 392:
            raise ValueError("Weepinbell blocked-step player left Route 29 row 392")
        x = player.get("x")
        if x == 563:
            reached = True
        elif x != 564 or reached:
            raise ValueError("Weepinbell blocked-step player left the expected blocked path")
    if not reached:
        raise ValueError("Weepinbell blocked-step player never reached tile 563")
    return {"observedFrames": 180, "observedFrameUnit": "completed-main-loop-frames",
            "measurements": [{"claim": claim, "name": name, "value": 1,
                              "operator": "eq", "expected": 1}
                             for claim, name in zip(CLAIMS, NAMES)]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Weepinbell copied-data control")
    changed = list(rows)
    for index, row in enumerate(changed):
        if row.get("action") != "held-left-against-weepinbell" or not row.get("samples"):
            continue
        row = copy(row)
        row["samples"] = list(row["samples"])
        sample = copy(row["samples"][-1])
        if fault == "wrong-blocked-tile":
            sample["player"] = {**sample["player"], "x": 562}
        elif fault == "missing-completed-frame":
            sample["frame"] += 1
        else:
            sample["actors"] = [({**actor, "species": 71} if actor.get("species") == 70
                                 else actor) for actor in sample["actors"]]
        row["samples"][-1] = sample
        changed[index] = row
        return changed
    raise ValueError("Weepinbell blocked-step control has no completed frame")
