"""Pure completed-frame check for a fresh Right press at a mounted Walk edge."""

from copy import deepcopy


KIND = "mounted-stantler-key-edge-v1"
REQUIREMENT = "current.mounted-stantler-key-edge"
CLAIMS = ("natural-input", "live-actor-identity", "logical-commit", "frame-pacing")
FAULTS = ("old-idle-reset", "reset-speed", "missing-key-edge", "missing-start",
          "wrong-actor")
ACTIONS = ("reach-speed-seven", "neutral-through-tile-end", "fresh-right-edge")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("fresh-right-after-neutral-tile")],
        "live-actor-identity": [exact("same-current-mounted-stantler")],
        "logical-commit": [exact("one-terminal-before-next-start")],
        "frame-pacing": [exact("fresh-edge-starts-without-idle"),
                         exact("fresh-edge-keeps-sprint-speed")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler key edge: " + reason)


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
             "Stantler identity or mounted ownership differs")
    return actor


def _stream(rows):
    windows = {action: [] for action in ACTIONS}
    events = []
    observed = []
    action_order = []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        action = row.get("action")
        _require(action in windows,
                 "unexpected observation action")
        if not action_order or action != action_order[-1]:
            _require(not windows[action]
                     and len(action_order) < len(ACTIONS)
                     and action == ACTIONS[len(action_order)],
                     "observation actions are missing or reordered")
            action_order.append(action)
        samples = deepcopy(row["samples"])
        _require(samples and row.get("completedGameFrames") == len(samples),
                 "observation chunk has wrong completed-frame count")
        windows[action].extend(samples)
        observed.extend(samples)
        events.extend(deepcopy(row.get("events", [])))
    _require(action_order == list(ACTIONS) and all(windows.values())
             and len(windows["fresh-right-edge"]) == 2,
             "reviewed key-edge actions are incomplete")
    _require([sample["frame"] for sample in observed] == list(range(
        observed[0]["frame"], observed[-1]["frame"] + 1)),
        "completed game frames have a gap or reordered action")
    _require(all(event.get("frame") in {sample["frame"] for sample in observed}
                 for event in events), "native event lacks a measured frame")
    return windows, events, observed


def _fault(windows, events, name):
    edge = windows["fresh-right-edge"][0]
    if edge["selector"].get("newKeys") != 16:
        edge = windows["fresh-right-edge"][1]
    actor = _actor(edge)
    if name == "old-idle-reset":
        actor["motionKind"] = "NONE"
        actor["motionPhase"] = "IDLE"
        actor["motionElapsed"] = 8
        actor["movementPolicy"]["speed"] = 0
        next_sample = windows["fresh-right-edge"][-1]
        if next_sample is not edge:
            next_actor = _actor(next_sample)
            next_actor["motionPhase"] = "MOVING"
            next_actor["motionKind"] = "WALK"
            next_actor["motionElapsed"] = 1
            next_actor["movementPolicy"]["speed"] = 8
    elif name == "reset-speed":
        actor["movementPolicy"]["speed"] = 8
    elif name == "missing-key-edge":
        edge["selector"]["newKeys"] = 0
        edge["selector"]["rawNew"] = 0
    elif name == "missing-start":
        start = next((event for event in events
                      if event.get("frame") == edge["frame"]
                      and event.get("data", {}).get("event") == "MOTION_STARTED"), None)
        _require(start is not None, "copied control lacks a native Walk start")
        start["data"]["event"] = "REMOVED_MOTION_STARTED"
    elif name == "wrong-actor":
        actor["subjectIdentity"] ^= 1
    else:
        raise ValueError("unknown Stantler key-edge control: " + name)
    return True


