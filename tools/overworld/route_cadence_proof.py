"""Full-route acceptance, separate from prepared setup and recorder calibration.

The caller must independently replay the dense retained stream and authenticate
its manifest/cleanup. This module checks the resulting full evidence report.
"""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_crash_measurement import CrashPresentationMeasurement
from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.runtime_cadence import classify_frame_hitches


LIMITS = dict(activeFrames=5000, tiles=80, cells=3, maps=2, followerMotions=16,
              inputFrames=2, renderStartFrames=2, settleFrames=4,
              cpuRatioPerMille=2000, cpuExtraNs=250000)
RULES = (
    ("live-actor-identity", "normal-route-follower-identity-samples", "gte", 1),
    ("natural-input", "normal-route-active-frames", "gte", 5000),
    ("natural-input", "normal-route-distinct-cells", "gte", 3),
    ("natural-input", "normal-route-distinct-maps", "gte", 2),
    ("natural-input", "normal-route-distinct-tiles", "gte", 80),
    ("logical-commit", "normal-route-player-errors", "eq", 0),
    ("rendered-motion", "normal-route-follower-render-errors", "eq", 0),
    ("rendered-motion", "normal-route-complete-follower-motions", "gte", 16),
    ("control-release", "normal-route-actor-frame-gaps", "eq", 0),
    ("host-cpu-pacing", "normal-route-process-cpu-hitches", "eq", 0))


def require(ok, reason):
    if not ok:
        raise ValueError("full route proof: " + reason)


