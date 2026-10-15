"""Normal held-input ledge Hop preserves one mounted actor's Walk momentum.

The controller owns ROM, recipe, reader and private-session authentication.
Native policy bytes supply the accumulated Linear time and fractional carry;
rounded tile times alone do not show whether momentum was reset.
"""

from copy import deepcopy


KIND = "mounted-stantler-running-ledge-v1"
REQUIREMENT = "current.mounted-stantler-running-ledge"
CLAIMS = ("natural-input", "live-actor-identity", "collision-decision",
          "logical-commit", "frame-pacing", "control-release")
ACTION = "down-through-running-ledge"
START = {"x": 590, "y": 392}
HOP_ROUTES = ((395, 397), (400, 402))
WALK_ORIGINS = (392, 393, 394, 397, 398, 399, 402)
END = {"x": 590, "y": 403}
# OverworldActorPolicyState in overworld_actor_system_internal.h: committed
# walkMomentum, lastWalkTime, and Linear elapsed/carry/mode/cap. Pending engine
# receipts and proposed paths can change when the next Walk is admitted.
MOMENTUM = tuple(range(8)) + (25, 32, 33, 34, 35)
FAULTS = ("reset-speed", "reset-linear-elapsed", "reset-linear-carry",
          "wrong-owner", "short-landing", "no-hop", "missing-hop-commit",
          "legacy-control-packet", "crash")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("continuous-held-down")],
        "live-actor-identity": [exact("same-current-mounted-stantler")],
        "collision-decision": [exact("two-running-south-ledge-hops")],
        "logical-commit": [exact("two-ledge-hops-and-seven-walk-commits")],
        "frame-pacing": [exact("ledge-preserves-committed-momentum")],
        "control-release": [exact("next-walk-within-one-frame")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler running ledge: " + reason)


def _actor(sample):
    actors = [actor for actor in sample.get("actors", [])
              if isinstance(actor, dict) and actor.get("active") is True
              and actor.get("role") == "MOUNTED" and actor.get("species") == 234]
    _require(len(actors) == 1, "expected one current mounted Stantler")
    actor = actors[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1
             and actor.get("handle", {}).get("slot") == 7
             and actor.get("handle", {}).get("encounterGeneration", 0) > 0,
             "mounted identity or input ownership differs")
    return actor


def _stream(rows):
    frames, events = [], []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        _require(row.get("action") == ACTION, "normal held-input action differs")
        samples = deepcopy(row["samples"])
        _require(samples and row.get("completedGameFrames") == len(samples),
                 "observation chunk has wrong completed-frame count")
        frames.extend(samples)
        events.extend(deepcopy(row.get("events", [])))
    _require(frames and all(right["frame"] == left["frame"] + 1
             and right.get("nativeCycle", 0) >= left.get("nativeCycle", 0)
             for left, right in zip(frames, frames[1:])),
             "completed game frame is missing or clock reversed")
    observed = {sample["frame"] for sample in frames}
    _require(all(event.get("frame") in observed for event in events),
             "native event lacks its completed game frame")
    return frames, events


def _policy_events(events, actor, operation=None):
    result = [event for event in events
              if event.get("kind") == "native-observation"
              and event.get("data", {}).get("observation") == "walk-policy"
              and event["data"].get("slot") == actor["handle"]["slot"]
              and (operation is None or event["data"].get("operation") == operation)]
    for event in result:
        owner = event["data"].get("publicSubject", {})
        _require(owner.get("handle") == actor["handle"]
                 and owner.get("subjectIdentity") == actor["subjectIdentity"]
                 and owner.get("role") == "MOUNTED" and owner.get("species") == 234,
                 "native policy has a different full owner")
    return result


def _fault(frames, events, name):
    hop_sample = next(sample for sample in frames
                      if _actor(sample).get("motionKind") == "HOP"
                      and _actor(sample).get("origin", {}).get("y") == 400)
    hop, hop_frame = _actor(hop_sample), hop_sample["frame"]
    recovery = next(_actor(sample) for sample in frames
                    if sample["frame"] > hop_frame
                    and _actor(sample).get("motionKind") == "WALK")
    if name == "reset-speed":
        recovery["movementPolicy"]["speed"] = recovery["movementPolicy"]["base"]
    elif name in ("reset-linear-elapsed", "reset-linear-carry"):
        event = next(event for event in _policy_events(events, hop, 1)
                     if event["frame"] > hop_frame)
        packet = bytearray.fromhex(event["data"]["policyBeforeHex"])
        packet[32 if name == "reset-linear-elapsed" else 33] ^= 1
        event["data"]["policyBeforeHex"] = packet.hex()
    elif name == "wrong-owner":
        hop["handle"]["fieldEpoch"] += 1
    elif name == "short-landing":
        hop["target"]["y"] = 401
    elif name == "no-hop":
        for sample in frames:
            actor = _actor(sample)
            if actor.get("motionKind") == "HOP" and actor.get("origin", {}).get("y") == 400:
                actor["motionKind"] = "WALK"
    elif name == "missing-hop-commit":
        event = next(event for event in events
                     if event.get("kind") == "native"
                     and event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                     and event["data"].get("valueB") == 2 and event["frame"] > hop_frame)
        event["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    elif name == "legacy-control-packet":
        commit = next(event for event in events
                      if event.get("kind") == "native"
                      and event.get("data", {}).get("event") == "LOGICAL_COMMIT"
                      and event["data"].get("valueB") == 2 and event["frame"] > hop_frame)
        event = next(event for event in events
                     if event.get("kind") == "native"
                     and event.get("data", {}).get("event") == "CONTROL_RETURNED"
                     and event["data"].get("valueB") == commit["data"]["valueA"])
        event["data"]["valueB"] = 2
    elif name == "crash":
        events.append({"frame": hop_frame, "kind": "native", "data": {
            "actorHandle": hop["handle"]["value"], "event": "WORLD_EFFECT",
            "valueA": 3, "reason": "OK"}})
    else:
        raise ValueError("unknown running-ledge control: " + name)
    return True


def _terminal(native, start, end, kind, label, previous_commit):
    """Pair the actual Actor commit ID with its finish and owner return.

    ActorSystem_WriteTerminalTrace uses (ownership, commitSequence) for
    CONTROL_RETURNED, unlike the (commitSequence, motionKind) pair on COMMIT
    and FINISHED. The preceding Walk may commit on the Hop start queue.
    """
    commits = [event for event in native
               if start < event["frame"] <= end
               and event["data"].get("event") == "LOGICAL_COMMIT"
               and event["data"].get("reason") == "OK"
               and event["data"].get("valueB") == kind]
    _require(len(commits) == 1, label + " lacks one native LOGICAL_COMMIT")
    commit_id = commits[0]["data"].get("valueA")
    _require(type(commit_id) is int and commit_id == previous_commit + 1,
             label + " committed a different motion sequence")
    terminal = {"LOGICAL_COMMIT": commits[0]["frame"]}
    for name in ("MOTION_FINISHED", "CONTROL_RETURNED"):
        matches = [event for event in native if start < event["frame"] <= end
                   and event["data"].get("event") == name
                   and event["data"].get("reason") == "OK"
                   and (event["data"].get("valueA"), event["data"].get("valueB"))
                   == ((1, commit_id) if name == "CONTROL_RETURNED" else (commit_id, kind))]
        _require(len(matches) == 1, label + " lacks one native " + name)
        terminal[name] = matches[0]["frame"]
    _require(terminal["LOGICAL_COMMIT"] <= terminal["MOTION_FINISHED"]
             <= terminal["CONTROL_RETURNED"], label + " terminal order differs")
    return terminal, commit_id


def _measure(frames, events):
    first, context = _actor(frames[0]), frames[0].get("context")
    handle, identity = first["handle"], first["subjectIdentity"]
    _require(isinstance(context, dict) and context.get("mapId") == 33
             and first.get("logical") == START,
             "prepared South run-up start differs")
    for index, sample in enumerate(frames):
        actor = _actor(sample)
        _require(sample.get("observationBoundary") == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context and actor.get("handle") == handle
                 and actor.get("subjectIdentity") == identity
                 and actor.get("behaviorFingerprint") == first.get("behaviorFingerprint"),
                 "frame is stale or mounted Stantler owner/profile changed")
        allowed = (0, 128) if index == 0 else (128,)
        _require(sample.get("selector", {}).get("rawHeld") in allowed
                 and sample.get("selector", {}).get("heldKeys") in allowed,
                 "Down was released or normal input differs")
    native = [event for event in events if event.get("kind") == "native"
              and event.get("data", {}).get("actorHandle") == handle["value"]]
    _require(not any(event["data"].get("event") in
                     ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND")
                     or (event["data"].get("event") == "WORLD_EFFECT"
                         and event["data"].get("valueA") == 3) for event in native),
             "ledge motion canceled, changed context or published Crash")
    starts = [(sample, _actor(sample)) for sample in frames
              if _actor(sample).get("motionPhase") == "MOVING"
              and _actor(sample).get("motionElapsed") == 1]
    hops = [(sample, actor) for sample, actor in starts if actor.get("motionKind") == "HOP"]
    _require(len(hops) == 2, "expected two running two-tile ledge Hops")
    walks = [(sample, actor) for sample, actor in starts if actor.get("motionKind") == "WALK"]
    # A terminal queue may already admit the next clear Walk; that extra start
    # at the end tile is not a completed extra motion in the checked window.
    _require(len(walks) in (7, 8) and all(
                 actor.get("origin") == {"x": 590, "y": y}
                 and actor.get("target") == {"x": 590, "y": y + 1}
                 for (_, actor), y in zip(walks, WALK_ORIGINS + (403,))),
             "normal South run-up and recovery Walk route differs")
    policy_events = _policy_events(events, first)
    _require(not any(event["data"].get("operation") == 0 for event in policy_events
                     if hops[0][0]["frame"] <= event["frame"] <= frames[-1]["frame"]),
             "running ledge called native Walk RESET")
    evidence = []
    for index, ((hop_sample, hop), (origin_y, landing_y)) in enumerate(zip(hops, HOP_ROUTES)):
        origin, landing = {"x": 590, "y": origin_y}, {"x": 590, "y": landing_y}
        _require(hop.get("origin") == origin and hop.get("target") == landing,
                 "running Hop did not cross the exact two-tile South ledge")
        preceding = [event for event in policy_events
                     if event["data"].get("operation") == 3
                     and event["frame"] <= hop_sample["frame"]]
        _require(len(preceding) == 3 * (index + 1),
                 "run-up lacks its actual Walk policy commits")
        momentum = bytes.fromhex(preceding[-1]["data"]["policyAfterHex"])
        _require(len(momentum) == 36 and momentum[0] == 1
                 and 0 < momentum[2] < momentum[3]
                 and momentum[32] > 0 and momentum[34] == 1,
                 "Stantler did not accumulate South running speed before the ledge")
        _require(hop.get("motionDuration") == momentum[2] * 2,
                 "running ledge Hop did not use current Walk speed")
        starts_native = [event for event in native
                         if event["data"].get("event") == "MOTION_STARTED"
                         and event["data"].get("valueA") == 2
                         and event["frame"] == hop_sample["frame"]]
        _require(len(starts_native) == 1
                 and starts_native[0]["data"].get("valueB") == hop["motionDuration"],
                 "shared native ledge Hop start is missing or duplicated")
        next_boundary = (hops[index + 1][0]["frame"] if index == 0 else frames[-1]["frame"])
        terminals, commit_id = _terminal(native, hop_sample["frame"], next_boundary,
                                         2, "ledge Hop", hop["commitSequence"])
        returned = terminals["CONTROL_RETURNED"]
        for sample in frames:
            if hop_sample["frame"] <= sample["frame"] <= returned:
                policy = _actor(sample).get("movementPolicy", {})
                _require((policy.get("direction"), policy.get("speed"), policy.get("base"))
                         == (momentum[0], momentum[2], momentum[3]),
                         "ledge Hop reset speed or heading")
        recovery = next((pair for pair in walks if pair[1].get("origin") == landing), None)
        _require(recovery is not None and 0 < recovery[0]["frame"] - returned <= 1,
                 "next Walk did not start within one completed frame")
        inputs = [event for event in policy_events
                  if event["data"].get("operation") == 1 and event["frame"] == recovery[0]["frame"]]
        _require(inputs and all(len(bytes.fromhex(event["data"]["policyBeforeHex"])) == 36
                 and all(bytes.fromhex(event["data"]["policyBeforeHex"])[byte] == momentum[byte]
                         for byte in MOMENTUM) for event in inputs),
                 "ledge reset committed acceleration or fractional carry")
        _require(recovery[1]["movementPolicy"]["base"] == momentum[3]
                 and 0 < recovery[1]["movementPolicy"]["speed"] <= momentum[2] + 1,
                 "resumed Walk speed reset to its starting time")
        evidence.append({"hopStartFrame": hop_sample["frame"], "hopReturnFrame": returned,
                         "resumedWalkFrame": recovery[0]["frame"], "preservedPolicyHex": momentum.hex(),
                         "linearElapsed": momentum[32], "linearCarry": momentum[33],
                         "commitSequence": commit_id})
    for sample, actor in walks[:7]:
        admissions = [event for event in native if event["frame"] == sample["frame"]
                      and event["data"].get("event") == "MOTION_STARTED"
                      and event["data"].get("reason") == "OK"
                      and event["data"].get("valueA") == 1
                      and event["data"].get("valueB") == actor.get("motionDuration")]
        _require(len(admissions) == 1, "normal South Walk lacks one actual native start")
        following = next((frame["frame"] for frame, _ in starts
                          if frame["frame"] > sample["frame"]), frames[-1]["frame"])
        _terminal(native, sample["frame"], following, 1, "normal South Walk",
                  actor["commitSequence"])
    _require(_actor(frames[-1]).get("logical") == END,
             "post-second-ledge Walk did not commit at the reviewed end tile")
    return {"values": {rule["name"]: 1 for rules in contract().values() for rule in rules},
            "subjectIdentity": identity, "actorHandle": handle, "hops": evidence}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.stantler-running-ledge"
                     and [action["id"] for action in test.get("actions", [])] == [ACTION],
                     "reviewed running-ledge recipe differs")
        frames, events = _stream(rows)
        applied = _fault(frames, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(frames, events)}
    except (ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        return {"passed": False, "faultApplied": applied, "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    reasons = {"reset-speed": "resumed Walk speed reset",
               "reset-linear-elapsed": "reset committed acceleration",
               "reset-linear-carry": "reset committed acceleration",
               "wrong-owner": "owner/profile changed", "short-landing": "exact two-tile",
               "no-hop": "expected two running", "missing-hop-commit": "one native LOGICAL_COMMIT",
               "legacy-control-packet": "one native CONTROL_RETURNED",
               "crash": "published Crash"}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and any(reasons[fault] in reason for reason in result["failures"])
                          for fault, result in controls.items()), "controls": controls}
