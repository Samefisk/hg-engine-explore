"""Pure Select/current-follower witness over retained shared-worker rows.

This module never runs a game or grants acceptance. The controller authenticates
the recipe, setup receipts, producer sources and retained file before replay.
"""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_role_profile_proof import inspect_transfer, WITNESS
from tools.overworld.devtools_runtime import actor_identity_checks

KIND = "mount-begin-current-follower-v1"
HOP = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")


def require(ok, reason):
    if not ok:
        raise ValueError("mount begin: " + reason)


class MountBeginMeasurement:
    def __init__(self, test=None):
        self.actions = None if test is None else {action["id"]:action for action in test["actions"]}
        self.input_keys = None
        self.failures = []
        self.previous = self.current = self.mounted = self.latest = None
        self.first = None
        self.milestones = []
        self.profile_events = []
        self.role = self.control = None
        self.hop = []
        self.start = None
        self.profile = None
        self.last_keys = 0
        self.closed = False
        self.trace_sequences = {}

    def _actor(self, snapshot, role, witness=True):
        actors = [a for a in snapshot["actors"] if a.get("active") is True and a.get("role") == role]
        require(len(actors) == 1, "expected exactly one " + role)
        actor = actors[0]
        select_current_actor(snapshot, actor)
        require(actor.get("identityVerified") is True and actor.get("presentationAttached") is True,
                "subject has no live presentation identity")
        source, engine = actor["sourceIdentity"], actor["engineIdentity"]
        require(sum(a.get("active") is True and a.get("subjectIdentity") == actor["subjectIdentity"]
                    for a in snapshot["actors"]) == 1
                and sum(a.get("active") is True and a.get("engineIdentity", {}).get("pointer") == engine["pointer"]
                        for a in snapshot["actors"]) == 1, "duplicate live subject/object identity")
        require(all(actor_identity_checks(actor, source, engine, snapshot["context"], 7).values())
                and source["object"] == engine["pointer"] and source["form"] == actor["form"]
                and source["level"] == actor["level"], "native source/engine identity differs")
        if witness:
            require(all(actor.get(k) == v for k, v in WITNESS.items()), "wrong current follower")
        return actor

    def _edge(self, snapshot, bit):
        selector = snapshot["selector"]
        # physicalPressed can already be released when the completed frame is
        # sampled. rawNew and translated newKeys are native latched edges.
        edge = (selector.get("rawNew", 0) & bit and selector.get("newKeys", 0) & bit
                and selector.get("rawHeld", 0) & bit and selector.get("heldKeys", 0) & bit
                and not self.last_keys & bit)
        if edge and self.input_keys is not None:
            name = {4:"SELECT",16:"RIGHT",32:"LEFT",64:"UP",128:"DOWN",2048:"Y"}[bit]
            require(name in self.input_keys, "native input differs from the recorded recipe action")
        return edge

    def _observe(self, snapshot, events):
        require(snapshot.get("fieldAvailable") is True and
                snapshot.get("observationBoundary") == "main-task-queue-completion", "incoherent snapshot")
        if self.latest is not None:
            require(snapshot["frame"] == self.latest["frame"] + 1, "missing completed frame")
            require(snapshot["nativeCycle"] >= self.latest["nativeCycle"], "native clock reversed")
        if self.first is None:
            self.first = deepcopy(snapshot)
        require(snapshot["frame"] - self.first["frame"] <= 600 and
                snapshot["nativeCycle"] - self.first["nativeCycle"] <= 4000, "observation budget exceeded")
        selector = snapshot["selector"]
        if self.previous is None:
            actor = self._actor(snapshot, "FOLLOWER", False)
            require(actor.get("species") == 174 and selector.get("activeFollowerPartySlot") == 3
                    and actor.get("subjectIdentity") != WITNESS["subjectIdentity"], "previous follower fixture differs")
            require(selector.get("highlight") == 2 and selector.get("state") == 0, "saved selector fixture differs")
            self.previous = deepcopy({**snapshot, "actors": [actor]})
        elif not self.milestones:
            if self._edge(snapshot, 2048):
                require(selector.get("state") == 2 and selector.get("highlight") == 2,
                        "Y did not open the current-party selector")
                actor = self._actor(snapshot, "FOLLOWER", False)
                require(actor["subjectIdentity"] == self.previous["actors"][0]["subjectIdentity"]
                        and selector.get("activeFollowerPartySlot") == 3, "previous follower changed before confirmation")
                self.milestones.append(dict(name="open", frame=snapshot["frame"], selector=deepcopy(selector)))
        elif len(self.milestones) == 1 and self._edge(snapshot, 2048):
            require(selector.get("state") == 0 and selector.get("highlight") == 2, "Y did not confirm selected current party slot")
            self.milestones.append(dict(name="confirm", frame=snapshot["frame"], selector=deepcopy(selector)))
        elif len(self.milestones) == 2 and self._edge(snapshot, 4):
            require(self.current is not None and selector.get("state") == 0, "Select lacked a closed current-follower boundary")
            selected = self._actor(snapshot, "FOLLOWER")
            require(selected["handle"] == self.current["actors"][0]["handle"]
                    and selected.get("motionPhase") == "IDLE" and selected.get("reservationId") == 0,
                    "Select did not start from the settled current follower")
            self.milestones.append(dict(name="mount", frame=snapshot["frame"], selector=deepcopy(selector)))
        if len(self.milestones) >= 2 and not any(a.get("role") == "MOUNTED" for a in snapshot["actors"]):
            candidates = [a for a in snapshot["actors"] if a.get("role") == "FOLLOWER" and a.get("species") == 56]
            if candidates and candidates[0].get("identityVerified") is True and candidates[0].get("presentationAttached") is True:
                actor = self._actor(snapshot, "FOLLOWER")
                require(selector.get("activeFollowerPartySlot") == 2, "selected party slot differs")
                if self.current is not None:
                    require(actor["handle"] == self.current["actors"][0]["handle"], "current follower changed")
                if len(self.milestones) == 2:
                    self.current = deepcopy({**snapshot, "actors": [actor]})
        mounted = [a for a in snapshot["actors"] if a.get("role") == "MOUNTED"]
        if mounted:
            require(len(self.milestones) == 3 and self.current is not None, "mount occurred without native Select")
            actor = self._actor(snapshot, "MOUNTED")
            before = self.current["actors"][0]
            require(actor["handle"] == before["handle"] and snapshot["context"] == self.current["context"]
                    and actor["engineIdentity"]["pointer"] == before["engineIdentity"]["pointer"], "mounted subject/object changed")
            require(actor.get("inputOwnership") == 1 and actor.get("lane") == "OWNER", "mounted control/Owner missing")
            for name in ("authorityGeneration", "engineAnchorGeneration"):
                require(actor[name] == before[name] + 1, "role generation differs")
            require(actor["presentationGeneration"] == before["presentationGeneration"], "presentation generation changed")
            if self.mounted is None:
                self.mounted = deepcopy({**snapshot, "actors": [actor]})
        elif self.mounted is not None:
            require(False, "mounted subject was lost")
        for event in events:
            require(event.get("frame") == snapshot["frame"], "event outside completed frame")
            d = event.get("data", {})
            if event.get("kind") == "trace-status":
                require(d.get("coverageComplete") is not False and d.get("code") not in
                        {"sequence-reset", "window-rearmed-externally", "unread-events-lost", "trace-filter-changed"}, "trace event loss")
            if event.get("kind") == "native-observation" and d.get("observation") in ("role-profile-getter", "role-profile-mount"):
                # The shared capture starts before menu input. Earlier getters
                # belong to the previous follower or selection setup, not Begin.
                # Select's native edge and the first mounted boundary define
                # the transfer window; no species/context verdict filters it.
                if len(self.milestones) == 3 and (self.mounted is None or snapshot["frame"] <= self.mounted["frame"]):
                    self.profile_events.append(deepcopy(event))
                    require(len(self.profile_events) <= 128, "profile event budget exceeded")
            if event.get("kind") != "native":
                continue
            stream, seq = d["traceStream"], d["sequence"]
            if stream in self.trace_sequences:
                require(seq == self.trace_sequences[stream] + 1, "semantic event was lost")
            self.trace_sequences[stream] = seq
            if self.current is None or d.get("actorHandle") != self.current["actors"][0]["handle"]["value"]:
                continue
            require(d.get("actor") == {k:v for k,v in self.current["actors"][0]["handle"].items() if k != "value"}, "trace identity differs")
            name = d.get("event")
            require(name not in ("MOTION_CANCELED", "ACTOR_RELEASED"), "subject canceled or released")
            if name in ("ACTOR_REBOUND", "CONTROL_REBOUND"):
                require(len(self.milestones) == 3 and d.get("reason") == "OK", "rebind without Select")
                if name == "ACTOR_REBOUND":
                    require(self.role is None and (d.get("valueA"), d.get("valueB")) == (2, 3), "wrong role rebind")
                    self.role = deepcopy(event)
                else:
                    require(self.control is None and (d.get("valueA"), d.get("valueB")) == (0, 1), "wrong control rebind")
                    self.control = deepcopy(event)
            elif name in HOP and self.mounted is not None:
                require(self.role is not None and self.control is not None and len(self.hop) < 4
                        and name == HOP[len(self.hop)] and d.get("reason") == "OK", "Hop lifecycle is missing or out of order")
                actor = self._actor(snapshot, "MOUNTED")
                if not self.hop:
                    require(d.get("valueA") == 2 and d.get("valueB", 0) > 0
                            and actor.get("motionKind") == "HOP" and actor.get("origin") != actor.get("target"), "wrong Hop start")
                    require(any(self._edge(snapshot, bit) for bit in (16,32,64,128)), "Hop lacks native direction input")
                    require(actor.get("motionDuration") == d["valueB"], "Hop duration differs from its actor")
                    self.start = deepcopy(actor)
                else:
                    commit = self.start["commitSequence"] + 1
                    require((d.get("valueA"), d.get("valueB")) ==
                            ((1, commit) if name == "CONTROL_RETURNED" else (commit, 2)), "wrong Hop terminal")
                    if name == "CONTROL_RETURNED":
                        require(actor["commitSequence"] == commit and actor["logical"] == self.start["target"], "Hop did not commit its destination")
                self.hop.append(deepcopy(event))
        self.latest = deepcopy(snapshot)
        self.last_keys = selector.get("rawHeld", 0)

    def observe(self, snapshot, events=()):
        require(not self.closed, "measurement is closed")
        if not self.failures:
            try:
                self._observe(snapshot, events)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                self.failures.append(str(error))
        return self.result()

    def observe_record(self, record):
        if "boundarySnapshot" in record and self.first is None:
            self.observe(record["boundarySnapshot"])
        if "samples" in record and self.first is not None:
            samples, events = record["samples"], record.get("events", [])
            if self.actions is not None:
                action = self.actions.get(record.get("action"))
                if record.get("phase") != "observe" or action is None or action["op"] not in ("step", "wait"):
                    self.failures.append("mount begin: samples do not belong to a reviewed input/wait action")
                self.input_keys = [] if action is None else action["args"].get("keys", [])
            if record.get("completedGameFrames") != len(samples) or not samples:
                self.failures.append("mount begin: invalid completed-frame chunk")
            for sample in samples:
                self.observe(sample, [e for e in events if e.get("frame") == sample.get("frame")])
        return self.result()

    def finish(self):
        if not self.failures:
            try:
                require(len(self.milestones) == 3 and self.role and self.control and len(self.hop) == 4,
                        "incomplete Select/rebind/Hop lifecycle")
                actor = self._actor(self.latest, "MOUNTED")
                require(self.latest["selector"]["state"] == 0 and actor.get("reservationId") == 0
                        and actor.get("motionPhase") == "IDLE"
                        and all(self.latest["selector"].get(k) == 0 for k in ("rawHeld","rawNew","newKeys","heldKeys")),
                        "terminal selector/motion/reservation/input is not closed")
                self.profile = inspect_transfer(self.profile_events, self.current, self.mounted)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                self.failures.append(str(error))
        self.closed = True
        return self.result()

    def result(self):
        measurements = {}
        if self.closed and not self.failures and self.profile:
            a,b = self.current["actors"][0], self.mounted["actors"][0]
            measurements = {"menu-input-milestones": 3,
                "mount-begin-public-role-transition": dict(beforeRole="FOLLOWER", afterRole="MOUNTED", traceFromRole=2, traceToRole=3,
                    beforeSubjectIdentity=a["subjectIdentity"], afterSubjectIdentity=b["subjectIdentity"],
                    beforeEncounterGeneration=a["handle"]["encounterGeneration"], afterEncounterGeneration=b["handle"]["encounterGeneration"],
                    traceActorHandle=self.role["data"]["actorHandle"], mountedActorHandle=b["handle"]["value"]),
                "subject-identity": [a["subjectIdentity"], b["subjectIdentity"]],
                "encounter-generation": b["handle"]["encounterGeneration"], "unique-live-identity-counts": [1,1],
                "resolved-species-and-role": [a["species"], b["species"], b["role"]],
                "closed-selector-and-stable-object": [0,a["engineIdentity"]["pointer"],b["engineIdentity"]["pointer"]]}
        return deepcopy(dict(kind=KIND, acceptedProof=False, state="failed" if self.failures else "passed" if measurements else "running",
            passed=bool(measurements),
            measurements=measurements, failures=self.failures, milestones=self.milestones, roleRebound=self.role,
            controlRebound=self.control, hop=self.hop, profileTransfer=self.profile))


