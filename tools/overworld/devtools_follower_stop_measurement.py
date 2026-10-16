"""One normal Stantler Walk followed by a stable follower stop (TKT-0008)."""
from copy import deepcopy

from tools.overworld.devtools_profile_feature_measurement import ProfileFeatureMeasurement, require
from tools.overworld.devtools_records import select_current_actor

KIND = "follower-stop-facing-v1"
REQUIREMENT = "current.follower-stop-facing"
IDLE_FRAMES = 32
SETUP = (("teleport", {"map": 33, "x": 584, "z": 403, "facing": 3}),
         ("party", {"slot": 0, "species": 234, "level": 10, "hp": 1, "status": 0}),
         ("spawn", {"species": 234, "form": 0, "role": "follower", "slot": 0, "level": 10}),
         ("step", {"frames": 24, "keys": []}),
         ("bind", {"subject": "stantler"}))
ACTIONS = (("step", {"frames": 32, "keys": ["RIGHT"]}),
           ("step", {"frames": 96, "keys": []}))


def validate_recipe(test):
    require(tuple((a["op"], a["args"]) for a in test["setup"]) == SETUP
            and tuple((a["op"], a["args"]) for a in test["actions"]) == ACTIONS
            and test["budgets"]["minObservedFrames"] == 128
            and test["budgets"]["maxFrames"] <= 600,
            "Stantler stop fixture or normal input differs")


