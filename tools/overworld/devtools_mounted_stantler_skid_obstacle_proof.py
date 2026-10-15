"""Completed-frame proof for a turn skid that meets a blocked tile."""

from copy import deepcopy

from tools.overworld.devtools_mount_gait import check_gait
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose


KEY_MASKS = {"run-right": 16, "turn-down": 128}
MIN_RUN_FRAMES = 19
MAX_RUN_FRAMES = 32
CLAIMS = ("natural-input", "live-actor-identity", "collision-decision",
          "logical-commit", "rendered-motion", "control-release")
NAMES = ("normal-right-then-down-input", "same-mounted-stantler",
         "crash-at-first-blocked-skid-tile", "only-clear-skid-commits",
         "rider-and-mount-stop-before-wall", "idle-control-before-blocked-tile")
SECOND = "mount.stantler-turn-skid-blocked-second"
FIRST = "mount.stantler-turn-skid-blocked-first"
TWO_KEYS = "mount.stantler-two-key-turn-skid-blocked-second"
CASES = {
    SECOND: {"requirement": "current.mounted-stantler-turn-skid-blocked-second",
             "start": 583, "runEnd": 588, "clearSkids": 1,
             "faults": ("wrong-actor", "wrong-input", "missing-due-skid",
                        "missing-blocked-admission", "missing-clear-skid",
                        "missing-commit", "missing-crash", "early-crash",
                        "wall-cross", "missing-control", "missing-gait",
                        "wrong-gait-owner", "wrong-gait-pose", "wrong-gait-stamp",
                        "wrong-pair-pointer", "wrong-seat", "wrong-height")},
    FIRST: {"requirement": "current.mounted-stantler-turn-skid-blocked-first",
            "start": 584, "runEnd": 589, "clearSkids": 0,
            "faults": ("wrong-actor", "wrong-input", "missing-due-skid",
                       "missing-blocked-admission", "phantom-skid",
                       "missing-crash", "wall-cross", "missing-control")},
}
CASES[TWO_KEYS] = {
    **CASES[SECOND],
    "faults": (*CASES[SECOND]["faults"], "wrong-recovery", "missing-recovery-start",
               "missing-recovery-admission"),
    "requirement": "current.mounted-stantler-two-key-turn-skid-blocked-second",
    "turnAction": "turn-down-left", "turnKeys": ("DOWN", "LEFT"),
    "turnMask": 160, "facing": 2, "faceOffset": (32768, 0),
    "names": ("normal-right-then-down-left-input", *NAMES[1:]),
}


def actions(case_id):
    case = CASES[case_id]
    return (("run-right", MAX_RUN_FRAMES, 16),
            (case.get("turnAction", "turn-down"), 18,
             case.get("turnMask", 128)))


def run_until(case_id):
    return {"kind": "actor-field", "subject": "stantler", "path": "target.x",
            "operator": "eq", "value": CASES[case_id]["runEnd"], "when": "final"}


def contract(case_id):
    _require(case_id in CASES, "unknown blocked-skid case")
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}]
            for claim, name in zip(CLAIMS, CASES[case_id].get("names", NAMES))}


def _require(ok, reason):
    if not ok:
        raise ValueError("mounted skid obstacle: " + reason)


def _actor(sample):
    matches = [actor for actor in sample.get("actors", [])
               if actor.get("active") is True and actor.get("role") == "MOUNTED"
               and actor.get("species") == 234]
    _require(len(matches) == 1, "expected one live mounted Stantler")
    actor = matches[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1,
             "identity or mounted ownership differs")
    return actor


