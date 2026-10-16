"""Finite cache-continuity witnesses over the existing sealed Cargo Tick tap.

This consumes observations only. It never grants route or movement admission.
The Throw meters still own actor/profile identity and complete motion/launch.
"""
from copy import deepcopy
import struct


def need(ok, reason):
    if not ok:
        raise ValueError("Cargo route continuity: " + reason)


def packets(sample, events, actor, image, previous_cycle=None, *, pending_ok=False):
    result = []
    for event in events:
        data = event.get("data", {})
        if event.get("kind") != "native-observation" or data.get("observation") != "throw-cargo-query" \
                or data.get("slot") != actor["handle"]["slot"]:
            continue
        identity = data.get("imageIdentity", {})
        # A Tick can cross VBlank while one field update remains in flight.
        # It must still start and finish in this completed sample interval.
        need(event.get("frame") == sample["frame"]
             and data.get("entryActorFrame") == data.get("returnActorFrame") == sample["actorFrame"]
             and type(data.get("returnNativeCycle")) is int
             and data.get("entryNativeCycle", 0) <= data["returnNativeCycle"]
             and type(data.get("entryNativeCycle")) is int
             and (sample["nativeCycle"]-1 if previous_cycle is None else previous_cycle) < data["entryNativeCycle"] <= data["returnNativeCycle"] <= sample["nativeCycle"]
             and data.get("subject") == actor["handle"]
             and data.get("boundary") == "native-cargo-tick-return"
             and all(identity.get(k) == image[k] for k in ("elfSha256", "packageSha256"))
             and type(identity.get("loadedEntry")) is int and identity["loadedEntry"] > 0
             and type(identity.get("tickEntry")) is int and identity["tickEntry"] > identity["loadedEntry"]
             and len(bytes.fromhex(identity.get("loaderOwner", ""))) == 28,
             "native query owner, clock or sealed image differs")
        raw = bytes.fromhex(data["resultHex"])
        after = data["after"]; workspace = after.get("workspace")
        if workspace is None and after.get("queryPointer") == 0:
            need(len(raw) == 140 and data.get("returnValue") == data.get("resultStatus") == raw[138] == 0
                 and data.get("status") == "PENDING" and after.get("frameValid") is True
                 and after.get("worldFrame") == sample["actorFrame"]
                 and after.get("subject") == after.get("worldSubject") == actor["handle"],
                 "unprepared query does not have a current Pending result")
            continue
        # An ordinary follow approach may be waiting for startup/streaming
        # or a current moving-target route. Authenticate Pending but grant no
        # graph credit until this Tick actually updated the resident state.
        if pending_ok and len(raw) == 140 and isinstance(workspace, dict) and raw[138] == 0 \
                and (workspace.get("nodeCount") == 0 or workspace.get("stateFrame") != sample["actorFrame"]):
            need(len(raw) == 140 and data.get("returnValue") == data.get("resultStatus") == 0
                 and data.get("status") == "PENDING" and after.get("frameValid") is True
                 and after.get("worldFrame") == sample["actorFrame"]
                 and after.get("subject") == after.get("worldSubject") == actor["handle"]
                 and workspace.get("owner") == actor["handle"] and workspace.get("ownerCurrent") is True
                 and workspace.get("valid") is True and workspace.get("stateSubject") == actor["handle"],
                 "deferred query is not current Pending")
            need(struct.unpack_from("<H", raw, 124)[0] <= 16 and raw[127]+raw[128] <= 1,
                 "native query exceeded its existing work budget")
            if workspace.get("stateFrame") == sample["actorFrame"]:
                need(raw[108:136].hex() == workspace.get("lastWorkHex"), "deferred query work differs")
            # A just-cleared current graph still exposes its current policy;
            # an untouched old workspace during a scope defer does not.
            if workspace.get("stateFrame") == sample["actorFrame"]:
                result.append(dict(frame=sample["frame"], actorFrame=sample["actorFrame"],
                    sequence=data["sequence"], status="PENDING", hasNextStep=False,
                    queryPointer=after["queryPointer"], workspace=deepcopy(workspace),
                    before=deepcopy(data["before"].get("workspace"))))
            continue
        need(len(raw) == 140 and data.get("returnValue") in (0, 1)
             and data.get("resultStatus") == raw[138] == data["returnValue"]
             and data.get("status") == ("PENDING", "REACHABLE")[raw[138]]
             and isinstance(workspace, dict) and workspace.get("owner") == actor["handle"]
             and workspace.get("ownerCurrent") is True and workspace.get("valid") is True
             and workspace.get("stateSubject") == actor["handle"]
             and after.get("subject") == after.get("worldSubject") == actor["handle"]
             and after.get("frameValid") is True and after.get("worldFrame") == sample["actorFrame"]
             and type(after.get("queryPointer")) is int and after["queryPointer"] > 0
             and workspace.get("stateFrame") == sample["actorFrame"]
             and 1 <= workspace.get("nodeCount", 0) <= 256,
             "native query result or current workspace differs")
        work = raw[108:136]
        need(work.hex() == workspace.get("lastWorkHex")
             and struct.unpack_from("<H", work, 16)[0] <= 16
             and work[19] + work[20] <= 1,
             "native query exceeded its existing work budget")
        need(workspace["origin"]["x"] == actor["engineObject"]["x"]
             and workspace["origin"]["y"] == actor["engineObject"]["y"],
             "native query origin differs from current owner")
        result.append(dict(frame=sample["frame"], actorFrame=sample["actorFrame"],
            sequence=data["sequence"], status=data["status"], hasNextStep=bool(raw[105]),
            queryPointer=after["queryPointer"], workspace=deepcopy(workspace),
            before=deepcopy(data["before"].get("workspace"))))
    return result


