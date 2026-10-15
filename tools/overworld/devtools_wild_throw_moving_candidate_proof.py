"""Accepted claim and copied-data controls for moving-candidate Wild Throw."""

from copy import deepcopy
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_moving_cargo_pickup import verify_cargo_autonomy
from tools.overworld.devtools_cargo_route_continuity import wild_witness, packets

from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    KIND, BUBBLE_SOUND_ID, BUBBLE_PLAY_CALLER, QUIET_BUBBLE_STOP_CALLER, THROW_APPLICATION_BIT,
    TRIGGER_CONDITION, retain_walk_graph, validate_route_binding, require, moving_pickup_witness,
)


CLAIMS = ("live-actor-identity", "natural-input", "rendered-motion",
          "control-release")
NAMES = {
    "live-actor-identity": ("same-current-stantler-and-geodude",),
    "natural-input": ("stantler-walk-before-notice",
                      "moving-candidate-while-throw-active",
                      "geodude-chases-candidate", "authored-notice-alert-and-complete-half-speed-walk-with-current-cargo-route"),
    "rendered-motion": ("same-stantler-launched-by-geodude",),
    "control-release": ("moving-cargo-exact-cancel-before-held", "no-battle-before-launch"),
}
FAULTS = ("no-prewalk", "idle-candidate", "wrong-launch-target", "stale-candidate",
          "battle-task", "wrong-cargo-binding", "wrong-trigger-binding",
          "missing-cargo-claim", "stale-claim-clock", "stale-cargo-handle",
          "missing-bubble-sound", "missing-quiet-stop", "wrong-stop-caller",
          "wrong-sound-id", "late-stop-cycle", "reversed-sound-order",
          "idle-at-pickup", "forced-at-pickup", "wrong-pickup-token",
          "missing-pickup-cancel", "wrong-pickup-cancel-owner",
          "reversed-pickup-control", "missing-pickup-held")
