"""Independent controller check for fading variance and eased mounted Walks."""
from copy import deepcopy

from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
from tools.overworld.devtools_mount_pacing_proof import MountedPacingNegative
from tools.overworld.devtools_mount_speed_slew_measurement import (
    keyed_walk_duration, walk_step_fx32, stop_skid_tail, variance_width,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import complete_travel
from tools.overworld.devtools_mount_gait import check_gait, check_ground_camera

KIND = "mounted-speed-slew-v1"
REQUIREMENT = "current.mounted-speed-slew"
MOTIONS = 13
RULES = (("natural-input", "held-right-walk-count", MOTIONS, "eq"),
         ("live-actor-identity", "mounted-stantler-identity", [1, "MOUNTED", 234, 1], "eq"),
         ("rendered-motion", "continuous-walk-count", MOTIONS, "eq"),
         ("rendered-motion", "paired-position-mismatch-count", 0, "eq"),
         ("rendered-motion", "camera-locked-draw-frame-count", 47, "gte"),
         ("rendered-motion", "mounted-shadow-aligned-frame-count", 62, "gte"),
         ("rendered-motion", "distance-gait-and-seat-frame-count", 62, "gte"),
         ("rendered-motion", "gait-acceleration-braking-observed", [1, 1], "eq"),
         ("rendered-motion", "gait-settled-after-release", 1, "eq"),
         ("rendered-motion", "authored-stop-skid-tail", 1, "eq"),
         ("frame-pacing", "authored-variance-tile-count", MOTIONS, "eq"),
         ("rendered-motion", "eased-speed-transition-count", 1, "gte"),
         ("frame-pacing", "maximum-callback-gap", 2, "lte"),
         ("frame-pacing", "maximum-boundary-gap", 2, "lte"),
         ("engine-boundary", "player-step-callback-count", MOTIONS, "eq"),
         ("control-release", "released-player-control", [1, 0, 1], "eq"))
CLAIMS = tuple(dict.fromkeys(row[0] for row in RULES))
FAULTS = ("mounted-pacing-absent-subject", "mounted-pacing-stale-subject",
          "mounted-pacing-bad-pair", "mounted-pacing-bad-completed-pair",
          "mounted-pacing-missing-reader", "mounted-speed-common-snap",
          "mounted-speed-shadow-lag", "mounted-gait-missing-bounce",
          "mounted-gait-missing-lean", "mounted-gait-phase-reset", "mounted-gait-camera-bob",
          "mounted-speed-persistent-variance")


def contract():
    result = {}
    for claim, name, expected, operator in RULES:
        result.setdefault(claim, []).append(dict(name=name, expected=deepcopy(expected),
            operator=operator, type="array" if isinstance(expected, list) else "integer",
            validator="meaningful-observation"))
    return result


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    if replay.get("passed") is not True or replay.get("failures") != [] \
            or meter.get("passed") is not True or meter.get("ready") is not True \
            or meter.get("closed") is not True or meter.get("acceptedProof") is not False \
            or meter.get("failures") != []:
        raise ValueError("mounted speed lacks closed independent replay")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"),
                                              closed=True, errors=[]):
        raise ValueError("mounted speed private session did not close cleanly")
    subject, initial = meter["subject"], meter["initial"]
    bound = select_current_actor(initial, subject)
    actor = next(a for a in initial["actors"] if a["handle"] == bound["handle"])
    identity = [int(actor.get("identityVerified") is True), actor.get("role"),
                actor.get("species"), actor.get("inputOwnership")]
    if identity != [1, "MOUNTED", 234, 1]:
        raise ValueError("mounted speed lacks live Stantler")
    cleanup = meter["cleanup"]
    reader = cleanup.get("mountPacing", {})
    if cleanup.get("closed") is not True or cleanup.get("advancedFrames") != 0 \
            or cleanup.get("acceptedProof") is not False or reader.get("closed") is not True \
            or reader.get("failure") is not None or reader.get("subject") != subject:
        raise ValueError("mounted speed reader cleanup differs")
    windows = meter["windows"]
    if len(windows) != 1:
        raise ValueError("mounted speed needs one continuous input window")
    main = windows[0]
    gait_frames = main.get("gaitFrames")
    if not isinstance(gait_frames, list) or len(gait_frames) < 62:
        raise ValueError("mounted gait lacks completed frame proof")
    for index, frame in enumerate(gait_frames):
        pair, draw, camera = frame["pair"], frame["draw"], frame["camera"]
        check_pair_pose(pair)
        check_gait(pair, required=True)
        check_ground_camera(frame, gait_frames[index - 1] if index else None)
        gait = pair["gait"]
        if gait["input"]["options"] != 0x5A:
            raise ValueError("mounted gait does not use the authored default controls")
        if index:
            prior = gait_frames[index - 1]
            if frame["frame"] != prior["frame"] + 1:
                raise ValueError("mounted gait frame sequence is incomplete")
            previous = prior["pair"]["gait"]
            if gait["session"] == previous["session"] and gait["stamp"] != previous["stamp"] \
                    and gait["previous"] != previous["pose"]:
                raise ValueError("mounted gait phase or damping reset between frames")
        if camera["targetPointer"] != pair["playerPointer"] + 0x70:
            raise ValueError("mounted gait moved the ground camera anchor")
        for key, pointer in (("player", pair["playerPointer"]), ("mount", pair["mountPointer"])):
            value = draw[key]
            expected = [sum(value[part][axis] for part in ("position", "face", "extra", "jump"))
                        + (0x6000 if axis == 2 else 0) for axis in range(3)]
            if value["objectPointer"] != pointer or value["graphics"] != expected:
                raise ValueError("mounted gait actual sprite XYZ differs")
    if not any(frame["pair"]["gait"]["pose"]["bodyY"] > 0 for frame in gait_frames):
        raise ValueError("mounted gait never produced a bounce")
    lean_signs = [int(any(frame["pair"]["gait"]["pose"]["leanX"] * sign > 0
                         for frame in gait_frames)) for sign in (-1, 1)]
    settled = int(all(gait_frames[-1]["pair"]["gait"]["pose"][key] == 0
                      for key in ("bodyY", "riderY", "leanX", "leanZ")))
    shadow_frames = main.get("shadowFrames")
    if not isinstance(shadow_frames, list) \
            or len(shadow_frames) != main.get("cameraLockedFrames") \
            or meter.get("frames") - len(shadow_frames) not in (0, 1) \
            or len(shadow_frames) < 62:
        raise ValueError("mounted speed lacks 62 completed shadow frames")
    if any(after["frame"] != before["frame"] + 1
           for before, after in zip(shadow_frames, shadow_frames[1:])):
        raise ValueError("mounted speed shadow frames are not contiguous")
    for frame in shadow_frames:
        mount = frame["mount"]
        mount_owned = [shadow for shadow in frame["shadows"]
                       if shadow.get("owner") == frame["mountPointer"]]
        if len(mount_owned) != 1:
            raise ValueError("mounted shadow owner count differs")
        shadow = mount_owned[0]
        if shadow.get("flags", 0) & 1 != 1 or shadow.get("hidden") != 0 \
                or shadow.get("callback") not in (0x021FD719, 0x021FD92D) \
                or shadow["position"] != mount:
            raise ValueError("mounted shadow trails its mount")
        if any(value.get("hidden") == 0 for value in frame["shadows"]
               if value.get("owner") == frame["playerPointer"]):
            raise ValueError("player shadow is visible while mounted")
    motions, callbacks, steps, traces = (main.get(key, []) for key in
                                        ("motions", "callbacks", "steps", "traces"))
    if len(motions) < MOTIONS or not callbacks:
        raise ValueError("mounted speed lacks complete motion or native callback")
    skid_count, skid_duration = stop_skid_tail(motions[MOTIONS - 1]["duration"])
    total = MOTIONS + skid_count
    if len(motions) != total or len(steps) != total:
        raise ValueError("mounted speed lacks exact authored stop-skid tail or world steps")
    if any(frame["pair"].get("input", {}).get("heldKeys") != 0
           for frame in gait_frames if frame["frame"] > motions[MOTIONS - 1]["finishFrame"]):
        raise ValueError("mounted stop-skid tail has input or unexpected motion")
    durations = [motion["duration"] for motion in motions[:MOTIONS]]
    if any(motion["commitBefore"] != 2 + index
           or type(motion["duration"]) is not int
           or motion["duration"] != keyed_walk_duration(
               index, actor["subjectIdentity"], actor["handle"]["encounterGeneration"],
               motion["commitBefore"])
           for index, motion in enumerate(motions[:MOTIONS])):
        raise ValueError("mounted speed lost its keyed variance value")
    one_frame_gaps = [max(after["startFrame"] - before["travelEnd"]["frame"] - 1,
                          before.get("lastEndpointFrame", before["travelEnd"]["frame"])
                          - before["travelEnd"]["frame"])
                      for before, after in zip(motions, motions[1:])
                      if before["duration"] == after["duration"] == 1
                      and before["target"] == after["origin"]]
    if any(gap != 0 for gap in one_frame_gaps):
        raise ValueError("mounted speed has a stationary frame between one-frame Walks")
    for index, motion in enumerate(motions):
        skid = index >= MOTIONS
        if not complete_travel(motion) or motion["kind"] != ("SKID" if skid else "WALK") \
                or (skid and (motion["duration"] != skid_duration or motion["commitBefore"] != 2 + index)) \
                or motion["target"] != [motion["origin"][0]+1, motion["origin"][1]] \
                or motion["commitAfter"] != (motion["commitBefore"]+1) & 0xFFFFFFFF \
                or (index and motion["origin"] != motions[index-1]["target"]):
            raise ValueError("mounted speed motion continuity differs")
        for sample in motion["samples"]:
            prior = motions[index - 1]["duration"] if index and not skid else 0
            expected = (motion["origin"][0] << 16) + 32768 \
                + walk_step_fx32(sample["elapsed"], motion["duration"], prior)
            if sample["render"][0] != expected \
                    or sample["render"][2] != (motion["origin"][1] << 16) + 32768 \
                    or sample["jumpOffset"] != 0:
                raise ValueError("mounted speed did not use the eased tile path")
        if motion.get("travelEnd", {}).get("observedBy") == "one-frame-successor":
            # Recheck the native origin and endpoint directly from retained
            # callback rows. A lone completed-queue target cannot prove the
            # one-frame tile's movement or exclude a common-mode snap.
            origin_pose = [(coordinate << 16) + 32768 for coordinate in motion["origin"]]
            target_pose = [(coordinate << 16) + 32768 for coordinate in motion["target"]]
            pair = [event["data"] for event in callbacks
                    if event["frame"] == motion["startFrame"]
                    and event["data"]["publicSubject"].get("origin") == dict(zip(("x", "y"), motion["origin"]))
                    and event["data"]["publicSubject"].get("target") == dict(zip(("x", "y"), motion["target"]))
                    and event["data"]["publicSubject"].get("motionDuration") == 1]
            start_pair = [value for value in pair
                          if value["publicSubject"].get("motionPhase") == "MOVING"
                          and value["publicSubject"].get("motionElapsed") == 0
                          and [value["player"]["pos_x"], value["player"]["pos_z"]] == origin_pose]
            end_pair = [value for value in pair
                        if value["publicSubject"].get("motionPhase") == "COMMIT_PENDING"
                        and value["publicSubject"].get("motionElapsed") == 1
                        and [value["player"]["pos_x"], value["player"]["pos_z"]] == target_pose]
            if not start_pair or not end_pair \
                    or start_pair[0]["returnActorFrame"] >= end_pair[0]["returnActorFrame"] \
                    or start_pair[0]["returnNativeCycle"] > end_pair[0]["returnNativeCycle"]:
                raise ValueError("mounted speed lacks one-frame native origin and endpoint")
        for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            if sum(e["data"].get("event") == name for e in traces) != total:
                raise ValueError("mounted speed missing native " + name)
        if skid:
            for name, frame, a, b in (
                ("MOTION_STARTED", motion["startFrame"], 4, skid_duration),
                ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 4),
                ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 4),
                ("CONTROL_RETURNED", motion["finishFrame"], 1, motion["commitAfter"]),
            ):
                matched = [e["data"] for e in traces if e["frame"] == frame and e["data"].get("event") == name]
                if len(matched) != 1 or matched[0].get("reason") != "OK" \
                        or (matched[0].get("valueA"), matched[0].get("valueB")) != (a, b):
                    raise ValueError("mounted stop-skid lifecycle differs")
    for event in callbacks + steps:
        value = event["data"]
        if value.get("subject") != subject or value.get("publicSubject", {}).get("handle") != actor["handle"]:
            raise ValueError("mounted speed callback owner differs")
        check_pair_pose(value)
    if reader.get("counts") != dict(presentation=len(callbacks), playerStep=len(steps)):
        raise ValueError("mounted speed native callback totals differ")
    cycles = [e["data"]["returnNativeCycle"] for e in callbacks]
    if any(type(cycle) is not int for cycle in cycles) \
            or any(after < before for before, after in zip(cycles, cycles[1:])):
        raise ValueError("mounted speed native callback clock differs")
    callback_gap = max((after-before for before, after in zip(cycles, cycles[1:])), default=0)
    control = reader.get("latestCompletedPose", {}).get("avatarControl", {})
    if type(control.get("flags")) is not int:
        raise ValueError("mounted speed lacks terminal player control")
    release = [1, control["flags"] & 1, int(control.get("playerMoveState") in (0, 3))]
    values = (MOTIONS, identity, MOTIONS, 0, main["cameraLockedFrames"],
              len(shadow_frames),
              len(gait_frames), lean_signs, settled, 1,
              len(durations), sum(after != before for before, after in zip(durations, durations[1:])), callback_gap,
              main["boundaryGap"], len(steps[:MOTIONS]), release)
    result = []
    for (claim, name, expected, operator), value in zip(RULES, values):
        if not (value == expected if operator == "eq" else
                type(value) is int and
                (value <= expected if operator == "lte" else value >= expected)):
            raise ValueError("mounted speed failed " + name)
        result.append(dict(claim=claim, name=name, value=value,
                           expected=deepcopy(expected), operator=operator, passed=True))
    return result


