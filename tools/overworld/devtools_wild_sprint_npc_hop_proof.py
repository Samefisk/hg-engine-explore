"""Exact Wild Sprint NPC-Hop proof from an idle adjacent tile."""

from copy import deepcopy

from tools.overworld.normal_play_observer import MotionRecorder, complete_travel


KIND = "wild-sprint-npc-hop-v1"
REQUIREMENT = "current.wild-sprint-npc-hop"
CLAIMS = ("controlled-action", "live-actor-identity", "profile-resolution",
          "collision-decision", "logical-commit", "rendered-motion",
          "control-release")
ACTIONS = ("direct-east-at-npc", "hop-over-npc", "close-direction-control")
FAULTS = ("wrong-terrain", "wrong-actor", "wrong-direction", "wrong-start",
          "short-hop", "missing-hop-commit")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "controlled-action": [exact("east-only-register-control")],
        "live-actor-identity": [exact("same-current-wild-stantler")],
        "profile-resolution": [exact("native-sprint-lane")],
        "collision-decision": [exact("open-takeoff-open-midpoint-safe-landing")],
        "logical-commit": [exact("one-two-tile-hop")],
        "rendered-motion": [exact("hop-rendered")],
        "control-release": [exact("hop-finished")],
    }


def _need(value, reason):
    if not value:
        raise ValueError("Wild Sprint NPC Hop: " + reason)


def _actor(sample, handle=None):
    actors = [actor for actor in sample.get("actors", [])
              if actor.get("active") is True and actor.get("role") == "WILD"
              and actor.get("species") == 234]
    _need(len(actors) == 1, "requires one current Wild Stantler")
    actor = actors[0]
    sprint_lane = (actor.get("behaviorFingerprint") == 1900232342
                   and actor.get("matchedLayerMask") == 1026)
    terminal_condition_layer = (actor.get("motionKind") == "NONE"
                                and actor.get("motionPhase") == "IDLE"
                                and actor.get("commitSequence") == 1
                                and isinstance(actor.get("matchedLayerMask"), int)
                                and actor["matchedLayerMask"] & 1026 == 1026)
    _need(actor.get("identityVerified") is True
          and actor.get("presentationAttached") is True
          and actor.get("inputOwnership") == 0
          and (sprint_lane or terminal_condition_layer)
          and (handle is None or actor.get("handle") == handle),
          "actor identity or resolved Sprint profile differs")
    return actor


def _stream(rows):
    commands = {}
    frames, events = [], []
    for row in rows:
        if row.get("phase") != "observe":
            continue
        action = row.get("action")
        if "command" in row:
            _need(action in (ACTIONS[0], ACTIONS[2]) and action not in commands,
                  "direction-control action is missing or duplicated")
            commands[action] = deepcopy(row)
        elif action == ACTIONS[1] and "samples" in row:
            samples = deepcopy(row["samples"])
            _need(samples and len(samples) == row.get("completedGameFrames"),
                  "completed-frame chunk differs")
            frames.extend(samples)
            events.extend(deepcopy(row.get("events", [])))
    _need(set(commands) == {ACTIONS[0], ACTIONS[2]} and len(frames) >= 16,
          "bounded direction-control window is incomplete")
    _need(all(right["frame"] == left["frame"] + 1
              and right.get("nativeCycle", 0) >= left.get("nativeCycle", 0)
              for left, right in zip(frames, frames[1:])),
          "completed game frame is missing or reordered")
    observed = {sample["frame"] for sample in frames}
    _need(all(event.get("frame") in observed for event in events),
          "native event has no completed game frame")
    return commands, frames, events