def run(rows, test=None, fault=None):
    """Replay an immutable retained stream; controls change copied meanings only."""
    meter = MountBeginMeasurement(test)
    applied = False
    names = {"missing-role": "ACTOR_REBOUND", "missing-control-rebind": "CONTROL_REBOUND",
             "missing-hop-start": "MOTION_STARTED", "missing-hop-commit": "LOGICAL_COMMIT",
             "missing-hop-finish": "MOTION_FINISHED", "missing-hop-control": "CONTROL_RETURNED"}
    for original in rows:
        row = original if fault is None else deepcopy(original)
        if fault is not None:
            snapshots = ([row["boundarySnapshot"]] if "boundarySnapshot" in row else []) + row.get("samples", [])
            for snapshot in snapshots:
                for actor in snapshot.get("actors", []):
                    if fault == "wrong-previous" and actor.get("role") == "FOLLOWER" and actor.get("species") == 174:
                        actor["subjectIdentity"] = WITNESS["subjectIdentity"]; applied = True
                    if fault == "wrong-current" and actor.get("species") == 56:
                        actor["subjectIdentity"] = WITNESS["subjectIdentity"] ^ 1; applied = True
                selector = snapshot.get("selector", {})
                if fault == "missing-select" and selector.get("rawNew", 0) & 4:
                    selector["rawNew"] &= ~4; applied = True
            for event in row.get("events", []):
                d = event.get("data", {})
                if fault in names and d.get("event") == names[fault] and d.get("actor", {}).get("slot") == 7:
                    d["event"] = "CONTROL_REMOVED"; applied = True
                observation = {"missing-getter": "role-profile-getter", "missing-begin": "role-profile-mount"}.get(fault)
                if observation and d.get("observation") == observation:
                    d["observation"] = "control-removed"; applied = True
        meter.observe_record(row)
    result = meter.finish()
    result.update(fault=fault, faultApplied=applied)
    return result


def negative_controls(rows, test=None):
    faults = ("wrong-previous", "wrong-current", "missing-select", "missing-getter", "missing-begin",
              "missing-role", "missing-control-rebind", "missing-hop-start", "missing-hop-commit",
              "missing-hop-finish", "missing-hop-control")
    controls = {fault: run(rows, test, fault) for fault in faults}
    return dict(acceptedProof=False, passed=all(r["faultApplied"] and not r["passed"] and r["failures"] for r in controls.values()),
                controls=controls)