class MountedSpeedNegative(MountedPacingNegative):
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown mounted speed fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.fault == "mounted-speed-persistent-variance":
            if self.applied or row.get("phase") != "observe":
                return row
            changed = deepcopy(row)
            handles = {s["handle"]["value"] for s in subjects.values()}
            for sample in changed.get("samples", []):
                for actor in sample.get("actors", []):
                    index = actor.get("commitSequence", -1) - 2
                    if actor.get("handle", {}).get("value") not in handles \
                            or actor.get("motionKind") != "WALK" or not 0 <= index < MOTIONS \
                            or variance_width(index) != 0:
                        continue
                    old_duration = keyed_walk_duration(index, actor["subjectIdentity"],
                        actor["handle"]["encounterGeneration"], actor["commitSequence"], fade=False)
                    if old_duration != actor["motionDuration"]:
                        actor["motionDuration"] = old_duration
                        self.applied = True
                        return changed
            return row
        if self.fault.startswith("mounted-gait-"):
            if self.applied or row.get("phase") != "observe":
                return row
            changed = deepcopy(row)
            if self.fault == "mounted-gait-camera-bob":
                for sample in changed.get("samples", []):
                    if not isinstance(sample.get("camera", {}).get("lookAtTarget"), list) \
                            or not sample.get("mountedDrawPose", {}).get("player", {}).get("graphicsPointer"):
                        continue
                    # Empty arm receipts and the allowed unready setup pose
                    # are not the baseline for the measured camera stream.
                    if not getattr(self, "camera_seen", False):
                        self.camera_seen = True
                        continue
                    sample["camera"]["lookAtTarget"][1] += 4096
                    self.applied = True
                    break
                return changed if self.applied else row
            for sample in changed.get("samples", []):
                pair = sample.get("mountPacing", {}).get("latestCompletedPose", {})
                gait = pair.get("gait", {})
                pose = gait.get("pose", {})
                if not pose.get("bodyY") or not pose.get("leanX"):
                    continue
                if self.fault == "mounted-gait-missing-bounce":
                    pair["mount"]["unk88_y"] -= pose["bodyY"]
                elif self.fault == "mounted-gait-missing-lean":
                    pair["player"]["face_x"] -= pose["leanX"]
                else:
                    pose["phase"] = (pose["phase"] + 256) & 65535
                self.applied = True
                break
            return changed if self.applied else row
        if self.fault not in ("mounted-speed-common-snap", "mounted-speed-shadow-lag"):
            return super().mutate(row, subjects)
        if self.applied or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        if self.fault == "mounted-speed-shadow-lag":
            for sample in changed.get("samples", []):
                shadows = sample.get("mountedDrawPose", {}).get("shadows", [])
                mount = sample.get("mountedDrawPose", {}).get("mount", {})
                owned = next((shadow for shadow in shadows
                              if shadow.get("owner") == mount.get("objectPointer")), None)
                if owned is not None:
                    owned["position"][0] -= 65536
                    self.applied = True
                    break
            return changed if self.applied else row
        handles = {s["handle"]["value"] for s in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((a for a in sample.get("actors", [])
                          if a.get("handle", {}).get("value") in handles
                          and a.get("motionKind") == "WALK"
                          and a.get("motionPhase") == "MOVING"), None)
            pair = sample.get("mountPacing", {}).get("latestCompletedPose")
            if actor is None or not isinstance(pair, dict):
                continue
            sample["player"]["pos_x"] += 65536
            pair["player"]["pos_x"] += 65536
            pair["mount"]["pos_x"] += 65536
            self.applied = True
            break
        return changed if self.applied else row


def validate_negative_result(result, fault):
    if fault not in FAULTS or result.get("passed") is not False:
        raise ValueError("mounted speed copied control did not fail")
    failures = result.get("failures", []) + result.get("measurements", {}).get(KIND, {}).get("failures", [])
    reasons = set()
    for value in failures:
        if isinstance(value, str):
            reasons.add(value)
        elif isinstance(value, dict):
            reasons.update(value.get(key) for key in ("detail", "message")
                           if isinstance(value.get(key), str))
    expected = {"mounted-pacing-absent-subject": "selected handle must name exactly one current active actor",
                "mounted-pacing-stale-subject": "selected actor has a stale authorityGeneration",
                "mounted-pacing-bad-pair": "mounted base, facing or rider offset differs",
                "mounted-pacing-bad-completed-pair": "mounted base, facing or rider offset differs",
                "mounted-pacing-missing-reader": "'mountPacing'",
                "mounted-speed-common-snap": "mounted gait input, state, or owner differs",
                "mounted-speed-shadow-lag": "mounted shadow trails its mount",
                "mounted-gait-missing-bounce": "mounted base, facing or rider offset differs",
                "mounted-gait-missing-lean": "mounted base, facing or rider offset differs",
                "mounted-gait-phase-reset": "mounted gait differs from distance and frame reference",
                "mounted-gait-camera-bob": "mounted gait moved or shook the actual ground camera",
                "mounted-speed-persistent-variance": "mounted speed variance did not fade at nominal maximum"}[fault]
    if not any(expected in reason for reason in reasons):
        raise ValueError("mounted speed copied control failed for an unrelated reason: " + fault)
