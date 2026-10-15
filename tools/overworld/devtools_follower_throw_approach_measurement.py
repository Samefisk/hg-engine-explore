"""The saved Mankey walks up to separate native Interest and Cargo.

This finite entry witness complements the complete moving-Cargo Throw case.
It uses that case's native binding and complete Hop readers, with no new tap.
"""
from copy import deepcopy
import struct
from tools.overworld.devtools_follower_throw_measurement import (
    FollowerThrowMeasurement, require, FOLLOWER, THROW_MASK, FIND_CARGO,
    TRIGGER_CONDITION, CARGO_CONDITION,
)
from tools.overworld.devtools_cargo_route_continuity import packets
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor

KIND = "follower-throw-approach-cargo-v1"
REQUIREMENT = "current.follower-throw-approach-cargo"
SUBJECTS = (("mankey",56,"FOLLOWER","existing"), ("trigger",95,"WILD","existing"),
            ("cargo",69,"WILD","spawn"), ("alternative",43,"WILD","spawn"))
SETUP = (("throw-tile","teleport",dict(map=33,x=586,z=407,facing=1)),
         ("ordinary-notice","step",dict(frames=20,keys=[])),
         ("bind-mankey","bind",dict(subject="mankey")),
         ("bind-trigger","bind",dict(subject="trigger")),
         ("spawn-cargo","spawn",dict(species=69,form=0,role="wild",level=5,x=586,z=399)),
         ("bind-cargo","bind",dict(subject="cargo")),
         ("spawn-alternative","spawn",dict(species=43,form=0,role="wild",level=5,x=588,z=399)),
         ("bind-alternative","bind",dict(subject="alternative")))
ACTIONS = (("approach","step",dict(frames=40,keys=["UP","B"])),
           ("ordinary-cargo-start","step",dict(frames=120,keys=[])))


def validate_recipe(test):
    require(test["id"] == "follower.throw-approach-cargo" and test["mode"] == "prepared"
        and test["requirements"] == [REQUIREMENT]
        and test["subjects"] == [dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in SUBJECTS]
        and tuple((a["id"],a["op"],a["args"]) for a in test["setup"]) == SETUP
        and tuple((a["id"],a["op"],a["args"]) for a in test["actions"]) == ACTIONS
        and test["assertions"] == [dict(kind="measurement-complete",measurement=KIND,when="final")]
        and test["budgets"]["maxFrames"] <= 320 and test["budgets"]["minObservedFrames"] == 160,
        "Follower approach fixture differs from unchanged Continue and ordinary input")


def reachable_cargo_admission(row, cargo):
    q=row["workspace"];context=q["compatibility"]
    if row["status"] != "REACHABLE" or context["cargo"] != cargo["handle"]:
        return False
    if row["hasNextStep"]:
        return True
    # Same authored physical predicate as OverworldPickupReach_Check: a
    # distinct current tile within reach and the current base-height limit.
    origin=q["origin"];dx=abs(origin["x"]-cargo["x"]);dy=abs(origin["y"]-cargo["y"])
    distance=context["pickupDistance"];height=(context["requestKey"]>>8)&255
    return type(distance) is int and 1 <= distance <= 8 and height <= 64 \
        and (context["requestKey"]>>16)&255 == distance and 0 < max(dx,dy) <= distance \
        and abs(origin["baseY"]-cargo["baseY"]) <= (height<<12)


