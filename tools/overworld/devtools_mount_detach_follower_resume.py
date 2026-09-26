"""Short Mounted-to-Follower recovery witness over completed public frames."""
from __future__ import annotations

from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder


KIND = "mount-detach-follower-resume-v1"
REQUIREMENT = "current.mount-detach-follower-resume"
PLAYER_CLEARANCE_TILES = 2
MAX_RESUME_FRAMES = 1
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
STABLE = ("handle", "subjectIdentity", "species", "form", "level",
          )


def require(value, reason):
    if not value:
        raise ValueError(reason)


class MountDetachFollowerResumeMeasurement:
    def __init__(self, test=None, max_frames=96):
        require(type(max_frames) is int and 8 <= max_frames <= 240,
                "invalid detach follower frame bound")
        self.test = test
        self.max_frames = max_frames
        self.subject = self.initial = self.terminal = self.last = self.actor = None
        self.frames = 0
        self.failures = []
        self.closed = False
        self.ready = False
        self.select_frame = None
        self.detach_frame = None
        self.clearance_frame = None
        self.motion_start_frame = None
        self.rebound_events = []
        self.motion_events = []
        self.motion = None
        self.mounted_policy = None
        self.follower_policy = None
        self.recorder = MotionRecorder()
        self.streams = {}

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.initial is None, "detach follower measurement is already armed")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"]
                     if item.get("handle") == selected["handle"])
        require(actor.get("species") == 155 and actor.get("role") == "MOUNTED"
                and actor.get("inputOwnership") == 1
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("handle", {}).get("slot") == 7,
                "requires one exact idle mounted Cyndaquil")
        self.subject = deepcopy(selected)
        self.initial = deepcopy(snapshot)
        self.actor = deepcopy(actor)
        self.mounted_policy = (
            actor["behaviorFingerprint"], actor["matchedLayerMask"])
        self.last = deepcopy(snapshot)
        self.streams = dict(trace_sequences or {})

    def _actor(self, snapshot):
        actors = [item for item in snapshot.get("actors", [])
                  if item.get("handle") == self.subject["handle"]]
        require(len(actors) == 1, "missing or duplicate detach follower subject")
        actor = actors[0]
        require(all(actor.get(key) == self.actor.get(key) for key in STABLE),
                "detach follower subject changed")
        require(actor.get("role") in ("MOUNTED", "FOLLOWER")
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True,
                "detach follower identity or role changed")
        current = dict(self.subject, role=actor["role"])
        current.pop("authorityGeneration", None)
        current.pop("engineAnchorGeneration", None)
        current.pop("presentationGeneration", None)
        select_current_actor(snapshot, current)
        source, engine = actor["sourceIdentity"], actor["engineIdentity"]
        require(source.get("species") == 155
                and source.get("personality") == actor["subjectIdentity"]
                and source.get("object") == engine.get("pointer")
                and source.get("object_id") == engine.get("object_id") == 231
                and source.get("map_id") == engine.get("object_map_id")
                == engine.get("current_map_id") == snapshot["context"]["mapId"]
                and actor["handle"]["encounterGeneration"]
                == source.get("encounter_generation")
                == engine.get("encounter_generation")
                and engine.get("in_manager") is True and engine.get("active") is True,
                "detach follower native identity differs")
        return actor

    def _events(self, snapshot, events, actor):
        own = []
        for event in events:
            require(event.get("frame") == snapshot["frame"],
                    "detach follower event completion frame differs")
            data = event.get("data", {})
            if event.get("kind") == "native":
                stream, sequence = data.get("traceStream"), data.get("sequence")
                require(type(stream) is int and type(sequence) is int,
                        "detach follower semantic sequence is missing")
                require(stream not in self.streams or sequence == self.streams[stream] + 1,
                        "detach follower semantic sequence gap")
                self.streams[stream] = sequence
                if data.get("actorHandle") == actor["handle"]["value"]:
                    require(data.get("actor") == {
                        key: value for key, value in actor["handle"].items()
                        if key != "value"
                    }, "detach follower semantic generation differs")
                    own.append(deepcopy(event))
            elif event.get("kind") == "trace-status":
                require(data.get("code") == "ring-overwrite"
                        and data.get("unreadEventsLost") == 0
                        and data.get("coverageComplete", True) is True,
                        "detach follower trace lost events")
        return own

    def _complete_motion(self, snapshot, actor):
        if not self.recorder.completed:
            return
        motion = self.recorder.completed.pop(0)
        require(self.motion is None, "more than one follower motion completed before close")
        require(motion.get("kind") == "WALK"
                and motion.get("handle") == actor["handle"]
                and self.follower_policy is not None
                and motion.get("fingerprint") == self.follower_policy[0]
                and motion.get("commitAfter") == (motion.get("commitBefore") + 1) & 0xFFFFFFFF
                and motion.get("terminalLogical") == motion.get("target"),
                "first follower Walk is incomplete")
        lifecycle = []
        for name in LIFECYCLE:
            candidates = [event for event in self.motion_events
                          if event["data"].get("event") == name
                          and event["frame"] == (motion["startFrame"] if name == "MOTION_STARTED"
                              else motion["commitFrame"] if name == "LOGICAL_COMMIT"
                              else motion["finishFrame"])]
            require(len(candidates) == 1,
                    "missing or duplicate follower " + name)
            lifecycle.append(candidates[0])
        require([event["data"]["sequence"] for event in lifecycle]
                == sorted({event["data"]["sequence"] for event in lifecycle}),
                "follower motion lifecycle order differs")
        kind = 1
        expected = ((kind, motion["duration"]),
                    (motion["commitAfter"], kind),
                    (motion["commitAfter"], kind),
                    (0, motion["commitAfter"]))
        require(all(event["data"].get("reason") == "OK" for event in lifecycle)
                and [(event["data"].get("valueA"), event["data"].get("valueB"))
                     for event in lifecycle] == list(expected),
                "follower motion lifecycle values differ")
        starts = [event for event in self.motion_events
                  if event["data"].get("event") == "MOTION_STARTED"]
        intents = [event for event in self.motion_events
                   if event["data"].get("event") == "INTENT_CREATED"]
        plans = [event for event in self.motion_events
                 if event["data"].get("event") == "PLAN_ACCEPTED"]
        require(len(starts) == 1 and intents and plans
                and intents[0]["data"]["sequence"] < plans[0]["data"]["sequence"]
                < starts[0]["data"]["sequence"],
                "first follower intent, plan and motion start differ")
        self.motion_start_frame = motion["startFrame"]
        self.motion = motion
        self.terminal = deepcopy(snapshot)
        if self.clearance_frame is not None:
            require(self.motion_start_frame <= self.clearance_frame + MAX_RESUME_FRAMES,
                    "follower resume latency exceeded")
            self.ready = True

    def _record_first_motion_events(self, own):
        if any(event["data"].get("event") == "CONTROL_RETURNED"
               for event in self.motion_events):
            return
        relevant = {"INTENT_CREATED", "PLAN_ACCEPTED", *LIFECYCLE}
        for event in own:
            name = event["data"].get("event")
            if name not in relevant:
                continue
            if name == "MOTION_STARTED":
                require(self.motion_start_frame is None,
                        "duplicate first follower motion start")
                self.motion_start_frame = event["frame"]
            self.motion_events.append(event)
            if name == "CONTROL_RETURNED":
                break

    def observe(self, snapshot, events):
        if self.initial is None or self.closed or self.failures or self.ready:
            return self.result()
        try:
            require(snapshot.get("fieldAvailable") is True
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("context") == self.initial["context"],
                    "detach follower field or context differs")
            require(snapshot["frame"] == self.last["frame"] + 1
                    and snapshot["nativeCycle"] > self.last["nativeCycle"],
                    "detach follower completed clock gap")
            self.frames += 1
            require(self.frames <= self.max_frames, "detach follower frame bound exceeded")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True
                    and native.get("coverageComplete") is True
                    and native.get("error") is None
                    and native.get("eventsDropped") == 0,
                    "detach follower native coverage incomplete")
            actor = self._actor(snapshot)
            selector = snapshot.get("selector", {})
            if selector.get("rawNew", 0) & selector.get("newKeys", 0) & 4:
                require(self.select_frame is None, "duplicate detach Select edge")
                self.select_frame = snapshot["frame"]
            own = self._events(snapshot, events, actor)
            if actor["role"] != self.actor["role"]:
                require(self.actor["role"] == "MOUNTED" and actor["role"] == "FOLLOWER"
                        and self.select_frame is not None
                        and snapshot["frame"] - self.select_frame <= 2,
                        "role change lacks the detach Select edge")
                rebound = [event for event in own
                           if event["data"].get("event") == "ACTOR_REBOUND"
                           and (event["data"].get("valueA"), event["data"].get("valueB")) == (3, 2)]
                control = [event for event in own
                           if event["data"].get("event") == "CONTROL_REBOUND"
                           and (event["data"].get("valueA"), event["data"].get("valueB")) == (1, 0)]
                require(len(rebound) == len(control) == 1,
                        "role change lacks exact detach rebound receipts")
                require(actor["authorityGeneration"] == self.actor["authorityGeneration"] + 1
                        and actor["engineAnchorGeneration"] == self.actor["engineAnchorGeneration"] + 1
                        and actor["inputOwnership"] == 0 and actor["reservationId"] == 0,
                        "detach follower ownership boundary differs")
                self.follower_policy = (
                    actor["behaviorFingerprint"], actor["matchedLayerMask"])
                require(self.follower_policy[0] != 0
                        and self.follower_policy != self.mounted_policy,
                        "detach follower policy identity was not restored")
                self.detach_frame = snapshot["frame"]
                self.rebound_events = rebound + control
            elif self.detach_frame is None:
                require(actor["authorityGeneration"] == self.actor["authorityGeneration"]
                        and actor["engineAnchorGeneration"] == self.actor["engineAnchorGeneration"],
                        "ownership changed without role rebound")
            else:
                require(actor["role"] == "FOLLOWER" and actor["inputOwnership"] == 0,
                        "detached actor did not stay autonomous")
                require((actor["behaviorFingerprint"], actor["matchedLayerMask"])
                        == self.follower_policy,
                        "restored follower policy identity changed")

            if self.detach_frame is not None:
                self._record_first_motion_events(own)
                player = snapshot["player"]
                player_distance = (
                    abs(player["x"] - self.initial["player"]["x"])
                    + abs(player["y"] - self.initial["player"]["y"])
                )
                if self.clearance_frame is None \
                        and player_distance >= PLAYER_CLEARANCE_TILES:
                    require(selector.get("rawHeld", 0) & 0xF0,
                            "player clearance lacks normal directional input")
                    self.clearance_frame = snapshot["frame"]
                self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
                require(not self.recorder.failures,
                        "follower motion: " + str(self.recorder.failures))
                self._complete_motion(snapshot, actor)
                if self.motion is not None and self.clearance_frame is not None:
                    require(self.motion_start_frame <= self.clearance_frame + MAX_RESUME_FRAMES,
                            "follower resume latency exceeded")
                    self.ready = True
                if self.clearance_frame is not None and self.motion_start_frame is None:
                    require(snapshot["frame"] <= self.clearance_frame + MAX_RESUME_FRAMES,
                            "follower resume latency exceeded")
            self.actor = deepcopy(actor)
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def finish(self):
        if not self.failures and not self.ready:
            self.failures.append("detach follower motion did not complete")
        self.closed = True
        return self.result()

    def result(self):
        return deepcopy({
            "passed": self.closed and self.ready and not self.failures,
            "ready": self.ready and not self.failures,
            "closed": self.closed,
            "acceptedProof": False,
            "requirements": [REQUIREMENT],
            "subject": self.subject,
            "initial": self.initial,
            "terminal": self.terminal,
            "frames": self.frames,
            "selectFrame": self.select_frame,
            "detachFrame": self.detach_frame,
            "clearanceFrame": self.clearance_frame,
            "motionStartFrame": self.motion_start_frame,
            "reboundEvents": self.rebound_events,
            "motionEvents": self.motion_events,
            "motion": self.motion,
            "mountedPolicy": self.mounted_policy,
            "followerPolicy": self.follower_policy,
            "failures": self.failures,
        })
