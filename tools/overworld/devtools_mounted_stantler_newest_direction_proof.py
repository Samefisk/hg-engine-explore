"""Completed-frame proof: a newly pressed direction wins while the old key stays held."""

from copy import deepcopy


KIND = "mounted-stantler-newest-held-direction-v1"
REQUIREMENT = "current.mounted-stantler-newest-held-direction"
CLAIMS = ("natural-input", "live-actor-identity", "logical-commit",
          "rendered-motion", "frame-pacing", "control-release")
NAMES = ("new-up-edge-while-left-held", "same-mounted-stantler",
         "two-west-skid-commits", "up-facing-west-skid-and-up-walk",
         "complete-variable-time-skid-tiles", "skid-ends-before-up-walk")
MIN_RUN_FRAMES = 19
MAX_RUN_FRAMES = 32
RUN_END_X = 588
ACTIONS = (("run-left", MAX_RUN_FRAMES, 32),
           ("new-up-while-left-held", 24, 96))
FAULTS = ("missing-new-edge", "older-direction-wins", "skid-cancel",
          "missing-commit", "up-missing", "wrong-actor")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in zip(CLAIMS, NAMES)}


def _require(ok, reason):
    if not ok:
        raise ValueError("mounted newest held direction: " + reason)


def _actor(sample):
    actors = [actor for actor in sample.get("actors", [])
              if actor.get("active") is True and actor.get("role") == "MOUNTED"
              and actor.get("species") == 234]
    _require(len(actors) == 1, "expected one live mounted Stantler")
    actor = actors[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1
             and actor.get("handle", {}).get("slot") == 7
             and actor.get("handle", {}).get("encounterGeneration", 0) > 0,
             "mounted Stantler identity or ownership differs")
    return actor


def run_until():
    return {"kind": "actor-field", "subject": "stantler",
            "path": "target.x", "operator": "eq",
            "value": RUN_END_X, "when": "final"}


def _stream(rows):
    windows = {name: [] for name, _, _ in ACTIONS}
    events = []
    order = []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        name = row.get("action")
        _require(name in windows and row.get("completedGameFrames")
                 == len(row["samples"]) and bool(row["samples"]),
                 "observation action or completed-frame count differs")
        if not order or name != order[-1]:
            _require(len(order) < len(ACTIONS)
                     and name == ACTIONS[len(order)][0]
                     and not windows[name], "observation action order differs")
            order.append(name)
        windows[name].extend(deepcopy(row["samples"]))
        events.extend(deepcopy(row.get("events", [])))
    left = windows["run-left"]
    _require(order == [name for name, _, _ in ACTIONS]
             and MIN_RUN_FRAMES <= len(left) <= MAX_RUN_FRAMES
             and len(windows["new-up-while-left-held"]) == 24,
             "measured Left run or exact 24-frame Up window differs")
    _require(all(_actor(sample).get("target", {}).get("x") != RUN_END_X
                 for sample in left[:-1])
             and _actor(left[-1]).get("target", {}).get("x") == RUN_END_X,
             "Left did not stop at the first completed fifth-Walk target")
    frames = [(name, sample) for name, _, _ in ACTIONS for sample in windows[name]]
    numbers = [sample["frame"] for _, sample in frames]
    _require(numbers == list(range(numbers[0], numbers[-1] + 1)),
             "completed game frames have a gap or reordered action")
    _require(all(event.get("frame") in numbers for event in events),
             "native event lies outside measured frames")
    return windows, frames, events


def _native(events, handle):
    return [event for event in events if event.get("kind") == "native"
            and event.get("data", {}).get("actorHandle") == handle]


def _event(native, name, a, b, earliest, latest):
    matches = [event for event in native
               if earliest <= event["frame"] <= latest
               and event["data"].get("event") == name
               and event["data"].get("reason") == "OK"
               and (event["data"].get("valueA"), event["data"].get("valueB"))
                   == (a, b)]
    _require(len(matches) == 1, "missing or duplicate native " + name)
    return matches[0]


