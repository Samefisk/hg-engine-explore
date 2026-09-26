"""Pure completed-frame Select handoff proof over a retained shared test stream.

The controller owns fixture, recipe, native source, and artifact authentication.
This meter does not start a game or grant proof by itself.
"""

from copy import deepcopy


KIND = "mount-select-mid-run-v1"
REQUIREMENT = "current.mount-select-mid-run"
CLAIMS = ("natural-input", "live-actor-identity", "frame-pacing", "control-release")
MAX_MOUNT_FRAMES = 8
FAULTS = ("missing-select-edge", "delayed-mount", "changed-actor", "missing-hop-commit")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("select-native-held-right-edge"),
                          exact("right-held-through-handoff")],
        "live-actor-identity": [
            {"name": "select-started-as-follower", "operator": "eq", "type": "string",
             "validator": "meaningful-observation", "expected": "FOLLOWER"},
            exact("select-mid-run-same-actor")],
        "frame-pacing": [{"name": "select-to-mount-completed-frames", "operator": "lte",
                          "type": "integer", "validator": "meaningful-observation",
                          "expected": MAX_MOUNT_FRAMES}],
        "control-release": [exact("mounted-hop-terminal-control")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mount Select mid-run: " + reason)


def _actor(snapshot, role):
    actors = [actor for actor in snapshot.get("actors", [])
              if actor.get("active") is True and actor.get("role") == role
              and actor.get("species") == 56]
    _require(len(actors) == 1, "expected one live Mankey " + role)
    actor = actors[0]
    _require(actor.get("identityVerified") is True and
             actor.get("presentationAttached") is True,
             "Mankey has no verified live presentation")
    _require(actor.get("handle", {}).get("slot") == 7 and
             actor.get("handle", {}).get("encounterGeneration", 0) > 0,
             "Mankey has no current follower actor handle")
    return actor


def _stream(rows):
    frames, events = [], []
    for row in rows:
        samples = row.get("samples")
        if samples is None:
            continue
        _require(row.get("phase") == "observe" and
                 row.get("action") in {"wait-saved-follower", "start-player-run",
                                       "press-select-during-run", "keep-right-until-mounted",
                                       "start-mounted-hop", "wait-hop-terminal"} and
                 row.get("completedGameFrames") == len(samples) and samples,
                 "sample chunk is not a complete reviewed action")
        frames.extend((row["action"], deepcopy(sample)) for sample in samples)
        events.extend(deepcopy(row.get("events", [])))
    _require(frames, "no completed game frames")
    for (left_action, left), (right_action, right) in zip(frames, frames[1:]):
        _require(right["frame"] == left["frame"] + 1,
                 "completed game frame is missing")
        _require(right.get("nativeCycle", 0) >= left.get("nativeCycle", 0),
                 "native clock reversed")
    observed = {sample["frame"] for _, sample in frames}
    _require(all(event.get("frame") in observed for event in events),
             "native event lacks its completed frame")
    return frames, events


def _fault(frames, events, name):
    if name == "missing-select-edge":
        select = next((sample for action, sample in frames
                       if action == "press-select-during-run"), None)
        _require(select is not None, "control has no Select sample")
        select["selector"]["rawNew"] &= ~4
        return True
    if name == "changed-actor":
        mount = next((sample for _, sample in frames
                      if any(actor.get("active") is True and actor.get("role") == "MOUNTED"
                             and actor.get("species") == 56 for actor in sample.get("actors", []))), None)
        _require(mount is not None, "control has no mounted sample")
        _actor(mount, "MOUNTED")["subjectIdentity"] ^= 1
        return True
    if name == "missing-hop-commit":
        first_mount = next((sample["frame"] for _, sample in frames
                            if any(actor.get("active") is True and actor.get("role") == "MOUNTED"
                                   and actor.get("species") == 56 for actor in sample.get("actors", []))), None)
        event = next((event for event in events if event.get("kind") == "native"
                      and first_mount is not None and event.get("frame", 0) >= first_mount
                      and event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                      and event.get("data", {}).get("reason") == "OK"), None)
        _require(event is not None, "control has no Hop commit")
        event["data"]["event"] = "CONTROL_REMOVED"
        return True
    if name == "delayed-mount":
        select = next((sample for action, sample in frames
                       if action == "press-select-during-run"), None)
        mount_index = next((index for index, (_, sample) in enumerate(frames)
                            if any(actor.get("active") is True and actor.get("role") == "MOUNTED"
                                   and actor.get("species") == 56 for actor in sample.get("actors", []))), None)
        _require(select is not None and mount_index is not None and mount_index > 0,
                 "control lacks Select or mounted actor")
        first_mount = frames[mount_index][1]["frame"]
        extra = max(1, MAX_MOUNT_FRAMES + 1 - (first_mount - select["frame"]))
        prior = frames[mount_index - 1][1]
        for _, sample in frames[mount_index:]:
            sample["frame"] += extra
            sample["nativeCycle"] += extra * 2
        for event in events:
            if event["frame"] >= first_mount:
                event["frame"] += extra
        for offset in range(extra):
            copied = deepcopy(prior)
            copied["frame"] = prior["frame"] + offset + 1
            copied["nativeCycle"] = prior["nativeCycle"] + (offset + 1) * 2
            frames.insert(mount_index + offset, ("keep-right-until-mounted", copied))
        return True
    raise ValueError("unknown Select mid-run control: " + str(name))


def _measure(frames, events):
    select_rows = [(index, sample) for index, (action, sample) in enumerate(frames)
                   if action == "press-select-during-run"]
    _require(len(select_rows) == 1, "Select was not exactly one completed frame")
    select_index, select = select_rows[0]
    _require(select_index > 0 and frames[select_index - 1][0] == "start-player-run",
             "Select did not follow the normal Right run")
    before = frames[select_index - 1][1]
    _require(before["selector"].get("rawHeld") == 16 and
             before["selector"].get("heldKeys") == 16,
             "Right was not held before Select")
    selector = select["selector"]
    _require(selector.get("rawNew") & 4 and selector.get("newKeys") & 4 and
             selector.get("rawHeld") == 20 and selector.get("heldKeys") == 20,
             "native Select edge with held Right is missing")
    follower = _actor(select, "FOLLOWER")
    _require(follower.get("motionKind") == "HOP" and
             follower.get("motionPhase") == "MOVING" and
             follower.get("reservationId", 0) > 0 and
             select["player"].get("movement_step") == 1 and
             select["player"].get("x", 0) > select["player"].get("x_prev", 0),
             "Select did not occur during both the player run and follower Hop")
    _require(select.get("fieldAvailable") is True and
             select.get("observationBoundary") == "main-task-queue-completion",
             "Select frame is not a complete field observation")
    mounted_rows = [(index, sample) for index, (_, sample) in enumerate(frames)
                    if index >= select_index and any(actor.get("active") is True
                    and actor.get("role") == "MOUNTED" and actor.get("species") == 56
                    for actor in sample.get("actors", []))]
    _require(mounted_rows, "saved Mankey never mounted")
    mount_index, mount = mounted_rows[0]
    _require(frames[mount_index][0] == "keep-right-until-mounted",
             "mount did not occur during continuous Right input")
    elapsed = mount["frame"] - select["frame"]
    _require(0 < elapsed <= MAX_MOUNT_FRAMES,
             "Select-to-mount exceeded eight completed game frames")
    for index in range(select_index + 1, mount_index + 1):
        action, sample = frames[index]
        _require(action == "keep-right-until-mounted" and
                 sample["selector"].get("rawHeld") == 16 and
                 sample["selector"].get("heldKeys") == 16,
                 "Right input was not retained through the handoff")
    mounted = _actor(mount, "MOUNTED")
    _require(mounted.get("subjectIdentity") == follower.get("subjectIdentity") and
             mounted.get("handle") == follower.get("handle") and
             mounted.get("engineIdentity", {}).get("pointer") ==
             follower.get("engineIdentity", {}).get("pointer") and
             mount.get("context") == select.get("context") and
             mounted.get("inputOwnership") == 1 and mounted.get("lane") == "OWNER",
             "mounted role did not retain the same current live actor")
    native = [event for event in events if event.get("kind") == "native" and
              event.get("data", {}).get("actorHandle") == mounted["handle"]["value"]]
    for name, old, new in (("ACTOR_REBOUND", 2, 3), ("CONTROL_REBOUND", 0, 1)):
        matches = [event for event in native if event["frame"] == mount["frame"] and
                   event["data"].get("event") == name and
                   event["data"].get("reason") == "OK" and
                   (event["data"].get("valueA"), event["data"].get("valueB")) == (old, new)]
        _require(len(matches) == 1, name + " native handoff is missing or duplicated")
    last_action, last = frames[-1]
    terminal = _actor(last, "MOUNTED")
    _require(last_action == "wait-hop-terminal" and
             terminal.get("motionPhase") == "IDLE" and terminal.get("reservationId") == 0 and
             terminal.get("commitSequence") == mounted.get("commitSequence") + 1 and
             terminal.get("subjectIdentity") == follower.get("subjectIdentity") and
             last["player"].get("x", 0) > select["player"].get("x", 0) and
             terminal.get("inputOwnership") == 1,
             "mounted Hop did not finish and return moving control")
    started = [event for event in native if event["frame"] >= mount["frame"] and
               event["data"].get("event") == "MOTION_STARTED" and
               event["data"].get("reason") == "OK" and event["data"].get("valueA") == 2]
    _require(len(started) == 1, "expected exactly one mounted Hop start")
    start_frame = started[0]["frame"]
    for name, value_a, value_b in (
            ("LOGICAL_COMMIT", terminal["commitSequence"], 2),
            ("MOTION_FINISHED", terminal["commitSequence"], 2),
            ("CONTROL_RETURNED", 1, terminal["commitSequence"])):
        matches = [event for event in native if start_frame <= event["frame"] <= last["frame"]
                   and event["data"].get("event") == name and
                   event["data"].get("reason") == "OK" and
                   (event["data"].get("valueA"), event["data"].get("valueB")) == (value_a, value_b)]
        _require(len(matches) == 1, name + " of mounted Hop is missing or duplicated")
    _require(not any(event["frame"] >= start_frame and
                     event["data"].get("event") == "MOTION_CANCELED" for event in native),
             "mounted Hop was canceled")
    values = {"select-native-held-right-edge": 1, "right-held-through-handoff": 1,
              "select-started-as-follower": "FOLLOWER",
              "select-mid-run-same-actor": 1,
              "select-to-mount-completed-frames": elapsed,
              "mounted-hop-terminal-control": 1}
    return {"values": values, "selectFrame": select["frame"],
            "mountFrame": mount["frame"], "terminalFrame": last["frame"],
            "subjectIdentity": follower["subjectIdentity"],
            "actorHandle": mounted["handle"], "playerX": [select["player"]["x"], last["player"]["x"]]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.select-mid-run" and test.get("setup") == [],
                     "reviewed normal-input recipe differs")
        frames, events = _stream(rows)
        applied = _fault(frames, events, fault) if fault else False
        evidence = _measure(frames, events)
        return {"passed": True, "faultApplied": applied, "failures": [], **evidence}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied,
                "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"] and
                          result["failures"] for result in controls.values()),
            "controls": controls}
