"""Completed-frame proof that mounted Sprint reaches the last open wall tile.

The copied save supplies the reviewed wall fixture. The controller authenticates
the native reader, ROM, save, recipe and disposable session before this checker.
"""

from copy import deepcopy


KIND = "mounted-stantler-wall-approach-v1"
REQUIREMENT = "current.mounted-stantler-wall-approach"
CLAIMS = ("natural-input", "live-actor-identity", "collision-decision",
          "logical-commit", "control-release")
ACTIONS = ("hold-right-to-wall", "turn-up-from-wall",
           "release-through-up-commit")
FAULTS = ("early-stop", "wall-entry", "wrong-clear-target", "missing-commit",
          "missing-turn", "wrong-actor", "missing-start")
START = {"x": 585, "y": 406}
WALL_EDGE = {"x": 589, "y": 406}
UP_LANDING = {"x": 589, "y": 405}


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("held-right-through-wall-approach")],
        "live-actor-identity": [exact("same-current-mounted-stantler")],
        "collision-decision": [exact("last-open-tile-not-wall")],
        "logical-commit": [exact("four-cardinal-approach-walks")],
        "control-release": [exact("up-turn-leaves-wall")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler wall approach: " + reason)


def _actor(sample):
    actors = [actor for actor in sample.get("actors", [])
              if isinstance(actor, dict) and actor.get("active") is True
              and actor.get("role") == "MOUNTED" and actor.get("species") == 234]
    _require(len(actors) == 1, "expected one live mounted Stantler")
    actor = actors[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1
             and actor.get("handle", {}).get("slot") == 7
             and actor.get("handle", {}).get("encounterGeneration", 0) > 0,
             "Stantler identity, presentation or mounted ownership differs")
    return actor


def _stream(rows):
    windows = {action: [] for action in ACTIONS}
    events, order = [], []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        action = row.get("action")
        _require(action in windows, "unexpected observation action")
        if not order or action != order[-1]:
            _require(len(order) < len(ACTIONS) and action == ACTIONS[len(order)]
                     and not windows[action],
                     "observation actions are missing or reordered")
            order.append(action)
        samples = deepcopy(row["samples"])
        _require(samples and row.get("completedGameFrames") == len(samples),
                 "observation chunk has wrong completed-frame count")
        windows[action].extend(samples)
        events.extend(deepcopy(row.get("events", [])))
    _require(order == list(ACTIONS) and all(windows.values()),
             "reviewed wall-approach actions are incomplete")
    frames = [sample for action in ACTIONS for sample in windows[action]]
    _require(len(windows[ACTIONS[0]]) == 120
             and len(windows[ACTIONS[1]]) <= 64
             and len(windows[ACTIONS[2]]) <= 16,
             "wall approach did not retain the exact Right120 and bounded Up/release input")
    _require(all(right["frame"] == left["frame"] + 1
                 and right.get("nativeCycle", 0) >= left.get("nativeCycle", 0)
                 for left, right in zip(frames, frames[1:])),
             "completed game frame is missing or clock reversed")
    observed = {sample["frame"] for sample in frames}
    _require(all(event.get("frame") in observed for event in events),
             "native event lacks its completed game frame")
    return windows, events, frames


def _walk_starts(samples, origin, target):
    return [sample for sample in samples
            if _actor(sample).get("motionKind") == "WALK"
            and _actor(sample).get("motionPhase") == "MOVING"
            and _actor(sample).get("motionElapsed") == 1
            and _actor(sample).get("origin") == origin
            and _actor(sample).get("target") == target]


def _fault(windows, events, name):
    right, up, release = (windows[action] for action in ACTIONS)
    if name == "early-stop":
        _actor(right[-1])["logical"]["x"] = 588
        right[-1]["player"]["x"] = 588
    elif name == "wall-entry":
        right[-1]["player"]["x"] = 590
    elif name == "wrong-clear-target":
        start = _walk_starts(right, {"x": 588, "y": 406}, WALL_EDGE)
        _require(len(start) == 1, "copied control lacks final clear Walk")
        _actor(start[0])["target"]["x"] = 590
    elif name == "missing-commit":
        walk = _walk_starts(right, {"x": 588, "y": 406}, WALL_EDGE)
        _require(len(walk) == 1, "copied control lacks final clear Walk")
        event = next((event for event in events
                      if event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                      and event["frame"] > walk[0]["frame"]), None)
        _require(event is not None, "copied control lacks final clear commit")
        event["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    elif name == "missing-turn":
        _actor(release[-1])["logical"]["y"] = 406
        release[-1]["player"]["y"] = 406
    elif name == "wrong-actor":
        _actor(up[0])["subjectIdentity"] ^= 1
    elif name == "missing-start":
        walk = _walk_starts(right, {"x": 588, "y": 406}, WALL_EDGE)
        _require(len(walk) == 1, "copied control lacks final clear Walk")
        event = next((event for event in events
                      if event.get("frame") == walk[0]["frame"]
                      and event.get("data", {}).get("event") == "MOTION_STARTED"
                      and event["data"].get("valueA") == 1), None)
        _require(event is not None, "copied control lacks final clear start")
        event["data"]["event"] = "REMOVED_MOTION_STARTED"
    else:
        raise ValueError("unknown Stantler wall-approach control: " + name)
    return True


def _measure(windows, events, frames):
    right, up, release = (windows[action] for action in ACTIONS)
    first = _actor(frames[0])
    handle, identity = first["handle"], first["subjectIdentity"]
    context = frames[0].get("context")
    _require(isinstance(context, dict) and context.get("mapId") == 33
             and first.get("logical") == START
             and frames[0].get("player", {}).get("x") == START["x"]
             and frames[0].get("player", {}).get("y") == START["y"],
             "copied-save wall-lane start differs")
    for sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor.get("handle") == handle
                 and actor.get("subjectIdentity") == identity,
                 "frame is stale or mounted Stantler changed")
        _require(actor.get("logical", {}).get("x", 590) <= 589
                 and sample.get("player", {}).get("x", 590) <= 589
                 and not (actor.get("motionPhase") in ("MOVING", "COMMIT_PENDING")
                          and actor.get("target", {}).get("x", 590) > 589),
                 "mounted actor entered or targeted the blocked wall")
        _require(actor.get("motionKind") != "HOP"
                 or actor.get("motionPhase") == "IDLE",
                 "solid wall started an unsafe Hop")
    for samples, key in ((right, 16), (up, 64), (release, 0)):
        for index, sample in enumerate(samples):
            allowed = ((0, 64) if samples is release and index == 0
                       else (0, key) if index == 0 else (key,))
            _require(sample.get("selector", {}).get("rawHeld") in allowed
                     and sample.get("selector", {}).get("heldKeys") in allowed,
                     "normal Right/Up input differs")

    _require(all(_actor(sample).get("logical", {}).get("y") == 406
                 and sample.get("player", {}).get("y") == 406
                 for sample in right),
             "Right approach left the reviewed east lane")
    _require(_actor(right[-1]).get("logical") == WALL_EDGE
             and right[-1].get("player", {}).get("x") == 589
             and right[-1].get("player", {}).get("y") == 406
             and _actor(right[-1]).get("motionPhase") == "IDLE",
             "Sprint stopped before the last open wall tile or did not settle")

    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    starts = []
    for x in range(585, 589):
        candidates = _walk_starts(right, {"x": x, "y": 406},
                                  {"x": x + 1, "y": 406})
        _require(len(candidates) == 1,
                 "one cardinal approach Walk is missing or duplicated")
        starts.append(candidates[0])
    _require(all(left["frame"] < next_["frame"]
                 for left, next_ in zip(starts, starts[1:])),
             "cardinal approach Walk order differs")
    up_starts = _walk_starts(up, WALL_EDGE, UP_LANDING)
    _require(len(up_starts) == 1,
             "safe Up Walk did not start from the last open wall tile")
    starts.append(up_starts[0])
    for index, sample in enumerate(starts):
        actor = _actor(sample)
        _require(actor.get("motionDuration", 0) >= 1
                 and sum(event["frame"] == sample["frame"]
                         and event["data"].get("event") == "MOTION_STARTED"
                         and event["data"].get("reason") == "OK"
                         and (event["data"].get("valueA"),
                              event["data"].get("valueB"))
                         == (1, actor["motionDuration"])
                         for event in native) == 1,
                 "cardinal approach or Up native Walk start is missing")
        end = (starts[index + 1]["frame"] if index + 1 < len(starts)
               else release[-1]["frame"])
        for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            _require(sum(sample["frame"] < event["frame"] <= end
                         and event["data"].get("event") == name
                         and event["data"].get("reason") == "OK"
                         and (event["data"].get("valueB") == 1
                              if name != "CONTROL_RETURNED"
                              else event["data"].get("valueA") == 1)
                         for event in native) == 1,
                     "cardinal approach or Up Walk did not commit and return control")
    _require(not any(event["data"].get("event") in
                     ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND",
                      "CONTROL_REBOUND") for event in native),
             "wall approach canceled or changed actor context")
    _require(_actor(up[-1]).get("logical") == UP_LANDING
             and up[-1].get("player", {}).get("x") == 589
             and up[-1].get("player", {}).get("y") == 405
             and _actor(up[-1]).get("motionPhase") == "COMMIT_PENDING"
             and _actor(release[-1]).get("logical") == UP_LANDING
             and release[-1].get("player", {}).get("x") == 589
             and release[-1].get("player", {}).get("y") == 405
             and _actor(release[-1]).get("motionPhase") == "IDLE",
             "mounted actor did not settle on the safe Up tile")
    return {"values": {"held-right-through-wall-approach": 1,
                       "same-current-mounted-stantler": 1,
                       "last-open-tile-not-wall": 1,
                       "four-cardinal-approach-walks": 1,
                       "up-turn-leaves-wall": 1},
            "subjectIdentity": identity, "actorHandle": handle,
            "approachWalkStartFrames": [sample["frame"] for sample in starts[:4]],
            "upWalkStartFrame": starts[-1]["frame"]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-sprint-wall-approach"
                     and [action["id"] for action in test.get("actions", [])]
                     == list(ACTIONS), "reviewed wall-approach recipe differs")
        windows, events, frames = _stream(rows)
        applied = _fault(windows, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(windows, events, frames)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied,
                "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
