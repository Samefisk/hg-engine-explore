"""Completed-frame proof of mounted Sprint crossing one static obstacle.

The controller authenticates the recipe, ROM, native reader and session. This
module checks normal input, the same mounted actor and copied-data controls.
"""

from copy import deepcopy


KIND = "mounted-stantler-obstacle-hop-v1"
REQUIREMENT = "current.mounted-stantler-obstacle-hop"
CLAIMS = ("natural-input", "live-actor-identity", "collision-decision",
          "logical-commit", "frame-pacing", "control-release")
ACTIONS = ("right-into-blocked-front", "release-through-hop",
           "walk-after-obstacle")
FAULTS = ("short-landing", "wrong-origin", "wrong-hop-time",
          "missing-commit", "reset-walk-speed", "wrong-actor")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("held-right-across-obstacle")],
        "live-actor-identity": [exact("same-current-mounted-stantler")],
        "collision-decision": [exact("static-front-two-tile-hop")],
        "logical-commit": [exact("one-hop-landing-commit")],
        "frame-pacing": [exact("hop-uses-sprint-speed"),
                         exact("post-hop-accelerates-to-four")],
        "control-release": [exact("hop-returns-to-walk")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler obstacle Hop: " + reason)


def _actor(sample):
    actors = [actor for actor in sample.get("actors", [])
              if actor.get("active") is True and actor.get("role") == "MOUNTED"
              and actor.get("species") == 234]
    _require(len(actors) == 1, "expected one live mounted Stantler")
    actor = actors[0]
    _require(actor.get("identityVerified") is True and
             actor.get("presentationAttached") is True and
             actor.get("inputOwnership") == 1 and
             actor.get("handle", {}).get("slot") == 7 and
             actor.get("handle", {}).get("encounterGeneration", 0) > 0,
             "Stantler identity, presentation or mounted ownership differs")
    return actor


def _stream(rows):
    windows = {action: [] for action in ACTIONS}
    events = []
    order = []
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
             "reviewed obstacle-Hop actions are incomplete")
    frames = [sample for action in ACTIONS for sample in windows[action]]
    _require(all(right["frame"] == left["frame"] + 1 and
                 right.get("nativeCycle", 0) >= left.get("nativeCycle", 0)
                 for left, right in zip(frames, frames[1:])),
             "completed game frame is missing or clock reversed")
    observed = {sample["frame"] for sample in frames}
    _require(all(event.get("frame") in observed for event in events),
             "native event lacks its completed game frame")
    return windows, events, frames