def _stream(rows, case_id):
    expected = actions(case_id)
    windows = {name: [] for name, _, _ in expected}
    events = []
    for row in rows:
        if row.get("phase") != "observe" or "samples" not in row:
            continue
        name = row.get("action")
        _require(name in windows
                 and row.get("completedGameFrames") == len(row["samples"]),
                 "unexpected observation action or count")
        windows[name].extend(deepcopy(row["samples"]))
        events.extend(deepcopy(row.get("events", [])))
    _require(MIN_RUN_FRAMES <= len(windows["run-right"]) <= MAX_RUN_FRAMES
             and len(windows[expected[1][0]]) == 18,
             "measured Right run or exact turn window differs")
    run_end = CASES[case_id]["runEnd"]
    _require(all(_actor(sample).get("target", {}).get("x") != run_end
                 for sample in windows["run-right"][:-1])
             and _actor(windows["run-right"][-1]).get("target", {}).get("x")
                 == run_end,
             "Right did not stop at the first completed target boundary")
    frames = [(name, sample) for name, _, _ in expected
              for sample in windows[name]]
    numbers = [sample["frame"] for _, sample in frames]
    _require(numbers == list(range(numbers[0], numbers[-1] + 1)),
             "completed frame gap or action order differs")
    _require(all(event.get("frame") in numbers for event in events),
             "native event is outside measured frames")
    return {"run-right": windows["run-right"],
            "turn-down": windows[expected[1][0]]}, frames, events


def _native(events, handle):
    return [event for event in events if event.get("kind") == "native"
            and event.get("data", {}).get("actorHandle") == handle]


def _event(native, name, frame, a, b):
    matches = [row for row in native
               if row["frame"] == frame
               and row["data"].get("event") == name
               and row["data"].get("reason") == "OK"
               and (row["data"].get("valueA"), row["data"].get("valueB"))
                   == (a, b)]
    _require(len(matches) == 1, "clear skid lacks one exact native " + name)
    return matches[0]


def _walk_receipts(events, handle, operation):
    receipts = []
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
                 "Walk receipt has wrong native call size")
        receipts.append((row, request, response))
    return receipts


def _skid_pair(sample, actor, case):
    pair = sample.get("mountedPair")
    _require(isinstance(pair, dict), "clear skid lacks the native mounted pair")
    identity = actor["engineIdentity"]
    _require(pair.get("playerPointer") == identity["anchorPointer"]
             and pair.get("mountPointer") == identity["pointer"],
             "clear skid pair is bound to another object")
    for name, raw in (("player", sample["player"]),
                      ("mount", actor["engineObject"])):
        _require(all(pair.get(name, {}).get(key) == value
                     for key, value in raw.items()),
                 "clear skid pair differs from its completed snapshot")
    pose = check_gait(pair, required=True)
    check_pair_pose(pair)
    # Keep the original facing check exact after removing only verified lean.
    _require(tuple(pair["player"]["face_" + axis]
                   - pair["mount"]["face_" + axis] - pose["lean" + axis.upper()]
                   for axis in "xz") == case.get("faceOffset", (0, -40960)),
             "mounted pair lost its facing offset")


