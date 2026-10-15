"""Completed-frame proof that a mounted turn skid reaches a blocked exit."""

from copy import deepcopy

REQUIREMENT = "current.mounted-stantler-turn-skid-blocked-exit"
CLAIMS = ("natural-input", "live-actor-identity", "collision-decision",
          "logical-commit", "rendered-motion", "frame-pacing", "control-release")
ACTIONS = (("run-right", 47, 16), ("turn-down", 18, 128))
FAULTS = ("wrong-actor", "wrong-input", "missing-first-skid",
          "missing-second-skid", "missing-commit", "missing-crash",
          "early-crash", "wall-cross", "missing-control")
NAMES = ("right-down-normal-input", "same-mounted-stantler",
         "blocked-recovery-crash", "two-clear-east-skid-commits",
         "down-facing-east-skid-pair", "eight-skid-frames",
         "idle-control-before-wall")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in zip(CLAIMS, NAMES)}


def _require(ok, reason):
    if not ok:
        raise ValueError("mounted blocked turn skid: " + reason)


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
        _require(name in windows
                 and row.get("completedGameFrames") == len(row["samples"]),
                 "unexpected observation action or count")
        windows[name].extend(deepcopy(row["samples"]))
        events.extend(deepcopy(row.get("events", [])))
    _require(all(len(windows[name]) == count for name, count, _ in ACTIONS),
             "exact input windows differ")
    frames = [(name, sample) for name, _, _ in ACTIONS
              for sample in windows[name]]
    numbers = [sample["frame"] for _, sample in frames]
    _require(numbers == list(range(numbers[0], numbers[-1] + 1)),
             "completed frame gap or action order differs")
    _require(all(event.get("frame") in numbers for event in events),
             "native event is outside measured frames")
    return windows, frames, events


