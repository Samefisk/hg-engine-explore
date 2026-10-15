"""Exact Follower Throw acceptance and copied-stream controls."""
from copy import deepcopy
import struct
from tools.overworld.devtools_follower_throw_measurement import (
    follower_moving_pickup, AWAY, AWAY_TARGET, FIND_CARGO, FIND_POSITION, FOLLOWER, KIND, NON45_KIND, NON45_REQUIREMENT, NORMAL_TIME, REQUIREMENT, RELEASE, SEARCH_TIME, THROW_MASK, THROW_RANGE, require, require_non45_away,
)
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_records import engine_binding_identity
from tools.overworld.devtools_cargo_route_continuity import follower_witness
from tools.overworld.devtools_moving_cargo_pickup import verify_cargo_autonomy

NAMES = {
    "live-actor-identity": ("same-follower-mankey-and-noticed-wild-interest-as-cargo",),
    "profile-resolution": ("same-interest-cargo-persists-through-pickup-and-windup", "both-search-profiles-use-authored-half-speed"),
    "natural-input": ("checked-cargo-motion-returns-before-carry", "moving-wild-trigger"),
    "rendered-motion": ("same-noticed-cargo-launches-exact-range-away-from-player", "complete-faster-pursuit-hop-and-resolved-away-position-phase"),
    "control-release": ("normal-follower-motion-returns-after-throw", "no-player-fallback-or-battle", "normal-return-removes-search-speed-boost", "unlimited-cargo-hop-keeps-query-key-through-native-return", "cargo-flight-completes-and-free-control-returns"),
}
CLAIMS = tuple(NAMES)
FAULTS = tuple(KIND+":"+n for n in ("missing-interactions", "stale-cargo", "binding-loss", "player-fallback",
    "cargo-motion-replaced", "wrong-launch", "flight-frozen", "missing-follow-return", "battle",
    "slow-search", "skipped-position", "leakingboost", "different-interest", "short-range", "toward-player", "missing-flight-return"))


def requirement(feature):
    require(feature in (KIND, NON45_KIND), "unknown Follower Throw case")
    return NON45_REQUIREMENT if feature == NON45_KIND else REQUIREMENT


def names(feature=KIND):
    requirement(feature)
    result = dict(NAMES)
    if feature == NON45_KIND:
        result["rendered-motion"] = ("native-non45-outward-flight-exact-radius-and-support", NAMES["rendered-motion"][1])
    return result


def claims(feature):
    return tuple(names(feature))


def faults(feature):
    requirement(feature)
    return tuple(feature + ":" + fault.split(":",1)[1] for fault in FAULTS) + (
        tuple(feature + ":" + fault for fault in ("cardinal-fallback", "diagonal45", "wrong-support"))
        if feature == NON45_KIND else ())


def contract(feature=KIND):
    return {claim:[dict(name=name,operator="eq",type="integer",validator="meaningful-observation",expected=1)
                   for name in values] for claim,values in names(feature).items()}


