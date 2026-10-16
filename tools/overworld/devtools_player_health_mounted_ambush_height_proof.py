"""Acceptance claims and copied-data controls for mounted hit height."""

from copy import deepcopy

from tools.overworld.devtools_player_health_mounted_ambush_height_measurement import (
    OBSERVE_FRAMES, KIND, MIN_FRAMES,
)


CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary",
          "natural-input", "control-release")
NAMES = {
    "live-actor-identity": ("current-mount-and-wild-weepinbell",),
    "profile-resolution": ("active-ambush-hop-profile",),
    "engine-boundary": ("mounted-ambush-minus-20", "mounted-shared-jump-restored-height"),
    "natural-input": ("unforced-ambush-hop",),
    "control-release": ("no-battle-or-blackout",),
}
FAULTS = ("ambush-off", "wrong-damage", "retained-mount-height",
          "retained-rider-height", "stale-mount", "battle-task", "wrong-overlay")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    if (replay.get("passed") is not True or result.get("ready") is not True
            or result.get("observedFrames") != replay.get("observedFrames")
            or replay.get("observedFrames", 0) < MIN_FRAMES
            or result.get("observedFrameUnit") != "completed-game-frame"
            or result.get("flightFrames", 0) < 1
            or type(result.get("acceptedHits")) is not int
            or result["acceptedHits"] < 1
            or result.get("hpAfter") != 100 - 20 * result["acceptedHits"]
            or result["hpAfter"] > 80
            or result.get("finalTile") == [585, 407]
            or result.get("jumpArcSeen") is not True
            or result.get("baselineFaceY") != result.get("finalFaceY")
            or not isinstance(result.get("subject"), dict)
            or not isinstance(result.get("mountSubject"), dict)):
        raise ValueError("mounted Ambush replay lacks HP and stable mounted height")
    commands = [row.get("action") for row in rows
                if row.get("command") is not None]
    if commands != ["ambush-tile", "prepare-cyndaquil", "mount-cyndaquil",
                    "bind-cyndaquil", "spawn-weepinbell", "bind-weepinbell",
                    "before-contact", "after-ambush"]:
        raise ValueError("Ambush command stream differs")
    steps = [row.get("action") for row in rows
             if row.get("phase") == "observe" and row.get("samples")]
    if steps.count("observe-ambush") < 1 \
            or any(name != "observe-ambush"
                   for name in steps):
        raise ValueError("Ambush has no bounded normal Hop and stable mounted frames")
    return {"observedFrames": result["observedFrames"],
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["mountSubject"], result["subject"]],
            "observeFrames": OBSERVE_FRAMES,
            "acceptedHits": result["acceptedHits"],
            "finalTile": result["finalTile"],
            "baselineFaceY": result["baselineFaceY"],
            "finalFaceY": result["finalFaceY"],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Ambush copied-data control")
    changed = deepcopy(rows)
    step = next(row for row in changed if row.get("action") == "observe-ambush"
                and row.get("samples"))
    end = next(row for row in changed if row.get("action") == "after-ambush")
    if fault == "ambush-off":
        for row in changed:
            if row.get("action") == "observe-ambush":
                for sample in row.get("samples", []):
                    for actor in sample["actors"]:
                        if actor.get("species") == 70 and actor.get("role") == "WILD":
                            actor["matchedLayerMask"] &= ~(1 << 25)
    elif fault == "wrong-damage":
        end["receipt"]["playerHealth"]["hp"] = 100
        end["receipt"]["playerHealth"]["savedHp"] = 100
    elif fault in ("retained-mount-height", "retained-rider-height"):
        offset = 65536
        for row in changed:
            if row.get("action") == "observe-ambush":
                for pose in row.get("samples", []):
                    if fault == "retained-mount-height":
                        mounted = next(a for a in pose["actors"]
                                       if a.get("species") == 155 and a.get("role") == "MOUNTED")
                        mounted["engineObject"]["face_y"] += offset
                    else:
                        pose["player"]["face_y"] += offset
        if fault == "retained-mount-height":
            mounted = next(a for a in end["snapshot"]["actors"]
                           if a.get("species") == 155 and a.get("role") == "MOUNTED")
            mounted["engineObject"]["face_y"] += offset
        else:
            end["snapshot"]["player"]["face_y"] += offset
    elif fault == "stale-mount":
        mounted = next(a for a in step["samples"][0]["actors"]
                       if a.get("species") == 155 and a.get("role") == "MOUNTED")
        mounted["subjectIdentity"] += 1
    elif fault == "battle-task":
        step["samples"][0]["fieldControl"]["taskPointer"] = 0x02100000
    else:
        end["receipt"]["playerHealth"]["identity"]["overlaySha256"] = "0" * 64
    return changed