def _measure(windows, events, observed):
    reach = windows["reach-speed-seven"]
    neutral = windows["neutral-through-tile-end"]
    fresh = windows["fresh-right-edge"]
    context = observed[0].get("context")
    first = _actor(observed[0])
    handle, identity = first["handle"], first["subjectIdentity"]
    _require(isinstance(context, dict) and context.get("mapId") == 33
             and first.get("logical") == {"x": 585, "y": 402},
             "prepared clear-lane start differs")
    for sample in observed:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor.get("handle") == handle
                 and actor.get("subjectIdentity") == identity,
                 "frame or mounted Stantler identity changed")
    _require(any(_actor(sample).get("motionKind") == "WALK"
                 and _actor(sample).get("motionElapsed") == 1
                 and _actor(sample).get("movementPolicy", {}).get("speed") == 8
                 for sample in reach), "first natural Sprint Walk is missing")
    second = _actor(reach[-1])
    _require(second.get("motionKind") == "WALK"
             and second.get("motionPhase") == "MOVING"
             and second.get("motionElapsed") == 1
             and second.get("movementPolicy", {}).get("speed") == 7,
             "Right did not stop at the second Walk start at speed seven")
    _require(all(sample["selector"].get("heldKeys") == 16
                 for sample in reach[1:]), "Right was not held through acceleration")
    _require(len(neutral) >= 2 and all(_actor(sample).get("motionKind") == "WALK"
                 and _actor(sample).get("motionPhase") in ("MOVING", "COMMIT_PENDING")
                 for sample in neutral), "neutral input interrupted the second Walk")
    _require(all(sample["selector"].get("heldKeys") == 0
                 and sample["selector"].get("newKeys") == 0
                 for sample in neutral[1:]), "Right was not released during the second Walk")
    terminal = neutral[-1]
    prior = _actor(terminal)
    _require(prior.get("motionPhase") == "COMMIT_PENDING"
             and prior.get("motionKind") == "WALK"
             and prior.get("motionElapsed") == prior.get("motionDuration")
             and prior.get("movementPolicy", {}).get("speed") == 7
             and prior.get("target", {}).get("x") == prior.get("origin", {}).get("x", 0) + 1
             and prior.get("target", {}).get("y") == prior.get("origin", {}).get("y"),
             "neutral tile did not reach the exact Right terminal boundary")
    _require(fresh[0]["frame"] == terminal["frame"] + 1,
             "fresh Right was delayed after the terminal Walk sample")
    edge_indices = [i for i, sample in enumerate(fresh)
                    if sample["selector"].get("newKeys") == 16
                    and sample["selector"].get("rawNew") == 16]
    _require(len(edge_indices) == 1 and edge_indices[0] in (0, 1),
             "fresh Right native key edge is missing or repeated")
    edge_index = edge_indices[0]
    if edge_index == 1:
        stale = fresh[0]["selector"]
        _require(stale.get("heldKeys") == 0 and stale.get("newKeys") == 0
                 and stale.get("rawHeld") == 0 and stale.get("rawNew") == 0,
                 "only the first queue may contain a stale pre-press key sample")
    edge = fresh[edge_index]
    _require(edge["selector"].get("heldKeys") == 16
             and edge["selector"].get("rawHeld") == 16,
             "fresh Right press is not the current held input")
    for sample in fresh[edge_index + 1:]:
        _require(sample["selector"].get("heldKeys") == 16
                 and sample["selector"].get("newKeys") == 0,
                 "Right was not held after the one fresh edge")
    started = _actor(edge)
    _require(started.get("motionPhase") == "MOVING"
             and started.get("motionKind") == "WALK"
             and started.get("motionElapsed") == 1
             and started.get("origin") == prior.get("target")
             and started.get("target", {}).get("x") == prior["target"]["x"] + 1
             and started.get("target", {}).get("y") == prior["target"]["y"],
             "fresh Right had an idle frame instead of the next Walk start")
    _require(started.get("movementPolicy", {}).get("speed") == 6
             and started.get("movementPolicy", {}).get("base") == 8
             and started.get("movementPolicy", {}).get("direction") == 3,
             "fresh Right reset Sprint speed instead of advancing seven to six")
    for sample in fresh[edge_index + 1:]:
        following = _actor(sample)
        _require(following.get("motionKind") == "WALK"
                 and following.get("motionPhase") == "MOVING"
                 and following.get("motionElapsed") == 2
                 and following.get("origin") == started.get("origin")
                 and following.get("target") == started.get("target")
                 and following.get("movementPolicy", {}).get("speed") == 6,
                 "fresh Right started an extra or reset Walk")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    terminal_names = ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
    for name in terminal_names:
        matching = [event for event in native
                    if terminal["frame"] <= event["frame"] <= edge["frame"]
                    and event["data"].get("event") == name
                    and event["data"].get("reason") == "OK"]
        _require(len(matching) == 1, "previous Walk lacks one native " + name)
    starts = [event for event in native if event["frame"] == edge["frame"]
              and event["data"].get("event") == "MOTION_STARTED"
              and event["data"].get("reason") == "OK"
              and event["data"].get("valueA") == 1]
    _require(len(starts) == 1, "fresh Right lacks its native Walk start")
    _require(sum(event["data"].get("event") == "MOTION_STARTED"
                 for event in native if event["frame"] in {sample["frame"] for sample in fresh}) == 1,
             "fresh Right has more than one native Walk start")
    _require(not any(event["data"].get("event") == "MOTION_CANCELED"
                     for event in native if terminal["frame"] <= event["frame"] <= edge["frame"]),
             "key-edge handoff canceled a motion")
    return {"values": {"fresh-right-after-neutral-tile": 1,
                       "same-current-mounted-stantler": 1,
                       "one-terminal-before-next-start": 1,
                       "fresh-edge-starts-without-idle": 1,
                       "fresh-edge-keeps-sprint-speed": 1},
            "subjectIdentity": identity, "actorHandle": handle,
            "terminalFrame": terminal["frame"], "rightEdgeFrame": edge["frame"],
            "edgeDelayCompletedFrames": edge["frame"] - terminal["frame"]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-key-edge"
                     and [action["id"] for action in test.get("actions", [])] == list(ACTIONS),
                     "reviewed key-edge recipe differs")
        windows, events, observed = _stream(rows)
        applied = _fault(windows, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(windows, events, observed)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied, "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