def measurements(feature,replay=None,record=None):
    if record is None:
        feature, replay, record = KIND, feature, replay
    requirement(feature)
    non45 = feature == NON45_KIND
    result=replay.get("measurements",{}).get(feature,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and result.get("passed") is True
            and result.get("ready") is True and result.get("acceptedProof") is False
            and result.get("observedFrames")==replay.get("observedFrames")
            and result.get("observedFrameUnit")=="completed-game-frame"
            and set(result.get("subjects",{}))=={"mankey","trigger","cargo"}
            and result.get("cargoCompleted") is True and result.get("triggerMoved") is True and result.get("flightMoved") is True,
            "Follower Throw lacks the same targets, own Cargo motion, and follow return")
    frames=result.get("frames",{})
    if feature == KIND and result["source"]["contractVersion"] == 2:
        verify_cargo_autonomy(result.get("cargoAutonomy"), None, result["source"], result["subjects"]["cargo"])
    require(all(type(frames.get(n)) is int for n in ("cargoBound","cargoWalk","claim","cargoControl","pickup","windup","launch","followStart","followReturn"))
            and frames["cargoBound"]<=frames["claim"]<=frames["pickup"]<=frames["windup"]<frames["launch"]<frames["followStart"]<frames["followReturn"]
            and frames["cargoWalk"]<frames["cargoControl"]<=frames["pickup"],
            "Follower Throw stage order differs")
    pickup = result.get("movingPickup")
    if pickup is None:
        require(frames.get("cargoCommit") == frames["cargoControl"],
                "Follower Throw normal Cargo terminal lacks its own commit")
    else:
        require(follower_moving_pickup(pickup["previous"], pickup["current"], pickup["events"],
                                      pickup["source"], result["subjects"]) == pickup
                and pickup["source"] == result.get("source")
                and pickup["frame"] == frames["cargoControl"] == frames["pickup"],
                "Follower Throw moving Cargo handoff differs from its exact native receipt")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
            "Follower Throw owned session cleanup is missing")
    witnesses=result.get("speedWitnesses",{})
    require({"cargo","normal"} <= set(witnesses) <= {"cargo","position","normal"}, "Follower Throw lacks complete carrier speed witnesses")
    require(result["subjects"]["trigger"]["handle"]==result["subjects"]["cargo"]["handle"]
            and result["subjects"]["trigger"]["subjectIdentity"]==result["subjects"]["cargo"]["subjectIdentity"]
            and engine_binding_identity(result["subjects"]["trigger"]["engineIdentity"])
                ==engine_binding_identity(result["subjects"]["cargo"]["engineIdentity"]),
            "Follower Throw Cargo is not the same noticed Object of interest")
    position=result.get("positionProfile",{});lane=bytes.fromhex(position.get("lanes",[""])[0])
    require(len(lane)==80 and position["appliedOverrides"]&FIND_POSITION and position["appliedOverrides"]&AWAY
            and lane[7]==lane[36]==SEARCH_TIME and lane[13]==AWAY_TARGET and lane[76]==THROW_RANGE,
            "Follower Throw lacks its resolved Find Position phase")
    for stage,w in witnesses.items():
        time=NORMAL_TIME if stage=="normal" else SEARCH_TIME
        profile=w["profile"];lane=bytes.fromhex(profile["lanes"][0]);plan=w["plan"]
        duration=min(65535,time+(plan["distance"]-1)*(time-(time>>2))
                     +((abs(plan["targetBaseY"]-plan["startBaseY"])>>12)*time*lane[48])//1600)
        commit=w["commitBefore"]+1
        mask=profile["appliedOverrides"]
        require(w["stage"]==stage and w["handle"]==result["subjects"]["mankey"]["handle"]
                and w["subjectIdentity"]==result["subjects"]["mankey"]["subjectIdentity"]
                and engine_binding_identity(w["engineIdentity"])
                    ==engine_binding_identity(result["subjects"]["mankey"]["engineIdentity"])
                and mask & FOLLOWER and (not mask & THROW_MASK if stage=="normal" else
                                        mask & (FIND_CARGO if stage=="cargo" else FIND_POSITION))
                and lane[7]==lane[36]==time and plan["duration"]==w["duration"]==duration
                and w["commitAfter"]==commit and w["returnFrame"]==w["startFrame"]+duration+w["pauseFrames"]
                and [(e["event"],e["valueA"],e["valueB"]) for e in w["lifecycle"]]==[
                    ("MOTION_STARTED",2,duration),("LOGICAL_COMMIT",commit,2),
                    ("MOTION_FINISHED",commit,2),("CONTROL_RETURNED",0,commit)]
                and [p["elapsed"] for p in w["poses"]]==list(range(duration+1))
                and [p["frame"] for p in w["poses"]]==list(range(w["startFrame"],w["startFrame"]+duration+1))
                and len({tuple(p["pose"][:2]) for p in w["poses"]})>=3
                and any(p["pose"][2]>0 for p in w["poses"])
                and w["poses"][-1]["pose"]==[(v<<16)+32768 for v in w["target"]]+[0],
                "Follower Throw carrier speed witness differs from complete authored native motion")
    require(witnesses["cargo"]["returnFrame"]<=frames["position"]<=frames["windup"]<frames["launch"]
            <witnesses["normal"]["startFrame"]<witnesses["normal"]["returnFrame"],
            "Follower Throw carrier speed stage order differs")
    if "position" in witnesses:
        require(witnesses["cargo"]["returnFrame"]<=witnesses["position"]["startFrame"]
                <witnesses["position"]["returnFrame"]<=frames["windup"],
                "Follower Throw admitted Position Hop did not complete before windup")
    flight=result.get("flightWitness");endpoint=result.get("launchEndpoint")
    require(isinstance(flight,dict) and isinstance(endpoint,dict), "Follower Throw lacks complete native Cargo flight")
    plan=flight["plan"];commit=flight["commitBefore"]+1;duration=flight["duration"]
    if non45:
        require_non45_away(plan["origin"], plan["target"], endpoint["player"])
        released = endpoint.get("releaseProfile", {})
        lane = bytes.fromhex(released.get("lanes", [""])[0])
        expected = min(65535, SEARCH_TIME + (THROW_RANGE-1)*(SEARCH_TIME-(SEARCH_TIME >> 2))
                       + ((abs(plan["targetBaseY"]-plan["startBaseY"]) >> 12)*SEARCH_TIME*lane[48]) // 1600) if len(lane)==80 else None
        require(expected == duration and released.get("appliedOverrides",0) & RELEASE
                and released["appliedOverrides"] & AWAY and lane[36] == SEARCH_TIME
                and lane[13] == AWAY_TARGET and lane[76] == THROW_RANGE
                and flight["poses"][0].get("supportY") == plan["startBaseY"]
                and flight["poses"][-1].get("supportY") == plan["targetBaseY"],
                "Follower Throw non45 flight time or native landing support differs")
    require(flight["handle"]==result["subjects"]["cargo"]["handle"]
            and flight["subjectIdentity"]==result["subjects"]["cargo"]["subjectIdentity"]
            and engine_binding_identity(flight["engineIdentity"])==engine_binding_identity(result["subjects"]["cargo"]["engineIdentity"])
            and endpoint["plan"]==plan and endpoint["targetBaseY"]==plan["targetBaseY"]
            and endpoint["origin"]==plan["origin"] and endpoint["target"]==plan["target"]
            and (max(abs(a-b) for a,b in zip(plan["origin"],plan["target"])) if non45 else
                 sum(abs(a-b) for a,b in zip(plan["origin"],plan["target"])))==plan["distance"]==endpoint["distance"]==THROW_RANGE
            and (non45 or plan["origin"][0]==plan["target"][0] or plan["origin"][1]==plan["target"][1])
            and max(abs(a-b) for a,b in zip(plan["target"],endpoint["player"]))>max(abs(a-b) for a,b in zip(plan["origin"],endpoint["player"]))
            and endpoint["frame"]==flight["startFrame"]==frames["launch"]
            and flight["commitAfter"]==commit and flight["returnFrame"]==flight["startFrame"]+duration+flight["pauseFrames"]
            and flight["returnFrame"]<frames["followReturn"]
            and [(e["event"],e["valueA"],e["valueB"]) for e in flight["lifecycle"]]==[
                ("MOTION_STARTED",2,duration),("LOGICAL_COMMIT",commit,2),("MOTION_FINISHED",commit,2),("CONTROL_RETURNED",0,commit)]
            and [p["frame"] for p in flight["poses"]]==list(range(flight["startFrame"],flight["startFrame"]+duration+1))
            and [p["elapsed"] for p in flight["poses"]]==list(range(duration+1))
            and flight["poses"][-1]["pose"]==[(v<<16)+32768 for v in plan["target"]]+[0],
            "Follower Throw flight lacks exact Away endpoint, dense landing and free control")
    follower_witness(result.get("routeContinuity"), witnesses["cargo"])
    require(all(q["workspace"]["compatibility"]["cargo"]==result["subjects"]["cargo"]["handle"]
                for q in result["routeContinuity"]["observations"]), "Follower Throw route query names a different Cargo")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,values in names(feature).items() for n in values]


class FollowerThrowNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown Follower Throw copied-data control")
        self.fault=fault.rsplit(":",1)[1];self.applied=False;self.flight_start=None

    def mutate(self,row,subjects):
        if row.get("phase")!="observe":return row
        changed=deepcopy(row)
        for sample in changed.get("samples",[]):
            actors=sample.get("actors",[])
            mankey=next((a for a in actors if a.get("species")==56 and a.get("role")=="FOLLOWER"),None)
            cargo=next((a for a in actors if a.get("species")==69 and a.get("role")=="WILD"),None)
            interactions=sample.get("pokemonCombat",{}).get("interactions",{})
            carrier=next((c for c in interactions.get("carriers",[]) if c.get("handle")==mankey.get("handle")),None) if mankey else None
            if cargo and carrier and carrier["throw"]["recovering"] and cargo.get("motionKind")=="HOP" and cargo.get("motionElapsed")==0:self.flight_start=sample["frame"]
            if self.fault=="missing-interactions":
                sample.get("pokemonCombat",{}).pop("interactions",None);self.applied=True
            elif self.fault=="different-interest" and carrier and carrier["bindings"]["cargo"]["bound"]:
                b=carrier["bindings"]["trigger"];other=deepcopy(cargo["handle"]);other["generation"]+=1
                raw=bytearray.fromhex(b["rawHex"]);raw[:12]=__import__('tools.overworld.devtools_follower_throw_measurement',fromlist=['raw_handle']).raw_handle(other)
                b.update(target=dict(kind="ACTOR",actor=other),rawHex=raw.hex())
                whole=bytearray.fromhex(carrier["rawBindingsHex"]);whole[12:36]=raw;carrier["rawBindingsHex"]=whole.hex();self.applied=True
            elif self.fault in ("short-range","toward-player") and cargo and carrier and carrier["throw"]["recovering"] and cargo.get("motionKind")=="HOP" and cargo.get("motionElapsed")==0:
                target=next(t for t in sample["pokemonCombat"]["targets"] if t["handle"]==cargo["handle"])
                raw=bytearray.fromhex(target["motion"]["rawHex"])
                x,y=cargo["target"]["x"],cargo["target"]["y"]
                if self.fault=="short-range":y-=1
                else:
                    y=2*cargo["origin"]["y"]-y
                    sample["player"].update(x=x,y=y)
                cargo["target"]=dict(x=x,y=y);struct.pack_into("<2h",raw,12,x,y);raw[29]=sum(abs(a-b) for a,b in zip((x,y),(cargo["origin"]["x"],cargo["origin"]["y"])))
                target["motion"]=decode_motion(bytes(raw));self.applied=True
            elif self.fault=="stale-cargo" and cargo:
                cargo["subjectIdentity"]+=1;self.applied=True
            elif self.fault in ("binding-loss","player-fallback") and carrier and carrier["bindings"]["cargo"]["bound"]:
                binding=carrier["bindings"]["trigger"]
                raw=bytearray.fromhex(binding["rawHex"])
                raw[:12]=bytes(12);raw[12]=0 if self.fault=="binding-loss" else 1
                raw[22]=0 if self.fault=="binding-loss" else 1
                binding.update(bound=self.fault!="binding-loss",flags=raw[22],targetCurrent=self.fault!="binding-loss",
                    target=dict(kind="NONE" if self.fault=="binding-loss" else "PLAYER",actor=None),rawHex=raw.hex())
                whole=bytearray.fromhex(carrier["rawBindingsHex"]);whole[12:36]=raw;carrier["rawBindingsHex"]=whole.hex();self.applied=True
            elif self.fault=="cargo-motion-replaced" and not self.applied and cargo and carrier and carrier["bindings"]["cargo"]["bound"] \
                    and carrier["bindings"]["cargo"]["target"]["actor"]==cargo["handle"] \
                    and cargo["handle"]==subjects.get("cargo",{}).get("handle") \
                    and cargo.get("motionKind")=="WALK" and cargo.get("motionElapsed",0)>0:
                cargo["target"]["x"]+=1;self.applied=True
            elif self.fault=="wrong-launch" and cargo and carrier and carrier["throw"]["recovering"] and cargo.get("motionKind")=="HOP":
                cargo["target"]={k:sample["player"][k] for k in ("x","y")};self.applied=True
            elif self.fault=="flight-frozen" and cargo and carrier and carrier["throw"]["recovering"] and cargo.get("motionKind")=="HOP":
                cargo["engineObject"]["pos_x"]=(cargo["origin"]["x"]<<16)+32768
                cargo["engineObject"]["pos_z"]=(cargo["origin"]["y"]<<16)+32768
                self.applied=True
            elif self.fault=="battle":
                sample["fieldControl"]["taskPointer"]=0x02100000;self.applied=True
            elif self.fault in ("slow-search","leakingboost") and mankey \
                    and mankey.get("motionKind")=="HOP" and mankey.get("motionPhase")=="MOVING" and mankey.get("motionElapsed")==0:
                mask=mankey.get("matchedLayerMask",0)
                eligible=(mask & FIND_CARGO if self.fault=="slow-search" else
                    row.get("action") in ("walk-player-right","normal-follow-return") and not mask & THROW_MASK)
                if eligible:
                    target=next(t for t in sample["pokemonCombat"]["targets"] if t["handle"]==mankey["handle"])
                    native=bytearray.fromhex(target["motion"]["rawHex"])
                    duration=mankey["motionDuration"]+2 if self.fault=="slow-search" else max(1,mankey["motionDuration"]-2)
                    struct.pack_into("<H",native,24,duration);target["motion"]=decode_motion(bytes(native))
                    mankey["motionDuration"]=duration
                    for event in changed.get("events",[]):
                        data=event.get("data",{})
                        if event.get("frame")==sample["frame"] and event.get("kind")=="native" \
                                and data.get("actorHandle")==mankey["handle"]["value"] and data.get("event")=="MOTION_STARTED":
                            data["valueB"]=duration
                    self.applied=True
            elif self.fault=="skipped-position" and mankey and mankey.get("matchedLayerMask",0)&FIND_POSITION:
                changed["events"]=[e for e in changed.get("events",[]) if not (e.get("frame")==sample["frame"]
                    and e.get("kind")=="native-observation" and e.get("data",{}).get("observation")=="behavior-resolved")]
                self.applied=True
            if self.applied and self.fault not in ("flight-frozen","skipped-position"):break
        if self.fault=="missing-flight-return":
            kept=[e for e in changed.get("events",[]) if not (e.get("kind")=="native" and e.get("data",{}).get("event")=="CONTROL_RETURNED"
                and e.get("data",{}).get("actorHandle")==subjects.get("cargo",{}).get("handle",{}).get("value")
                and self.flight_start is not None and e.get("frame",0)>=self.flight_start)]
            if len(kept)!=len(changed.get("events",[])):changed["events"]=kept;self.applied=True
        if self.fault=="missing-follow-return" and row.get("action") in ("walk-player-right","normal-follow-return"):
            kept=[e for e in changed.get("events",[]) if not (e.get("kind")=="native" and e.get("data",{}).get("event")=="CONTROL_RETURNED"
                and e.get("data",{}).get("actorHandle")==subjects.get("mankey",{}).get("handle",{}).get("value"))]
            if len(kept)!=len(changed.get("events",[])):changed["events"]=kept;self.applied=True
        return changed if self.applied else row


class FollowerThrowFeatureNegative(FollowerThrowNegative):
    def __init__(self, feature, fault):
        require(feature == NON45_KIND and fault in faults(feature), "unknown non45 Follower Throw copied control")
        suffix = fault.split(":",1)[1]
        super().__init__(KIND + ":" + (suffix if KIND + ":" + suffix in FAULTS else "wrong-launch"))
        self.fault = suffix

    def mutate(self, row, subjects):
        if self.fault not in ("cardinal-fallback", "diagonal45", "wrong-support"):
            return super().mutate(row, subjects)
        if row.get("phase") != "observe":
            return row
        changed = deepcopy(row)
        for sample in changed.get("samples", []):
            cargo = next((a for a in sample.get("actors", [])
                          if a.get("handle") == subjects.get("cargo", {}).get("handle")), None)
            if cargo is None or cargo.get("motionKind") != "HOP":
                continue
            if self.fault == "wrong-support":
                if cargo.get("motionElapsed") == cargo.get("motionDuration"):
                    cargo["engineObject"]["pos_y"] += 4096
                    self.applied = True
            elif cargo.get("motionElapsed") == 0:
                origin = cargo["origin"]
                target = dict(x=origin["x"] + (0 if self.fault == "cardinal-fallback" else 8), y=origin["y"] + 8)
                cargo["target"] = target
                row = next(r for r in sample["pokemonCombat"]["targets"] if r["handle"] == cargo["handle"])
                native = bytearray.fromhex(row["motion"]["rawHex"])
                struct.pack_into("<2h", native, 12, target["x"], target["y"])
                native[29] = 8
                row["motion"] = decode_motion(bytes(native))
                self.applied = True
        return changed if self.applied else row


def validate_negative_result(feature,result=None,fault=None):
    if fault is None:
        result, fault = feature, result
        feature = fault.split(":",1)[0]
    require(feature == fault.split(":",1)[0], "Follower Throw copied control case differs")
    require(fault in faults(feature) and result.get("passed") is False and result.get("failures"), "Follower Throw copied control did not fail")
    expected={"missing-interactions":"interactions are absent", "stale-cargo":"different subject or role",
        "binding-loss":"lost or changed its bound trigger", "player-fallback":"used Player fallback",
        "cargo-motion-replaced":"replaced Cargo's accepted motion", "wrong-launch":"exact-range cardinal endpoint away",
        "flight-frozen":"flight lacks exact landing", "missing-follow-return":"normal follow return", "battle":"entered battle",
        "slow-search":"cargo displayed Hop time", "skipped-position":"authored Away modifier",
        "leakingboost":"normal displayed Hop time", "different-interest":"lost or changed its bound trigger",
        "short-range":"exact-range cardinal endpoint away", "toward-player":"exact-range cardinal endpoint away",
        "missing-flight-return":"flight did not return on time",
        "cardinal-fallback":"non45 Away projection", "diagonal45":"non45 Away projection",
        "wrong-support":"native landing support"}[fault.rsplit(":",1)[1]]
    if feature == NON45_KIND and fault.rsplit(":",1)[1] in ("wrong-launch", "short-range", "toward-player"):
        expected = "non45 Away projection"
    require(any(expected in str(f) for f in result.get("measurements",{}).get(feature,{}).get("failures",[])),
            "Follower Throw copied control failed for a different reason")
