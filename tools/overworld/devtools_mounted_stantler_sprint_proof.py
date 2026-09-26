"""Pure completed-frame proof of the prepared mounted Stantler Sprint Walk.

The controller authenticates the recipe, ROM, native reader and session. This
module only checks retained normal-input frames and copied-data controls.
"""

from copy import deepcopy


KIND = "mounted-stantler-sprint-v1"
REQUIREMENT = "current.mounted-stantler-sprint-parity"
CLAIMS = ("natural-input", "live-actor-identity", "logical-commit",
          "frame-pacing", "control-release")
FAULTS = ("remove-walk-start", "slow-walk", "unexpected-hop",
          "reset-after-acceleration", "diagonal-target", "wrong-actor")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("held-right-and-two-direction-input")],
        "live-actor-identity": [exact("same-current-mounted-stantler")],
        "logical-commit": [{"name": "complete-clear-lane-walks", "operator": "gte",
                            "type": "integer", "validator": "meaningful-observation",
                            "expected": 8}],
        "frame-pacing": [exact("accelerates-to-four-speed"),
                         exact("clear-lane-no-hops"),
                         exact("four-speed-walks-continue"),
                         exact("cardinal-only-two-key-window")],
        "control-release": [exact("walks-return-control")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler Sprint: " + reason)


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
    frames, events = [], []
    actions = {"sprint-right", "settle-right", "hold-two-directions"}
    for row in rows:
        samples = row.get("samples")
        if samples is None:
            continue
        _require(row.get("phase") == "observe" and row.get("action") in actions
                 and row.get("completedGameFrames") == len(samples) and samples,
                 "sample chunk differs from a reviewed observation action")
        frames.extend((row["action"], deepcopy(sample)) for sample in samples)
        events.extend(deepcopy(row.get("events", [])))
    _require(frames, "no completed game frames")
    for (_, left), (_, right) in zip(frames, frames[1:]):
        _require(right["frame"] == left["frame"] + 1 and
                 right.get("nativeCycle", 0) >= left.get("nativeCycle", 0),
                 "completed game frame is missing or clock reversed")
    observed = {sample["frame"] for _, sample in frames}
    _require(all(event.get("frame") in observed for event in events),
             "native event lacks its completed game frame")
    return frames, events


def _fault(frames, events, name):
    right = [(action, sample) for action, sample in frames if action == "sprint-right"]
    starts = [(action, sample, _actor(sample)) for action, sample in right
              if _actor(sample).get("motionPhase") == "MOVING"
              and _actor(sample).get("motionElapsed") == 1]
    walks = [(action, sample, actor) for action, sample, actor in starts
             if actor.get("motionKind") == "WALK"]
    _require(len(walks) >= 8, "copied control lacks eight Walk starts")
    if name == "remove-walk-start":
        first = walks[0][1]["frame"]
        for event in events:
            if event.get("frame") == first and event.get("data", {}).get("event") == "MOTION_STARTED":
                event["data"]["event"] = "REMOVED_MOTION_STARTED"
                return True
    elif name == "slow-walk":
        walks[0][2]["movementPolicy"]["speed"] = 10
        return True
    elif name == "unexpected-hop":
        walks[4][2]["motionKind"] = "HOP"
        return True
    elif name == "reset-after-acceleration":
        at_speed_four = [actor for _, _, actor in walks
                         if actor.get("movementPolicy", {}).get("speed") == 4]
        _require(len(at_speed_four) >= 2,
                 "copied control lacks continued speed-four Walk")
        at_speed_four[1]["movementPolicy"]["speed"] = 8
        return True
    elif name == "diagonal-target":
        chord = next((sample for action, sample in frames
                      if action == "hold-two-directions"), None)
        _require(chord is not None, "copied control lacks two-direction input")
        actor = _actor(chord)
        actor["motionKind"] = "WALK"
        actor["motionPhase"] = "MOVING"
        actor["origin"] = {"x": chord["player"]["x"], "y": chord["player"]["y"]}
        actor["target"] = {"x": actor["origin"]["x"] + 1,
                           "y": actor["origin"]["y"] - 1}
        return True
    elif name == "wrong-actor":
        _actor(frames[0][1])["subjectIdentity"] ^= 1
        return True
    raise ValueError("unknown or inapplicable Stantler Sprint control: " + name)


def _measure(frames, events):
    right = [(sample, _actor(sample)) for action, sample in frames
             if action == "sprint-right"]
    chord = [(sample, _actor(sample)) for action, sample in frames
             if action == "hold-two-directions"]
    _require(len(right) == 160 and len(chord) == 40,
             "held-input windows have wrong completed-frame lengths")
    first = right[0][1]
    handle = first["handle"]
    identity = first["subjectIdentity"]
    context = right[0][0].get("context")
    _require(isinstance(context, dict) and context.get("mapId") == 33
             and first.get("logical") == {"x": 585, "y": 402},
             "prepared starting tile or map differs")
    first_right_frame = right[0][0]["frame"]
    first_chord_frame = chord[0][0]["frame"]
    for action, sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion" and
                 sample.get("fieldAvailable") is True and
                 sample.get("context") == context and actor.get("handle") == handle and
                 actor.get("subjectIdentity") == identity,
                 "frame is stale or Stantler changed")
        if action == "sprint-right":
            allowed = (0, 16) if sample["frame"] == first_right_frame else (16,)
            _require(sample["selector"].get("rawHeld") in allowed and
                     sample["selector"].get("heldKeys") in allowed,
                     "Right was not held for the natural Sprint window")
        if action == "hold-two-directions":
            allowed = (0, 16, 80) if sample["frame"] == first_chord_frame else (80,)
            _require(sample["selector"].get("rawHeld") in allowed and
                     sample["selector"].get("heldKeys") in allowed,
                     "UP and RIGHT were not held together")
    starts = [(sample, actor) for sample, actor in right
              if actor.get("motionPhase") == "MOVING" and
              actor.get("motionElapsed") == 1]
    walks = [(sample, actor) for sample, actor in starts if actor.get("motionKind") == "WALK"]
    _require(all(_actor(sample).get("motionKind") != "HOP" for _, sample in frames),
             "a Hop started on the clear Sprint lane")
    _require(len(walks) >= 8 and len(starts) == len(walks),
             "eight normal Sprint Walk starts are missing")
    _require(walks[0][1]["movementPolicy"]["speed"] == 8 and
             sum(actor["movementPolicy"]["speed"] == 4 for _, actor in walks) >= 4,
             "Stantler did not accelerate from slow Walk to speed four")
    first_four = next(index for index, (_, actor) in enumerate(walks)
                      if actor["movementPolicy"]["speed"] == 4)
    _require(all(actor["movementPolicy"]["speed"] == 4
                 for _, actor in walks[first_four:]),
             "Sprint speed reset after acceleration")
    for _, actor in walks:
        origin, target = actor["origin"], actor["target"]
        speed = actor["movementPolicy"]["speed"]
        _require((target["x"] - origin["x"], target["y"] - origin["y"]) == (1, 0)
                 and speed <= actor["motionDuration"] <= speed + 2,
                 "clear-lane Walk is not one cardinal tile with authored timing")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    for index, (walk_sample, _) in enumerate(walks[:8]):
        started = [event for event in native if event["frame"] == walk_sample["frame"]
                   and event["data"].get("event") == "MOTION_STARTED"
                   and event["data"].get("reason") == "OK"
                   and event["data"].get("valueA") == 1]
        _require(len(started) == 1, "native one-tile Walk start is missing")
        next_frame = walks[index + 1][0]["frame"]
        terminal = [event for event in native
                    if walk_sample["frame"] < event["frame"] <= next_frame]
        for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            _require(sum(event["data"].get("event") == name and
                         event["data"].get("reason") == "OK"
                         for event in terminal) == 1,
                     "native Walk did not commit, finish and return control")
        _require(not any(event["data"].get("event") == "MOTION_CANCELED"
                         for event in terminal), "clear-lane Walk was canceled")
    _require(not any(event["data"].get("event") == "MOTION_CANCELED"
                     for event in native), "mounted Sprint motion was canceled")
    _require(any(actor.get("motionKind") == "WALK"
                 and actor.get("motionPhase") == "MOVING" for _, actor in chord),
             "two-direction window has no mounted Walk")
    for sample, actor in chord:
        if actor.get("motionKind") == "WALK" and actor.get("motionPhase") != "IDLE":
            dx = actor["target"]["x"] - actor["origin"]["x"]
            dy = actor["target"]["y"] - actor["origin"]["y"]
            _require(abs(dx) + abs(dy) == 1,
                     "two held directions started a diagonal Walk")
    for (left, _), (right_sample, _) in zip(chord, chord[1:]):
        dx = right_sample["player"]["x"] - left["player"]["x"]
        dy = right_sample["player"]["y"] - left["player"]["y"]
        _require(not dx or not dy, "player moved diagonally under two held directions")
    return {"values": {"held-right-and-two-direction-input": 1,
                       "same-current-mounted-stantler": 1,
                       "complete-clear-lane-walks": 8,
                       "accelerates-to-four-speed": 1,
                       "clear-lane-no-hops": 1,
                       "four-speed-walks-continue": 1,
                       "cardinal-only-two-key-window": 1,
                       "walks-return-control": 1},
            "subjectIdentity": identity, "actorHandle": handle,
            "walkStartFrames": [sample["frame"] for sample, _ in walks],
            "rightFrames": len(right), "chordFrames": len(chord)}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-sprint-parity"
                     and [action["id"] for action in test.get("actions", [])] ==
                     ["sprint-right", "settle-right", "hold-two-directions"],
                     "reviewed prepared recipe differs")
        frames, events = _stream(rows)
        applied = _fault(frames, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(frames, events)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied,
                "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