def _measure(case, windows, frames, events):
    first = _actor(frames[0][1])
    handle, identity = first["handle"], first["subjectIdentity"]
    fingerprint, context = first["behaviorFingerprint"], frames[0][1]["context"]
    _require(context.get("mapId") == 33
             and first["logical"] == {"x": case["start"], "y": 406},
             "prepared start tile differs")
    wall_center = (589 << 16) + 0x8000
    for name, sample in frames:
        actor = _actor(sample)
        _require(sample.get("observationBoundary")
                 == "main-task-queue-completion"
                 and sample.get("fieldAvailable") is True
                 and sample.get("context") == context
                 and actor["handle"] == handle
                 and actor["subjectIdentity"] == identity
                 and actor["behaviorFingerprint"] == fingerprint,
                 "completed frame or Stantler identity differs")
        mask = 16 if name == "run-right" else case.get("turnMask", 128)
        held = sample["selector"]["heldKeys"]
        _require(sample["selector"]["rawHeld"] == held
                 and sample["selector"]["simulatedKeys"] == 0
                 and held in ((0, mask) if sample is windows[
                     "run-right" if name == "run-right" else "turn-down"][0]
                              else (mask,)),
                 "normal held-key window differs")
        player = sample["player"]
        mount = actor["engineObject"]
        _require(actor["logical"]["y"] == 406
                 and actor["logical"]["x"] <= 589
                 and player["y"] == 406 and player["x"] <= 589
                 and mount["pos_x"] <= wall_center
                 and player["pos_x"] <= wall_center
                 and (actor["motionKind"] == "NONE"
                      or (actor["target"]["y"] == 406
                          and actor["target"]["x"] <= 589)),
                 "mounted pair crossed or moved into the blocked tile")
    run_end = _actor(windows["run-right"][-1])
    # Per-subject Walk time variance can end Right on either side of the
    # rendered arrival boundary. Both still require the native Walk commit
    # below before the due skid can start.
    run_origin = {"x": case["runEnd"] - 1, "y": 406}
    run_target = {"x": case["runEnd"], "y": 406}
    arriving = (run_end["motionPhase"] == "MOVING"
                and 0 < run_end["motionElapsed"] < run_end["motionDuration"]
                and run_end["logical"] == run_origin)
    arrived = (run_end["motionPhase"] == "COMMIT_PENDING"
               and 0 < run_end["motionElapsed"] == run_end["motionDuration"]
               and run_end["logical"] == run_target)
    _require(run_end["motionKind"] == "WALK"
             and (arriving or arrived)
             and run_end["origin"] == run_origin
             and run_end["target"] == run_target,
             "Right run-up did not leave the last Walk awaiting native commit")
    skid = [(sample, _actor(sample)) for sample in windows["turn-down"]
            if _actor(sample)["motionKind"] == "SKID"]
    count = case["clearSkids"]
    _require((bool(skid) if count else not skid),
             "clear skid or blocked first tile differs")
    if count:
        _require([actor["motionElapsed"] for _, actor in skid]
                 == list(range(1, len(skid) + 1))
                 and skid[-1][1]["motionElapsed"]
                     == skid[0][1]["motionDuration"],
                 "clear skid did not complete contiguous travel")
    for index, (sample, actor) in enumerate(skid):
        _require(actor["origin"] == {"x": case["runEnd"], "y": 406}
                 and actor["target"] == {"x": 589, "y": 406}
                 and sample["player"]["facing"] == case.get("facing", 1)
                 and actor["engineObject"]["facing"] == case.get("facing", 1),
                 "clear skid did not retain its resolved facing while moving east")
        _require(sample["frame"] == skid[0][0]["frame"] + index,
                 "clear skid frames are not consecutive")
        _skid_pair(sample, actor, case)
    native = _native(events, handle["value"])
    down_start = windows["turn-down"][0]["frame"]
    run_commit = [row for row in native
                  if row["frame"] >= down_start
                  and row["data"].get("event") == "LOGICAL_COMMIT"
                  and row["data"].get("reason") == "OK"
                  and row["data"].get("valueA")
                      == run_end["commitSequence"] + 1
                  and row["data"].get("valueB") == 1]
    _require(len(run_commit) == 1,
             "in-flight Right Walk did not commit before the turn skid")
    due = [(row, response) for row, _, response in
           _walk_receipts(events, handle["value"], 1)
           if row["frame"] >= run_commit[0]["frame"]
           and response[16] == 2 and response[11] == 2
           and response[17] == 3 and response[18] == case.get("facing", 1)
           and (response[20] & 2) != 0]
    _require(len(due) == 1,
             "Down did not produce one due two-tile east skid")
    starts_result = [(row, request, response) for row, request, response in
                     _walk_receipts(events, handle["value"], 2)
                     if row["frame"] >= due[0][0]["frame"]
                     and (request[20] & 2) != 0]
    _require([response[15] for _, _, response in starts_result]
             == ([1, 2] if count else [2]),
             "skid admission did not accept clear tiles then block at wall")
    finish_frame = None
    finish_sequence = None
    if count:
        start, start_actor = skid[0]
        finish_frame = skid[-1][0]["frame"] + 1
        commit = start_actor["commitSequence"] + 1
        _event(native, "MOTION_STARTED", start["frame"], 4,
               start_actor["motionDuration"])
        _event(native, "LOGICAL_COMMIT", finish_frame, commit, 4)
        _event(native, "MOTION_FINISHED", finish_frame, commit, 4)
        returned = _event(native, "CONTROL_RETURNED", finish_frame, 1, commit)
        finish_sequence = returned["data"]["sequence"]
    starts = [row for row in native
              if row["data"].get("event") == "MOTION_STARTED"
              and row["data"].get("valueA") == 4
              and row["frame"] >= down_start]
    _require(len(starts) == count
             and not any(row["data"].get("event") == "MOTION_CANCELED"
                         and row["frame"] >= down_start for row in native),
             "blocked skid started extra or canceled motion")
    crashes = [row for row in native
               if row["data"].get("event") == "WORLD_EFFECT"
               and row["data"].get("reason") == "OK"
               and row["data"].get("valueA") == 3
               and row["frame"] >= down_start]
    _require(crashes, "first blocked skid tile did not Crash")
    _require(crashes[0]["frame"] >= starts_result[-1][0]["frame"],
             "Crash preceded the blocked skid admission")
    if count:
        _require(all(row["frame"] > finish_frame
                     or (row["frame"] == finish_frame
                         and row["data"].get("sequence", 0) > finish_sequence)
                     for row in crashes),
                 "Crash preceded the clear skid commit and control return")
    expected_commit = run_end["commitSequence"] + 1 + count
    def stopped(actor):
        return (actor["logical"] == {"x": 589, "y": 406}
                and actor["commitSequence"] == expected_commit
                and actor["motionKind"] == "NONE"
                and actor["motionPhase"] == "IDLE"
                and actor["movementPolicy"]["pending"] == 0
                and actor["movementPolicy"]["speed"] == 0
                and actor["inputOwnership"] == 1)
    tail = [sample for sample in windows["turn-down"]
            if sample["frame"] >= crashes[0]["frame"]]
    _require(tail and stopped(_actor(tail[0])),
             "Crash did not stop at the last clear tile and return control")
    recovery = [sample for sample in tail if not stopped(_actor(sample))]
    _require(bool(recovery) == (case.get("turnMask") == 160),
             "held two-key input did not resume ordinary movement after Crash")
    if recovery:
        _require(case.get("turnMask") == 160,
                 "unexpected movement after blocked Crash")
        start = recovery[0]["frame"]
        _require([sample["frame"] for sample in recovery]
                 == list(range(start, tail[-1]["frame"] + 1)),
                 "held recovery Walk silently returned idle before completion")
        _require(start > crashes[0]["frame"]
                 and stopped(_actor(next(sample for sample in tail
                                         if sample["frame"] == start - 1))),
                 "held recovery Walk lacks the prior idle Crash boundary")
        for sample in recovery:
            actor = _actor(sample)
            _require(actor["logical"] == {"x": 589, "y": 406}
                     and actor["origin"] == {"x": 589, "y": 406}
                     and actor["target"] == {"x": 588, "y": 406}
                     and actor["commitSequence"] == expected_commit
                     and actor["motionKind"] == "WALK"
                     and actor["motionPhase"] == "MOVING"
                     and actor["motionElapsed"] == sample["frame"] - start + 1
                     and 0 < actor["motionElapsed"] < actor["motionDuration"]
                     and actor["movementPolicy"]["pending"] == 2
                     and actor["movementPolicy"]["direction"] == 2
                     and sample["player"]["facing"] == actor["engineObject"]["facing"] == 2
                     and actor["inputOwnership"] == 1,
                     "held recovery did not start one normal West Walk away from wall")
        _event(native, "MOTION_STARTED", start, 1,
               _actor(recovery[0])["motionDuration"])
        duration = _actor(recovery[0])["motionDuration"]
        inputs = [(request, response) for row, request, response in
                  _walk_receipts(events, handle["value"], 1)
                  if row["frame"] == start and request[10] == 2
                  and response[16:21] == bytes((2, 2, 2, duration, 9))]
        admissions = [(request, response) for row, request, response in
                      _walk_receipts(events, handle["value"], 2)
                      if row["frame"] == start and response[15] == 1
                      and request[17:21] == bytes((2, 2, duration, 9))]
        _require(len(inputs) == len(admissions) == 1,
                 "held recovery lacks native ordinary West Walk admission")
    _require(len([row for row in native
                  if row["frame"] >= crashes[0]["frame"]
                  and row["data"].get("event") == "MOTION_STARTED"
                  and row["data"].get("valueA") == 1]) == int(bool(recovery)),
             "Crash recovery started extra ordinary Walks")
    return {"values": dict.fromkeys(case.get("names", NAMES), 1), "actorHandle": handle,
            "subjectIdentity": identity, "clearSkidFrames": [s["frame"] for s, _ in skid],
            "firstCrashFrame": crashes[0]["frame"], "blockedTile": [590, 406],
            "idleCrashFrame": tail[0]["frame"],
            "heldRecoveryFrame": recovery[0]["frame"] if recovery else None}


