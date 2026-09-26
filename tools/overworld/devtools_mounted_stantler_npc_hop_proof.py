"""Completed-frame proof of mounted Sprint crossing the Route 29 stock NPC.

The controller authenticates the recipe, ROM, native reader and session. This
checker uses normal input and one bound mounted actor. The stock NPC and clear
terrain at the reviewed map tile are fixture facts, not live reader claims.
"""

from copy import deepcopy


KIND = "mounted-stantler-npc-hop-v1"
REQUIREMENT = "current.mounted-stantler-npc-hop"
CLAIMS = ("natural-input", "live-actor-identity", "collision-decision",
          "logical-commit", "frame-pacing", "control-release")
ACTIONS = ("right-into-npc-front", "release-through-npc-hop")
FAULTS = ("short-landing", "wrong-origin", "wrong-hop-time",
          "missing-commit", "missing-control-return", "duplicate-hop-start",
          "wrong-actor")
START = {"x": 599, "y": 395}
LANDING = {"x": 601, "y": 395}


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("held-right-into-npc")],
        "live-actor-identity": [exact("same-current-mounted-stantler")],
        "collision-decision": [exact("npc-front-two-tile-hop")],
        "logical-commit": [exact("one-npc-hop-landing-commit")],
        "frame-pacing": [exact("npc-hop-uses-sprint-speed")],
        "control-release": [exact("npc-hop-returns-control")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler NPC Hop: " + reason)


def _actor(sample):
    actors = [actor for actor in sample.get("actors", [])
              if isinstance(actor, dict)
              and actor.get("active") is True and actor.get("role") == "MOUNTED"
              and actor.get("species") == 234]
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
             "reviewed NPC-Hop actions are incomplete")
    frames = [sample for action in ACTIONS for sample in windows[action]]
    _require(all(right["frame"] == left["frame"] + 1
                 and right.get("nativeCycle", 0) >= left.get("nativeCycle", 0)
                 for left, right in zip(frames, frames[1:])),
             "completed game frame is missing or clock reversed")
    observed = {sample["frame"] for sample in frames}
    _require(all(event.get("frame") in observed for event in events),
             "native event lacks its completed game frame")
    return windows, events, frames


def _fault(windows, events, name):
    hop = _actor(windows[ACTIONS[0]][-1])
    if name == "short-landing":
        hop["target"]["x"] = 600
    elif name == "wrong-origin":
        hop["origin"]["x"] = 598
    elif name == "wrong-hop-time":
        hop["motionDuration"] -= 1
    elif name == "wrong-actor":
        _actor(windows[ACTIONS[1]][0])["subjectIdentity"] ^= 1
    elif name in ("missing-commit", "missing-control-return"):
        wanted = ("LOGICAL_COMMIT" if name == "missing-commit"
                  else "CONTROL_RETURNED")
        event = next((event for event in events
                      if event.get("data", {}).get("event") == wanted), None)
        _require(event is not None, "copied control lacks native " + wanted)
        event["data"]["event"] = "REMOVED_" + wanted
    elif name == "duplicate-hop-start":
        event = next((event for event in events
                      if event.get("data", {}).get("event") == "MOTION_STARTED"), None)
        _require(event is not None, "copied control lacks native Hop start")
        events.append(deepcopy(event))
    else:
        raise ValueError("unknown Stantler NPC-Hop control: " + name)
    return True