def _fault(windows, events, name):
    hop = _actor(windows[ACTIONS[0]][-1])
    if name == "short-landing":
        hop["target"]["x"] = 581
    elif name == "wrong-origin":
        hop["origin"]["x"] = 579
    elif name == "wrong-hop-time":
        hop["motionDuration"] -= 1
    elif name == "missing-commit":
        event = next((event for event in events
                      if event.get("data", {}).get("event") == "LOGICAL_COMMIT"), None)
        _require(event is not None, "copied control lacks native Hop commit")
        event["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    elif name == "reset-walk-speed":
        last = _actor(windows[ACTIONS[2]][-1])
        _require(last.get("movementPolicy", {}).get("speed") == 4,
                 "copied control lacks speed-four Walk policy")
        last["movementPolicy"]["speed"] = 8
    elif name == "wrong-actor":
        _actor(windows[ACTIONS[1]][0])["subjectIdentity"] ^= 1
    else:
        raise ValueError("unknown Stantler obstacle-Hop control: " + name)
    return True


def _measure(windows, events, frames):
    approach, release, recovery = (windows[action] for action in ACTIONS)
    first = _actor(frames[0])
    handle, identity = first["handle"], first["subjectIdentity"]
    context = frames[0].get("context")
    _require(isinstance(context, dict) and context.get("mapId") == 33
             and first.get("logical") == {"x": 580, "y": 397}
             and frames[0].get("player", {}).get("x") == 580
             and frames[0].get("player", {}).get("y") == 397,
             "prepared blocked-front start differs")
    for sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor.get("handle") == handle
                 and actor.get("subjectIdentity") == identity,
                 "frame is stale or mounted Stantler changed")
    for samples, key in ((approach, 16), (release, 0), (recovery, 16)):
        for index, sample in enumerate(samples):
            allowed = (0, 16) if index == 0 else (key,)
            _require(sample.get("selector", {}).get("rawHeld") in allowed
                     and sample.get("selector", {}).get("heldKeys") in allowed,
                     "normal Right/release input differs")

    hop_sample = approach[-1]
    hop = _actor(hop_sample)
    hop_speed = hop.get("movementPolicy", {}).get("speed")
    _require(hop.get("motionKind") == "HOP"
             and hop.get("motionPhase") == "MOVING"
             and hop.get("motionElapsed") == 1
             and hop.get("origin") == {"x": 580, "y": 397}
             and hop.get("target") == {"x": 582, "y": 397},
             "blocked static front did not start one two-tile forward Hop")
    # The blocked front starts from rest. Walk momentum remains zero until a
    # clear-ground Walk begins, so the two-tile Hop uses the eight-frame
    # starting Walk time without writing that time into momentum.
    _require(hop_speed == 0 and hop.get("motionDuration") == 16,
             "standing obstacle Hop did not use Sprint starting Walk time")
    _require(not any(_actor(sample).get("motionKind") == "WALK"
                     and _actor(sample).get("motionPhase") == "MOVING"
                     for sample in approach),
             "a Walk entered the blocked front before the Hop")
    _require(_actor(release[-1]).get("motionPhase") == "IDLE"
             and _actor(release[-1]).get("logical") == {"x": 582, "y": 397}
             and release[-1].get("player", {}).get("x") == 582
             and release[-1].get("player", {}).get("y") == 397,
             "obstacle Hop did not land and release at the two-tile target")

    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    hop_starts = [event for event in native
                  if event["data"].get("event") == "MOTION_STARTED"
                  and event["data"].get("reason") == "OK"
                  and event["frame"] <= release[-1]["frame"]]
    _require(len(hop_starts) == 1
             and hop_starts[0]["frame"] == hop_sample["frame"]
             and (hop_starts[0]["data"].get("valueA"),
                  hop_starts[0]["data"].get("valueB")) == (2, 16),
             "native obstacle-Hop start is missing or duplicated")
    terminal = [event for event in native
                if hop_sample["frame"] < event["frame"] <= release[-1]["frame"]]
    for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
        _require(sum(event["data"].get("event") == name
                     and event["data"].get("reason") == "OK"
                     and (event["data"].get("valueB") == 2
                          if name != "CONTROL_RETURNED"
                          else event["data"].get("valueA") == 1)
                     for event in terminal) == 1,
                 "native obstacle Hop did not commit, finish and return control")
    _require(not any(event["data"].get("event") == "MOTION_CANCELED"
                     for event in native), "obstacle Hop or recovery was canceled")

    walks = [(sample, _actor(sample)) for sample in recovery
             if _actor(sample).get("motionKind") == "WALK"
             and _actor(sample).get("motionPhase") == "MOVING"
             and _actor(sample).get("motionElapsed") == 1]
    _require(len(walks) >= 4 and walks[0][1].get("origin") == {"x": 582, "y": 397}
             and walks[0][1].get("movementPolicy", {}).get("speed") in (7, 8)
             and _actor(recovery[-1]).get("movementPolicy", {}).get("speed") == 4,
             "normal post-Hop Sprint Walk did not accelerate to speed four")
    speeds = [actor["movementPolicy"]["speed"] for _, actor in walks]
    _require(all(4 <= speed <= 8 for speed in speeds)
             and all(right in (left, left - 1)
                     for left, right in zip(speeds, speeds[1:])),
             "Sprint Walk speed reset after obstacle Hop")
    for _, actor in walks:
        origin, target = actor["origin"], actor["target"]
        speed = actor["movementPolicy"]["speed"]
        _require((target["x"] - origin["x"], target["y"] - origin["y"]) == (1, 0)
                 and speed <= actor["motionDuration"] <= speed + 2,
                 "post-Hop Walk is not one cardinal tile with authored timing")
    _require(not any(_actor(sample).get("motionKind") == "HOP"
                     and _actor(sample).get("motionPhase") == "MOVING"
                     for sample in recovery),
             "a second Hop started on clear recovery terrain")
    for sample, _ in (walks[0], walks[-1]):
        _require(sum(event["frame"] == sample["frame"]
                     and event["data"].get("event") == "MOTION_STARTED"
                     and event["data"].get("reason") == "OK"
                     and event["data"].get("valueA") == 1
                     for event in native) == 1,
                 "normal one-tile Walk did not start after Hop")
    return {"values": {"held-right-across-obstacle": 1,
                       "same-current-mounted-stantler": 1,
                       "static-front-two-tile-hop": 1,
                       "one-hop-landing-commit": 1,
                       "hop-uses-sprint-speed": 1,
                       "post-hop-accelerates-to-four": 1,
                       "hop-returns-to-walk": 1},
            "subjectIdentity": identity, "actorHandle": handle,
            "hopStartFrame": hop_sample["frame"],
            "hopLandingFrame": release[-1]["frame"],
            "recoveryWalkStartFrames": [sample["frame"] for sample, _ in walks]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-sprint-obstacle-hop"
                     and [action["id"] for action in test.get("actions", [])]
                     == list(ACTIONS), "reviewed obstacle-Hop recipe differs")
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
