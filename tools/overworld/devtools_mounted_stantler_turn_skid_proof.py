"""Completed-frame proof for Stantler's natural mounted turn skid."""

from copy import deepcopy

from tools.overworld.devtools_mount_control_stress import check_snapshot_pair


KIND = "mounted-stantler-turn-skid-v1"
REQUIREMENT = "current.mounted-stantler-turn-skid-facing"
CLAIMS = ("natural-input", "live-actor-identity", "logical-commit",
          "rendered-motion", "frame-pacing", "control-release")
ACTIONS = (("run-right", 49, 16), ("turn-down", 18, 128))
FAULTS = ("old-facing", "short-skid", "missing-second-tile", "missing-commit", "wrong-actor")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in (
                ("natural-input", "right-down-normal-input"),
                ("live-actor-identity", "same-mounted-stantler"),
                ("logical-commit", "two-east-skid-commits"),
                ("rendered-motion", "down-facing-east-skid-pair"),
                ("frame-pacing", "sixteen-skid-frames"),
                ("control-release", "skid-return-then-down-walk"))}


def _require(ok, reason):
    if not ok:
        raise ValueError("mounted Stantler turn skid: " + reason)


def _actor(sample):
    matches = [actor for actor in sample.get("actors", [])
               if actor.get("active") is True and actor.get("role") == "MOUNTED"
               and actor.get("species") == 234]
    _require(len(matches) == 1, "expected one live mounted Stantler")
    actor = matches[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1,
             "identity or mounted ownership differs")
    return actor


def _stream(rows):
    windows = {name: [] for name, _, _ in ACTIONS}
    events = []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        name = row.get("action")
        _require(name in windows and row.get("completedGameFrames") == len(row["samples"]),
                 "unexpected observation action or count")
        windows[name].extend(deepcopy(row["samples"]))
        events.extend(deepcopy(row.get("events", [])))
    _require(all(len(windows[name]) == count for name, count, _ in ACTIONS),
             "exact input windows differ")
    frames = [(name, sample) for name, _, _ in ACTIONS for sample in windows[name]]
    numbers = [sample["frame"] for _, sample in frames]
    _require(numbers == list(range(numbers[0], numbers[-1] + 1)),
             "completed frame gap or action order differs")
    _require(all(event.get("frame") in numbers for event in events),
             "native event is outside measured frames")
    return windows, frames, events