def _fault(case, windows, events, fault):
    _require(fault in case["faults"], "unknown copied-data control")
    turn = windows["turn-down"]
    skid = [(sample, _actor(sample)) for sample in turn
            if _actor(sample)["motionKind"] == "SKID"]
    if fault == "wrong-actor":
        _actor(windows["run-right"][0])["subjectIdentity"] ^= 1
    elif fault == "wrong-input":
        turn[0]["selector"]["heldKeys"] = 16
    elif fault in ("missing-due-skid", "missing-blocked-admission"):
        operation = 1 if fault == "missing-due-skid" else 2
        receipts = [row for row in events
                    if row.get("kind") == "native-observation"
                    and row.get("data", {}).get("observation") == "walk-policy"
                    and row["data"].get("operation") == operation
                    and row["frame"] >= turn[0]["frame"]]
        if operation == 1:
            receipts = [row for row in receipts
                        if (response := bytes.fromhex(row["data"]["responseHex"]))[16] == 2
                        and response[11] == 2 and response[17] == 3
                        and response[18] == case.get("facing", 1)
                        and response[20] & 2]
        else:
            receipts = [row for row in receipts
                        if bytes.fromhex(row["data"]["requestHex"])[20] & 2
                        and bytes.fromhex(row["data"]["responseHex"])[15] == 2]
        _require(len(receipts) == 1, "copied control lacks one exact skid Walk receipt")
        receipt = receipts[0]
        response = bytearray.fromhex(receipt["data"]["responseHex"])
        if operation == 1:
            response[20] &= ~2
        else:
            response[15] = 1
        receipt["data"]["responseHex"] = response.hex()
    elif fault == "missing-clear-skid":
        _require(skid, "copied control lacks clear skid")
        skid[0][1]["motionKind"] = "NONE"
    elif fault == "phantom-skid":
        _actor(turn[0])["motionKind"] = "SKID"
    elif fault == "missing-commit":
        commit = next((row for row in events
                       if row.get("data", {}).get("event") == "LOGICAL_COMMIT"
                       and row["data"].get("valueB") == 4
                       and row["frame"] >= turn[0]["frame"]), None)
        _require(commit is not None, "copied control lacks clear skid commit")
        commit["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
    elif fault in ("missing-crash", "early-crash"):
        crashes = [row for row in events
                   if row.get("data", {}).get("event") == "WORLD_EFFECT"
                   and row["data"].get("valueA") == 3]
        _require(crashes, "copied control lacks blocked Crash")
        for row in crashes:
            if fault == "missing-crash":
                row["data"]["event"] = "REMOVED_WORLD_EFFECT"
            else:
                _require(skid, "early-Crash control lacks clear skid")
                row["frame"] = skid[0][0]["frame"]
                row["data"]["sequence"] = 0
    elif fault == "wall-cross":
        _actor(turn[-1])["logical"]["x"] = 590
    elif fault == "missing-control":
        crash_frame = min(row["frame"] for row in events
                          if row.get("data", {}).get("event") == "WORLD_EFFECT"
                          and row["data"].get("valueA") == 3)
        for sample in turn:
            if sample["frame"] >= crash_frame and _actor(sample)["motionKind"] == "NONE":
                _actor(sample)["movementPolicy"]["pending"] = 1
    elif fault in ("missing-gait", "wrong-gait-owner", "wrong-gait-pose",
                   "wrong-gait-stamp", "wrong-pair-pointer", "wrong-seat", "wrong-height"):
        _require(skid, "copied gait control lacks a clear skid")
        sample, actor = skid[0]
        pair = sample["mountedPair"]
        if fault == "missing-gait":
            pair.pop("gait", None)
        elif fault == "wrong-gait-owner":
            pair["gait"]["owner"] ^= 4
        elif fault == "wrong-gait-pose":
            pair["gait"]["pose"]["leanX"] += 1
        elif fault == "wrong-gait-stamp":
            pair["gait"]["stamp"] += 1
        elif fault == "wrong-pair-pointer":
            pair["mountPointer"] ^= 4
        else:
            key = "face_x" if fault == "wrong-seat" else "unk88_y"
            # Preserve the same-snapshot binding: the actual pose must fail.
            sample["player"][key] += 1
            pair["player"][key] += 1
    elif fault in ("wrong-recovery", "missing-recovery-start", "missing-recovery-admission"):
        crash_frame = min(row["frame"] for row in events
                          if row.get("data", {}).get("event") == "WORLD_EFFECT"
                          and row["data"].get("valueA") == 3)
        recovery = next(sample for sample in turn
                        if sample["frame"] > crash_frame
                        and _actor(sample)["motionKind"] == "WALK")
        if fault == "wrong-recovery":
            _actor(recovery)["target"]["x"] = 589
        elif fault == "missing-recovery-start":
            event = next(row for row in events if row["frame"] == recovery["frame"]
                         and row.get("data", {}).get("event") == "MOTION_STARTED"
                         and row["data"].get("valueA") == 1)
            event["data"]["event"] = "REMOVED_RECOVERY_START"
        else:
            event = next(row for row in events if row["frame"] == recovery["frame"]
                         and row.get("data", {}).get("observation") == "walk-policy"
                         and row["data"].get("operation") == 2)
            response = bytearray.fromhex(event["data"]["responseHex"])
            response[15] = 2
            event["data"]["responseHex"] = response.hex()
    return True


def run(rows, test, fault=None):
    applied = False
    try:
        case_id = test.get("id")
        _require(case_id in CASES, "unknown blocked-skid route")
        case = CASES[case_id]
        _require([action["id"] for action in test.get("actions", [])]
                 == [name for name, _, _ in actions(case_id)]
                 and [(action["op"], action["args"])
                      for action in test["actions"]]
                    == [("step", {"frames": MAX_RUN_FRAMES,
                                   "keys": ["RIGHT"],
                                   "until": run_until(case_id)}),
                        ("step", {"frames": 18,
                                  "keys": list(case.get("turnKeys", ("DOWN",)))})],
                 "reviewed normal-input route differs")
        windows, frames, events = _stream(rows, case_id)
        applied = _fault(case, windows, events, fault) if fault else False
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(case, windows, frames, events)}
    except (ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        return {"passed": False, "faultApplied": applied,
                "failures": [str(error)]}


def negative_controls(rows, test):
    case = CASES[test["id"]]
    controls = {fault: run(rows, test, fault) for fault in case["faults"]}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          and result["failures"] for result in controls.values()),
            "controls": controls}
