"""Finite approach admission proof; full Throw remains the existing case."""
from copy import deepcopy
import struct
from tools.overworld.devtools_follower_throw_approach_measurement import KIND, REQUIREMENT, reachable_cargo_admission
from tools.overworld.devtools_follower_throw_measurement import require, FIND_CARGO, FOLLOWER, THROW_MASK, TRIGGER_CONDITION
from tools.overworld.devtools_records import engine_binding_identity
from tools.overworld.devtools_walk_matrix_observer import decode_motion

NAMES={"live-actor-identity":("unchanged-saved-mankey-distinct-native-interest-and-cargo",),
       "profile-resolution":("current-cargo-admits-authored-find-cargo-and-half-speed-pursuit",),
       "controlled-action":("unchanged-continue-up-b40-neutral120-no-y-or-party-edit",),
       "engine-boundary":("separate-bell-cargo-has-current-native-reachable-pickup-route",),
       "rendered-motion":("complete-native-normal-hop-and-cargo-pursuit",),
       "control-release":("unlimited-normal-hop-policy-survives-current-tile-advance-and-return",)}
CLAIMS=tuple(NAMES)
FAULTS=tuple(KIND+":"+f for f in ("policy-midpoint","policy-return","stale-query-owner","wrong-cargo","missing-return","slow-pursuit"))


def contract():
    return {c:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1) for n in ns]
            for c,ns in NAMES.items()}


def measurements(replay,record):
    r=replay.get("measurements",{}).get(KIND,{})
    require(replay.get("passed") is True and replay.get("failures") == [] and r.get("passed") is True
            and r.get("ready") is True and r.get("acceptedProof") is False
            and r.get("observedFrames") == replay.get("observedFrames") == 160
            and r.get("observedFrameUnit") == "completed-game-frame"
            and set(r.get("subjects",{})) == {"mankey","trigger","cargo","alternative"},
            "Follower approach lacks its exact finite saved-follower observation")
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
            "Follower approach owned session cleanup is missing")
    ws=r["speedWitnesses"]
    require(set(ws) == {"normal","cargo"}, "Follower approach lacks complete ordinary Hop and pursuit")
    for stage,w in ws.items():
        time=7 if stage == "normal" else 3;lane=bytes.fromhex(w["profile"]["lanes"][0]);p=w["plan"];commit=w["commitBefore"]+1
        duration=min(65535,time+(p["distance"]-1)*(time-(time>>2))
                     +((abs(p["targetBaseY"]-p["startBaseY"])>>12)*time*lane[48])//1600)
        require(w["stage"] == stage and w["handle"] == r["subjects"]["mankey"]["handle"]
                and w["subjectIdentity"] == r["subjects"]["mankey"]["subjectIdentity"]
                and engine_binding_identity(w["engineIdentity"]) == engine_binding_identity(r["subjects"]["mankey"]["engineIdentity"])
                and w["profile"]["appliedOverrides"] & FOLLOWER
                and (not w["profile"]["appliedOverrides"] & THROW_MASK if stage == "normal" else w["profile"]["appliedOverrides"] & FIND_CARGO)
                and lane[7] == lane[36] == time and p["duration"] == w["duration"] == duration
                and w["commitAfter"] == commit and w["returnFrame"] == w["startFrame"]+duration+w["pauseFrames"]
                and [(e["event"],e["valueA"],e["valueB"]) for e in w["lifecycle"]] == [("MOTION_STARTED",2,duration),
                    ("LOGICAL_COMMIT",commit,2),("MOTION_FINISHED",commit,2),("CONTROL_RETURNED",0,commit)]
                and [x["elapsed"] for x in w["poses"]] == list(range(duration+1))
                and [x["frame"] for x in w["poses"]] == list(range(w["startFrame"],w["startFrame"]+duration+1))
                and len({tuple(x["pose"][:2]) for x in w["poses"]}) >= 3 and any(x["pose"][2] > 0 for x in w["poses"])
                and w["poses"][-1]["pose"] == [(v<<16)+32768 for v in w["target"]]+[0],
                "Follower approach complete authored native Hop differs")
    hop=r["approach"];admit=r["admission"];notice=r["notice"]
    b=notice["binding"]
    require(type(notice["frame"]) is int and notice["frame"] <= admit["frame"]
            and b["bound"] is True and b["targetCurrent"] is True
            and b["sourceConditionId"] == TRIGGER_CONDITION and b["sourceApplication"] == 20
            and b["target"] == dict(kind="ACTOR",actor=r["subjects"]["trigger"]["handle"])
            and admit["bindings"]["trigger"] == b,
            "Follower approach lacks genuine native Onix Interest before Cargo admission")
    require(hop["motion"] == ws["normal"] and hop["startFrame"] == ws["normal"]["startFrame"]
            and hop["returnFrame"] == ws["normal"]["returnFrame"]
            and ws["normal"]["returnFrame"] <= ws["cargo"]["startFrame"]
            and admit["frame"] <= admit["contributionFrame"] <= ws["cargo"]["startFrame"]
            and admit["query"]["frame"] == admit["frame"]
            and reachable_cargo_admission(admit["query"],admit["cargoPosition"])
            and admit["query"]["workspace"]["owner"] == r["subjects"]["mankey"]["handle"]
            and admit["query"]["workspace"]["compatibility"]["cargo"] == r["subjects"]["cargo"]["handle"],
            "Follower approach Cargo admission, contribution or pursuit order differs")
    queryframes={q["frame"] for q in hop["queries"]}
    require(hop["startFrame"] in queryframes and hop["returnFrame"] in queryframes
            and any(hop["startFrame"] < f < hop["startFrame"]+hop["duration"] for f in queryframes),
            "Follower approach lacks complete native query boundaries")
    origin=hop["queries"][0]["workspace"]["origin"]
    require(any(hop["startFrame"] < q["frame"] < hop["startFrame"]+hop["duration"]
                and (q["workspace"]["origin"]["x"],q["workspace"]["origin"]["y"]) != (origin["x"],origin["y"])
                for q in hop["queries"]), "Follower approach lacks a native current-tile advance query")
    for q in hop["queries"]:
        for key in ("before","workspace"):
            v=q.get(key)
            if v is not None and v.get("valid"):
                require(v["owner"] == r["subjects"]["mankey"]["handle"] and v["ownerCurrent"] is True
                        and (v["compatibility"]["movementPolicyRevision"] == hop["policyKey"]
                             or (key == "workspace" and q["frame"] == hop["returnFrame"]
                                 and admit["contributionFrame"] == q["frame"])),
                        "Follower approach unlimited route policy changed during normal Hop or return")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,ns in NAMES.items() for n in ns]


class FollowerThrowApproachNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown Follower approach copied control")
        self.fault=fault.rsplit(":",1)[1];self.applied=False

    def mutate(self,row,subjects):
        if self.applied or row.get("phase") != "observe":return row
        changed=deepcopy(row)
        for sample in changed.get("samples",[]):
            m=next((a for a in sample.get("actors",[]) if a.get("role") == "FOLLOWER" and a.get("species") == 56),None)
            if m is None:continue
            own=[e for e in changed.get("events",[]) if e.get("frame") == sample["frame"]
                 and (e.get("data",{}).get("actorHandle") == m["handle"]["value"]
                      or e.get("data",{}).get("slot") == m["handle"]["slot"])]
            returned=any(e.get("data",{}).get("event") == "CONTROL_RETURNED" for e in own)
            normal=not m.get("matchedLayerMask",0) & THROW_MASK
            for e in own:
                d=e.get("data",{})
                if d.get("observation") == "throw-cargo-query" and normal \
                        and ((self.fault == "policy-midpoint" and m["motionKind"] == "HOP" and m["motionElapsed"] > 0)
                             or (self.fault == "policy-return" and returned) or self.fault == "stale-query-owner"):
                    key="before" if self.fault == "policy-return" else "after";v=d[key].get("workspace")
                    if v is not None:
                        if self.fault == "stale-query-owner":v["owner"]["generation"] += 1
                        else:v["compatibility"]["movementPolicyRevision"] ^= 1
                        self.applied=True;break
            if self.fault == "missing-return" and normal and returned:
                changed["events"]=[e for e in changed["events"] if not (e in own and e.get("data",{}).get("event") == "CONTROL_RETURNED")]
                self.applied=True
            if self.fault == "wrong-cargo":
                inter=sample.get("pokemonCombat",{}).get("interactions",{})
                carrier=next((c for c in inter.get("carriers",[]) if c.get("handle") == m["handle"]),None)
                if carrier and carrier["bindings"]["cargo"]["bound"]:
                    from tools.overworld.devtools_follower_throw_measurement import raw_handle
                    alternative=next(a for a in sample["actors"] if a.get("species") == 43)
                    b=carrier["bindings"]["cargo"];raw=bytearray.fromhex(b["rawHex"]);raw[:12]=raw_handle(alternative["handle"])
                    b["target"]["actor"]=deepcopy(alternative["handle"]);b["rawHex"]=raw.hex()
                    rawb=bytearray.fromhex(carrier["rawBindingsHex"]);rawb[36:60]=raw;carrier["rawBindingsHex"]=rawb.hex();self.applied=True
            if self.fault == "slow-pursuit" and m.get("matchedLayerMask",0) & FIND_CARGO \
                    and m["motionKind"] == "HOP" and m["motionElapsed"] == 0:
                target=next(t for t in sample["pokemonCombat"]["targets"] if t["handle"] == m["handle"])
                raw=bytearray.fromhex(target["motion"]["rawHex"]);m["motionDuration"] += 2
                struct.pack_into("<H",raw,24,m["motionDuration"]);target["motion"]=decode_motion(bytes(raw))
                for e in own:
                    if e.get("data",{}).get("event") == "MOTION_STARTED":e["data"]["valueB"]=m["motionDuration"]
                self.applied=True
            if self.applied:break
        return changed if self.applied else row


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"), "Follower approach copied control did not fail")
    expected={"policy-midpoint":"unlimited route policy changed","policy-return":"unlimited route policy changed",
        "stale-query-owner":"query result or current workspace differs","wrong-cargo":"different or stale Cargo",
        "missing-return":"normal follow return or search control did not return on time","slow-pursuit":"cargo displayed Hop time"}[fault.rsplit(":",1)[1]]
    require(any(expected in str(f) for f in result.get("measurements",{}).get(KIND,{}).get("failures",[])),
            "Follower approach copied control failed for a different reason")
