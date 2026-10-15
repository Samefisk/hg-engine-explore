"""One current Wild Geodude must close its accepted Walk after Throw notice.

The saved TKT-0046 trigger is a normal North 16-frame Walk whose resolved lane
changes on the next frame. The accepted plan belongs to the old lane; its
terminal commit must still return control before another Throw intent.
Its current origin is on row412, within five horizontal tiles of the Player.
"""

from copy import deepcopy

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_profile_feature_measurement import (
    ProfileFeatureMeasurement, application_index, require,
)
from tools.overworld.devtools_records import select_current_actor


KIND = "throw-notice-walk-commit-v1"
REQUIREMENT = "current.throw-notice-walk-commit"
NOTICE = _stable_condition_id("throw", "condition-throw-notices-player")
THROW_APPLICATION = application_index("apply-throw")
THROW_MASK = 1 << THROW_APPLICATION
POST_FRAMES = 8
WAIT_FRAMES = 300
FINISH_FRAMES = 60


def validate_recipe(test):
    require(test["id"] == "wild.throw-notice-walk-commit"
            and test["mode"] == "prepared"
            and test["measurements"] == [{"kind": KIND, "subject": "snorlax"}]
            and test["subjects"] == [
                {"id": "snorlax", "species": 143, "role": "WILD", "acquire": "spawn"},
                {"id": "geodude", "species": 74, "role": "WILD", "acquire": "spawn"},
            ]
            and [(a["id"], a["op"], a["args"]) for a in test["setup"]] == [
                ("throw-tile", "teleport", {"map": 33, "x": 585, "z": 406, "facing": 1}),
                ("prepare-passive-follower", "party", {"slot": 0, "species": 155, "level": 20}),
                ("create-passive-follower", "spawn", {"species": 155, "form": 0,
                                               "role": "follower", "slot": 0, "level": 20}),
                ("spawn-snorlax", "spawn", {"species": 143, "form": 0,
                                              "role": "wild", "level": 5, "x": 585, "z": 403}),
                ("settle-snorlax", "step", {"frames": 40, "keys": []}),
                ("spawn-geodude", "spawn", {"species": 74, "form": 0,
                                              "role": "wild", "level": 5, "x": 586, "z": 412}),
                ("bind-snorlax", "bind", {"subject": "snorlax"}),
                ("bind-geodude", "bind", {"subject": "geodude"}),
            ]
            and [(a["id"], a["op"], a["args"]) for a in test["actions"]] == [
                ("wait-ordinary-up-walk", "step", {"frames": WAIT_FRAMES, "keys": [],
                    "until": {"kind": "measurement-stage", "measurement": KIND,
                              "stage": "ordinary-up-walk", "when": "final"}}),
                ("enter-notice-range", "step", {"frames": 1, "keys": ["DOWN", "B"]}),
                ("finish-accepted-walk", "step", {"frames": FINISH_FRAMES, "keys": [],
                    "until": {"kind": "measurement-complete", "measurement": KIND,
                              "when": "final"}}),
            ]
            and test["budgets"]["maxFrames"] <= 550
            and test["budgets"]["minObservedFrames"] >= 25,
            "Throw notice Walk fixture differs")


def _tile(actor, key):
    point = actor[key]
    return [point["x"], point["y"]]


def _current_plan(snapshot, actor):
    combat = snapshot.get("pokemonCombat", {})
    require(combat.get("schemaVersion") == 1 and combat.get("available") is True
            and combat.get("frame") == snapshot["frame"]
            and combat.get("nativeCycle") == snapshot["nativeCycle"]
            and combat.get("observationBoundary") == "main-task-queue-completion"
            and combat.get("identity", {}).get("romSha256") == snapshot["romSha256"],
            "Throw Walk lacks current native plan reader")
    targets = [row for row in combat.get("targets", [])
               if row.get("handle") == actor["handle"]]
    require(len(targets) == 1 and targets[0].get("role") == "WILD"
            and targets[0].get("species") == 74,
            "Throw Walk native plan owner differs")
    motion = targets[0].get("motion", {})
    plan = motion.get("plan", {})
    require(motion.get("phase") == actor.get("motionPhase")
            and plan.get("version") == 1 and plan.get("kind") == 1
            and plan.get("fieldEpoch") == actor["handle"]["fieldEpoch"]
            and plan.get("reservationId") == actor["reservationId"]
            and plan.get("origin") == _tile(actor, "origin")
            and plan.get("target") == _tile(actor, "target")
            and plan.get("duration") == actor["motionDuration"]
            and plan.get("facing") == actor["engineObject"]["facing"],
            "Throw Walk accepted plan differs from its current actor")
    return deepcopy(plan)