def _measure(windows, events, frames):
    approach, release = (windows[action] for action in ACTIONS)
    first = _actor(frames[0])
    handle, identity = first["handle"], first["subjectIdentity"]
    context = frames[0].get("context")
    _require(isinstance(context, dict) and context.get("mapId") == 33
             and first.get("logical") == START
             and frames[0].get("player", {}).get("x") == START["x"]
             and frames[0].get("player", {}).get("y") == START["y"],
             "prepared NPC-front start differs")
    for sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor.get("handle") == handle
                 and actor.get("subjectIdentity") == identity,
                 "frame is stale or mounted Stantler changed")
    for samples, key in ((approach, 16), (release, 0)):
        for index, sample in enumerate(samples):
            allowed = (0, 16) if index == 0 else (key,)
            _require(sample.get("selector", {}).get("rawHeld") in allowed
                     and sample.get("selector", {}).get("heldKeys") in allowed,
                     "normal Right/release input differs")

    hop_sample = approach[-1]
    hop = _actor(hop_sample)
    _require(hop.get("motionKind") == "HOP"
             and hop.get("motionPhase") == "MOVING"
             and hop.get("motionElapsed") == 1
             and hop.get("origin") == START
             and hop.get("target") == LANDING,
             "NPC front did not start one two-tile forward Hop")
    _require(hop.get("movementPolicy", {}).get("speed") == 0
             and hop.get("motionDuration") == 16,
             "standing NPC Hop did not use Sprint starting Walk time")
    _require(not any(_actor(sample).get("motionKind") == "WALK"
                     and _actor(sample).get("motionPhase") == "MOVING"
                     for sample in frames),
             "a Walk entered the NPC tile")
    _require(all(_actor(sample).get("motionKind") == "HOP"
                 and _actor(sample).get("motionPhase") in ("MOVING", "COMMIT_PENDING")
                 for sample in release[:-1])
             and _actor(release[-1]).get("motionPhase") == "IDLE"
             and _actor(release[-1]).get("logical") == LANDING
             and release[-1].get("player", {}).get("x") == LANDING["x"]
             and release[-1].get("player", {}).get("y") == LANDING["y"],
             "NPC Hop did not land and release at the two-tile target")

    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    starts = [event for event in native
              if event["data"].get("event") == "MOTION_STARTED"]
    _require(len(starts) == 1
             and starts[0]["frame"] == hop_sample["frame"]
             and starts[0]["data"].get("reason") == "OK"
             and (starts[0]["data"].get("valueA"),
                  starts[0]["data"].get("valueB")) == (2, 16),
             "native NPC-Hop start is missing or duplicated")
    terminal_frame = release[-1]["frame"]
    terminal = [event for event in native
                if event["data"].get("event") in
                ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]
    _require(all(hop_sample["frame"] < event["frame"] <= terminal_frame
                 for event in terminal),
             "native NPC-Hop terminal event is outside the release window")
    for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
        _require(sum(event["data"].get("event") == name
                     and event["data"].get("reason") == "OK"
                     and (event["data"].get("valueB") == 2
                          if name != "CONTROL_RETURNED"
                          else event["data"].get("valueA") == 1)
                     for event in terminal) == 1,
                 "native NPC Hop did not commit, finish and return control")
    terminal_events = {name: next(event for event in terminal
                                  if event["data"].get("event") == name)
                       for name in ("LOGICAL_COMMIT", "MOTION_FINISHED",
                                    "CONTROL_RETURNED")}
    _require(terminal_events["LOGICAL_COMMIT"]["frame"]
             <= terminal_events["MOTION_FINISHED"]["frame"]
             <= terminal_events["CONTROL_RETURNED"]["frame"],
             "native NPC-Hop terminal order differs")
    _require(not any(event["data"].get("event") in
                     ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND")
                     for event in native),
             "NPC Hop was canceled or changed actor context")
    return {"values": {"held-right-into-npc": 1,
                       "same-current-mounted-stantler": 1,
                       "npc-front-two-tile-hop": 1,
                       "one-npc-hop-landing-commit": 1,
                       "npc-hop-uses-sprint-speed": 1,
                       "npc-hop-returns-control": 1},
            "subjectIdentity": identity, "actorHandle": handle,
            "hopStartFrame": hop_sample["frame"],
            "hopLandingFrame": terminal_frame,
            "terminalEventFrames": {name: event["frame"]
                                    for name, event in terminal_events.items()}}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-sprint-npc-hop"
                     and [action["id"] for action in test.get("actions", [])]
                     == list(ACTIONS), "reviewed NPC-Hop recipe differs")
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