def _fault(windows, events, name):
    skid = next((sample for sample in windows["turn-down"]
                 if _actor(sample).get("motionKind") == "SKID"), None)
    _require(skid is not None, "copied control lacks skid")
    actor = _actor(skid)
    if name == "old-facing":
        skid["player"]["facing"] = actor["engineObject"]["facing"] = 3
        skid["player"]["face_x"] -= 32768
        skid["player"]["face_z"] = actor["engineObject"]["face_z"]
    elif name == "short-skid":
        actor["motionDuration"] = 7
    elif name == "missing-second-tile":
        second = next((sample for sample in windows["turn-down"]
                       if _actor(sample).get("motionKind") == "SKID"
                       and _actor(sample)["origin"] != actor["origin"]), None)
        _require(second is not None, "copied control lacks second skid tile")
        _actor(second)["motionKind"] = "NONE"
    elif name == "wrong-actor":
        actor["subjectIdentity"] ^= 1
    elif name == "missing-commit":
        commit = next((event for event in events
                       if event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                       and event.get("data", {}).get("valueB") == 4), None)
        _require(commit is not None, "copied control lacks skid commit")
        commit["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    else:
        raise ValueError("unknown Stantler skid control: " + name)
    return True


def _measure(windows, frames, events):
    first = _actor(frames[0][1])
    handle, identity = first["handle"], first["subjectIdentity"]
    context = frames[0][1]["context"]
    _require(context.get("mapId") == 33 and first["logical"] == {"x": 586, "y": 402},
             "prepared starting tile differs")
    for name, sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor["handle"] == handle
                 and actor["subjectIdentity"] == identity,
                 "completed frame or Stantler identity differs")
        check_snapshot_pair(sample, actor)
        mask = next(mask for action, _, mask in ACTIONS if action == name)
        held = sample["selector"]["heldKeys"]
        _require(sample["selector"]["rawHeld"] == held
                 and sample["selector"]["simulatedKeys"] == 0
                 and held in ((0, mask) if sample is windows[name][0]
                              else (mask,)),
                 "normal held-key window differs")
    skid = [(sample, _actor(sample)) for sample in windows["turn-down"]
            if _actor(sample)["motionKind"] == "SKID"]
    origin, target = validate_skid_pose(skid)
    _require(all(_actor(sample)["motionKind"] == "WALK"
                 for sample in windows["run-right"])
             and windows["run-right"][-1]["player"]["x"] == origin["x"]
             and windows["run-right"][-1]["player"]["y"] == origin["y"]
             and _actor(windows["run-right"][-1])["motionDuration"] == 4,
             "right run or turn boundary differs")
    recovery = [(sample, _actor(sample)) for sample in windows["turn-down"]
                if sample["frame"] > skid[-1][0]["frame"]]
    _require(len(recovery) == 2 and recovery[0][1]["motionKind"] == "NONE"
             and recovery[0][1]["motionPhase"] == "IDLE"
             and recovery[1][1]["motionKind"] == "WALK"
             and recovery[1][1]["motionElapsed"] == 1
             and recovery[1][1]["target"] == {"x": target["x"], "y": target["y"] + 1}
             and recovery[1][0]["player"]["facing"] == 1,
             "skid did not return control into Down recovery")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]
              and skid[0][0]["frame"] <= event["frame"] <= recovery[1][0]["frame"]]
    for tile in range(2):
        start_sample, start_actor = skid[tile * 8]
        finish_frame = skid[8][0]["frame"] if tile == 0 else recovery[0][0]["frame"]
        commit = start_actor["commitSequence"] + 1
        for name, frame, a, b in (
            ("MOTION_STARTED", start_sample["frame"], 4, 8),
            ("LOGICAL_COMMIT", finish_frame, commit, 4),
            ("MOTION_FINISHED", finish_frame, commit, 4),
            ("CONTROL_RETURNED", finish_frame, 1, commit),
        ):
            matches = [event for event in native if event["data"].get("event") == name
                       and event["frame"] == frame and event["data"].get("reason") == "OK"
                       and (event["data"].get("valueA"), event["data"].get("valueB")) == (a, b)]
            _require(len(matches) == 1, "skid tile lacks one exact native " + name)
    for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED"):
        _require(sum(event["data"].get("event") == name
                     and event["data"].get("valueA" if name == "MOTION_STARTED" else "valueB") == 4
                     for event in native) == 2, "skid has extra native " + name)
    _require(not any(event["data"].get("event") == "MOTION_CANCELED" for event in native),
             "skid was canceled")
    values = {rule[0]["name"]: 1 for rule in contract().values()}
    return {"values": values, "actorHandle": handle, "subjectIdentity": identity,
            "skidFrames": [sample["frame"] for sample, _ in skid],
            "skidOrigin": origin, "skidTarget": target}


def validate_skid_pose(skid):
    """The renderer faces the new turn for every old-heading skid tile frame."""
    _require(len(skid) == 16 and [actor["motionElapsed"] for _, actor in skid]
             == list(range(1, 9)) * 2, "exact two eight-frame skid tiles are missing")
    origin, target = skid[0][1]["origin"], skid[-1][1]["target"]
    _require([sample["frame"] for sample, _ in skid]
             == list(range(skid[0][0]["frame"], skid[0][0]["frame"] + 16)),
             "skid tile frames are not continuous")
    _require(target == {"x": origin["x"] + 2, "y": origin["y"]}
             and all(actor["motionDuration"] == 8
                     and actor["origin"] == {"x": origin["x"] + index // 8, "y": origin["y"]}
                     and actor["target"] == {"x": origin["x"] + index // 8 + 1, "y": origin["y"]}
                     and actor["commitSequence"] == skid[0][1]["commitSequence"] + index // 8
                     and sample["player"]["facing"] == 1
                     and actor["engineObject"]["facing"] == 1
                     for index, (sample, actor) in enumerate(skid)),
             "skid did not face Down while traveling east")
    _require(all(sample["player"]["face_y"] - actor["engineObject"]["face_y"] == 32768
                 and sample["player"]["face_z"] - actor["engineObject"]["face_z"] == -40960
                 for sample, actor in skid),
             "south rider did not stay behind the mount")
    return origin, target


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-turn-skid-facing"
                     and [action["id"] for action in test.get("actions", [])]
                     == [name for name, _, _ in ACTIONS],
                     "reviewed recipe differs")
        windows, frames, events = _stream(rows)
        applied = _fault(windows, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(windows, frames, events)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied, "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