def _current_trigger(snapshot, actor):
    interactions = snapshot.get("pokemonCombat", {}).get("interactions", {})
    require(interactions.get("schemaVersion") == 1
            and interactions.get("available") is True
            and interactions.get("frame") == snapshot["frame"]
            and interactions.get("nativeCycle") == snapshot["nativeCycle"]
            and interactions.get("identity", {}).get("romSha256") == snapshot["romSha256"],
            "Throw Walk lacks current native interaction reader")
    carriers = [row for row in interactions.get("carriers", [])
                if row.get("slot") == actor["handle"]["slot"]
                and row.get("handle") == actor["handle"]]
    require(len(carriers) == 1, "Throw notice carrier identity differs")
    trigger = carriers[0].get("bindings", {}).get("trigger", {})
    require(trigger.get("bound") is True and trigger.get("targetCurrent") is True
            and trigger.get("sourceConditionId") == NOTICE
            and trigger.get("sourceApplication") == THROW_APPLICATION
            and trigger.get("target", {}).get("kind") == "PLAYER",
            "Throw notice has no current native player binding")
    return deepcopy(trigger)


def _resolved_speed(events, actor):
    fingerprint = actor["behaviorFingerprint"]
    rows = [e["data"] for e in events if e.get("kind") == "native-observation"
            and e.get("data", {}).get("observation") == "behavior-resolved"
            and e["data"].get("resolved") is True
            and e["data"].get("fingerprint") == fingerprint]
    require(len(rows) == 1, "Throw notice has no exact resolved profile receipt")
    row = rows[0]
    raw = bytes.fromhex(row["resultHex"])
    require(len(raw) == 216 and row.get("lanes") == [raw[:80].hex(), raw[80:160].hex()]
            and int.from_bytes(raw[188:192], "little") == THROW_MASK
            and row.get("appliedOverrides") == THROW_MASK
            and int.from_bytes(raw[192:196], "little") == fingerprint
            and raw[7] == raw[87] == 8,
            "Throw notice resolved lane did not select speed 8")
    return raw[7]


