"""One natural Follower Throw, from current Trigger/Cargo through follow return.

Uses the existing completed-queue interactions, actor motion and semantic trace.
Prepared placement earns no movement or profile credit.
"""
from copy import deepcopy
from pathlib import Path
import struct

from tools.overworld.devtools_application_bank import canonical_bank, local_application
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_cargo_route_continuity import packets, same_graph
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_moving_cargo_pickup import CargoAutonomy, checked_moving_pickup

KIND = "follower-throw-moving-cargo-v1"
REQUIREMENT = "current.follower-throw-moving-cargo"
NON45_KIND = "follower-throw-away-non45-v1"
NON45_REQUIREMENT = "current.follower-throw-away-non45"
SUBJECTS = (("mankey", 56, "FOLLOWER", "existing"),
            ("trigger", 69, "WILD", "spawn"), ("cargo", 69, "WILD", "spawn"))
SETUP = (("throw-tile", "teleport", {"map": 33, "x": 586, "z": 407, "facing": 1}),
         ("prepare-mankey", "party", {"slot": 0, "species": 56, "level": 20}),
         ("create-follower", "spawn", {"species": 56, "form": 0, "role": "follower", "slot": 0, "level": 20}),
         ("bind-mankey", "bind", {"subject": "mankey"}),
         ("spawn-trigger", "spawn", {"species": 69, "form": 0, "role": "wild", "level": 5, "x": 590, "z": 403}),
         ("bind-trigger", "bind", {"subject": "trigger"}),
         ("bind-cargo", "bind", {"subject": "cargo"}))
LAUNCH_LIMIT, RETURN_LIMIT = 600, 240
ACTIONS = (("natural-pickup-and-launch", "step", {"frames": LAUNCH_LIMIT, "keys": [],
            "until": {"kind": "measurement-stage", "measurement": KIND, "stage": "launched", "when": "final"}}),
           ("walk-player-right", "step", {"frames": 32, "keys": ["RIGHT"]}),
           ("normal-follow-return", "step", {"frames": RETURN_LIMIT, "keys": [],
            "until": {"kind": "measurement-stage", "measurement": KIND, "stage": "resumed", "when": "final"}}))
NON45_SETUP = tuple((name, op, dict(args, x=585, z=403) if name == "spawn-trigger" else args)
                    for name, op, args in SETUP)
NON45_ACTIONS = tuple((name, op, dict(args, until=dict(args["until"], measurement=NON45_KIND))
                      if "until" in args else args) for name, op, args in ACTIONS)


APPLICATION = application_index("apply-throw")
_BANK = canonical_bank(Path(__file__).resolve().parents[2])
_SPECIES = 56
APPLICATION_LOCAL = local_application(_BANK, _SPECIES, APPLICATION)
FOLLOWER = 1 << local_application(_BANK, _SPECIES, application_index("apply-follower"))
FIND_CARGO, FIND_POSITION, RELEASE, AWAY = (1 << local_application(_BANK, _SPECIES, application_index(n)) for n in
    ("apply-throw", "apply-throw-find-position", "apply-throw-release", "apply-throw-away"))
THROW_MASK = FIND_CARGO | FIND_POSITION | RELEASE | AWAY
TRIGGER_CONDITION, CARGO_CONDITION = 12365, 26783
THROW_RANGE, AWAY_TARGET = 8, 14
BOUNDARY = "main-task-queue-completion"
# Long Hop supplies time7. Each search application divides by2. The nearby
# normal Follower motion must remove both search overrides again.
SEARCH_TIME, NORMAL_TIME = 3, 7


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_recipe(test):
    non45 = test.get("measurements") == [dict(kind=NON45_KIND, subject="mankey")]
    require(test["id"] == ("follower.throw-away-non45" if non45 else "follower.throw-moving-cargo") and test["mode"] == "prepared"
            and test["requirements"] == [NON45_REQUIREMENT if non45 else REQUIREMENT]
            and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a) for n,s,r,a in SUBJECTS]
            and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == (NON45_SETUP if non45 else SETUP)
            and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == (NON45_ACTIONS if non45 else ACTIONS)
            and test["assertions"] == [{"kind": "measurement-complete", "measurement": NON45_KIND if non45 else KIND, "when": "final"}]
            and test["budgets"]["maxFrames"] <= 1100 and test["budgets"]["minObservedFrames"] == 2,
            "Follower Throw fixture or bounded natural input differs")


