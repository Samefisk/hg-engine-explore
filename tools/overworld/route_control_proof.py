"""Independent acceptance of the two live route recorder controls.

Input is the full replay report, never a compact progress report. Prepared
setup establishes identity only; none of its timing earns route credit.
"""
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.runtime_cadence import classify_frame_hitches, classify_player_motion


def require(condition, message):
    if not condition:
        raise ValueError("live route proof: " + message)


def number(value, low=0, high=0xFFFFFFFFFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def identity(a, b):
    return isinstance(a, dict) and isinstance(b, dict) and all(
        a.get(k) == b.get(k) for k in ("handle", "species", "role", "subjectIdentity"))


def cpu(values):
    require(isinstance(values, list) and 16 <= len(values) <= 192120, "missing bounded CPU samples")
    for value in values:
        number(value, 1)
    return classify_frame_hitches(values, 2000, 250000)


def route_control_measurements(measurement, manifest):
    """Return the two original registry rows, or raise ValueError on any gap."""
    try:
        return _measurements(measurement, manifest)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("live route proof: incomplete evidence") from error


def _measurements(m, manifest):
    require(m.get("passed") is True and m.get("ready") is True and m.get("failures") == [],
            "replay did not finish cleanly")
    subject = m["subject"]
    require(subject.get("species") == 155 and subject.get("role") == "FOLLOWER"
            and type(subject.get("subjectIdentity")) is int
            and subject["subjectIdentity"] == 2046726716
            and subject.get("identityVerified") is True, "wrong saved follower")
    b = m["baseline"]
    require(identity(b["subject"], subject) and b.get("fixtureMode") == "prepared"
            and b.get("controlBaselinePassed") is True and b.get("failures") == []
            and b.get("evidenceGaps") == [], "invalid baseline")
    require(number(b["playerMotions"]) >= 4 and number(b["followerMotions"]) >= 1
            and b.get("heldFirstThree") is True and number(b["heldMultiTileSegments"]) >= 1,
            "baseline lacks held first-three player motion")
    baseline_cpu = cpu(b["cpuSamples"])
    require(baseline_cpu == b["cpu"] and baseline_cpu["hitchCount"] == 0, "baseline CPU hitch")
    settled = b["settledSnapshot"]
    actor = select_current_actor(settled, subject)
    actual = next(a for a in settled["actors"] if identity(a, actor))
    require(actual["motionPhase"] == "IDLE" and actual["motionKind"] == "NONE"
            and actual["crashPresentation"].get("known") is True
            and actual["crashPresentation"].get("timer") == 0, "baseline not settled")
    mon = settled["party"][1]
    require(all(mon.get(k) == v for k, v in {"slot": 1, "species": 155, "personality": 2046726716,
            "form": 0, "level": 6, "status": 0}.items()) and mon.get("identityVerified") is True
            and mon.get("isEgg") is False and number(mon["hp"], 1) == mon["maxHp"], "saved party readback differs")
    require(any(g.get("slot") == 1 and g.get("field") == "hp" and g.get("passed") is True
            and g.get("personality") == mon["personality"] and g.get("species") == 155
            and g.get("native") == g.get("decoded") == mon["hp"]
            for g in settled["partyObservation"]["nativeGetterChecks"]), "native HP readback is absent")
    require(len(b["motionTail"]) >= 4 and all(row.get("reachedTarget") is True
            and all(row.get(k) == 0 for k in ("acceptanceStall", "startStall", "interiorStalls",
                "renderRegressions", "settleStall")) for row in b["motionTail"]), "baseline player completion differs")
    prepared = b["preparedSetup"]
    require([p["command"] for p in prepared] == ["party", "spawn"], "prepared operations differ")
    spawn = prepared[1]["receipt"]
    require(spawn.get("preparedOnly") is True and spawn.get("requestedSubject") == {
        "slot": 1, "species": 155, "role": "FOLLOWER", "personality": 2046726716,
        "form": 0, "level": 6}, "saved source differs")
    require(identity(select_current_actor(spawn["snapshot"], subject), subject), "spawn owner differs")
    terminal = b["lastFollowerTerminal"]
    require(terminal["handle"] == subject["handle"] and terminal["frame"] <= settled["frame"],
            "follower terminal owner differs")
    events = terminal["events"]
    names = {"start": "MOTION_STARTED", "commit": "LOGICAL_COMMIT",
             "finish": "MOTION_FINISHED", "control": "CONTROL_RETURNED"}
    selected = []
    for key, name in names.items():
        require(len(events[key]) == 1, "missing follower " + key)
        row = events[key][0]
        require(row["event"] == name and row["handle"] == subject["handle"]
                and b["nativeTrace"].count(row) == 1, "follower trace differs")
        selected.append(row)
    require(selected[0]["frame"] < terminal["frame"]
            and selected[0]["valueB"] == terminal["frame"]-selected[0]["frame"]
            and all(r["frame"] == terminal["frame"] for r in selected[1:])
            and selected[1]["valueA"] == selected[2]["valueA"] == terminal["commit"]
            and selected[3]["valueA"] == 0 and selected[3]["valueB"] == terminal["commit"]
            and [r["sequence"] for r in selected] == sorted(set(r["sequence"] for r in selected)),
            "follower lifecycle differs")
    require(set(m["detections"]) == {"cpu-hitch", "player-start-stall"}, "missing exact faults")
    c = m["detections"]["cpu-hitch"]
    report = cpu(c["cpuSamples"])
    cycles = c["nativeCycles"]
    require(len(cycles) == len(c["cpuSamples"]) and all(type(v) is int for v in cycles)
            and cycles == list(range(cycles[0], cycles[0] + len(cycles))), "CPU cycle coverage differs")
    index = number(c["intervalIndex"], 0, len(cycles)-1)
    work = c["receipt"]
    require(report == c["classifier"] and report["hitchFrames"] == [index]
            and c["cpuSamples"][:len(b["cpuSamples"])] == b["cpuSamples"]
            and c["nativeCycle"] == cycles[index] == work["targetNativeCycle"]
            and work["nativeCycleBefore"] == work["nativeCycle"] == c["nativeCycle"]-1
            and c["cpuNs"] == c["cpuSamples"][index]
            and number(work["workEndCpuNs"])-number(work["workStartCpuNs"])
                == number(work["workCpuNs"], 100000000, 2000000000)
            and c["cpuNs"] >= work["workCpuNs"], "CPU fault is not its exact measured cycle")
    p = m["detections"]["player-start-stall"]
    step, admission, pins = p["motion"], p["admission"], p["pins"]
    report = classify_player_motion(step["samples"], step["start"], step["targetRender"],
        maximum_acceptance_frames=2, maximum_start_frames=2, maximum_settle_frames=4)
    require(report == p["classifier"] and report["startStall"] == 1
            and report["reachedTarget"] is False and not any(report[k] for k in
                ("acceptanceStall", "renderRegressions", "interiorStalls"))
            and step["callbacks"] == 1 and step["accepted"] is True, "wrong player failure")
    native = admission["admission"]
    require(native["origin"] == step["origin"] and native["target"] == step["target"]
            and native["objectPointer"] == admission["playerPointer"]
            and admission["pinned"] == step["start"] ==
                [native["objectBefore"]["pos_x"], native["objectBefore"]["pos_z"]]
            and all(s["render"] == step["start"] for s in step["samples"]), "pin is not the admitted step")
    require(4 <= len(pins) <= 120 and len(pins) == sum(s["accepted"] is True for s in step["samples"])
            and [r["frame"] for r in pins] == list(range(p["admissionFrame"], p["frame"]+1))
            and pins[0]["frame"] >= step["startFrame"], "pin frame coverage differs")
    for i, pin in enumerate(pins):
        require(pin["action"] == "player-pinned" and pin["writeIndex"] == i+1
                and pin["after"] == step["start"] and pin["nativeCycle"] > c["nativeCycle"]
                and (not i or pin["nativeCycle"] >= pins[i-1]["nativeCycle"]), "pin sequence differs")
    cleanup = m["cleanup"]
    require(cleanup == manifest.get("observerControlCleanup") and cleanup["closed"] is True
            and cleanup.get("advancedFrames") == 0 and cleanup.get("released") is True
            and cleanup["frame"] == p["frame"] == cleanup["snapshot"]["frame"]
            and cleanup["snapshot"]["nativeCycle"] == pins[-1]["nativeCycle"], "cleanup boundary differs")
    control = cleanup["routeControl"]
    history = m["receipts"]
    require([r["action"] for r in history] == ["armed", "cpu-work", "armed", "player-admitted"]
            + ["player-pinned"]*len(pins) + ["closed"], "native intervention history differs")
    require(control["type"] == "native-route-control-v1" and control["state"] == "closed"
            and control["failure"] is None and control["closed"] is True
            and control["requiresCoreClose"] is True and control["receipts"] == history
            and history[-1]["action"] == "closed" and history[-1]["requiresCoreClose"] is True
            and history[-1]["frame"] == p["frame"] and history.count(work) == 1
            and history.count(admission) == 1 and all(history.count(pin) == 1 for pin in pins),
            "cleanup does not close the exact faults")
    require(identity(control["subject"], subject), "cleanup subject differs")
    for row in history:
        require(identity(row["subject"], subject) and row["context"] == step["inputContext"]
                and row["playerPointer"] == admission["playerPointer"]
                and row["playerManager"] == admission["playerManager"], "fault owner differs")
    return [{"claim": claim, "name": name, "value": value, "operator": "eq",
             "threshold": value, "passed": True} for claim, name, value in (
        ("live-actor-identity", "live-route-recorder-baseline-identity", 1),
        ("controlled-action", "live-route-recorder-baseline-and-faults", [1, 1, 1]))]