class FollowerStopMeasurement(ProfileFeatureMeasurement):
    def __init__(self, kind=KIND, test=None, max_frames=240):
        super().__init__(kind, test, max_frames)
        self.current_events = []
        self.walk = None
        self.walks = []
        self.idle = []
        self.policy_replies = []

    def _discover(self, snapshot):
        candidates = [a for a in snapshot.get("actors", [])
                      if a.get("active") is True and a.get("species") == 234
                      and a.get("role") == "FOLLOWER"]
        require(len(candidates) == 1, "Stantler follower is absent or ambiguous")
        self.subject = select_current_actor(snapshot, candidates[0])
        self.subjects = {"stantler": deepcopy(self.subject)}
        require(snapshot.get("context", {}).get("mapId") == 33,
                "Stantler stop is outside Route 29")
        self.initial = deepcopy(snapshot)
        return True

    def observe(self, snapshot, events):
        self.current_events = list(events)
        return super().observe(snapshot, events)

    def _policy(self, snapshot, actor):
        for event in self.current_events:
            data = event.get("data", {})
            if event.get("kind") != "native-observation" \
                    or data.get("observation") != "walk-policy" \
                    or data.get("slot") != 7 or data.get("operation") != 1:
                continue
            for subject in (data.get("publicSubject"), data.get("publicSubjectAfter")):
                require(isinstance(subject, dict) and all(
                    subject.get(k) == actor.get(k) for k in (
                        "handle", "subjectIdentity", "species", "role",
                        "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")),
                    "Stantler stop policy receipt has a stale owner")
            request = bytes.fromhex(data["requestHex"])
            response = bytes.fromhex(data["responseHex"])
            require(len(request) == len(response) == 28
                    and request[:4] == response[:4] == b"\x01\x00\x1c\x00"
                    and request[8:10] == response[8:10] == b"\x07\x01"
                    and request[4:8] == response[4:8]
                    and data.get("returnValue") == 1
                    and event["frame"] == snapshot["frame"]
                    and data.get("entryActorFrame") == data.get("returnActorFrame") == snapshot["actorFrame"],
                    "Stantler stop policy ABI or completed-frame boundary differs")
            if request[10] == 255 and response[16] == 0 and response[20] & 8:
                require(response[15] == 0 and response[17:19] == b"\xff\xff",
                        "empty follower stop reply requested a direction")
                self.policy_replies.append({"frame": event["frame"], "sequence": data["sequence"],
                                            "requestHex": data["requestHex"], "responseHex": data["responseHex"]})

    def _sample(self, snapshot, actors):
        actor = actors["stantler"]
        frame = snapshot["frame"]
        engine = actor["engineObject"]
        require(all(type(engine.get(k)) is int for k in ("facing", "pos_x", "pos_z", "movement_cmd"))
                and 0 <= engine["facing"] <= 3,
                "Stantler native facing or pose is missing")
        self._policy(snapshot, actor)
        events = [e for e in self.current_events if e.get("kind") == "native"
                  and e.get("data", {}).get("actorHandle") == actor["handle"]["value"]]
        names = [e["data"].get("event") for e in events]
        tile = [actor["logical"]["x"], actor["logical"]["y"]]
        # A chained successor can share its predecessor's commit boundary.
        # Complete the prior accepted Walk before adopting that successor.
        if self.walk is not None and "LOGICAL_COMMIT" in names and "CONTROL_RETURNED" in names:
            require(actor["commitSequence"] == self.walk["commitBefore"] + 1
                    and tile == self.walk["target"] and self.walk["movingSamples"] > 0,
                    "Stantler Walk did not commit its own target once")
            commit = next(e for e in events if e["data"].get("event") == "LOGICAL_COMMIT")
            control = next(e for e in events if e["data"].get("event") == "CONTROL_RETURNED")
            require(commit["data"].get("valueA") == actor["commitSequence"]
                    and control["data"].get("valueB") == actor["commitSequence"],
                    "Stantler Walk commit/control receipt differs")
            self.walks.append({**self.walk, "finishFrame": frame, "commitAfter": actor["commitSequence"],
                               "facing": engine["facing"]})
            self.walk = None
            self.idle = []
        if "MOTION_STARTED" in names:
            start = next(e for e in events if e["data"].get("event") == "MOTION_STARTED")
            origin = [actor["origin"]["x"], actor["origin"]["y"]]
            target = [actor["target"]["x"], actor["target"]["y"]]
            require(actor["motionKind"] == "WALK" and actor["motionPhase"] in ("PLANNED", "MOVING")
                    and actor["motionElapsed"] in (0, 1) and 1 <= actor["motionDuration"] <= 32
                    and origin != target and start["data"].get("valueA") == 1
                    and start["data"].get("valueB") == actor["motionDuration"] and self.walk is None,
                    "Stantler has no coherent genuine Walk start")
            self.walk = {"startFrame": frame, "origin": origin, "target": target,
                         "duration": actor["motionDuration"], "commitBefore": actor["commitSequence"],
                         "movingSamples": 0}
            self.idle = []
        if self.walk is not None and actor["motionKind"] == "WALK":
            require([actor["origin"]["x"], actor["origin"]["y"]] == self.walk["origin"]
                    and [actor["target"]["x"], actor["target"]["y"]] == self.walk["target"]
                    and actor["motionDuration"] == self.walk["duration"],
                    "Stantler changed its accepted Walk plan")
            self.walk["movingSamples"] += 1
        idle = actor["motionKind"] == "NONE" and actor["motionPhase"] == "IDLE"
        if idle and self.walks and self.walk is None:
            last = self.walks[-1]
            require(tile == last["target"] and actor["commitSequence"] == last["commitAfter"]
                    and actor["inputOwnership"] == 0 and actor["reservationId"] == 0,
                    "Stantler stop did not release Walk control")
            expected = self.idle[-1]["facing"] if self.idle else last["facing"]
            if engine["facing"] != expected:
                # A real stock FACE command is explicit presentation work.
                # It begins a new stable interval; an empty reply is not FACE.
                require(engine["movement_cmd"] == engine["facing"],
                        "idle Stantler changed facing without a face command")
                self.idle = []
            self.idle.append({"frame": frame, "facing": engine["facing"],
                              "logical": tile, "commitSequence": actor["commitSequence"]})
        elif not idle:
            self.idle = []
        self.samples.append({"frame": frame, "motionKind": actor["motionKind"],
                             "motionPhase": actor["motionPhase"], "facing": engine["facing"],
                             "commitSequence": actor["commitSequence"], "logical": tile})

    @property
    def ready(self):
        return bool(self.walks and len(self.idle) >= IDLE_FRAMES and any(
            row["frame"] >= self.idle[0]["frame"] for row in self.policy_replies))

    def result(self):
        return {**super().result(), "walks": deepcopy(self.walks),
                "idle": deepcopy(self.idle), "policyReplies": deepcopy(self.policy_replies)}

    def finish(self):
        if not self.ready and not self.failures and self.walk is not None:
            self.failures.append("Stantler Walk has no paired commit/control")
        return super().finish()