class ThrowNoticeWalkCommitMeasurement(ProfileFeatureMeasurement):
    def __init__(self, kind=KIND, test=None, max_frames=550):
        super().__init__(kind, test, max_frames)
        self.start = None
        self.walk = None
        self.notice = None
        self.returned = None
        self.post_frames = 0
        self.walk_subject = None
        self.walk_events = []

    @property
    def ready(self):
        return self.returned is not None and self.post_frames >= POST_FRAMES

    @property
    def closed(self):
        return self.ready

    def stage(self, name):
        return name == "ordinary-up-walk" and self.start is not None

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            if not self.subjects and not self._discover(snapshot):
                return self.result()
            if self.last is not None:
                require(snapshot["frame"] == self.last["frame"] + 1,
                        "Throw notice completed-frame stream has a gap")
            require(snapshot.get("context") == self.initial.get("context")
                    and snapshot.get("context", {}).get("mapId") == 33
                    and [self.initial["player"]["x"], self.initial["player"]["y"]]
                        == [585, 406],
                    "Throw notice natural field setup changed")
            for name, selected in self.subjects.items():
                current = select_current_actor(snapshot, selected)
                require(current["handle"] == selected["handle"],
                        name + " changed identity during Throw notice")
            self.frames += 1
            require(self.frames <= self.max_frames, "Throw notice frame limit exceeded")
            actor = next(a for a in snapshot["actors"]
                         if a.get("handle") == self.subjects["geodude"]["handle"])
            frame = snapshot["frame"]
            if self.walk is None:
                if self.start is not None and frame == self.start["frame"] + 1:
                    notices = [e for e in events if e.get("kind") == "native"
                               and e.get("data", {}).get("event") == "CONDITIONAL_RESOLVED"
                               and e["data"].get("actorHandle") == actor["handle"]["value"]
                               and e["data"].get("valueA") == NOTICE]
                    require([snapshot["player"]["x"], snapshot["player"]["y"]] == [585, 407]
                            and len(notices) == 1
                            and actor.get("motionKind") == "WALK"
                            and actor.get("motionPhase") == "MOVING"
                            and actor.get("motionElapsed") == 1
                            and actor.get("reservationId") == self.start["token"]
                            and _current_plan(snapshot, actor) == self.start["plan"]
                            and actor.get("behaviorFingerprint") != self.start["fingerprint"]
                            and actor.get("matchedLayerMask") == THROW_MASK,
                            "Throw notice missed the next frame or changed its accepted Walk")
                    speed = _resolved_speed(events, actor)
                    self.walk = self.start
                    self.walk_subject = select_current_actor(snapshot, actor)
                    self.notice = {"frame": frame, "event": deepcopy(notices[0]),
                                   "trigger": _current_trigger(snapshot, actor),
                                   "fingerprint": actor["behaviorFingerprint"],
                                   "resolvedSpeed": speed}
                elif self.start is not None:
                    require(False, "Throw notice missed the next completed frame")
                elif (actor.get("motionKind") == "WALK"
                        and actor.get("motionPhase") == "MOVING"
                        and actor.get("motionElapsed") == 0
                        and actor.get("motionDuration") == 16
                        and actor.get("movementPolicy", {}).get("base") == 16
                        and actor.get("matchedLayerMask") == 0
                        and actor.get("origin", {}).get("y") == 412
                        and abs(actor["origin"]["x"] - 585) <= 5
                        and actor.get("target") == {"x": actor["origin"]["x"], "y": 411}
                        and actor.get("engineObject", {}).get("facing") == 0
                        and [snapshot["player"]["x"], snapshot["player"]["y"]] == [585, 406]):
                    plan = _current_plan(snapshot, actor)
                    self.start = {
                        "frame": frame, "handle": deepcopy(actor["handle"]),
                        "subjectIdentity": actor["subjectIdentity"],
                        "token": actor["reservationId"], "plan": plan,
                        "commitBefore": actor["commitSequence"],
                        "fingerprint": actor["behaviorFingerprint"],
                        "origin": _tile(actor, "origin"), "target": _tile(actor, "target"),
                    }
            if self.walk is not None:
                current = select_current_actor(snapshot, self.walk_subject)
                actor = next(a for a in snapshot["actors"]
                             if a.get("handle") == current["handle"])
                require(actor["handle"] == self.walk["handle"]
                        and actor["subjectIdentity"] == self.walk["subjectIdentity"]
                        and actor["identityVerified"] is True
                        and actor["presentationAttached"] is True,
                        "Throw notice Walk owner changed")
                owned = [e for e in events if e.get("kind") == "native"
                         and e.get("data", {}).get("actorHandle") == self.walk["handle"]["value"]]
                self.walk_events.extend(deepcopy(owned))
                terminal = self.walk["frame"] + self.walk["plan"]["duration"]
                if frame < terminal:
                    require(actor.get("motionKind") == "WALK"
                            and actor.get("motionPhase") == "MOVING"
                            and actor.get("reservationId") == self.walk["token"]
                            and actor.get("motionElapsed") == frame - self.walk["frame"]
                            and _current_plan(snapshot, actor) == self.walk["plan"],
                            "Throw notice interrupted its accepted Walk")
                if self.returned is None and frame >= terminal:
                    names = ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
                    terminal_events = [next((e for e in owned
                        if e["data"].get("event") == name), None) for name in names]
                    if all(terminal_events):
                        require(frame <= terminal + 1
                                and terminal_events[0]["data"]["sequence"]
                                    < terminal_events[1]["data"]["sequence"]
                                    < terminal_events[2]["data"]["sequence"]
                                and terminal_events[0]["data"]["valueA"]
                                    == self.walk["commitBefore"] + 1
                                and terminal_events[1]["data"]["valueA"]
                                    == self.walk["commitBefore"] + 1
                                and terminal_events[2]["data"]["valueB"]
                                    == self.walk["commitBefore"] + 1,
                                "Throw notice Walk terminal events differ")
                        self.returned = {"frame": frame, "events": deepcopy(terminal_events)}
                    require(self.returned is not None or frame <= terminal + 1,
                            "Throw notice accepted Walk stayed COMMIT_PENDING")
                if self.returned is not None:
                    require(not (actor.get("motionPhase") == "COMMIT_PENDING"
                                 and actor.get("reservationId") == self.walk["token"])
                            and actor.get("commitSequence", 0)
                                >= self.walk["commitBefore"] + 1,
                            "Throw notice retained the old Walk or control claim")
                    if frame > self.returned["frame"]:
                        self.post_frames += 1
            self.last = deepcopy(snapshot)
            if self.ready:
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("Throw notice Walk did not close in the bounded natural window")
        return self.result()

    def result(self):
        return {**super().result(),
                "walkSubject": deepcopy(self.walk_subject),
                "walk": deepcopy(self.walk), "notice": deepcopy(self.notice),
                "returned": deepcopy(self.returned), "postFrames": self.post_frames,
                "terminal": deepcopy(self.terminal),
                "walkEvents": deepcopy(self.walk_events)}