SOUND_FAULTS = FAULTS[10:16]
PICKUP_FAULTS = FAULTS[16:]


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def route_witness(witness, subject):
    require(isinstance(witness,dict) and witness.get("mode") in ("prepared","initial-pending"),
            "moving Throw lacks its current Notice route witness")
    start,end=witness["startFrame"],witness["endFrame"]
    require(end==start+20 and witness["alertClocks"] ==
            [dict(frame=f,timer=max(0,end-f)) for f in range(start,end+1)]
            and end<=witness["resumedFrame"]<=end+1,
            "moving Throw lacks its complete authored Notice alert")
    lane=bytes.fromhex(witness["profile"]["lanes"][0])
    require(len(lane)==80 and lane[3]==20 and lane[7]==8 and lane[36]==2,
            "moving Throw Notice Search profile differs")
    if witness["mode"]=="prepared":
        wild_witness(witness,subject)
    else:
        initial=witness["initialPending"];sample=initial["sample"];event=initial["event"]
        require(sample["frame"]==start and event["data"]["sequence"]<witness["profile"]["sequence"]
                and initial["notice"]["frame"]==start and initial["notice"]["owner"]==subject["handle"],
                "moving Throw initial Pending/Notice order differs")
        validate_route_binding(initial["notice"]["binding"],"PLAYER",TRIGGER_CONDITION)
        rows=packets(sample,[event],dict(handle=subject["handle"]),witness["queryImage"],
                     initial["previousCycle"],pending_ok=True)
        require(rows==[] and all(event["data"][stage].get("queryPointer")==0
                and event["data"][stage].get("workspace") is None for stage in ("before","after")),
                "moving Throw initial query was not exact unprepared Pending")
        require(witness["baseline"]["workspace"]["owner"]==subject["handle"]
                and witness["baseline"]["frame"]>=end,
                "moving Throw prepared route predates its initial Notice alert")
        retain_walk_graph(witness["baseline"],witness["postAlert"])
    receipts=witness["routeReceipts"]
    require(receipts and (witness["mode"]=="prepared" or receipts[0]==witness["baseline"])
            and receipts[0]["frame"]<=witness["walk"]["startFrame"],
            "moving Throw deferred its first prepared graph past Walk admission")
    previous=None
    for row in receipts:
        if row.get("allocation"):
            require(row["allocation"]["image"]==witness["queryImage"],
                    "moving Throw allocation uses a different native image")
        retain_walk_graph(witness["baseline"],row)
        if previous is not None:
            require((previous["frame"],previous["sequence"])<(row["frame"],row["sequence"]),
                    "moving Throw route receipts reversed")
            retain_walk_graph(previous,row)
        previous=row
    walk=witness["walk"];commit=walk["commitBefore"]+1
    require(walk["handle"]==subject["handle"] and walk["subjectIdentity"]==subject["subjectIdentity"]
            and walk["duration"]==8 and walk["commitAfter"]==commit
            and witness["searchStartFrame"]==walk["startFrame"]
            and walk["returnFrame"]==walk["startFrame"]+8
            and end<=witness["reachableFrame"]<=walk["startFrame"]
            and 0<=walk["startFrame"]-witness["reachableFrame"]<=1
            and sum(abs(a-b) for a,b in zip(walk["origin"],walk["target"]))==1
            and [(s["frame"],s["elapsed"]) for s in walk["samples"]]==
                [(walk["startFrame"]+n,n) for n in range(9)]
            and len({tuple(s["pose"]) for s in walk["samples"]})>=3
            and walk["samples"][-1]["pose"]==[(n<<16)+32768 for n in walk["target"]],
            "moving Throw lacks its complete first half-speed Walk")
    events=walk["lifecycle"]
    require([(e["data"]["event"],e["data"]["valueA"],e["data"]["valueB"]) for e in events]==[
                ("MOTION_STARTED",1,8),("LOGICAL_COMMIT",commit,1),
                ("MOTION_FINISHED",commit,1),("CONTROL_RETURNED",0,commit)]
            and events[0]["frame"]==walk["startFrame"]
            and all(e["frame"]==walk["returnFrame"] for e in events[1:])
            and all(e["data"]["actorHandle"]==subject["handle"]["value"]
                    and e["data"]["actor"]=={k:v for k,v in subject["handle"].items() if k!="value"} for e in events)
            and all(a["data"]["sequence"]<b["data"]["sequence"] for a,b in zip(events,events[1:])),
            "moving Throw lacks its exact first Walk commit/finish/control return")
    require({q["frame"] for q in walk["queries"]}==set(range(walk["startFrame"],walk["returnFrame"]+1)),
            "moving Throw lacks its dense first Walk route reads")
    for row in walk["queries"]:
        require(row in receipts, "moving Throw Walk route receipt differs")
        retain_walk_graph(witness["baseline"],row)


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    if (replay.get("passed") is not True or result.get("ready") is not True
            or result.get("observedFrames") != replay.get("observedFrames")
            or result.get("observedFrames", 0) < 2
            or result.get("observedFrameUnit") != "completed-game-frame"
            or not result.get("preNoticeWalkFrame", 0) < result.get("movingCandidateFrame", 0)
            or not result.get("movingCandidateFrame", 0) <= result.get("walkPursuitFrame", 0)
            or not result.get("walkPursuitFrame", 0) < result.get("launchFrame", 0)
            or set(result.get("subjects", {})) != {"stantler", "geodude"}):
        raise ValueError("moving Throw replay lacks the same actor's Walk and launch")
    pairs = result.get("quietBubbleSoundPairs")
    if (not isinstance(pairs, list) or not pairs
            or any(not isinstance(pair, dict)
                   or any(type(pair.get(key)) is not int for key in (
                       "frame", "actorFrame", "nativeCycle", "playSequence", "stopSequence",
                       "previousNativeCycle", "completedNativeCycle", "playEntryNativeCycle",
                       "playReturnNativeCycle", "stopEntryNativeCycle", "stopReturnNativeCycle"))
                   or not (pair["previousNativeCycle"] < pair["playEntryNativeCycle"]
                           <= pair["playReturnNativeCycle"] <= pair["stopEntryNativeCycle"]
                           <= pair["stopReturnNativeCycle"] <= pair["completedNativeCycle"])
                   or pair["nativeCycle"] != pair["stopEntryNativeCycle"]
                   or pair["playSequence"] >= pair["stopSequence"]
                   or pair.get("sequenceId") != BUBBLE_SOUND_ID
                   or pair.get("playCaller") != BUBBLE_PLAY_CALLER
                   or pair.get("stopCaller") != QUIET_BUBBLE_STOP_CALLER
                   or pair["frame"] > result["launchFrame"] for pair in pairs)):
        raise ValueError("moving Throw replay lacks the synchronous quiet bubble sound proof")
    witness = result.get("movingPickup")
    require(isinstance(witness, dict), "moving Throw lacks its moving pickup witness")
    authenticated = moving_pickup_witness(witness["previous"], witness["current"], witness["events"],
                                         witness["source"], result["subjects"])
    require(authenticated == witness and result["walkPursuitFrame"] <= witness["frame"] < result["launchFrame"],
            "moving Throw pickup witness differs from current motion and launch")
    # The receipt must be the exact recorded adjacent pair, not a substitute.
    samples = [sample for row in rows if row.get("phase") == "observe" for sample in row.get("samples", [])]
    require(witness["previous"] in samples and witness["current"] in samples
            and witness["events"] == [event for row in rows if row.get("phase") == "observe"
                                     for event in row.get("events", []) if event.get("frame") == witness["frame"]],
            "moving Throw pickup witness is not the retained native stream")
    route_witness(result.get("routeContinuity"), result["subjects"]["geodude"])
    if witness["source"]["contractVersion"] == 2:
        verify_cargo_autonomy(result.get("cargoAutonomy"), rows, witness["source"], result["subjects"]["stantler"])
    commands = [row.get("action") for row in rows if row.get("command") is not None]
    if commands != ["throw-tile", "prepare-passive-follower", "create-passive-follower",
                    "spawn-stantler", "bind-stantler",
                    "spawn-geodude", "bind-geodude"]:
        raise ValueError("moving Throw setup command stream differs")
    prewalks = [row for row in rows if row.get("phase") == "setup"
                and row.get("action") == "walk-stantler-before-notice"
                and row.get("samples")]
    if not prewalks:
        raise ValueError("moving Throw lacks pre-Notice natural Stantler Walk")
    steps = [row for row in rows if row.get("phase") == "observe"
             and row.get("samples")]
    if not steps or any(row.get("action") != "natural-moving-pickup-and-launch"
                        for row in steps):
        raise ValueError("moving Throw has no declared natural frame stream")
    return {"observedFrames": result["observedFrames"],
            "observedFrameUnit": "completed-game-frame",
            "preNoticeWalkFrame": result["preNoticeWalkFrame"],
            "movingCandidateFrame": result["movingCandidateFrame"],
            "walkPursuitFrame": result["walkPursuitFrame"],
            "launchFrame": result["launchFrame"],
            "movingPickupFrame": witness["frame"], "pickupMotionIdentity": witness["motionIdentity"],
            "quietBubbleSoundPairs": deepcopy(pairs),
            "subjects": [result["subjects"]["stantler"],
                         result["subjects"]["geodude"]],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown moving Throw copied-data control")
    changed = deepcopy(rows)
    steps = [row for row in changed
             if row.get("action") == "natural-moving-pickup-and-launch"
             and row.get("samples")]
    if not steps:
        raise ValueError("moving Throw control lacks its frame stream")
    samples = [sample for row in steps for sample in row["samples"]]
    if fault in SOUND_FAULTS:
        events = [event for row in steps for event in row.get("events", [])]
        plays = [event for event in events if event.get("data", {}).get("observation") == "sound-play"
                 and event["data"].get("caller") == BUBBLE_PLAY_CALLER]
        stops = [event for event in events if event.get("data", {}).get("observation") == "sound-stop"
                 and event["data"].get("caller") == QUIET_BUBBLE_STOP_CALLER]
        if not plays or not stops:
            raise ValueError("moving Throw sound control lacks its actual bubble/quiet call pair")
        play, stop = plays[0], stops[0]
        if fault in ("missing-bubble-sound", "missing-quiet-stop"):
            for row in steps:
                row["events"] = [event for event in row.get("events", [])
                    if event not in (plays + stops if fault == "missing-bubble-sound" else [stop])]
        elif fault == "wrong-stop-caller":
            stop["data"]["caller"] += 2
        elif fault == "wrong-sound-id":
            stop["data"]["sequenceId"] += 1
        elif fault == "late-stop-cycle":
            completed = next(s["nativeCycle"] for s in samples if s["frame"] == stop["frame"])
            stop["data"]["entryNativeCycle"] = completed + 1
            stop["data"]["returnNativeCycle"] = completed + 1
        else:
            play["data"]["sequence"], stop["data"]["sequence"] = stop["data"]["sequence"], play["data"]["sequence"]
        return changed
    if fault in PICKUP_FAULTS:
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        cargo = next(row["receipt"] for row in changed if row.get("action") == "bind-stantler")
        carrier = next(row["receipt"] for row in changed if row.get("action") == "bind-geodude")
        prior = pickup = None
        for previous, current in zip(samples, samples[1:]):
            state = current.get("pokemonCombat", {}).get("interactions", {}).get("throwState", {})
            raw = state.get("targets", [])
            if len(raw) == 10 and raw[carrier["handle"]["slot"]] == (cargo["handle"]["slot"] + 1) | 128:
                prior, pickup = previous, current
                break
        require(pickup is not None, "moving Throw pickup control lacks its exact carried transition")
        actor = next(a for a in prior["actors"] if a["handle"] == cargo["handle"])
        native = next(r for r in prior["pokemonCombat"]["targets"] if r["handle"] == cargo["handle"])
        cancel = next((e for row in steps for e in row.get("events", []) if e.get("frame") == pickup["frame"]
                       and e.get("data", {}).get("actorHandle") == cargo["handle"]["value"]
                       and e["data"].get("event") == "MOTION_CANCELED"), None)
        control = next((e for row in steps for e in row.get("events", []) if e.get("frame") == pickup["frame"]
                        and e.get("data", {}).get("actorHandle") == cargo["handle"]["value"]
                        and e["data"].get("event") == "CONTROL_RETURNED"), None)
        require(cancel is not None and control is not None,
                "moving Throw pickup control lacks its actual CANCEL/CONTROL pair")
        if fault in ("idle-at-pickup", "forced-at-pickup", "wrong-pickup-token"):
            raw = bytearray.fromhex(native["motion"]["rawHex"])
            if fault == "idle-at-pickup":
                raw[48] = 0; actor.update(motionPhase="IDLE", motionKind="NONE", reservationId=0)
            elif fault == "forced-at-pickup":
                raw[37] = 1
            else:
                actor["reservationId"] += 1
            native["motion"] = decode_motion(bytes(raw))
        elif fault == "missing-pickup-cancel":
            for row in steps: row["events"] = [e for e in row.get("events", []) if e != cancel]
        elif fault == "wrong-pickup-cancel-owner":
            cancel["data"].update(actorHandle=carrier["handle"]["value"],
                                   actor={k:v for k,v in carrier["handle"].items() if k != "value"})
        elif fault == "reversed-pickup-control":
            cancel["data"]["sequence"], control["data"]["sequence"] = control["data"]["sequence"], cancel["data"]["sequence"]
        else:
            timer = next(r for r in pickup["pokemonCombat"]["movementTimers"] if r["handle"] == cargo["handle"])
            timer["movementActorControlMode"] = 0
        return changed
    cargo_subject = next(row["receipt"] for row in changed
                         if row.get("action") == "bind-stantler")
    def target(sample):
        selected = select_current_actor(sample, cargo_subject)
        require(selected["species"] == 234 and selected["role"] == "WILD",
                "moving Throw control Cargo identity differs")
        return next(actor for actor in sample["actors"]
                    if actor.get("handle") == selected["handle"])
    if fault == "no-prewalk":
        for row in changed:
            if row.get("action") == "walk-stantler-before-notice":
                for sample in row.get("samples", []):
                    actor = target(sample)
                    actor["motionKind"] = "NONE"
    elif fault == "idle-candidate":
        for sample in samples:
            actor = target(sample)
            if actor.get("motionKind") == "WALK":
                actor["motionKind"] = "NONE"
    elif fault == "wrong-launch-target":
        for sample in samples:
            actor = target(sample)
            if actor.get("motionKind") == "HOP":
                actor["target"]["y"] = 406
    elif fault == "stale-candidate":
        target(samples[-1])["subjectIdentity"] += 1
    elif fault == "battle-task":
        samples[-1]["fieldControl"]["taskPointer"] = 0x02100000
    else:
        import struct
        from tools.overworld.devtools_follower_throw_measurement import raw_handle
        bound_geo = next(row["receipt"] for row in changed
                         if row.get("action") == "bind-geodude")
        cargo_subject = next(row["receipt"] for row in changed
                             if row.get("action") == "bind-stantler")
        applied = False
        for sample in samples:
            geo = next((a for a in sample["actors"]
                        if a.get("handle") == bound_geo["handle"]
                        and a.get("subjectIdentity") == bound_geo["subjectIdentity"]
                        and a.get("species") == 74 and a.get("role") == "WILD"
                        and a.get("matchedLayerMask", 0) & THROW_APPLICATION_BIT), None)
            if geo is None:
                continue
            cargo = next(a for a in sample["actors"]
                         if a.get("handle") == cargo_subject["handle"]
                         and a.get("subjectIdentity") == cargo_subject["subjectIdentity"]
                         and a.get("species") == 234 and a.get("role") == "WILD")
            value = sample["pokemonCombat"]["interactions"]
            owners = [r for r in value["carriers"]
                      if r.get("handle") == geo["handle"]]
            if len(owners) != 1:
                raise ValueError("moving Throw control lacks its exact carrier owner")
            row = owners[0]
            bindings = row["bindings"]
            trigger, bound_cargo = bindings["trigger"], bindings["cargo"]
            state = value["throwState"]
            slot, cargo_slot = geo["handle"]["slot"], cargo["handle"]["slot"]
            if (row.get("available") is not True or row.get("role") != "WILD"
                    or any(b.get("bound") is not True
                           or b.get("targetCurrent") is not True
                           or b.get("flags") != 1
                           for b in (trigger, bound_cargo))
                    or trigger.get("target") != {"kind": "PLAYER", "actor": None}
                    or bound_cargo.get("target") != {"kind": "ACTOR", "actor": cargo["handle"]}
                    or state["targets"][slot] != cargo_slot + 1
                    or not state["targetMask"] & (1 << cargo_slot)
                    or not state["carrierMask"] & (1 << slot)
                    or state["recoveringMask"] & (1 << slot)):
                continue
            applied = True
            if fault == "stale-claim-clock":
                value["nativeCycle"] -= 1
            elif fault == "missing-cargo-claim":
                state=value["throwState"];state["targetMask"]=0
                state["rawHex"]=(bytes(state["targets"])+struct.pack("<3H",0,state["carrierMask"],state["recoveringMask"])).hex()
            else:
                key="trigger" if fault == "wrong-trigger-binding" else "cargo"
                b=row["bindings"][key]; data=bytearray.fromhex(b["rawHex"])
                if key == "trigger":
                    b["target"]={"kind":"ACTOR","actor":deepcopy(cargo["handle"])}
                    data[:12]=raw_handle(b["target"]["actor"]);data[12]=2
                else:
                    b["target"]["actor"]["fieldEpoch" if fault == "stale-cargo-handle" else "slot"] += 1
                    data[:12]=raw_handle(b["target"]["actor"])
                b["rawHex"]=data.hex(); raw=bytearray.fromhex(row["rawBindingsHex"])
                start=12 if key=="trigger" else 36;raw[start:start+24]=data;row["rawBindingsHex"]=raw.hex()
        if not applied:
            raise ValueError("moving Throw control lacks its current bound Cargo claim")
    return changed