def same_graph(baseline, current, *, allow_reset=False):
    """Owner, static context and policy always stay current.

    Wild nearest-Cargo ranking (TKT-0051) restarts the graph on each target
    check, so Wild callers pass allow_reset; the TKT-0041 no-reset rule is
    outdated there. Follower routes still keep their graph.
    """
    for stage in (current.get("before"), current["workspace"]):
        need(isinstance(stage, dict) and stage.get("owner") == baseline["workspace"]["owner"],
             "route workspace owner changed")
        a, b = baseline["workspace"]["compatibility"], stage["compatibility"]
        need(all(a[k] == b[k] for k in ("cargo", "bounds", "scopeRevision", "edges", "edgeCount",
                    "requestKey", "roleMask", "pickupDistance", "required"))
             and current["queryPointer"] == baseline["queryPointer"]
             and stage["storage"] == baseline["workspace"]["storage"],
             "route static context or exact Cargo changed")
        need(a["movementPolicyRevision"] == b["movementPolicyRevision"], "route policy changed")
        need(allow_reset or stage["nodeCount"] >= baseline["workspace"]["nodeCount"], "route graph reset")
    need(allow_reset or current["workspace"]["nodeCount"] >= current["before"]["nodeCount"],
         "route graph reset")


def profile(data, actor, source):
    need(data is not None and data.get("resolved") is True
         and data.get("fingerprint") == actor["behaviorFingerprint"]
         and data.get("sourceSha256") == source["profileSha256"], "resolved profile is missing")
    raw = bytes.fromhex(data["resultHex"])
    need(len(raw) == 216 and struct.unpack_from("<II", raw, 188) ==
         (actor["matchedLayerMask"], actor["behaviorFingerprint"])
         and data.get("lanes") == [raw[:80].hex(), raw[80:160].hex()], "resolved profile bytes differ")
    return raw[:80]


def follower_witness(witness, speed):
    need(isinstance(witness, dict) and witness.get("startFrame") == speed["startFrame"]
         and witness.get("returnFrame") == speed["returnFrame"]
         and witness.get("duration") == speed["duration"]
         and witness.get("commitSequence") == speed["commitAfter"], "missing complete Hop route witness")
    rows = witness.get("observations", [])
    expected = set(range(speed["startFrame"], speed["startFrame"]+speed["duration"])) | {speed["returnFrame"]}
    need(rows and {r["frame"] for r in rows} == expected, "missing Hop or exact return query")
    for index, row in enumerate(rows):
        # The first receipt may add the first proven destination and admit Hop
        # in that same Tick. Its entry precedes its return, so compare forward.
        # Every later entry/return still retains the first returned graph.
        baseline = rows[0] if index else dict(row, workspace=row["before"])
        same_graph(baseline, row)


def wild_witness(witness, subject):
    need(isinstance(witness, dict), "missing alert-to-Walk route witness")
    baseline, resumed = witness["baseline"], witness["postAlert"]
    need(baseline["workspace"]["owner"] == subject["handle"]
         and baseline["workspace"]["compatibility"]["required"] == 1
         and baseline["workspace"]["nodeCount"] >= 2
         and witness["endFrame"] == witness["startFrame"]+20
         and witness["endFrame"] <= resumed["frame"] <= witness["endFrame"]+1
         and witness["endFrame"] <= witness["reachableFrame"] <= witness["searchStartFrame"]
         and 0 <= witness["searchStartFrame"]-witness["reachableFrame"] <= 1,
         "alert clock or reachable-to-Walk spacing differs")
    same_graph(baseline, resumed, allow_reset=True)
    event = witness["nativeStart"]; data = event["data"]
    need(event["frame"] == witness["searchStartFrame"] and data["event"] == "MOTION_STARTED"
         and data["actorHandle"] == subject["handle"]["value"]
         and data["actor"] == {k:v for k,v in subject["handle"].items() if k != "value"}
         and data["valueA"] == 1 and data["valueB"] == 8, "Walk admission owner or half-speed duration differs")