def _receipt(events, handle, operation):
    result = []
    for row in events:
        data = row.get("data", {})
        if (row.get("kind") != "native-observation"
            or data.get("observation") != "walk-policy"
            or data.get("operation") != operation
            or data.get("publicSubject", {}).get("handle", {}).get("value")
                != handle):
            continue
        request = bytes.fromhex(data["requestHex"])
        response = bytes.fromhex(data["responseHex"])
        _require(len(request) == len(response) == 28,
                 "native Walk receipt size differs")
        result.append((row, request, response))
    return result


def _groups(skid):
    groups = []
    for sample, actor in skid:
        key = (actor["origin"]["x"], actor["target"]["x"],
               actor["commitSequence"])
        if not groups or key != groups[-1][0]:
            groups.append((key, []))
        groups[-1][1].append((sample, actor))
    return [group for _, group in groups]


def _measure(windows, frames, events):
    first = _actor(frames[0][1])
    context = frames[0][1]["context"]
    handle, identity = first["handle"], first["subjectIdentity"]
    fingerprint = first["behaviorFingerprint"]
    _require(context.get("mapId") == 33
             and first["logical"] == {"x": 593, "y": 402},
             "prepared map 33 start tile differs")
    for name, sample in frames:
        actor = _actor(sample)
        native = sample.get("nativeObservation", {})
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor["handle"] == handle
                 and actor["subjectIdentity"] == identity
                 and actor["behaviorFingerprint"] == fingerprint
                 and native.get("installedBeforeBoot") is True
                 and native.get("coverageComplete") is True
                 and native.get("error") is None
                 and native.get("eventsDropped") == 0
                 and native.get("profilesEvicted") == 0,
                 "frame, native coverage or mounted Stantler identity differs")
        player, mount = sample["player"], actor["engineObject"]
        _require(all(player.get("pos_" + axis) == mount.get("pos_" + axis)
                     and type(player.get("pos_" + axis)) is int
                     for axis in "xyz")
                 and player.get("facing") == mount.get("facing"),
                 "rider and mount base or facing differs")
        selector = sample["selector"]
        expected = 32 if name == "run-left" else 96
        _require(selector.get("rawHeld") == selector.get("heldKeys")
                 and selector.get("simulatedKeys") == 0
                 and selector.get("heldKeys") in ((0, expected)
                     if sample is windows[name][0] else (expected,)),
                 "normal held-key window differs")
    left, combo = windows["run-left"], windows["new-up-while-left-held"]
    _require(combo[0]["selector"].get("rawHeld") == 96
             and combo[0]["selector"].get("heldKeys") == 96
             and combo[0]["selector"].get("rawNew") == 64
             and combo[0]["selector"].get("newKeys") == 64
             and all(sample["selector"].get("rawNew") == 0
                     and sample["selector"].get("newKeys") == 0
                     for sample in combo[1:]),
             "fresh Up edge while Left stays held is missing")
    run_end = _actor(left[-1])
    _require(run_end["motionKind"] == "WALK"
             and run_end["motionPhase"] in ("MOVING", "COMMIT_PENDING")
             and run_end["origin"] == {"x": 589, "y": 402}
             and run_end["target"] == {"x": RUN_END_X, "y": 402}
             and 0 < run_end["motionElapsed"] <= run_end["motionDuration"]
             and (run_end["motionPhase"] == "COMMIT_PENDING")
                 == (run_end["motionElapsed"] == run_end["motionDuration"])
             and run_end["movementPolicy"]["direction"] == 2
             and 0 < run_end["movementPolicy"]["speed"] <= 4,
             "Left run-up did not leave the measured Walk at the turn boundary")
    skid_origin_x = run_end["target"]["x"]
    native = _native(events, handle["value"])
    _require(not any(event["data"].get("event") == "MOTION_CANCELED"
                     for event in native), "a due or active skid was canceled")
    skid = [(sample, _actor(sample)) for sample in combo
            if _actor(sample)["motionKind"] == "SKID"]
    groups = _groups(skid)
    _require(len(groups) == 2, "two West skid tiles are missing")
    due = [(row, request, response) for row, request, response in
           _receipt(events, handle["value"], 1)
           if row["frame"] >= combo[0]["frame"]
           and request[10] == 0 and response[10] == 0
           and response[11] == 2 and response[16] == 2
           and response[17] == 2 and response[18] == 0
           and response[20] & 2]
    _require(len(due) == 1,
             "native newest Up request did not propose two West skid tiles")
    admissions = [(row, response) for row, request, response in
                  _receipt(events, handle["value"], 2)
                  if row["frame"] >= due[0][0]["frame"] and request[20] & 2]
    _require(len(admissions) == 2
             and all(response[15] == 1 for _, response in admissions),
             "both skid tiles lack accepted native START_RESULT")
    first_start = groups[0][0][0]["frame"]
    old_commit = _event(native, "LOGICAL_COMMIT",
                        run_end["commitSequence"] + 1, 1,
                        combo[0]["frame"], first_start)
    old_finish = _event(native, "MOTION_FINISHED",
                        run_end["commitSequence"] + 1, 1,
                        old_commit["frame"], first_start)
    old_return = _event(native, "CONTROL_RETURNED", 1,
                        run_end["commitSequence"] + 1,
                        old_finish["frame"], first_start)
    _require(old_commit["data"]["sequence"] < old_finish["data"]["sequence"]
             < old_return["data"]["sequence"]
             and old_return["data"]["sequence"]
                 < _event(native, "MOTION_STARTED", 4,
                          groups[0][0][1]["motionDuration"], first_start,
                          first_start)["data"]["sequence"],
             "old Left Walk did not finish before the skid started")
    first_skid_start = _event(native, "MOTION_STARTED", 4,
                              groups[0][0][1]["motionDuration"], first_start,
                              first_start)
    _require(not any(event["data"].get("event") == "MOTION_STARTED"
                     and event["data"].get("valueA") == 1
                     and old_return["data"]["sequence"]
                         < event["data"].get("sequence", -1)
                         < first_skid_start["data"]["sequence"]
                     for event in native),
             "older Left key started an ordinary Walk before the skid")
    _require(due[0][0]["frame"] >= old_commit["frame"]
             and due[0][0]["frame"] <= first_start,
             "new Up request did not reach the old Walk terminal boundary")
    last_return = old_return
    for tile, group in enumerate(groups):
        origin = {"x": skid_origin_x - tile, "y": 402}
        target = {"x": skid_origin_x - tile - 1, "y": 402}
        duration = group[0][1]["motionDuration"]
        _require(duration > 0 and len(group) == duration
                 and [actor["motionElapsed"] for _, actor in group]
                     == list(range(1, duration + 1))
                 and [sample["frame"] for sample, _ in group]
                     == list(range(group[0][0]["frame"],
                                   group[0][0]["frame"] + duration)),
                 "skid tile frames do not match their displayed duration")
        for sample, actor in group:
            player, mount = sample["player"], actor["engineObject"]
            _require(actor["origin"] == origin and actor["target"] == target
                     and actor["motionDuration"] == duration
                     and player["facing"] == mount["facing"] == 0
                     and player["face_z"] > mount["face_z"],
                     "Up-facing rider and mount did not travel West together")
        start_frame = group[0][0]["frame"]
        finish_low = group[-1][0]["frame"] + 1
        finish_high = (groups[tile + 1][0][0]["frame"] if tile == 0
                       else combo[-1]["frame"])
        commit = group[0][1]["commitSequence"] + 1
        start = _event(native, "MOTION_STARTED", 4, duration,
                       start_frame, start_frame)
        committed = _event(native, "LOGICAL_COMMIT", commit, 4,
                           finish_low, finish_high)
        finished = _event(native, "MOTION_FINISHED", commit, 4,
                          committed["frame"], committed["frame"])
        returned = _event(native, "CONTROL_RETURNED", 1, commit,
                          finished["frame"], finished["frame"])
        _require(last_return["data"]["sequence"]
                 < start["data"]["sequence"]
                 < committed["data"]["sequence"]
                 < finished["data"]["sequence"]
                 < returned["data"]["sequence"],
                 "skid commit, finish and control order differs")
        last_return = returned
    _require(sum(event["data"].get("event") == "MOTION_STARTED"
                 and event["data"].get("valueA") == 4
                 and event["frame"] >= combo[0]["frame"]
                 for event in native) == 2,
             "extra skid motion started")
    up = [(sample, _actor(sample)) for sample in combo
          if _actor(sample)["motionKind"] == "WALK"
          and _actor(sample)["origin"] == {"x": skid_origin_x - 2, "y": 402}
          and _actor(sample)["target"] == {"x": skid_origin_x - 2, "y": 401}]
    _require(up and up[0][0]["frame"] > groups[-1][-1][0]["frame"]
             and up[0][1]["motionElapsed"] == 1
             and up[0][0]["player"]["facing"] == 0,
             "Up Walk from the last skid tile is missing")
    up_start = _event(native, "MOTION_STARTED", 1,
                      up[0][1]["motionDuration"], up[0][0]["frame"],
                      up[0][0]["frame"])
    _require(up_start["data"]["sequence"] > last_return["data"]["sequence"],
             "Up Walk started before skid control returned")
    _require(not any(actor["motionKind"] == "WALK"
                     and actor["origin"]["x"] <= skid_origin_x
                     and actor["target"]["x"] < actor["origin"]["x"]
                     for sample, actor in ((sample, _actor(sample))
                                           for sample in combo)
                     if sample["frame"] >= old_finish["frame"]),
             "older Left key started an extra ordinary West Walk")
    return {"values": dict.fromkeys(NAMES, 1), "actorHandle": handle,
            "subjectIdentity": identity,
            "skidFrames": [[sample["frame"] for sample, _ in group]
                           for group in groups],
            "firstUpWalkFrame": up[0][0]["frame"]}


