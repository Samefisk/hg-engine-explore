"""Completed-frame proof for Stantler's natural mounted turn skid."""

from copy import deepcopy

from tools.overworld.devtools_mount_control_stress import check_snapshot_pair
from tools.overworld.devtools_mount_gait import check_gait, normalized_pair


KIND = "mounted-stantler-turn-skid-v1"
REQUIREMENT = "current.mounted-stantler-turn-skid-facing"
CLAIMS = ("natural-input", "live-actor-identity", "logical-commit",
          "rendered-motion", "frame-pacing", "control-release")
ACTIONS = (("run-right", 40, 16), ("turn-down", 18, 128))
FAULTS = ("old-facing", "short-skid", "missing-second-tile", "missing-commit", "wrong-actor",
          "missing-pair", "missing-gait", "wrong-gait-owner", "wrong-gait-pose",
          "wrong-gait-stamp", "wrong-pair-pointer", "stale-pair", "wrong-seat", "wrong-height",
          "missing-first-return", "wrong-gap-state", "wrong-gap-commit", "missing-down-start")
SKID_TIME = 2 * 3  # Shared SkidTime doubles the last displayed Walk time.
SKID_GAP = 2       # This fixture's stock stationary-command completion seam.


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in (
                ("natural-input", "right-down-normal-input"),
                ("live-actor-identity", "same-mounted-stantler"),
                ("logical-commit", "two-east-skid-commits"),
                ("rendered-motion", "down-facing-east-skid-pair"),
                ("frame-pacing", "twelve-skid-frames"),
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


def _checked_pose(sample, actor):
    """Bind current native gait to this exact pair before checking the seat."""
    pair = sample.get("mountedPair")
    _require(isinstance(pair, dict), "native mounted pair is missing")
    identity = actor["engineIdentity"]
    _require(pair.get("playerPointer") == identity["anchorPointer"]
             and pair.get("mountPointer") == identity["pointer"],
             "native mounted pair is bound to another object")
    for name, raw in (("player", sample["player"]), ("mount", actor["engineObject"])):
        _require(all(pair.get(name, {}).get(key) == value for key, value in raw.items()),
                 "native mounted pair differs from its completed snapshot")
    check_gait(pair, required=True)
    checked = normalized_pair(pair)
    checked_sample = dict(sample, player=checked["player"])
    checked_actor = dict(actor, engineObject=checked["mount"])
    check_snapshot_pair(checked_sample, checked_actor)
    return checked_sample, checked_actor


def _fault(windows, events, name):
    skid = next((sample for sample in windows["turn-down"]
                 if _actor(sample).get("motionKind") == "SKID"), None)
    _require(skid is not None, "copied control lacks skid")
    actor = _actor(skid)
    if name == "old-facing":
        skid["player"]["facing"] = actor["engineObject"]["facing"] = 3
        skid["player"]["face_x"] -= 32768
        skid["player"]["face_z"] = (actor["engineObject"]["face_z"]
                                      + skid["mountedPair"]["gait"]["pose"]["leanZ"])
        skid["mountedPair"]["player"].update(skid["player"])
        skid["mountedPair"]["mount"].update(actor["engineObject"])
    elif name == "short-skid":
        actor["motionDuration"] = SKID_TIME - 1
    elif name == "missing-second-tile":
        second = next((sample for sample in windows["turn-down"]
                       if _actor(sample).get("motionKind") == "SKID"
                       and _actor(sample)["origin"] != actor["origin"]), None)
        _require(second is not None, "copied control lacks second skid tile")
        _actor(second)["motionKind"] = "NONE"
    elif name == "wrong-actor":
        actor["subjectIdentity"] ^= 1
    elif name in ("missing-commit", "missing-first-return", "missing-down-start"):
        event_name = {"missing-commit": "LOGICAL_COMMIT",
                      "missing-first-return": "CONTROL_RETURNED",
                      "missing-down-start": "MOTION_STARTED"}[name]
        wanted_frame = (skid["frame"] + SKID_TIME if name == "missing-first-return"
                        else skid["frame"] + 2 * SKID_TIME + SKID_GAP
                            if name == "missing-down-start" else None)
        commit = next((event for event in events
                       if event.get("data", {}).get("event") == event_name
                       and event.get("data", {}).get("actorHandle") == actor["handle"]["value"]
                       and (wanted_frame is None or event["frame"] == wanted_frame)
                       and event.get("data", {}).get("valueB" if name == "missing-commit" else "valueA")
                           == (4 if name == "missing-commit" else 1)), None)
        _require(commit is not None, "copied control lacks native " + event_name)
        commit["data"]["event"] = "REMOVED_" + event_name
    elif name in ("wrong-gap-state", "wrong-gap-commit"):
        gap = next((sample for sample in windows["turn-down"]
                    if sample["frame"] == skid["frame"] + SKID_TIME), None)
        _require(gap is not None, "copied control lacks interim skid return")
        if name == "wrong-gap-state":
            _actor(gap)["movementPolicy"]["pending"] = 0
        else:
            _actor(gap)["commitSequence"] -= 1
    elif name == "missing-pair":
        skid.pop("mountedPair", None)
    elif name in ("missing-gait", "wrong-gait-owner", "wrong-gait-pose",
                  "wrong-gait-stamp", "wrong-pair-pointer", "stale-pair",
                  "wrong-seat", "wrong-height"):
        pair = skid["mountedPair"]
        if name == "missing-gait":
            pair.pop("gait", None)
        elif name == "wrong-gait-owner":
            pair["gait"]["owner"] ^= 4
        elif name == "wrong-gait-pose":
            pair["gait"]["pose"]["leanX"] += 1
        elif name == "wrong-gait-stamp":
            pair["gait"]["stamp"] -= 1
        elif name == "wrong-pair-pointer":
            pair["mountPointer"] ^= 4
        elif name == "stale-pair":
            pair["player"]["pos_x"] -= 1
        else:
            key = "face_z" if name == "wrong-seat" else "unk88_y"
            # A real bad seat must fail even when its snapshot binding agrees.
            skid["player"][key] += 1
            pair["player"][key] += 1
    else:
        raise ValueError("unknown Stantler skid control: " + name)
    return True


def _measure(windows, frames, events):
    first = _actor(frames[0][1])
    handle, identity = first["handle"], first["subjectIdentity"]
    pointers = first["engineIdentity"]["anchorPointer"], first["engineIdentity"]["pointer"]
    context = frames[0][1]["context"]
    _require(context.get("mapId") == 33 and first["logical"] == {"x": 586, "y": 402},
             "prepared starting tile differs")
    for name, sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor["handle"] == handle
                 and actor["subjectIdentity"] == identity
                 and (actor["engineIdentity"]["anchorPointer"], actor["engineIdentity"]["pointer"])
                     == pointers,
                 "completed frame or Stantler identity differs")
        _checked_pose(sample, actor)
        mask = next(mask for action, _, mask in ACTIONS if action == name)
        held = sample["selector"]["heldKeys"]
        _require(sample["selector"]["rawHeld"] == held
                 and sample["selector"]["simulatedKeys"] == 0
                 and held in ((0, mask) if sample is windows[name][0]
                              else (mask,)),
                 "normal held-key window differs")
    skid = [(sample, _actor(sample)) for sample in windows["turn-down"]
            if _actor(sample)["motionKind"] == "SKID"]
    origin, target = validate_skid_pose([_checked_pose(sample, actor) for sample, actor in skid])
    _require(all(_actor(sample)["motionKind"] == "WALK"
                 for sample in windows["run-right"])
             and windows["run-right"][-1]["player"]["x"] == origin["x"]
             and windows["run-right"][-1]["player"]["y"] == origin["y"]
             and _actor(windows["run-right"][-1])["motionDuration"] == 3,
             "right run or turn boundary differs")
    gap = [(sample, _actor(sample)) for sample in windows["turn-down"]
           if skid[SKID_TIME - 1][0]["frame"] < sample["frame"] < skid[SKID_TIME][0]["frame"]]
    _require(len(gap) == SKID_GAP
             and all(actor["motionKind"] == "NONE" and actor["motionPhase"] == "IDLE"
                     and actor["commitSequence"] == skid[0][1]["commitSequence"] + 1
                     and actor["origin"] == origin
                     and actor["target"] == {"x": origin["x"] + 1, "y": origin["y"]}
                     and actor["logical"] == actor["target"]
                     and {"x": sample["player"]["x"], "y": sample["player"]["y"]} == actor["target"]
                     and actor["movementPolicy"]["pending"] == 1
                     and actor["movementPolicy"]["pendingSkid"] == 0
                     and actor["movementPolicy"]["skid"] == 1
                     for sample, actor in gap),
             "interim skid return lost its completed tile or pending continuation")
    recovery = [(sample, _actor(sample)) for sample in windows["turn-down"]
                if sample["frame"] > skid[-1][0]["frame"]]
    _require(len(recovery) == 4
             and recovery[0][0]["frame"] == skid[-1][0]["frame"] + 1
             and recovery[0][1]["motionElapsed"] == 1
             and recovery[0][1]["origin"] == target
             and recovery[0][1]["target"] == {"x": target["x"], "y": target["y"] + 1}
             and recovery[0][1]["commitSequence"] == skid[-1][1]["commitSequence"] + 1
             and all(actor["motionKind"] == "WALK"
                     and actor["target"]["x"] == target["x"]
                     and actor["target"]["y"] == actor["origin"]["y"] + 1
                     and sample["player"]["facing"] == 1 for sample, actor in recovery),
             "skid did not return control into Down recovery")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]
              and skid[0][0]["frame"] <= event["frame"] <= recovery[0][0]["frame"]]
    for tile in range(2):
        start_sample, start_actor = skid[tile * SKID_TIME]
        finish_frame = start_sample["frame"] + SKID_TIME
        commit = start_actor["commitSequence"] + 1
        for name, frame, a, b in (
            ("MOTION_STARTED", start_sample["frame"], 4, SKID_TIME),
            ("LOGICAL_COMMIT", finish_frame, commit, 4),
            ("MOTION_FINISHED", finish_frame, commit, 4),
            ("CONTROL_RETURNED", finish_frame, 1, commit),
        ):
            matches = [event for event in native if event["data"].get("event") == name
                       and event["frame"] == frame and event["data"].get("reason") == "OK"
                       and (event["data"].get("valueA"), event["data"].get("valueB")) == (a, b)]
            _require(len(matches) == 1, "skid tile lacks one exact native " + name)
    down = recovery[0]
    _require(sum(event["data"].get("event") == "MOTION_STARTED"
                 and event["frame"] == down[0]["frame"]
                 and event["data"].get("reason") == "OK"
                 and (event["data"].get("valueA"), event["data"].get("valueB"))
                     == (1, down[1]["motionDuration"]) for event in native) == 1,
             "final skid return lacks its exact native Down Walk start")
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
    """Pure static pose check; full proof supplies only gait-checked pairs."""
    _require(len(skid) == 2 * SKID_TIME and [actor["motionElapsed"] for _, actor in skid]
             == list(range(1, SKID_TIME + 1)) * 2, "exact two six-frame skid tiles are missing")
    origin, target = skid[0][1]["origin"], skid[-1][1]["target"]
    _require([sample["frame"] for sample, _ in skid]
             == [skid[0][0]["frame"] + index + (SKID_GAP if index >= SKID_TIME else 0)
                 for index in range(2 * SKID_TIME)],
             "skid tile frames or exact completion gap differ")
    _require(target == {"x": origin["x"] + 2, "y": origin["y"]}
             and all(actor["motionDuration"] == SKID_TIME
                     and actor["origin"] == {"x": origin["x"] + index // SKID_TIME, "y": origin["y"]}
                     and actor["target"] == {"x": origin["x"] + index // SKID_TIME + 1, "y": origin["y"]}
                     and actor["commitSequence"] == skid[0][1]["commitSequence"] + index // SKID_TIME
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
