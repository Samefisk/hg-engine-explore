"""Exact controlled Walk matrix; accepts native values, never creates samples.

The stream meter owns binding, fixture readback, raw framing and lifecycle
partitioning. Tick endpoints below are lossless views of native entry/return
reads. A native elapsed value is not a completed-frame index.
"""

LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
CASES = tuple(
    dict(index=index, duration=duration, direction=direction, keys=list(keys), mode=mode)
    for index, (duration, direction, keys, mode) in enumerate([
        *((n, 2 if n % 2 else 3, ("LEFT",) if n % 2 else ("RIGHT",), 0)
          for n in range(1, 33)),
        *((n, 4 if n % 2 else 7, ("UP", "LEFT") if n % 2 else ("DOWN", "RIGHT"), 1)
          for n in range(1, 33)),
        (5, 4, ("UP", "LEFT"), 2),
    ])
)
DURATIONS = tuple(case["duration"] for case in CASES)


def require(value, reason):
    if not value:
        raise ValueError("Walk matrix: " + reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def validate_motion(case, subject, reservation, ticks, events):
    """Validate one case and return only measurements from its actual ticks.

    Tick: {before,after}; each endpoint contains elapsed,duration,phase,subject,
    reservationId,frame,actorFrame,nativeCycle. Lifecycle rows contain event,
    reason,valueA/valueB,sequence,frame,actorFrame and subject. Event frame is
    queue delivery; tick frame is the last completed frame at native entry.
    Compare their actorFrame clocks, never these different frame boundaries.
    The caller must partition
    them by the real Actor reservation, not by guessed time windows.
    """
    require(isinstance(case, dict) and integer(case.get("index"))
            and case["index"] < len(CASES) and case == CASES[case["index"]], "case differs")
    require(isinstance(subject, dict) and bool(subject), "subject missing")
    require(integer(reservation, 1), "reservation missing")
    duration = case["duration"]
    require(isinstance(ticks, list) and len(ticks) == duration, "tick count differs")
    elapsed = []
    previous = None
    for index, tick in enumerate(ticks):
        require(isinstance(tick, dict), "tick missing")
        before, after = tick.get("before", {}), tick.get("after", {})
        for endpoint in (before, after):
            require(endpoint.get("subject") == subject
                    and type(endpoint.get("reservationId")) is int
                    and endpoint["reservationId"] == reservation, "tick owner differs")
            require(type(endpoint.get("duration")) is int and endpoint["duration"] == duration,
                    "native duration differs")
            require(all(integer(endpoint.get(k)) for k in ("elapsed", "frame", "actorFrame", "nativeCycle")),
                    "tick clock or elapsed missing")
        require(before["elapsed"] == index and after["elapsed"] == index + 1,
                "native elapsed sequence differs")
        require(before.get("phase") == "MOVING" and after.get("phase") ==
                ("COMMIT_PENDING" if index + 1 == duration else "MOVING"), "tick phase differs")
        require(after["nativeCycle"] >= before["nativeCycle"]
                and after["frame"] == before["frame"]
                and after["actorFrame"] == before["actorFrame"], "tick clock pair differs")
        if previous is not None:
            require(before["nativeCycle"] > previous["nativeCycle"]
                    and before["frame"] == previous["frame"] + 1
                    and before["actorFrame"] == previous["actorFrame"] + 1,
                    "tick cadence differs")
        elapsed.append(before["elapsed"])
        previous = after
    require(isinstance(events, list) and not any(e.get("event") == "MOTION_CANCELED" for e in events),
            "motion canceled")
    events = [event for event in events if event.get("event") in LIFECYCLE]
    require(len(events) == len(LIFECYCLE), "lifecycle count differs")
    sequence = None
    event_frame = None
    event_actor_frame = None
    for event, name in zip(events, LIFECYCLE):
        require(event.get("event") == name and event.get("reason") == "OK"
                and event.get("subject") == subject, "lifecycle identity or meaning differs")
        key = "valueA" if name == "MOTION_STARTED" else "valueB"
        require(name == "CONTROL_RETURNED" or type(event.get(key)) is int and event[key] == 1,
                "lifecycle Walk kind differs")
        require(integer(event.get("sequence"), 1) and integer(event.get("frame"))
                and integer(event.get("actorFrame"))
                and (sequence is None or event["sequence"] > sequence)
                and (event_frame is None or event["frame"] >= event_frame)
                and (event_actor_frame is None or event["actorFrame"] >= event_actor_frame),
                "lifecycle order differs")
        sequence, event_frame = event["sequence"], event["frame"]
        event_actor_frame = event["actorFrame"]
    require(events[0]["actorFrame"] <= ticks[0]["before"]["actorFrame"]
            and events[1]["actorFrame"] >= ticks[-1]["after"]["actorFrame"],
            "lifecycle tick window differs")
    return dict(duration=ticks[0]["before"]["duration"], sequence=elapsed, elapsedCount=len(elapsed))


def validate_matrix(motions, diagonal_attempt):
    """Validate all raw cases; retain the two original registry object shapes.

    Motions contain case,subject,reservation,ticks,events. The final mode-2
    gating receipt must separately prove a real cardinal request was rejected;
    that input/binding proof belongs to the stream meter.
    """
    require(isinstance(motions, list) and len(motions) == len(CASES), "matrix count differs")
    results = []
    reservations = set()
    for expected, motion in zip(CASES, motions):
        require(motion.get("case") == expected, "matrix order differs")
        result = validate_motion(**motion)
        require(motion["reservation"] not in reservations, "reservation reused")
        reservations.add(motion["reservation"])
        results.append(result)
    require(isinstance(diagonal_attempt, dict)
            and isinstance(diagonal_attempt.get("before"), list)
            and len(diagonal_attempt["before"]) == 2
            and all(type(v) is int for v in diagonal_attempt["before"])
            and diagonal_attempt.get("after") == diagonal_attempt["before"]
            and diagonal_attempt.get("mode") == "IDLE"
            and type(diagonal_attempt.get("pending")) is int and diagonal_attempt["pending"] == 0,
            "diagonal-only gating differs")
    durations = [r["duration"] for r in results]
    return dict(counts=dict(durations=durations, elapsedCounts=[r["elapsedCount"] for r in results],
                           diagonalAttempt=diagonal_attempt),
                elapsed=dict(durations=durations, sequences=[r["sequence"] for r in results]))