def _fault(windows, events, name):
    _require(name in FAULTS, "unknown copied-data control")
    combo = windows["new-up-while-left-held"]
    handle = _actor(combo[0])["handle"]["value"]
    if name == "missing-new-edge":
        combo[0]["selector"]["rawNew"] = 0
        combo[0]["selector"]["newKeys"] = 0
    elif name == "older-direction-wins":
        due = next((row for row, request, response in _receipt(events, handle, 1)
                    if row["frame"] >= combo[0]["frame"]
                    and request[10] == 0 and response[20] & 2), None)
        _require(due is not None, "copied control lacks exact Up skid receipt")
        request = bytearray.fromhex(due["data"]["requestHex"])
        request[10] = 2
        due["data"]["requestHex"] = request.hex()
    elif name == "skid-cancel":
        started = next((row for row in _native(events, handle)
                        if row["data"].get("event") == "MOTION_STARTED"
                        and row["data"].get("valueA") == 4), None)
        _require(started is not None, "copied control lacks skid start")
        started["data"]["event"] = "MOTION_CANCELED"
    elif name == "missing-commit":
        committed = next((row for row in _native(events, handle)
                          if row["data"].get("event") == "LOGICAL_COMMIT"
                          and row["data"].get("valueB") == 4), None)
        _require(committed is not None, "copied control lacks skid commit")
        committed["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    elif name == "up-missing":
        skid = [(sample, _actor(sample)) for sample in combo
                if _actor(sample)["motionKind"] == "SKID"]
        _require(skid, "copied control lacks skid")
        last_skid_target = skid[-1][1]["target"]
        up = next((sample for sample in combo
                   if _actor(sample)["motionKind"] == "WALK"
                   and _actor(sample)["origin"] == last_skid_target
                   and _actor(sample)["target"] ==
                       {"x": last_skid_target["x"], "y": 401}), None)
        _require(up is not None, "copied control lacks Up Walk")
        _actor(up)["motionKind"] = "NONE"
    else:
        _actor(combo[0])["subjectIdentity"] ^= 1
    return True


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-newest-held-direction"
                     and [(action.get("id"), action.get("op"), action.get("args"))
                          for action in test.get("actions", [])]
                     == [("run-left", "step", {"frames": MAX_RUN_FRAMES,
                         "keys": ["LEFT"], "until": run_until()}),
                         ("new-up-while-left-held", "step",
                          {"frames": 24, "keys": ["LEFT", "UP"]})],
                     "reviewed fifth-Walk normal-input route differs")
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