def _fault(commands, frames, events, name):
    arm = commands[ACTIONS[0]]
    calls = commands[ACTIONS[2]]["receipt"]["obstacleIntent"]["calls"]
    if name == "wrong-terrain":
        cell = next(cell for cell in arm["snapshot"]["terrain"]["cells"]
                    if (cell["x"], cell["z"]) == (600, 395))
        cell["collision"] = True
    elif name == "wrong-actor":
        _actor(frames[0])["subjectIdentity"] ^= 1
    elif name == "wrong-direction":
        calls[0]["registersAfter"]["r1"] = 1
    elif name == "wrong-start":
        _actor(commands[ACTIONS[0]]["snapshot"])["logical"]["x"] = 598
    elif name == "short-hop":
        hop = next(actor for sample in frames
                   if (actor := _actor(sample))["motionKind"] == "HOP")
        hop["target"]["x"] = 600
    elif name == "missing-hop-commit":
        commit = next(event for event in events
                      if event.get("kind") == "native"
                      and event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                      and event["data"].get("valueB") == 2)
        commit["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    else:
        raise ValueError("unknown NPC-Hop copied control")
    return True


def _measure(commands, frames, events):
    arm = commands[ACTIONS[0]]["receipt"]
    close = commands[ACTIONS[2]]["receipt"]
    initial = commands[ACTIONS[0]].get("snapshot", {})
    _need(arm.get("snapshot", {}).get("frame") == initial.get("frame")
          and arm.get("snapshot", {}).get("context") == initial.get("context"),
          "command and terrain snapshots differ at arm boundary")
    first = _actor(initial)
    handle, identity = first["handle"], first["subjectIdentity"]
    _need(initial.get("context", {}).get("mapId") == 33
          and first.get("logical") == {"x": 599, "y": 395}
          and first.get("commitSequence") == 0
          and first.get("behaviorFingerprint") == 1900232342
          and first.get("matchedLayerMask") == 1026
          and first.get("motionKind") == "NONE"
          and first.get("motionPhase") == "IDLE"
          and initial.get("player", {}).get("x") == 604
          and initial.get("player", {}).get("y") == 395,
          "reviewed Route 29 idle takeoff differs")
    cells = {(cell["x"], cell["z"]): cell
             for cell in initial.get("terrain", {}).get("cells", [])}
    _need(all(cells.get((x, 395), {}).get("loaded") is True
              and cells[(x, 395)].get("collision") is blocked
              for x, blocked in ((599, False), (600, False), (601, False))),
          "takeoff, NPC midpoint or landing terrain differs")
    control = close.get("obstacleIntent", {})
    _need(arm.get("armed") is True and close.get("closed") is True
          and close.get("advancedFrames") == 0
          and control.get("closed") is True and control.get("terminal") is True
          and control.get("stage") == 1 and control.get("failure") is None
          and control.get("initialCommit") == 0
          and control.get("guestMemoryWrites") == 0
          and control.get("subject") == arm["obstacleIntent"]["subject"],
          "direction control did not close at the Hop landing")
    calls = control.get("calls", [])
    accepted = [call for call in calls if call.get("returnValue") == 2]
    _need(len(accepted) == 1 and accepted[0].get("stage") == 0
          and accepted[0].get("expectedKind") == "HOP"
          and accepted[0].get("registersBefore", {}).get("r2") == 1,
          "real idle NPC Hop was not admitted")
    for call in calls:
        _need(call.get("direction") == 3
              and call.get("registersAfter", {}).get("r1") == 3
              and all(call["registersAfter"].get(key) == value
                      for key, value in call["registersBefore"].items() if key != "r1")
              and call.get("guestMemoryWrites") == 0
              and call.get("profileHex") == accepted[0].get("profileHex")
              and call.get("before", {}).get("actor", {}).get("handle") == handle,
              "direction control changed more than the candidate register")
    _need(accepted[0]["after"]["actor"].get("motionKind") == "HOP"
          and accepted[0]["after"]["actor"].get("motionPhase") == "MOVING",
          "native caller did not start a Hop")
    context = initial["context"]
    recorder = MotionRecorder()
    for sample in frames:
        actor = _actor(sample, handle)
        _need(sample.get("observationBoundary") == "main-task-queue-completion"
              and sample.get("context") == context
              and actor.get("subjectIdentity") == identity
              and sample.get("selector", {}).get("rawHeld") == 0
              and sample.get("selector", {}).get("heldKeys") == 0,
              "observation lost actor, context or neutral input")
        recorder.observe(sample["frame"], actor, actor["engineObject"])
        _need(not recorder.failures, "rendered Hop has a frame or pose gap")
    moving = [(sample, _actor(sample)) for sample in frames
              if _actor(sample).get("motionPhase") == "MOVING"]
    hop = next(((sample, actor) for sample, actor in moving
                if actor.get("motionKind") == "HOP"), None)
    _need(hop is not None
          and hop[1].get("origin") == {"x": 599, "y": 395}
          and hop[1].get("target") == {"x": 601, "y": 395}
          and _actor(frames[-1]).get("logical") == {"x": 601, "y": 395}
          and _actor(frames[-1]).get("commitSequence") == 1,
          "two-tile Hop path or terminal commit differs")
    final = _actor(frames[-1])
    profiles = commands[ACTIONS[2]]["snapshot"].get("nativeObservation", {}).get(
        "resolvedProfiles", [])
    _need(any(profile.get("resolved") is True
              and profile.get("fingerprint") == final.get("behaviorFingerprint")
              and profile.get("appliedOverrides") == final.get("matchedLayerMask")
              for profile in profiles),
          "terminal condition layer lacks native resolver evidence")
    _need(len(recorder.completed) == 1
          and recorder.completed[0]["kind"] == "HOP"
          and complete_travel(recorder.completed[0])
          and recorder.completed[0]["origin"] == [599, 395]
          and recorder.completed[0]["target"] == [601, 395],
          "complete rendered Hop path differs")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    starts = [event for event in native
              if event["data"].get("event") == "MOTION_STARTED"
              and event["data"].get("valueA") == 2]
    _need(len(starts) == 1 and starts[0]["frame"] == hop[0]["frame"]
          and starts[0]["data"].get("valueA") == 2
          and starts[0]["data"].get("valueB") == hop[1]["motionDuration"],
          "Hop lacks one native motion start")
    for name in ("LOGICAL_COMMIT", "MOTION_FINISHED"):
        _need(sum(event["data"].get("event") == name
                  and event["data"].get("valueB") == 2
                  for event in native) == 1,
              "Hop lacks one native " + name)
    _need(sum(event["data"].get("event") == "CONTROL_RETURNED"
              for event in native) == 1
          and not any(event["data"].get("event") in
                      ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND")
                      for event in native),
          "Hop control did not return cleanly")
    return {"values": {"east-only-register-control": 1,
                       "same-current-wild-stantler": 1,
                       "native-sprint-lane": 1,
                       "open-takeoff-open-midpoint-safe-landing": 1,
                       "one-two-tile-hop": 1,
                       "hop-rendered": 1,
                       "hop-finished": 1},
            "actorHandle": handle, "subjectIdentity": identity,
            "hopStartFrame": hop[0]["frame"], "landingFrame": frames[-1]["frame"]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _need(test.get("id") == "walk.wild.sprint-npc-hop"
                  and [action["id"] for action in test.get("actions", [])] == list(ACTIONS),
                  "reviewed NPC Hop recipe differs")
        commands, frames, events = _stream(rows)
        applied = _fault(commands, frames, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(commands, frames, events)}
    except (ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        return {"passed": False, "faultApplied": applied, "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