def require_non45_away(origin, target, player):
    outward = tuple(a-b for a,b in zip(origin, player))
    radius = max(abs(v) for v in outward)
    delta = tuple(a-b for a,b in zip(target, origin))
    require(radius > 0 and all(delta) and abs(delta[0]) != abs(delta[1])
            and max(abs(v) for v in delta) == THROW_RANGE
            and delta == tuple((1 if v >= 0 else -1) * ((abs(v)*THROW_RANGE + radius//2)//radius)
                               for v in outward)
            and max(abs(a-b) for a,b in zip(target,player)) > radius,
            "Follower Throw non45 Away projection differs from the authored outward vector")


def tile(actor, field="logical"):
    return tuple(actor[field][k] for k in ("x", "y"))


def raw_handle(handle):
    return struct.pack("<6H", *(handle[k] for k in ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")), 0)


def follower_moving_pickup(previous, current, events, source, subjects):
    """Authenticate Follower bindings, then the shared target-only handoff."""
    meter = FollowerThrowMeasurement(source)
    meter.subjects = subjects
    for sample in (previous, current):
        meter._boundary(sample)
        target = meter._actor(sample, "cargo")
        interest = meter._actor(sample, "trigger")
        carrier = meter._actor(sample, "mankey")
        require(target["handle"] == interest["handle"]
                and target["subjectIdentity"] == interest["subjectIdentity"]
                and target["engineIdentity"] == interest["engineIdentity"],
                "moving pickup Cargo is not the noticed Interest")
        row, state = meter._carrier(sample, carrier)
        for name, condition in (("trigger", TRIGGER_CONDITION), ("cargo", CARGO_CONDITION)):
            bound = row["bindings"][name]
            require(bound["bound"] is True and bound["targetCurrent"] is True
                    and bound["sourceConditionId"] == condition
                    and bound["sourceApplication"] == APPLICATION
                    and bound["sourceApplicationLocal"] == APPLICATION_LOCAL and bound["lifetime"] == 0
                    and bound["target"] == {"kind": "ACTOR", "actor": target["handle"]},
                    "moving pickup Follower binding differs")
        flags = row["throw"]
        require(flags["targetSlot"] == target["handle"]["slot"] and flags["carrier"]
                and state["targetMask"] & (1 << target["handle"]["slot"])
                and flags["carried"] is (sample is current) and not flags["windup"],
                "moving pickup Follower claim is not free Cargo then HELD")
    return checked_moving_pickup(previous, current, events, source,
        meter._actor(previous, "cargo"), meter._actor(current, "cargo"),
        meter._actor(previous, "mankey"), meter._actor(current, "mankey"))


class FollowerThrowMeasurement:
    def __init__(self, source, feature=KIND):
        require(feature in (KIND, NON45_KIND), "unknown Follower Throw case")
        self.kind = feature
        self.requirement = NON45_REQUIREMENT if feature == NON45_KIND else REQUIREMENT
        self.setup = NON45_SETUP if feature == NON45_KIND else SETUP
        self.actions = NON45_ACTIONS if feature == NON45_KIND else ACTIONS
        require(set(source) == ({"contractVersion", "romSha256", "overlaySha256", "profileSha256"}
                | ({"queryImage"} if source["contractVersion"] == 2 else set()))
                and source["contractVersion"] in (1, 2), "Follower Throw source identity differs")
        self.source = source
        self.latest = self.initial = self.terminal = None
        self.subjects = {}
        self.setup_index = self.action_index = self.observed_frames = 0
        self.setup_frames = 0
        self.action_frames = [0,0,0]
        self.failures = []
        self.frames = {}
        self.binding_witness = None
        self.cargo_walk = self.follow_motion = None
        self.windup_target = None
        self.trigger_moved = False
        self.flight_moved = False
        self.launch_pose = None
        self.cargo_completed = False
        self.moving_pickup = None
        self.party_hp = None
        self.profiles = {}
        self.speed_motion = None
        self.speed_witnesses = {}
        self.route_hop = self.route_witness = None
        self.position_profile = self.flight = self.flight_witness = None
        self.launch_endpoint = None
        self.autonomy = CargoAutonomy(source) if feature == KIND and source["contractVersion"] == 2 else None

    def _autonomy(self, sample, events):
        if self.autonomy is None or "cargo" not in self.subjects:
            return
        actor = self._actor(sample, "cargo")
        targets = sample.get("pokemonCombat", {}).get("interactions", {}).get("throwState", {}).get("targets", [])
        codes = [v for v in targets if v & 63 == actor["handle"]["slot"] + 1]
        self.autonomy.observe(sample, actor, events, self.profiles,
                              claimed=bool(codes), held=any(v & 128 for v in codes))

    def _profile_events(self, events):
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "native-observation" and data.get("observation") == "behavior-resolved" \
                    and data.get("resolved") is True:
                raw = bytes.fromhex(data["resultHex"])
                require(len(raw) == 216 and struct.unpack_from("<I", raw, 192)[0] == data["fingerprint"]
                        and struct.unpack_from("<I", raw, 188)[0] == data["appliedOverrides"]
                        and data.get("lanes") == [raw[:80].hex(), raw[80:160].hex()]
                        and data.get("sourceSha256") == self.source["profileSha256"],
                        "Follower Throw native profile receipt differs")
                self.profiles[data["fingerprint"]] = deepcopy(data)

    def _speed_sample(self, sample, mankey, flags, follower_events, *, stage=None):
        """Bind three ordinary Hops to the existing profile/motion receipts.

        Complete the old command before reading a possible same-frame new
        admission. Native control-return valueB is its completed commit ID.
        """
        frame = sample["frame"]
        pose = tuple(mankey["engineObject"][k] for k in ("pos_x", "pos_z", "unk88_y"))
        require(all(type(v) is int for v in pose), "Follower Throw carrier native pose is missing")
        active = self.speed_motion
        if active is not None:
            commit = active["commitBefore"] + 1
            require(not any(e.get("event") == "MOTION_CANCELED" for e in follower_events),
                    "Follower Throw search motion was canceled")
            active["lifecycle"].extend(deepcopy(e) for e in follower_events
                if e.get("event") in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"))
            returned = any(e.get("event") == "CONTROL_RETURNED" and e.get("valueB") == commit for e in follower_events)
            if returned:
                expected = [("MOTION_STARTED", 2, active["duration"]), ("LOGICAL_COMMIT", commit, 2),
                            ("MOTION_FINISHED", commit, 2), ("CONTROL_RETURNED", 0, commit)]
                require([(e["event"], e["valueA"], e["valueB"]) for e in active["lifecycle"]] == expected
                        and mankey["commitSequence"] == commit
                        and frame == active["startFrame"] + active["duration"] + active["pauseFrames"]
                        and pose == tuple((v << 16) + 32768 for v in active["target"]) + (0,)
                        and len(active["poses"]) == active["duration"] + 1
                        and len({tuple(p["pose"][:2]) for p in active["poses"]}) >= 3
                        and any(p["pose"][2] > 0 for p in active["poses"]),
                        "Follower Throw complete carrier speed witness lacks native landing or control return")
                active["returnFrame"] = frame
                active["commitAfter"] = commit
                self.speed_witnesses[active["stage"]] = deepcopy(active)
                self.speed_motion = None
            else:
                elapsed = frame - active["startFrame"]
                if elapsed <= active["duration"]:
                    require(mankey["motionKind"] == "HOP"
                            and tile(mankey, "origin") == tuple(active["origin"])
                            and tile(mankey, "target") == tuple(active["target"])
                            and mankey["motionDuration"] == active["duration"]
                            and mankey["motionElapsed"] == elapsed
                            and mankey["commitSequence"] == active["commitBefore"] + int(elapsed == active["duration"]),
                            "Follower Throw carrier speed command was replaced or paused")
                    if elapsed == active["duration"]:
                        require(any(e.get("event") == "LOGICAL_COMMIT" and e.get("valueA") == commit
                                    and e.get("valueB") == 2 for e in follower_events)
                                and pose == tuple((v << 16) + 32768 for v in active["target"]) + (0,),
                                "Follower Throw carrier speed command lacks its timed commit")
                    active["poses"].append(dict(frame=frame, elapsed=elapsed, pose=list(pose)))
                else:
                    require(elapsed < active["duration"] + active["pauseFrames"]
                            and mankey["commitSequence"] == commit and mankey["motionPhase"] == "SETTLING",
                            "Follower Throw normal follow return or search control did not return on time")
        if self.speed_motion is not None:
            return
        mask = mankey.get("matchedLayerMask", 0)
        stage = stage or ("cargo" if mask & FIND_CARGO and not flags["carried"] else
                 "position" if mask & FIND_POSITION and flags["carried"] and not flags["windup"] and not mask & RELEASE else
                 "normal" if self.frames.get("launch") is not None and not mask & THROW_MASK
                 and not flags["recovering"] and not flags["targetRaw"] else None)
        if stage is None or stage in self.speed_witnesses or mankey.get("motionKind") != "HOP" \
                or mankey.get("motionPhase") != "MOVING" or mankey.get("motionElapsed") != 0:
            return
        starts = [e for e in follower_events if e.get("event") == "MOTION_STARTED"]
        if not starts:
            return
        profile = self.profiles.get(mankey["behaviorFingerprint"])
        require(profile is not None and profile["appliedOverrides"] == mask and mask & FOLLOWER,
                "Follower Throw carrier speed lacks the same resolved native profile")
        lane = bytes.fromhex(profile["lanes"][0])
        time = NORMAL_TIME if stage == "normal" else SEARCH_TIME
        require(lane[7] == time and lane[36] == time,
                "Follower Throw " + stage + " speed does not match authored search boost or normal return")
        rows = [r for r in sample["pokemonCombat"].get("targets", []) if r.get("handle") == mankey["handle"]]
        require(len(rows) == 1 and rows[0].get("role") == "FOLLOWER", "Follower Throw carrier speed lacks native motion bytes")
        motion = decode_motion(bytes.fromhex(rows[0]["motion"]["rawHex"]))
        require(motion == rows[0]["motion"], "Follower Throw carrier speed decoded motion differs")
        plan = motion["plan"]
        require(plan["pauseFrames"] == lane[22],
                "Follower Throw Hop pause differs from its authored profile")
        distance = max(abs(a-b) for a,b in zip(plan["origin"], plan["target"]))
        duration = min(65535, time + (distance-1) * (time-(time >> 2))
                       + ((abs(plan["targetBaseY"]-plan["startBaseY"]) >> 12) * time * lane[48]) // 1600)
        require(plan["version"] == 1 and plan["kind"] == 2 and motion["phase"] == "MOVING" and motion["elapsed"] == 0
                and plan["fieldEpoch"] == mankey["handle"]["fieldEpoch"]
                and plan["behaviorFingerprint"] == mankey["behaviorFingerprint"] & 65535
                and plan["origin"] == list(tile(mankey,"origin")) and plan["target"] == list(tile(mankey,"target"))
                and plan["distance"] == distance and distance > 0
                and plan["duration"] == mankey["motionDuration"] == duration
                and plan["reservationId"] == mankey["reservationId"] != 0
                and starts == [dict(starts[0], valueA=2, valueB=duration)]
                and pose == tuple((v << 16) + 32768 for v in plan["origin"]) + (0,),
                "Follower Throw " + stage + " displayed Hop time differs from its authored profile")
        require(stage == "normal" or (lane[20] <= distance <= lane[21] and plan["startBaseY"] == plan["targetBaseY"]),
                "Follower Throw search speed witness needs a flat Hop within its authored distance range")
        self.speed_motion = dict(stage=stage, handle=deepcopy(mankey["handle"]),
            subjectIdentity=mankey["subjectIdentity"], engineIdentity=deepcopy(mankey["engineIdentity"]),
            startFrame=frame, commitBefore=mankey["commitSequence"], origin=plan["origin"], target=plan["target"],
            duration=duration, pauseFrames=plan["pauseFrames"], plan=deepcopy(plan), profile=deepcopy(profile),
            lifecycle=deepcopy(starts), poses=[dict(frame=frame, elapsed=0, pose=list(pose))])

    def _route_sample(self, sample, mankey, events):
        if self.source["contractVersion"] != 2 or self.route_witness is not None:
            return
        motion = self.speed_motion
        if self.route_hop is None and motion is not None and motion["stage"] == "cargo":
            require(mankey["engineObject"].get("x_range") == mankey["engineObject"].get("y_range") == -1,
                    "Follower Throw route witness requires unlimited native ranges")
            self.route_hop = dict(startFrame=motion["startFrame"], duration=motion["duration"],
                returnFrame=motion["startFrame"]+motion["duration"]+motion["pauseFrames"],
                commitSequence=motion["commitBefore"]+1, observations=[])
        active = self.route_hop
        if active is None:
            return
        frame = sample["frame"]
        if frame < active["startFrame"]+active["duration"] or frame == active["returnFrame"]:
            current = packets(sample, events, mankey, self.source["queryImage"], self.latest["nativeCycle"])
            require(current, "Follower Throw lacks a current route read during Hop or return")
            for row in current:
                require(row["workspace"]["compatibility"]["cargo"]==self.subjects["cargo"]["handle"],
                        "Follower Throw route query names a different Cargo")
                if active["observations"]:
                    same_graph(active["observations"][0], row)
                active["observations"].append(row)
        if frame == active["returnFrame"]:
            complete = self.speed_witnesses.get("cargo")
            require(complete is not None and complete["returnFrame"] == frame
                    and complete["commitAfter"] == active["commitSequence"],
                    "Follower Throw route key lacks its complete authored Hop return")
            self.route_witness = deepcopy(active)

    def _boundary(self, sample, fixture=True):
        require(sample.get("fieldAvailable") is True and sample.get("observationBoundary") == BOUNDARY
                and sample.get("romSha256") == self.source["romSha256"]
                and type(sample.get("frame")) is int and type(sample.get("nativeCycle")) is int
                and sample.get("fieldControl", {}).get("taskPointer") == 0,
                "Follower Throw lacks a completed field queue or entered battle")
        if fixture:
            require(sample.get("context", {}).get("mapId") == 33, "Follower Throw left Route29")

    def _actor(self, sample, name):
        selected = select_current_actor(sample, self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])

    def _carrier(self, sample, mankey):
        combat = sample.get("pokemonCombat", {})
        value = combat.get("interactions", {})
        require(combat.get("available") is True and combat.get("frame") == sample["frame"]
                and combat.get("nativeCycle") == sample["nativeCycle"]
                and combat.get("identity", {}).get("overlaySha256") == self.source["overlaySha256"]
                and combat["identity"].get("romSha256") == self.source["romSha256"]
                and value.get("schemaVersion") == 1 and value.get("available") is True
                and value.get("frame") == sample["frame"] and value.get("nativeCycle") == sample["nativeCycle"]
                and value.get("observationBoundary") == BOUNDARY
                and value.get("fieldSystem") == sample["fieldControl"].get("fieldPointer")
                and value.get("identity", {}).get("romSha256") == self.source["romSha256"],
                "Follower Throw interactions are absent, stale, or unauthenticated")
        rows = [r for r in value.get("carriers", []) if r.get("handle") == mankey["handle"]]
        require(len(rows) == 1 and rows[0].get("available") is True and rows[0].get("role") == "FOLLOWER",
                "Follower Throw carrier is absent or stale")
        row = rows[0]
        raw = bytes.fromhex(row.get("rawBindingsHex", ""))
        require(len(raw) == 60 and raw[:12] == raw_handle(mankey["handle"]),
                "Follower Throw native binding subject differs")
        for key, start in (("trigger", 12), ("cargo", 36)):
            bound = row["bindings"][key]
            data = raw[start:start+24]
            require(data.hex() == bound.get("rawHex") and data[13] == 0
                    and data[12] == {"NONE": 0, "PLAYER": 1, "ACTOR": 2}.get(bound["target"]["kind"])
                    and struct.unpack_from("<HIBBBB", data, 14) == (bound["sourceConditionId"], bound["expiresAt"],
                        bound["sourceApplicationLocal"], bound["lifetime"], bound["flags"], bound["reason"])
                    and bound["bound"] is bool(bound["flags"]),
                    "Follower Throw raw binding receipt differs")
            if bound["target"]["kind"] == "ACTOR":
                require(data[:12] == raw_handle(bound["target"]["actor"]), "Follower Throw raw target handle differs")
            require(bound["target"]["kind"] != "PLAYER", "Follower Throw used Player fallback")
        state = value["throwState"]
        native = bytes.fromhex(state["rawHex"])
        require(len(native) == 16 and list(native[:10]) == state["targets"]
                and struct.unpack_from("<3H", native, 10) == (state["targetMask"],state["carrierMask"],state["recoveringMask"]),
                "Follower Throw raw claim masks differ")
        slot = mankey["handle"]["slot"]; target = native[slot]
        expect = dict(targetRaw=target, targetSlot=((target&63)-1 if target else None),
            carried=bool(target&128), windup=bool(target&64), targeted=bool(state["targetMask"]&(1<<slot)),
            carrier=bool(state["carrierMask"]&(1<<slot)), recovering=bool(state["recoveringMask"]&(1<<slot)))
        require(row.get("throw") == expect, "Follower Throw claim receipt differs")
        return row, state

    def _events(self, events, actor):
        found = []
        identity = {k:v for k,v in actor["handle"].items() if k != "value"}
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "trace-status":
                require(data.get("code") not in ("unread-events-lost", "sequence-reset", "invalid-native-ring", "trace-filter-changed")
                        and data.get("unreadEventsLost", 0) == 0 and data.get("coverageComplete", True) is True,
                        "Follower Throw semantic trace is incomplete")
            if event.get("kind") == "native" and data.get("actorHandle") == actor["handle"]["value"]:
                require(data.get("actor") == identity and type(data.get("sequence")) is int,
                        "Follower Throw semantic event has a stale handle")
                found.append(data)
        return found

    def _sample(self, sample, events):
        self._boundary(sample)
        self._profile_events(events)
        if self.latest is not None:
            require(sample["frame"] == self.latest["frame"]+1, "Follower Throw completed-frame stream has a gap")
        actors = {n:self._actor(sample,n) for n,_,_,_ in SUBJECTS}
        mankey, trigger, cargo = (actors[n] for n in ("mankey","trigger","cargo"))
        require(trigger["handle"] == cargo["handle"] and trigger["subjectIdentity"] == cargo["subjectIdentity"]
                and trigger["engineIdentity"] == cargo["engineIdentity"]
                and mankey["handle"] != cargo["handle"],
                "Follower Throw Cargo is not the exact noticed Object of interest")
        party = [p for p in sample.get("party",[]) if p.get("personality") == mankey["subjectIdentity"]]
        require(len(party)==1 and party[0].get("identityVerified") is True and party[0].get("species")==56
                and party[0].get("hp",0)>0, "Follower Throw lacks the same living party Mankey")
        if self.party_hp is None:self.party_hp=party[0]["hp"]
        require(party[0]["hp"] == self.party_hp, "Follower Throw damaged its allied carrier")
        carrier, state = self._carrier(sample,mankey)
        flags = carrier["throw"]; bindings = carrier["bindings"]
        cargo_events = self._events(events,cargo); follower_events = self._events(events,mankey)
        self._autonomy(sample, events)
        require(not any(e.get("event")=="MOTION_CANCELED" for e in follower_events),
                "Follower Throw canceled its accepted carrier motion")
        self._speed_sample(sample, mankey, flags, follower_events)
        self._route_sample(sample, mankey, events)
        frame = sample["frame"]
        self.observed_frames += 1
        require(self.observed_frames <= LAUNCH_LIMIT+RETURN_LIMIT+32, "Follower Throw exceeded its frame bound")
        if trigger.get("motionKind")=="WALK" and trigger.get("motionPhase")=="MOVING":self.trigger_moved=True
        launch = (self.frames.get("windup") is not None and self.frames.get("launch") is None
                  and flags["recovering"] and not flags["carried"] and flags["targetRaw"]==0
                  and cargo.get("motionKind")=="HOP" and cargo.get("motionPhase")=="MOVING")
        if bindings["cargo"]["bound"] and self.frames.get("cargoBound") is None:
            require(mankey.get("matchedLayerMask",0)&FIND_CARGO, "Follower Throw bound Cargo lacks Find Throw Cargo")
            self.frames["cargoBound"]=frame
            self.binding_witness={k:deepcopy(bindings[k]) for k in ("trigger","cargo")}
        if self.frames.get("cargoBound") is not None and self.frames.get("launch") is None and not launch:
            for name, condition in (("trigger",TRIGGER_CONDITION),("cargo",CARGO_CONDITION)):
                bound=bindings[name]
                require(bound["bound"] is True and bound["targetCurrent"] is True
                        and bound["sourceConditionId"]==condition and bound["sourceApplication"]==APPLICATION
                        and bound["sourceApplicationLocal"]==APPLICATION_LOCAL
                        and bound["lifetime"]==0 and bound["target"] == {"kind":"ACTOR","actor":actors[name]["handle"]},
                        "Follower Throw lost or changed its bound "+name+" before launch")
        if flags["targetRaw"]:
            require(flags["targetSlot"]==cargo["handle"]["slot"] and flags["carrier"]
                    and state["targetMask"] & (1<<cargo["handle"]["slot"]),
                    "Follower Throw claimed a different Cargo")
            self.frames.setdefault("claim",frame)
        if self.cargo_walk is None and self.frames.get("cargoBound") and not flags["carried"] \
                and cargo.get("motionKind")=="WALK" and cargo.get("motionPhase")=="MOVING":
            self.cargo_walk=dict(origin=tile(cargo,"origin"),target=tile(cargo,"target"),duration=cargo["motionDuration"],
                elapsed=cargo["motionElapsed"],commit=cargo["commitSequence"],frame=frame,samples=0)
            self.frames["cargoWalk"]=frame
        canceled = any(e.get("event") == "MOTION_CANCELED" for e in cargo_events)
        if flags["carried"] and self.frames.get("pickup") is None:
            prior_cargo = self._actor(self.latest, "cargo")
            if prior_cargo.get("motionPhase") in ("MOVING", "SETTLING") and not canceled:
                commit = prior_cargo["commitSequence"] + 1
                kind = {"WALK": 1, "HOP": 2}.get(prior_cargo.get("motionKind"))
                require(kind is not None and cargo["commitSequence"] == commit
                        and cargo["inputOwnership"] == 0
                        and [(e["event"], e["valueA"], e["valueB"]) for e in cargo_events
                             if e.get("event") in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]
                            == [("LOGICAL_COMMIT", commit, kind), ("MOTION_FINISHED", commit, kind),
                                ("CONTROL_RETURNED", 0, commit)],
                        "moving pickup lacks Cargo CANCEL or its exact natural control return")
        if canceled:
            require(flags["carried"] and self.frames.get("pickup") is None,
                    "Follower Throw canceled Cargo's accepted motion before carry")
            self.moving_pickup = follower_moving_pickup(self.latest, sample, events, self.source, self.subjects)
            self.cargo_completed = True
            self.frames["cargoControl"] = frame
        if self.cargo_walk is not None and not self.cargo_completed:
            walk=self.cargo_walk
            require(not any(e.get("event")=="MOTION_CANCELED" for e in cargo_events),
                    "Follower Throw canceled Cargo's accepted motion before carry")
            if cargo["commitSequence"]==walk["commit"]+1:
                commit=cargo["commitSequence"]
                require([(e["event"],e["valueA"],e["valueB"]) for e in cargo_events
                            if e.get("event") in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
                        == [("LOGICAL_COMMIT",commit,1),("MOTION_FINISHED",commit,1),("CONTROL_RETURNED",0,commit)]
                        and walk["samples"]>=2 and cargo["inputOwnership"]==0,
                        "Follower Throw Cargo motion lacks its own completion and free control")
                self.cargo_completed=True;self.frames["cargoCommit"]=self.frames["cargoControl"]=frame
            else:
                require(cargo["commitSequence"]==walk["commit"] and not flags["carried"]
                        and cargo.get("motionKind")=="WALK" and cargo.get("motionPhase")=="MOVING"
                        and tile(cargo,"origin")==walk["origin"] and tile(cargo,"target")==walk["target"]
                        and cargo["motionDuration"]==walk["duration"]
                        and (frame==walk["frame"] or cargo["motionElapsed"]==walk["elapsed"]+1),
                        "Follower Throw froze or replaced Cargo's accepted motion")
                walk["elapsed"]=cargo["motionElapsed"];walk["samples"]+=1
        if flags["carried"]:
            require(self.frames.get("claim") is not None and self.cargo_completed,
                    "Follower Throw carried Cargo before its checked motion control return")
            self.frames.setdefault("pickup",frame)
            if mankey.get("matchedLayerMask",0)&FIND_POSITION:
                self.frames.setdefault("position",frame)
                resolved=self.profiles.get(mankey["behaviorFingerprint"])
                require(resolved is not None and resolved["appliedOverrides"]==mankey["matchedLayerMask"]
                        and mankey["matchedLayerMask"] & AWAY, "Follower Throw held phase lacks its authored Away modifier")
                lane=bytes.fromhex(resolved["lanes"][0])
                require(lane[13]==AWAY_TARGET and lane[7]==lane[36]==SEARCH_TIME and lane[76]==THROW_RANGE,
                        "Follower Throw Find Position profile lacks half speed or exact Away aim")
                self.position_profile=deepcopy(resolved)
            if flags["windup"]:
                require(mankey.get("matchedLayerMask",0)&RELEASE, "Follower Throw windup lacks Throw Held Actor")
                if "windup" not in self.frames:
                    self.frames["windup"]=frame
                    require(self.position_profile is not None, "Follower Throw lacks its resolved Find Position phase")
        if launch:
            require(self.trigger_moved and self.cargo_completed and self.frames.get("pickup") is not None,
                    "Follower Throw launched without moving Trigger/Cargo and pickup")
            self._start_flight(sample,mankey,cargo,cargo_events)
            prior=self._actor(self.latest,"mankey")
            require(tile(cargo,"origin")==tuple(prior["engineObject"][k] for k in ("x","y")),
                    "Follower Throw launch origin differs from its real carrier")
            self.frames["launch"]=frame
            self.launch_pose=tuple(cargo["engineObject"][k] for k in ("pos_x","pos_z"))
        if self.frames.get("launch") is not None:
            if not bindings["trigger"]["bound"] and not bindings["cargo"]["bound"]:
                self.frames.setdefault("bindingsCleared",frame)
            if frame>self.frames["launch"] and cargo.get("motionKind")=="HOP" and cargo.get("motionPhase")=="MOVING":
                pose=tuple(cargo["engineObject"][k] for k in ("pos_x","pos_z"))
                require(all(type(n) is int for n in pose), "Follower Throw Cargo native pose is missing")
                self.flight_moved |= pose!=self.launch_pose
            if not flags["recovering"] and not flags["targetRaw"] and not flags["carrier"] and not flags["targeted"] \
                    and not bindings["cargo"]["bound"] and not mankey.get("matchedLayerMask",0)&THROW_MASK \
                    and mankey.get("matchedLayerMask",0)&FOLLOWER:
                if self.follow_motion is None and mankey.get("motionKind") in ("WALK","HOP") \
                        and mankey.get("motionPhase")=="MOVING" and any(e.get("event")=="MOTION_STARTED" for e in follower_events):
                    require(self.frames.get("bindingsCleared",frame)>=self.frames["launch"]
                            and self.frames.get("bindingsCleared",frame)<frame,
                            "Follower Throw did not clear its old bindings before normal follow")
                    self.follow_motion=dict(commit=mankey["commitSequence"],origin=tile(mankey,"origin"),target=tile(mankey,"target"),frame=frame)
                    self.frames["followStart"]=frame
                if self.follow_motion is not None and mankey["commitSequence"]==self.follow_motion["commit"]+1 \
                        and any(e.get("event")=="CONTROL_RETURNED" for e in follower_events):
                    require(tile(mankey)==self.follow_motion["target"]
                            and any(e.get("event")=="CONTROL_RETURNED" and e.get("valueB")==mankey["commitSequence"] for e in follower_events)
                            and tuple(mankey["engineObject"][k] for k in ("pos_x","pos_z"))==tuple((v<<16)+32768 for v in self.follow_motion["target"]),
                            "Follower Throw normal follow did not release its prior targets")
                    fresh=bindings["trigger"]
                    if fresh["bound"]:
                        require(fresh["flags"]==1 and fresh["targetCurrent"] is True
                                and fresh["sourceConditionId"]==TRIGGER_CONDITION and fresh["sourceApplication"]==APPLICATION
                                and fresh["sourceApplicationLocal"]==APPLICATION_LOCAL
                                and fresh["lifetime"]==0 and fresh["target"]["kind"]=="ACTOR",
                                "Follower Throw new Trigger is not a current authored binding")
                        candidates=[a for a in sample["actors"] if a.get("handle")==fresh["target"]["actor"]]
                        require(len(candidates)==1 and candidates[0].get("role")=="WILD",
                                "Follower Throw new Trigger lacks a current Wild actor")
                        select_current_actor(sample,candidates[0])
                    self.frames.setdefault("followReturn",frame)
        self._flight_sample(sample,cargo,cargo_events)
        self.latest=self.terminal=deepcopy(sample)

    def _start_flight(self,sample,mankey,cargo,events):
        rows=[r for r in sample["pokemonCombat"].get("targets",[]) if r.get("handle")==cargo["handle"]]
        require(len(rows)==1 and rows[0].get("role")=="WILD", "Follower Throw flight lacks its current Cargo motion")
        motion=decode_motion(bytes.fromhex(rows[0]["motion"]["rawHex"]))
        require(motion==rows[0]["motion"], "Follower Throw flight motion decode differs")
        plan=motion["plan"];origin=tile(cargo,"origin");target=tile(cargo,"target")
        player=tuple(sample["player"][k] for k in ("x","y"))
        non45 = self.kind == NON45_KIND
        distance=max(abs(a-b) for a,b in zip(origin,target)) if non45 else sum(abs(a-b) for a,b in zip(origin,target))
        if non45:
            require_non45_away(origin, target, player)
            prior = self._actor(self.latest, "mankey")
            released = self.profiles.get(prior["behaviorFingerprint"])
            require(released is not None and released["appliedOverrides"] == prior["matchedLayerMask"]
                    and prior["matchedLayerMask"] & RELEASE and prior["matchedLayerMask"] & AWAY,
                    "Follower Throw non45 flight lacks its current resolved release profile")
            lane = bytes.fromhex(released["lanes"][0])
            expected = min(65535, SEARCH_TIME + (THROW_RANGE-1)*(SEARCH_TIME-(SEARCH_TIME >> 2))
                           + ((abs(plan["targetBaseY"]-plan["startBaseY"]) >> 12)*SEARCH_TIME*lane[48]) // 1600)
            require(lane[36] == SEARCH_TIME and plan["duration"] == expected
                    and cargo["engineObject"].get("pos_y") == plan["startBaseY"],
                    "Follower Throw non45 flight time or starting support differs")
        require(plan["version"]==1 and plan["kind"]==2 and plan["fieldEpoch"]==cargo["handle"]["fieldEpoch"]
                and plan["behaviorFingerprint"]==cargo["behaviorFingerprint"]&65535
                and plan["origin"]==list(origin) and plan["target"]==list(target)
                and plan["distance"]==distance==THROW_RANGE
                and (non45 or origin[0]==target[0] or origin[1]==target[1])
                and max(abs(a-b) for a,b in zip(target,player))>max(abs(a-b) for a,b in zip(origin,player))
                and motion["phase"]=="MOVING" and motion["elapsed"]==0
                and plan["duration"]==cargo["motionDuration"]>0
                and plan["reservationId"]==cargo["reservationId"]!=0
                and [(e["event"],e["valueA"],e["valueB"]) for e in events if e.get("event")=="MOTION_STARTED"]
                    ==[("MOTION_STARTED",2,plan["duration"])],
                "Follower Throw native launch is not an exact-range " + ("non45" if non45 else "cardinal") + " endpoint away from Player")
        self.launch_endpoint=dict(frame=sample["frame"],origin=list(origin),target=list(target),player=list(player),
            distance=distance,targetBaseY=plan["targetBaseY"],plan=deepcopy(plan))
        if non45:
            self.launch_endpoint["releaseProfile"] = deepcopy(released)
        self.flight=dict(startFrame=sample["frame"],handle=deepcopy(cargo["handle"]),
            subjectIdentity=cargo["subjectIdentity"],engineIdentity=deepcopy(cargo["engineIdentity"]),
            commitBefore=cargo["commitSequence"],duration=plan["duration"],pauseFrames=plan["pauseFrames"],
            plan=deepcopy(plan),poses=[],lifecycle=deepcopy([e for e in events if e.get("event")=="MOTION_STARTED"]))

    def _flight_sample(self,sample,cargo,events):
        active=self.flight
        if active is None:return
        frame=sample["frame"];elapsed=frame-active["startFrame"];commit=active["commitBefore"]+1
        require(not any(e.get("event")=="MOTION_CANCELED" for e in events), "Follower Throw canceled Cargo flight")
        active["lifecycle"].extend(deepcopy(e) for e in events
            if e.get("event") in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"))
        pose=[cargo["engineObject"][k] for k in ("pos_x","pos_z","unk88_y")]
        require(all(type(v) is int for v in pose), "Follower Throw flight pose is missing")
        if elapsed<=active["duration"]:
            require(cargo["motionKind"]=="HOP" and cargo["motionElapsed"]==elapsed
                    and cargo["motionDuration"]==active["duration"]
                    and tile(cargo,"origin")==tuple(active["plan"]["origin"])
                    and tile(cargo,"target")==tuple(active["plan"]["target"])
                    and cargo["commitSequence"]==active["commitBefore"]+int(elapsed==active["duration"]),
                    "Follower Throw flight was paused or replaced")
            active["poses"].append(dict(frame=frame,elapsed=elapsed,pose=pose))
            if self.kind == NON45_KIND:
                support = cargo["engineObject"].get("pos_y")
                require(type(support) is int, "Follower Throw non45 flight lacks native support height")
                active["poses"][-1]["supportY"] = support
                if elapsed == active["duration"]:
                    require(support == active["plan"]["targetBaseY"],
                            "Follower Throw non45 native landing support differs")
        if any(e.get("event")=="CONTROL_RETURNED" and e.get("valueB")==commit for e in events):
            require(elapsed==active["duration"]+active["pauseFrames"]
                    and [(e["event"],e["valueA"],e["valueB"]) for e in active["lifecycle"]]==[
                        ("MOTION_STARTED",2,active["duration"]),("LOGICAL_COMMIT",commit,2),
                        ("MOTION_FINISHED",commit,2),("CONTROL_RETURNED",0,commit)]
                    and len(active["poses"])==active["duration"]+1
                    and active["poses"][-1]["pose"]==[(v<<16)+32768 for v in active["plan"]["target"]]+[0]
                    and cargo["commitSequence"]==commit and cargo["inputOwnership"]==0,
                    "Follower Throw flight lacks exact landing and free control")
            active.update(returnFrame=frame,commitAfter=commit)
            self.flight_witness=deepcopy(active);self.flight=None
        else:
            require(elapsed<active["duration"]+active["pauseFrames"], "Follower Throw Cargo flight did not return on time")

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase")=="setup", "Follower Throw initial boundary is misplaced")
                self._boundary(row["initialSnapshot"],False);self.latest=deepcopy(row["initialSnapshot"])
                self._profile_events(row.get("initialEvents", []))
                return self.result()
            if row.get("phase")=="setup":
                require(self.setup_index<len(self.setup) and row.get("action")==self.setup[self.setup_index][0], "Follower Throw setup order differs")
                _,op,args=self.setup[self.setup_index]
                if op=="step":
                    require("command" not in row, "Follower Throw Trigger wait must use normal frames")
                    for sample,events,_ in validate_raw_chunk(row,self.latest):
                        self._profile_events(events)
                        self._boundary(sample);self.latest=deepcopy(sample)
                        if on_sample:on_sample(sample,self.observed_frames)
                    self.setup_frames+=row["completedGameFrames"]
                    require(self.setup_frames<=args["frames"], "Follower Throw Trigger wait frame count differs")
                    if self.setup_frames<args["frames"]:return self.result()
                else:
                    require(row.get("command")==op, "Follower Throw setup command differs")
                    sample=row["snapshot"];self._boundary(sample)
                    self._profile_events(row.get("events", []) + row.get("receipt", {}).get("events", []))
                    if op=="bind":
                        name=self.setup[self.setup_index][2]["subject"]
                        selected=select_current_actor(sample,row["receipt"])
                        require(selected["species"]==dict((n,s) for n,s,_,_ in SUBJECTS)[name]
                                and selected["role"]==dict((n,r) for n,_,r,_ in SUBJECTS)[name], "Follower Throw bound role or species differs")
                        self.subjects[name]=deepcopy(row["receipt"])
                        if name=="mankey":
                            actor=self._actor(sample,name)
                            require(tile(actor)==(586,408) and actor["motionKind"]=="NONE" and actor["motionPhase"]=="IDLE"
                                    and actor["reservationId"]==0,
                                    "Follower Throw Mankey did not settle behind the player")
                    self.latest=deepcopy(sample)
                    self._autonomy(sample, row.get("events", []) + row.get("receipt", {}).get("events", []))
                self.setup_index+=1
                if self.setup_index==len(self.setup):self.initial=deepcopy(self.latest)
                return self.result()
            require(self.setup_index==len(self.setup) and self.action_index<len(self.actions)
                    and row.get("action")==self.actions[self.action_index][0] and row.get("phase")=="observe" and "command" not in row,
                    "Follower Throw action order differs")
            action=self.action_index
            for sample,events,_ in validate_raw_chunk(row,self.latest):
                self.action_frames[action]+=1
                require(self.action_frames[action]<=self.actions[action][2]["frames"], "Follower Throw action frame bound exceeded")
                self._sample(sample,events)
                if on_sample:on_sample(sample,self.observed_frames)
            if (action==0 and self.stage("launched")) or (action==1 and self.action_frames[1]==32) or (action==2 and self.stage("resumed")):self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def stage(self,name):
        require(name in ("launched","resumed"), "unknown Follower Throw stage")
        return not self.failures and ("launch" in self.frames if name=="launched" else
            "followReturn" in self.frames and {"cargo", "normal"} <= set(self.speed_witnesses) \
            and self.position_profile is not None and self.speed_motion is None and self.flight_witness is not None
            and (self.autonomy is None or self.autonomy.result()["ready"])
            and (self.source["contractVersion"] == 1 or self.route_witness is not None))

    def result(self):
        ready=not self.failures and self.action_index==len(self.actions) and "followReturn" in self.frames and self.flight_moved \
            and {"cargo", "normal"} <= set(self.speed_witnesses) \
            and self.position_profile is not None and self.speed_motion is None and self.flight_witness is not None \
            and (self.autonomy is None or self.autonomy.result()["ready"]) \
            and (self.source["contractVersion"] == 1 or self.route_witness is not None)
        return dict(kind=self.kind,requirements=[self.requirement],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",source=deepcopy(self.source),subjects=deepcopy(self.subjects),
            frames=deepcopy(self.frames),bindingWitness=deepcopy(self.binding_witness),windupTarget=self.windup_target,
            cargoCompleted=self.cargo_completed,movingPickup=deepcopy(self.moving_pickup),triggerMoved=self.trigger_moved,flightMoved=self.flight_moved,
            cargoAutonomy=self.autonomy.result() if self.autonomy is not None else None,
            speedWitnesses=deepcopy(self.speed_witnesses),positionProfile=deepcopy(self.position_profile),
            launchEndpoint=deepcopy(self.launch_endpoint),flightWitness=deepcopy(self.flight_witness),
            routeContinuity=deepcopy(self.route_witness),failures=list(self.failures))

    def finish(self):
        if self.frames.get("launch") is not None and not self.flight_moved and not self.failures:
            self.failures.append("Follower Throw launched Cargo has no native movement")
        if self.position_profile is None and self.frames.get("launch") is not None and not self.failures:
            self.failures.append("Follower Throw lacks its resolved Find Position phase")
        if self.flight_witness is None and self.frames.get("launch") is not None and not self.failures:
            self.failures.append("Follower Throw lacks its complete Cargo flight and free control")
        if not self.result()["ready"] and not self.failures:self.failures.append("Follower Throw ended without pickup, launch, and normal follow return")
        return self.result()