def _fault(windows, events, fault):
    _require(fault in FAULTS, "unknown copied-data control")
    skid = [(sample, _actor(sample)) for sample in
            windows["turn-down"]
            if _actor(sample).get("motionKind") == "SKID"]
    _require(len(skid) >= 5, "copied control lacks two skid tiles")
    if fault == "wrong-actor":
        skid[0][1]["subjectIdentity"] ^= 1
    elif fault == "wrong-input":
        windows["turn-down"][0]["selector"]["heldKeys"] = 16
    elif fault == "missing-first-skid":
        skid[0][1]["motionKind"] = "NONE"
    elif fault == "missing-second-skid":
        skid[4][1]["motionKind"] = "NONE"
    elif fault == "missing-commit":
        commit = next((event for event in events
                       if event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                       and event["data"].get("valueB") == 4
                       and event["frame"] >= skid[4][0]["frame"]), None)
        _require(commit is not None, "copied control lacks second skid commit")
        commit["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    elif fault in ("missing-crash", "early-crash"):
        crashes = [event for event in events
                   if event.get("data", {}).get("event") == "WORLD_EFFECT"
                   and event["data"].get("valueA") == 3]
        _require(crashes, "copied control lacks blocked Crash")
        for event in crashes:
            if fault == "missing-crash":
                event["data"]["event"] = "REMOVED_WORLD_EFFECT"
            else:
                event["frame"] = skid[0][0]["frame"]
                event["data"]["sequence"] = 0
    elif fault == "wall-cross":
        _actor(windows["turn-down"][-1])["logical"]["y"] = 405
    elif fault == "missing-control":
        _actor(windows["turn-down"][-1])["movementPolicy"]["pending"] = 1
    return True


def _measure(windows, frames, events):
    first = _actor(frames[0][1])
    handle, identity = first["handle"], first["subjectIdentity"]
    fingerprint = first["behaviorFingerprint"]
    context = frames[0][1]["context"]
    _require(context.get("mapId") == 33
             and first["logical"] == {"x": 584, "y": 404},
             "prepared start tile differs")
    for name, sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary")
                 == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor["handle"] == handle
                 and actor["subjectIdentity"] == identity
                 and actor["behaviorFingerprint"] == fingerprint,
                 "completed frame or Stantler identity differs")
        mask = next(mask for action, _, mask in ACTIONS if action == name)
        held = sample["selector"]["heldKeys"]
        _require(sample["selector"]["rawHeld"] == held
                 and sample["selector"]["simulatedKeys"] == 0
                 and held in ((0, mask) if sample is windows[name][0]
                              else (mask,)),
                 "normal held-key window differs")
        _require(actor["logical"]["y"] == 404
                 and actor["logical"]["x"] <= 602
                 and sample["player"]["y"] == 404
                 and sample["player"]["x"] <= 602
                 and actor["target"]["y"] == 404
                 and actor["target"]["x"] <= 602,
                 "mounted pair crossed the blocked turn wall")
    skid = [(sample, _actor(sample)) for sample in
            windows["turn-down"]
            if _actor(sample)["motionKind"] == "SKID"]
    _require(len(skid) == 8
             and [actor["motionElapsed"] for _, actor in skid]
                 == list(range(1, 5)) * 2
             and [sample["frame"] for sample, _ in skid[:4]]
                 == list(range(skid[0][0]["frame"], skid[0][0]["frame"] + 4))
             and [sample["frame"] for sample, _ in skid[4:]]
                 == list(range(skid[4][0]["frame"], skid[4][0]["frame"] + 4))
             and skid[4][0]["frame"] == skid[0][0]["frame"] + 6,
             "two complete four-frame skid tiles are missing")
    run_end = _actor(windows["run-right"][-1])
    _require(run_end["motionKind"] == "WALK"
             and run_end["motionDuration"] == 2
             and run_end["logical"] == {"x": 600, "y": 404},
             "Right run-up or two-frame turn boundary differs")
    for index, (sample, actor) in enumerate(skid):
        tile = index // 4
        _require(actor["origin"] == {"x": 600 + tile, "y": 404}
                 and actor["target"] == {"x": 601 + tile, "y": 404}
                 and actor["motionDuration"] == 4
                 and sample["player"]["facing"] == 1
                 and actor["engineObject"]["facing"] == 1,
                 "skid did not face Down while moving east through clear tiles")
        player, mount = sample["player"], actor["engineObject"]
        _require(all(player["pos_" + axis] == mount["pos_" + axis]
                     for axis in "xyz")
                 and player["face_z"] - mount["face_z"] == -40960,
                 "mounted skid pair lost its shared base or Down-facing offset")
    native = [event for event in events
              if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    second_finish_frame = None
    second_finish_sequence = None
    for tile in range(2):
        start_sample, start_actor = skid[tile * 4]
        finish_frame = skid[4][0]["frame"] - 2 if tile == 0 else skid[-1][0]["frame"] + 1
        commit = start_actor["commitSequence"] + 1
        for event_name, frame, a, b in (
            ("MOTION_STARTED", start_sample["frame"], 4, 4),
            ("LOGICAL_COMMIT", finish_frame, commit, 4),
            ("MOTION_FINISHED", finish_frame, commit, 4),
            ("CONTROL_RETURNED", finish_frame, 1, commit),
        ):
            matches = [event for event in native
                       if event["data"].get("event") == event_name
                       and event["frame"] == frame
                       and event["data"].get("reason") == "OK"
                       and (event["data"].get("valueA"),
                            event["data"].get("valueB")) == (a, b)]
            _require(len(matches) == 1,
                     "skid tile lacks one exact native " + event_name)
        second_finish_frame = finish_frame
        if tile == 1:
            second_finish_sequence = next(event["data"]["sequence"]
                for event in native if event["data"].get("event") == "CONTROL_RETURNED"
                and event["frame"] == finish_frame
                and event["data"].get("valueB") == commit)
    _require(sum(event["data"].get("event") == "MOTION_STARTED"
                 and event["data"].get("valueA") == 4
                 and event["frame"] >= skid[0][0]["frame"]
                 for event in native) == 2
             and not any(event["data"].get("event") == "MOTION_CANCELED"
                         for event in native),
             "skid has an extra start or canceled motion")
    crashes = [event for event in native
               if event["data"].get("event") == "WORLD_EFFECT"
               and event["data"].get("reason") == "OK"
               and event["data"].get("valueA") == 3
               and (event["frame"] > second_finish_frame
                    or (event["frame"] == second_finish_frame
                        and event["data"].get("sequence", 0)
                            > second_finish_sequence))]
    _require(crashes, "blocked recovery did not Crash after both skid commits")
    _require(not any(event["data"].get("event") == "MOTION_STARTED"
                     and event["frame"] > second_finish_frame
                     for event in native),
             "blocked recovery started motion through the wall")
    final = _actor(windows["turn-down"][-1])
    _require(final["logical"] == {"x": 602, "y": 404}
             and final["motionKind"] == "NONE"
             and final["motionPhase"] == "IDLE"
             and final["movementPolicy"]["pending"] == 0
             and final["movementPolicy"]["speed"] == 0
             and final["inputOwnership"] == 1,
             "Crash did not stop before the wall and return control")
    return {"values": dict.fromkeys(NAMES, 1), "actorHandle": handle,
            "subjectIdentity": identity, "skidFrames": [s["frame"] for s, _ in skid],
            "skidOrigin": {"x": 600, "y": 404},
            "skidTarget": {"x": 602, "y": 404},
            "firstCrashFrame": crashes[0]["frame"]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-turn-skid-blocked-exit"
                     and [action["id"] for action in test.get("actions", [])]
                         == [name for name, _, _ in ACTIONS]
                     and [(action["op"], action["args"]) for action in test["actions"]]
                         == [("step", {"frames": count, "keys": keys})
                             for (_, count, _), keys in zip(
                                 ACTIONS, (["RIGHT"], ["DOWN"]))],
                     "reviewed route differs")
        windows, frames, events = _stream(rows)
        applied = _fault(windows, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(windows, frames, events)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied,
                "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