def number(value, low=0, high=0xFFFFFFFFFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def terminal(proof, handle):
    require(proof["handle"] == handle, "terminal owner differs")
    groups = proof["events"]
    names = {"start":"MOTION_STARTED", "commit":"LOGICAL_COMMIT",
             "finish":"MOTION_FINISHED", "control":"CONTROL_RETURNED"}
    rows = []
    for key, name in names.items():
        require(len(groups[key]) == 1, "missing full follower " + key)
        row = groups[key][0]
        require(row["handle"] == handle and row["event"] == name, "terminal meaning differs")
        rows.append(row)
    require(rows[0]["frame"] < proof["frame"]
            and rows[0]["valueB"] == proof["frame"]-rows[0]["frame"]
            and all(r["frame"] == proof["frame"] for r in rows[1:])
            and rows[1]["valueA"] == rows[2]["valueA"] == proof["commit"]
            and rows[3]["valueA"] == 0 and rows[3]["valueB"] == proof["commit"]
            and all(a["sequence"] < b["sequence"] for a,b in zip(rows,rows[1:])),
            "incomplete follower lifecycle")


def cadence_measurements(measurement, *, include_host_cpu=True):
    """Return the unchanged route rows, or ValueError on missing proof.

    The historical route requires the host CPU row. The current game-cadence
    adapter uses the same physical checks and retained CPU diagnostics, but
    deliberately omits that host-owned row from its accepted claims.
    """
    try:
        return _measurements(measurement, include_host_cpu=include_host_cpu)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("full route proof: incomplete evidence") from error


def _measurements(m, *, include_host_cpu=True):
    require(m.get("state") == "passed" and m.get("passed") is True and m.get("ready") is True
            and m.get("failures") == [] and m.get("evidenceGaps") == [], "replay is incomplete")
    require(m["limits"] == LIMITS, "original limits changed")
    active = number(m["activeMovementFrames"], 5000, 65535)
    observed = number(m["observedFrames"], active, 65535)
    number(m["sampledFrames"], observed, 65535)
    require(set(m["terminalState"]) == {"playerInFlight", "playerCollisionWaitPending", "followerInFlight",
            "crashPresentationPending", "setupTransitionPending"}
            and all(v is False for v in m["terminalState"].values()), "pending terminal work")
    tiles, cells = m["routeTiles"], m["routeCells"]
    for points, floor in ((tiles,80),(cells,3)):
        require(isinstance(points,list) and floor <= len(points) <= 131070, "route geometry floor")
        for point in points:
            require(isinstance(point,list) and len(point) == 2, "invalid route point")
            for coordinate in point: number(coordinate, 0, 32767)
        require(len({tuple(p) for p in points}) == len(points), "duplicate route geometry")
    require({(x//32,z//32) for x,z in tiles} == {tuple(c) for c in cells}
            and len(tiles) == number(m["distinctTiles"])
            and len(cells) == number(m["streamingCells"]), "geometry counts differ")
    maps = m["maps"]
    require(isinstance(maps,list) and len(maps) >= 2 and maps == sorted(set(maps)), "map floor")
    for map_id in maps: number(map_id, 0, 539)
    player_motions = number(m["playerMotions"], 4, observed)
    follower_motions = number(m["followerMotions"], 16, observed)
    for field in ("heldMultiTileSegments", "heldCellCrossings", "heldMapCrossings"):
        number(m[field], 1, player_motions)
    values = m["cpuSamples"]
    require(isinstance(values,list) and 16 <= len(values) <= 393210
            and len(values) == number(m["routeNativeCycles"])
            and len(values) <= number(m["nativeCycles"]), "native CPU coverage differs")
    for value in values: number(value, 1)
    cpu = classify_frame_hitches(values, 2000, 250000)
    require(cpu == m["cpu"], "actual route CPU classifier differs")
    if include_host_cpu:
        require(cpu["hitchCount"] == 0, "actual route CPU hitch")
    subject, snapshot = m["subject"], m["settledSnapshot"]
    require(subject.get("role") == "FOLLOWER" and subject.get("species") == 155
            and subject.get("identityVerified") is True, "wrong subject")
    current = select_current_actor(snapshot, subject)
    actor = next(a for a in snapshot["actors"] if a["handle"] == current["handle"])
    require(not any(a.get("active") is True and a.get("role") == "MOUNTED" for a in snapshot["actors"])
            and actor["motionPhase"] == "IDLE" and actor["motionKind"] == "NONE"
            and actor["reservationId"] == actor["inputOwnership"] == 0, "not an idle unmounted follower")
    crash = actor["crashPresentation"]
    require(crash.get("known") is True and crash.get("timer") == 0
            and crash.get("frame") == snapshot["frame"] and crash.get("nativeCycle") == snapshot["nativeCycle"]
            and crash.get("handle") == subject["handle"], "active or stale crash state")
    player = snapshot["player"]
    require(player_settled_at(snapshot, snapshot["context"]["mapId"], player["x"], player["y"]),
            "player not settled")
    require(number(snapshot["frame"])-number(m["setup"]["bound"]) == observed,
            "route is not one dense bound observation window")
    require(snapshot.get("routeControl") is None, "live fault used in normal route")
    mon = snapshot["party"][1]
    require(mon.get("slot") == 1 and mon.get("species") == 155
            and mon.get("personality") == subject["subjectIdentity"]
            and mon.get("identityVerified") is True and mon.get("isEgg") is False
            and number(mon["hp"], 1) <= number(mon["maxHp"], 1) and mon.get("status") == 0,
            "saved party identity or eligibility differs")
    require(any(g.get("slot") == 1 and g.get("field") == "hp" and g.get("passed") is True
            and g.get("personality") == subject["subjectIdentity"] and g.get("species") == 155
            and g.get("native") == g.get("decoded") == mon["hp"]
            and g.get("boundary") == "natural-GetMonData-return"
            for g in snapshot["partyObservation"]["nativeGetterChecks"]), "missing native HP readback")
    if m["fixtureMode"] == "prepared":
        require([c["command"] for c in m["preparedSetup"]] == ["party","spawn"], "prepared setup differs")
        spawn = m["preparedSetup"][-1]["receipt"]
        requested = spawn["requestedSubject"]
        require(requested == dict(slot=1, species=155, role="FOLLOWER", personality=subject["subjectIdentity"],
                form=0, level=6) and subject["subjectIdentity"] == 2046726716
                and spawn.get("preparedOnly") is True, "wrong saved prepared subject")
    else:
        require(m["fixtureMode"] == "normal" and not m["preparedSetup"]
                and m["setup"].get("confirmed") is not None
                and (m["setup"].get("initialEligible") is True
                     or all(m["setup"].get(k) is not None for k in ("healed","exitedCenter"))),
                "normal setup evidence missing")
    require(1 <= len(m["motionTail"]) <= 16, "missing player completion tail")
    for row in m["motionTail"]:
        require(row["reachedTarget"] is True and all(row[k] == 0 for k in
            ("acceptanceStall","startStall","interiorStalls","renderRegressions","settleStall")),
            "player completion error")
    terminal(m["lastFollowerTerminal"], subject["handle"])
    require(m["lastFollowerTerminal"]["frame"] <= snapshot["frame"], "future terminal")
    require(isinstance(m["handoffs"],list) and m["handoffs"], "missing field rebind")
    previous = None
    for h in m["handoffs"]:
        before, after = h["before"], h["after"]
        old, new = before["handle"], after["handle"]
        require(all(before[k] == after[k] == subject[k] for k in ("species","role","subjectIdentity"))
                and all(old[k] == new[k] for k in ("value","slot","generation","encounterGeneration"))
                and all(new[k] == old[k]%65535+1 for k in ("fieldEpoch","mapGeneration"))
                and (previous is None or old == previous), "rebind identity chain differs")
        event, rebound = h["context"], h["rebound"]
        require(event["event"] == "CONTEXT_CHANGED" and rebound["event"] == "ACTOR_REBOUND"
                and event["handle"] == old and rebound["handle"] == new
                and event["valueA"] == old["fieldEpoch"] and event["valueB"] == new["fieldEpoch"]
                and event["frame"] == rebound["frame"] and event["sequence"] < rebound["sequence"]
                and rebound["valueA"] in maps and rebound["valueB"] in maps
                and rebound["valueA"] != rebound["valueB"], "native rebind receipt differs")
        if h.get("oldTerminal") is not None:
            terminal(h["oldTerminal"], old)
            require(h["oldTerminal"]["frame"] < rebound["frame"], "old terminal is not before rebind")
        if "canceledMotion" in h:
            canceled = h["canceledMotion"]
            require(canceled["cancel"]["event"] == "MOTION_CANCELED"
                    and canceled["control"]["event"] == "CONTROL_RETURNED"
                    and canceled["cancel"]["frame"] == event["frame"] == canceled["control"]["frame"]
                    and canceled["cancel"]["handle"] == old == canceled["control"]["handle"]
                    and canceled["cancel"]["sequence"] < canceled["control"]["sequence"] < event["sequence"],
                    "cancel lacks native terminal")
            canceled_actor = canceled["terminal"]["actor"]
            UnmountedCadenceMeasurement._canceled_follower_pose(canceled_actor)
            require(canceled["terminal"]["frame"] == event["frame"]
                    and canceled_actor["motionPhase"] == "CANCELED"
                    and canceled_actor["commitSequence"] == canceled["motion"]["commitBefore"]
                    and canceled["cancel"]["valueB"] == canceled["control"]["valueB"] == canceled_actor["commitSequence"],
                    "canceled motion gained commit credit")
            terminal(h["recoveryTerminal"], new)
            require(h["recoveryTerminal"]["events"]["start"][0]["frame"] > rebound["frame"],
                    "recovery is not later normal motion")
        else:
            require(h.get("oldTerminal") is not None, "idle rebind lacks old terminal")
        previous = new
    require(previous == subject["handle"], "final rebind is not current")
    for proof in m["crashPresentations"]:
        check_crash_proof(proof, m["handoffs"])
    values = (observed, active, len(cells), len(maps), len(tiles), 0, 0, follower_motions, 0, cpu["hitchCount"])
    rules = RULES if include_host_cpu else RULES[:-1]
    return [dict(claim=claim, name=name, value=value, operator=op, threshold=limit, passed=True)
            for (claim,name,op,limit),value in zip(rules, values)]


def game_cadence_measurements(measurement):
    """Return the nine gameplay rows; host CPU remains diagnostic only."""
    return cadence_measurements(measurement, include_host_cpu=False)


def check_crash_proof(proof, handoffs):
    """Rebuild one effect from raw poses; a map change alone grants no credit."""
    checker = CrashPresentationMeasurement()
    old = proof["previousActor"]
    if proof.get("preRollFrame") is not None:
        before = proof.get("preRollPreviousActor")
        require(before is not None, "crash pre-roll lacks its preceding actor")
        baseline = dict(frame=proof["preRollFrame"]-1,
                        nativeCycle=before["crashPresentation"]["nativeCycle"],
                        context=proof["context"])
        checker.observe(baseline, before, None)
    prior = dict(frame=proof["startFrame"]-1, nativeCycle=old["crashPresentation"]["nativeCycle"], context=proof["context"])
    checker.observe(prior, old, proof.get("preRollPreviousActor"))
    for row in proof["samples"]:
        actor_copy = deepcopy(proof["terminal"])
        actor_copy.update(crashPresentation=row["metadata"], engineObject=row["rawEngine"])
        checker.observe(dict(frame=row["frame"], nativeCycle=row["nativeCycle"], context=proof["context"]), actor_copy, old)
        old = actor_copy
    restoration = proof.get("transitionRestoration")
    if restoration is not None:
        require(any(restoration["transition"] == {"context": h["context"], "rebound": h["rebound"]}
                    for h in handoffs), "crash restoration lacks the retained handoff")
        checker.observe(restoration["snapshot"], restoration["actor"], old,
                        transition=restoration["transition"])
    require(checker.ready and checker.proofs == [proof], "crash restoration differs")
