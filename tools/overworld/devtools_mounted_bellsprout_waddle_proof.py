"""Completed-frame pose proof for one natural Mounted Bellsprout Walk."""

from copy import deepcopy


KIND = "mounted-bellsprout-waddle-sway-v1"
REQUIREMENT = "current.mounted-bellsprout-waddle-sway"
CLAIMS = ("natural-input", "live-actor-identity", "profile-resolution",
          "logical-commit", "rendered-motion", "frame-pacing", "control-release")
FAULTS = ("lost-sway", "pose-split", "follower-speed-cap", "extra-start",
          "logical-side-step", "wrong-actor")
ACTIONS = ("start-one-right-walk", "finish-one-right-walk")
LANE_Z = (402 << 16) + 0x8000


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("one-right-press-then-release")],
        "live-actor-identity": [exact("same-current-mounted-bellsprout")],
        "profile-resolution": [exact("normal-meander-and-waddle-effects")],
        "logical-commit": [exact("one-right-tile-one-commit")],
        "rendered-motion": [exact("both-sides-waddle-sway"),
                            exact("player-pokemon-pose-pair")],
        "frame-pacing": [exact("full-meander-walk-frame-sequence")],
        "control-release": [exact("walk-terminal-control-return")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Bellsprout Waddle: " + reason)


def _actor(sample):
    found = [actor for actor in sample.get("actors", [])
             if actor.get("active") is True and actor.get("role") == "MOUNTED"
             and actor.get("species") == 69]
    _require(len(found) == 1, "expected one live mounted Bellsprout")
    actor = found[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1
             and actor.get("handle", {}).get("slot") == 7
             and actor.get("handle", {}).get("encounterGeneration", 0) > 0,
             "Bellsprout identity or mounted control differs")
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
            _require(not windows[action]
                     and len(order) < len(ACTIONS)
                     and action == ACTIONS[len(order)],
                     "observation actions are missing or reordered")
            order.append(action)
        samples = deepcopy(row["samples"])
        _require(samples and len(samples) == row.get("completedGameFrames"),
                 "observation chunk has wrong completed-frame count")
        windows[action].extend(samples)
        events.extend(deepcopy(row.get("events", [])))
    _require(order == list(ACTIONS) and all(windows.values()),
             "reviewed Waddle actions are incomplete")
    observed = [sample for action in ACTIONS for sample in windows[action]]
    _require([sample["frame"] for sample in observed] == list(range(
        observed[0]["frame"], observed[-1]["frame"] + 1)),
        "completed game frames have a gap or reordered action")
    measured = {sample["frame"] for sample in observed}
    _require(all(event.get("frame") in measured for event in events),
             "native event lacks a measured frame")
    return windows, events, observed


def _fault(windows, events, name):
    start = windows[ACTIONS[0]][-1]
    walk = [sample for action in ACTIONS for sample in windows[action]
            if _actor(sample).get("motionKind") == "WALK"]
    _require(walk, "copied control lacks the Walk")
    if name == "lost-sway":
        for sample in walk:
            _actor(sample)["engineObject"]["pos_z"] = LANE_Z
            sample["player"]["pos_z"] = LANE_Z
    elif name == "pose-split":
        _actor(walk[0])["engineObject"]["pos_z"] += 0x1000
    elif name == "follower-speed-cap":
        _actor(start)["movementPolicy"]["speed"] = 8
    elif name == "extra-start":
        found = next((event for event in events
                      if event.get("data", {}).get("event") == "MOTION_STARTED"), None)
        _require(found is not None, "copied control lacks a native start")
        events.append(deepcopy(found))
    elif name == "logical-side-step":
        _actor(walk[-1])["logical"]["y"] += 1
    elif name == "wrong-actor":
        _actor(walk[0])["subjectIdentity"] ^= 1
    else:
        raise ValueError("unknown Bellsprout Waddle control: " + name)
    return True


def _measure(windows, events, observed):
    start_window = windows[ACTIONS[0]]
    finish_window = windows[ACTIONS[1]]
    context = observed[0].get("context")
    first = _actor(observed[0])
    handle, identity = first["handle"], first["subjectIdentity"]
    _require(isinstance(context, dict) and context.get("mapId") == 33,
             "prepared map 33 fixture differs")
    for sample in observed:
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor.get("handle") == handle
                 and actor.get("subjectIdentity") == identity,
                 "frame or current Bellsprout identity changed")
    started_sample = start_window[-1]
    started = _actor(started_sample)
    _require(started.get("motionKind") == "WALK"
             and started.get("motionPhase") == "MOVING"
             and started.get("motionElapsed") == 1
             and started.get("origin") == {"x": 585, "y": 402}
             and started.get("target") == {"x": 586, "y": 402},
             "natural Right input did not start one clear-lane Walk")
    _require(started.get("movementPolicy", {}).get("speed") == 14
             and 14 <= started.get("motionDuration", 0) <= 16,
             "mounted Walk lost normal Meander time or used the Follower cap")
    _require(any(sample["selector"].get("heldKeys") == 16
                 and sample["selector"].get("rawHeld") == 16
                 for sample in start_window)
             and all(sample["selector"].get("heldKeys") in (0, 16)
                     for sample in start_window)
             and all(sample["selector"].get("heldKeys") == 0
                     for sample in finish_window[1:]),
             "one Right press was not released during the Walk")
    _require(all(_actor(sample).get("motionKind") == "NONE"
                 and _actor(sample).get("motionPhase") == "IDLE"
                 for sample in start_window[:-1]),
             "a prior motion entered the one-Walk input window")
    duration = started["motionDuration"]
    walk = [sample for sample in observed
            if _actor(sample).get("motionKind") == "WALK"]
    _require([_actor(sample).get("motionElapsed") for sample in walk]
             == list(range(1, duration + 1))
             and all(_actor(sample).get("origin") == started["origin"]
                     and _actor(sample).get("target") == started["target"]
                     and _actor(sample).get("motionDuration") == duration
                     for sample in walk),
             "Walk did not provide every elapsed completed-frame pose")
    terminal = _actor(walk[-1])
    idle = _actor(finish_window[-1])
    _require(terminal.get("motionPhase") == "COMMIT_PENDING"
             and idle.get("motionPhase") == "IDLE"
             and idle.get("motionKind") == "NONE"
             and terminal.get("logical") == started["target"]
             and idle.get("logical") == started["target"]
             and finish_window[-1]["player"].get("x") == 586,
             "Walk did not commit one Right tile and return idle")
    offsets = []
    x_positions = []
    for sample in walk:
        actor = _actor(sample)
        player = sample.get("player", {})
        pokemon = actor.get("engineObject", {})
        _require(all(type(item.get(key)) is int
                     for item, key in ((player, "pos_x"), (player, "pos_z"),
                                       (pokemon, "pos_x"), (pokemon, "pos_z"))),
                 "current player or Bellsprout pose is missing")
        _require(player["pos_x"] == pokemon["pos_x"]
                 and player["pos_z"] == pokemon["pos_z"]
                 and player.get("y") == 402
                 and actor.get("logical", {}).get("y") == 402,
                 "player and dependent Bellsprout split or sway changed logical lane")
        offsets.append(pokemon["pos_z"] - LANE_Z)
        x_positions.append(pokemon["pos_x"])
    _require(any(offset > 0 for offset in offsets[:-1])
             and any(offset < 0 for offset in offsets[:-1])
             and max(map(abs, offsets)) < 0x8000
             and offsets[-1] == 0,
             "normal Waddle Walk lacks bounded sway on both sides")
    _require(x_positions == sorted(x_positions)
             and x_positions[-1] == (586 << 16) + 0x8000
             and idle.get("engineObject", {}).get("pos_z") == LANE_Z
             and finish_window[-1]["player"].get("pos_z") == LANE_Z,
             "Walk endpoint or idle pose did not return to lane center")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED",
                 "CONTROL_RETURNED"):
        matching = [event for event in native
                    if event["data"].get("event") == name
                    and event["data"].get("reason") == "OK"]
        _require(len(matching) == 1, "one Walk lacks exactly one native " + name)
    _require(not any(event["data"].get("event") == "MOTION_CANCELED"
                     for event in native), "Waddle Walk was canceled")
    return {"values": {
        "one-right-press-then-release": 1,
        "same-current-mounted-bellsprout": 1,
        "normal-meander-and-waddle-effects": 1,
        "one-right-tile-one-commit": 1,
        "both-sides-waddle-sway": 1,
        "player-pokemon-pose-pair": 1,
        "full-meander-walk-frame-sequence": 1,
        "walk-terminal-control-return": 1},
        "actorHandle": handle, "subjectIdentity": identity,
        "durationCompletedFrames": duration,
        "swayMinFx32": min(offsets), "swayMaxFx32": max(offsets)}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.bellsprout-waddle-sway"
                     and [action["id"] for action in test.get("actions", [])] == list(ACTIONS),
                     "reviewed Waddle recipe differs")
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