class FollowerThrowApproachMeasurement(FollowerThrowMeasurement):
    def __init__(self, source):
        super().__init__(source)
        require(source["contractVersion"] == 2, "Follower approach needs the sealed query source")
        self.action_frames = [0,0]
        self.approach_hop = self.approach_witness = None
        self.admission = None
        self.notice = None
        self.party_identity = None

    def _policy(self, sample, mankey, rows):
        active = self.approach_hop
        if active is None:
            return
        for row in rows:
            for key in ("before", "workspace"):
                q = row.get(key)
                if q is None or not q.get("valid"):
                    continue
                require(q.get("owner") == mankey["handle"] and q.get("ownerCurrent") is True,
                        "Follower approach query owner changed")
                revision = q["compatibility"]["movementPolicyRevision"]
                # A newly published search profile may legitimately change
                # Hop timing at the returned idle boundary. Its entry workspace
                # must still retain the old normal-Hop key. No earlier change
                # is allowed, including changes of Cargo pose or loaded scope.
                new_search = (key == "workspace" and sample["frame"] == active["returnFrame"]
                              and mankey["matchedLayerMask"] & FIND_CARGO)
                require(revision == active["policyKey"] or new_search,
                        "Follower approach unlimited route policy changed during normal Hop or return")
            active["queries"].append(deepcopy(row))
        if sample["frame"] == active["returnFrame"]:
            complete = self.speed_witnesses.get("normal")
            require(complete is not None and complete["returnFrame"] == sample["frame"]
                and complete["commitAfter"] == active["commitSequence"]
                and rows and rows[-1].get("before",{}).get("compatibility",{}).get("movementPolicyRevision") == active["policyKey"],
                "Follower approach lacks the exact native ordinary-Hop return query")
            # At least the admission, a native current-tile advance, and return
            # must be observed. Startup/streaming Pending earns no route credit.
            queried = {r["frame"] for r in active["queries"]}
            require(active["startFrame"] in queried and active["returnFrame"] in queried
                    and any(active["startFrame"] < f < active["startFrame"]+active["duration"] for f in queried),
                    "Follower approach lacks normal-Hop route boundaries")
            origin = active["queries"][0]["workspace"]["origin"]
            require(any(active["startFrame"] < r["frame"] < active["startFrame"]+active["duration"]
                        and (r["workspace"]["origin"]["x"],r["workspace"]["origin"]["y"]) != (origin["x"],origin["y"])
                        for r in active["queries"]),
                    "Follower approach lacks a native current-tile advance query")
            active["motion"] = deepcopy(complete)
            self.approach_witness = deepcopy(active)
            self.approach_hop = None

    def _notice(self, sample, binding, target):
        if not binding["bound"]:
            require(self.notice is None, "Follower approach lost its current native Onix Interest")
            return False
        require(binding["targetCurrent"] is True
                and binding["sourceConditionId"] == TRIGGER_CONDITION
                and binding["sourceApplication"] == 20
                and binding["target"] == dict(kind="ACTOR",actor=target["handle"]),
                "Follower approach bound a wrong or stale native Onix Interest")
        if self.notice is None:
            self.notice = dict(frame=sample["frame"],binding=deepcopy(binding))
        return True

    def _sample(self, sample, events):
        self._boundary(sample);self._profile_events(events)
        require(self.latest is not None and sample["frame"] == self.latest["frame"]+1,
                "Follower approach completed-frame stream has a gap")
        actors = {n:self._actor(sample,n) for n,_,_,_ in SUBJECTS}
        m,t,c = (actors[n] for n in ("mankey","trigger","cargo"))
        require(len({a["handle"]["value"] for a in actors.values()}) == 4,
                "Follower approach Interest and Cargo are not distinct")
        party = [p for p in sample["party"] if p.get("personality") == m["subjectIdentity"]]
        require(len(party) == 1 and party[0].get("identityVerified") is True and party[0].get("species") == 56
                and party[0].get("hp",0) > 0 and party[0]["personality"] == self.party_identity,
                "Follower approach changed the saved party Mankey")
        carrier,_ = self._carrier(sample,m);bindings = carrier["bindings"];flags = carrier["throw"]
        follower_events = self._events(events,m)
        entry_complete = self.admission is not None and "cargo" in self.speed_witnesses
        noticed = entry_complete or self._notice(sample,bindings["trigger"],t)
        rows = [] if entry_complete else packets(sample, events, m, self.source["queryImage"], self.latest["nativeCycle"], pending_ok=True)
        if self.approach_witness is None:
            if self.approach_hop is None and m["motionKind"] == "HOP" and m["motionPhase"] == "MOVING" \
                    and m["motionElapsed"] == 0 and not m["matchedLayerMask"] & THROW_MASK and noticed:
                require(m["engineObject"].get("x_range") == m["engineObject"].get("y_range") == -1,
                        "Follower approach needs unlimited native ranges")
                prepared = [r for r in rows if r["workspace"]["nodeCount"] > 0]
                # A current Pending query earns no ordinary-Hop credit.
                if prepared:
                    self._speed_sample(sample,m,flags,follower_events,stage="normal")
                    motion = self.speed_motion
                    require(motion is not None, "Follower approach ordinary Hop lacks native admission")
                    self.approach_hop = dict(startFrame=motion["startFrame"],duration=motion["duration"],
                        returnFrame=motion["startFrame"]+motion["duration"]+motion["pauseFrames"],
                        commitSequence=motion["commitBefore"]+1,
                        policyKey=prepared[-1]["workspace"]["compatibility"]["movementPolicyRevision"],queries=[])
            elif self.approach_hop is not None:
                self._speed_sample(sample,m,flags,follower_events,stage="normal")
            self._policy(sample,m,rows)
        if bindings["cargo"]["bound"] and self.admission is None:
            require(self.notice is not None and noticed,
                    "Follower approach Cargo preceded genuine native Onix Interest")
            b=bindings["cargo"]
            require(b["targetCurrent"] is True and b["sourceConditionId"] == CARGO_CONDITION
                    and b["sourceApplication"] == 20 and b["flags"] == 1 and b["lifetime"] == 0
                    and b["target"] == dict(kind="ACTOR",actor=c["handle"]),
                    "Follower approach bound a different or stale Cargo")
            position=dict(handle=deepcopy(c["handle"]),x=c["engineObject"]["x"],
                          y=c["engineObject"]["y"],baseY=c["engineObject"]["pos_y"])
            reached = [r for r in rows if reachable_cargo_admission(r,position)]
            require(reached, "Follower approach Cargo admission lacks current Reachable travel or pickup goal")
            self.admission = dict(frame=sample["frame"],contributionFrame=None,bindings=deepcopy(bindings),
                                  query=deepcopy(reached[-1]),cargoPosition=position)
        if self.admission is not None and not entry_complete:
            b=bindings["cargo"]
            require(b["bound"] and b["targetCurrent"] and b["target"] == dict(kind="ACTOR",actor=c["handle"])
                    and (not flags["targetRaw"] or flags["targetSlot"] == c["handle"]["slot"]),
                    "Follower approach lost or changed its admitted Cargo")
            if m["matchedLayerMask"] & FIND_CARGO and self.admission["contributionFrame"] is None:
                self.admission["contributionFrame"]=sample["frame"]
        if self.admission is not None and self.approach_witness is not None and "cargo" not in self.speed_witnesses:
            self._speed_sample(sample,m,flags,follower_events)
        self.observed_frames += 1
        require(self.observed_frames <= 160, "Follower approach exceeded its exact input window")
        self.latest=self.terminal=deepcopy(sample)

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "Follower approach initial boundary differs")
                self._boundary(row["initialSnapshot"],False);self.latest=deepcopy(row["initialSnapshot"])
                self._profile_events(row.get("initialEvents",[]));return self.result()
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP) and row.get("action") == SETUP[self.setup_index][0],
                        "Follower approach setup order differs")
                _,op,args=SETUP[self.setup_index]
                if op == "step":
                    require("command" not in row, "Follower approach Notice must use normal frames")
                    for sample,events,_ in validate_raw_chunk(row,self.latest):
                        self._boundary(sample);self._profile_events(events);self.latest=deepcopy(sample)
                        if on_sample:on_sample(sample,self.observed_frames)
                    self.setup_frames += row["completedGameFrames"]
                    require(self.setup_frames <= 20, "Follower approach Notice wait differs")
                    if self.setup_frames < 20:return self.result()
                else:
                    require(row.get("command") == op, "Follower approach setup command differs")
                    sample=row["snapshot"];self._boundary(sample);self._profile_events(row.get("events",[])+row.get("receipt",{}).get("events",[]))
                    if op == "bind":
                        name=args["subject"];selected=select_current_actor(sample,row["receipt"])
                        spec=next(r for r in SUBJECTS if r[0] == name)
                        require((selected["species"],selected["role"]) == spec[1:3], "Follower approach bound subject differs")
                        self.subjects[name]=deepcopy(row["receipt"])
                        if name == "mankey":
                            self.party_identity=selected["subjectIdentity"]
                            require(any(p.get("personality") == self.party_identity and p.get("species") == 56
                                    for p in sample.get("party",[])), "Follower approach lacks the saved party Mankey")
                        elif name == "trigger":
                            carrier,_=self._carrier(sample,self._actor(sample,"mankey"))
                            self._notice(sample,carrier["bindings"]["trigger"],selected)
                    self.latest=deepcopy(sample)
                self.setup_index += 1
                if self.setup_index == len(SETUP):self.initial=deepcopy(self.latest)
                return self.result()
            require(self.setup_index == len(SETUP) and self.action_index < len(ACTIONS)
                    and row.get("phase") == "observe" and "command" not in row
                    and row.get("action") == ACTIONS[self.action_index][0], "Follower approach action order differs")
            for sample,events,_ in validate_raw_chunk(row,self.latest):
                self.action_frames[self.action_index] += 1
                require(self.action_frames[self.action_index] <= ACTIONS[self.action_index][2]["frames"], "Follower approach action bound differs")
                self._sample(sample,events)
                if on_sample:on_sample(sample,self.observed_frames)
            if self.action_frames[self.action_index] == ACTIONS[self.action_index][2]["frames"]:self.action_index += 1
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index == len(ACTIONS) and self.observed_frames == 160 \
              and self.notice is not None and self.approach_witness is not None and self.admission is not None and "cargo" in self.speed_witnesses
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",subjects=deepcopy(self.subjects),
            notice=deepcopy(self.notice),approach=deepcopy(self.approach_witness),admission=deepcopy(self.admission),
            speedWitnesses=deepcopy(self.speed_witnesses),failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Follower approach ended without ordinary Hop return, current Cargo admission and native pursuit")
        return self.result()
