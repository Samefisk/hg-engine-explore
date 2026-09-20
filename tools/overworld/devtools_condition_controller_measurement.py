"""Measure one real Wild conditional-profile caller and stale-target boundary."""
from __future__ import annotations

from copy import deepcopy

from tools.overworld.devtools_condition_controller import (
    CONDITION_APPLICATION,
    CONDITION_COOLDOWN,
    CONDITION_DURATION,
    CONDITION_ID,
    CONDITION_NAME,
    HOP_DISTANCE,
    HOP_DURATION,
    HOP_TRAVEL_FRAMES,
    KIND,
    LOCOMOTION_HOP,
    RUNTIME_ACTIVE_MASKS_OFFSET,
    SUBJECT_ROLE,
    SUBJECT_SPECIES,
    TARGET_ROLE,
    decode_profile,
    expected_profile,
    stale_generation,
    target_generation_address,
)
from tools.overworld.devtools_records import select_current_actor


LIFECYCLE = (
    "INTENT_CREATED",
    "MOTION_STARTED",
    "LOGICAL_COMMIT",
    "MOTION_FINISHED",
    "CONTROL_RETURNED",
)


def require(value, reason):
    if not value:
        raise ValueError("condition live controller: " + reason)


def _handle(value):
    require(isinstance(value, dict), "actor handle is missing")
    keys = ("slot", "generation", "fieldEpoch", "mapGeneration",
            "encounterGeneration")
    require(all(type(value.get(key)) is int and value[key] >= 0 for key in keys),
            "actor handle fields differ")
    return {key: value[key] for key in keys}


def _distance(point, target):
    return max(abs(point[0] - target[0]), abs(point[1] - target[1]))


class ConditionControllerMeasurement:
    def __init__(self, test=None, max_frames=240, **_kwargs):
        require(type(max_frames) is int and 1 <= max_frames <= 600,
                "invalid frame bound")
        self.test = test
        self.max_frames = max_frames
        self.subject = self.initial = self.last = self.terminal = None
        self.frames = 0
        self.closed = False
        self.failures = []
        self.evaluations = []
        self.wrappers = []
        self.target_fault = None
        self.traces = []
        self.motion_samples = []
        self.cleanup = None
        self.event_index = 0

    def _reader(self, value, *, closed):
        reader = value.get("conditionController", value)
        fixture = reader.get("fixture", {})
        condition = fixture.get("condition", {})
        profile = fixture.get("profile", {})
        callbacks = reader.get("callbacks", {})
        require(reader.get("armed") is True
                and reader.get("closed") is closed
                and reader.get("failure") is None
                and reader.get("acceptedProof") is False,
                "native reader state differs")
        require(fixture.get("fixtureVersion") == 1
                and condition.get("id") == CONDITION_ID
                and condition.get("name") == CONDITION_NAME
                and condition.get("applicationIndex") == CONDITION_APPLICATION
                and condition.get("activation") == "timed"
                and condition.get("durationFrames") == CONDITION_DURATION
                and condition.get("cooldownFrames") == CONDITION_COOLDOWN
                and condition.get("targetKind") == "actor"
                and condition.get("targetRole") == TARGET_ROLE
                and profile.get("id") == "ambush-plant-active"
                and profile.get("applicationIndex") == CONDITION_APPLICATION,
                "controlled condition fixture differs")
        require(set(callbacks) == {"adapterEvaluate", "wildEvaluate"}
                and all(type(item.get("address")) is int
                        and item["address"] % 2 == 0
                        and 0x02000000 <= item["address"] < 0x02400000
                        and isinstance(item.get("entrySha256"), str)
                        and len(item["entrySha256"]) == 64
                        for item in callbacks.values()),
                "native callback authentication differs")
        return reader

    def _subject_actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot.get("actors", [])
                     if item.get("handle") == selected["handle"])
        require(actor.get("species") == SUBJECT_SPECIES
                and actor.get("role") == SUBJECT_ROLE
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True,
                "Wild Weepinbell identity differs")
        return actor

    def _target_actor(self, snapshot, handle):
        wanted = _handle(handle)
        matches = [item for item in snapshot.get("actors", [])
                   if _handle(item.get("handle")) == wanted]
        require(len(matches) == 1
                and matches[0].get("role") == TARGET_ROLE
                and matches[0].get("identityVerified") is True,
                "Follower target is not one current live actor")
        return matches[0]

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        try:
            require(self.subject is None and not self.closed,
                    "measurement was already armed")
            self.subject = deepcopy(subject)
            actor = self._subject_actor(snapshot)
            require(actor.get("motionPhase") in ("IDLE", "MOVING", "SETTLING")
                    and isinstance(actor.get("motionKind"), str),
                    "subject has no live motion state at the armed boundary")
            reader = self._reader(receipt, closed=False)
            require(reader.get("subject") == self.subject
                    and reader.get("startFrame") == snapshot.get("frame")
                    and reader.get("guestMemoryWriteBytes") == 3
                    and reader.get("guestMemoryWriteOperations") == 3
                    and reader.get("catalogPatch", {}).get("applied") is True
                    and reader["catalogPatch"].get("restored") is False,
                    "arm receipt differs")
            self.initial = self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _evaluation(self, event, snapshot):
        data = event["data"]
        status = data.get("status")
        require(data.get("subject") == self.subject
                and data.get("caller")
                    == "OverworldWildSpawns_EvaluateConditionsForSlot"
                and data.get("slot") == self.subject["handle"]["slot"]
                and status in (0, 3)
                and data.get("motionAtEntry", {}).get("phase") == "IDLE",
                "adapter call is not one real idle Wild-controller call")
        runtime = data.get("runtimePointer")
        require(type(runtime) is int and runtime % 4 == 0
                and 0x02000000 <= runtime < 0x02400000,
                "condition runtime pointer differs")
        if status == 0:
            condition = data.get("condition", {})
            target = data.get("resolvedTarget", {})
            require(condition.get("id") == CONDITION_ID
                    and condition.get("applicationIndex")
                        == CONDITION_APPLICATION
                    and condition.get("conditionTrue") is True
                    and condition.get("active") is True
                    and condition.get("timed") is True
                    and condition.get("durationFrames") == CONDITION_DURATION
                    and condition.get("cooldownFrames") == CONDITION_COOLDOWN
                    and data.get("activeApplicationMask")
                        & (1 << CONDITION_APPLICATION)
                    and target.get("kind") == "ACTOR"
                    and target.get("role") == TARGET_ROLE,
                    "successful condition result differs")
            target_actor = self._target_actor(snapshot, target.get("handle"))
            require(target.get("position")
                    == [target_actor["logical"]["x"],
                        target_actor["logical"]["y"]],
                    "condition target position differs from the live Follower")
            resolved = decode_profile(data.get("profileHex"))
            require(all(resolved.get(key) == value
                        for key, value in expected_profile().items()),
                    "resolved Ambush Plant conditional profile differs")
        else:
            require(self.target_fault is not None
                    and data.get("staleTarget") == self.target_fault["after"]
                    and data.get("activeApplicationMask") == 0
                    and data.get("targetValid") is False,
                    "STALE_TARGET did not clear condition resolution")
        self.evaluations.append({**deepcopy(data), "frame": event["frame"],
                                 "order": event["order"]})

    def _wrapper(self, event):
        data = event["data"]
        require(data.get("subject") == self.subject
                and data.get("slot") == self.subject["handle"]["slot"]
                and data.get("motionAtEntry", {}).get("phase") == "IDLE",
                "Wild condition wrapper owner differs")
        result = data.get("resultFlags")
        require(type(result) is int and 0 <= result <= 7,
                "Wild condition wrapper result differs")
        if result & 4:
            require(data.get("activeApplicationMaskAfter") == 0
                    and data.get("targetValidAfter") is False,
                    "stale target did not fail closed")
        self.wrappers.append({**deepcopy(data), "frame": event["frame"],
                              "order": event["order"]})

    def _target_staled(self, event, snapshot, actor):
        require(self.target_fault is None, "target generation was changed twice")
        data = event["data"]
        before = data.get("before")
        after = data.get("after")
        target = data.get("targetHandle")
        prepared_index = data.get("preparedIndex")
        state_pointer = data.get("statePointer")
        require(data.get("subject") == self.subject
                and actor.get("motionPhase") == "MOVING"
                and actor.get("motionKind") == "HOP"
                and type(before) is int
                and after == stale_generation(before)
                and isinstance(target, dict)
                and target.get("generation") == before
                and data.get("bytesWritten") == 2
                and data.get("address")
                    == target_generation_address(state_pointer, prepared_index)
                and data.get("actorTargetUnchanged") is True,
                "controlled stale-target write differs")
        self._target_actor(snapshot, target)
        self.target_fault = {**deepcopy(data), "frame": event["frame"],
                             "order": event["order"]}

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            require(self.initial is not None and not self.closed,
                    "measurement is not open")
            require(snapshot.get("frame") == self.last.get("frame") + 1
                    and snapshot.get("nativeCycle", 0)
                        >= self.last.get("nativeCycle", 0),
                    "completed-frame clock has a gap")
            actor = self._subject_actor(snapshot)
            reader = self._reader(snapshot, closed=False)
            require(reader.get("subject") == self.subject,
                    "reader subject changed")
            self.frames += 1
            require(self.frames <= self.max_frames, "frame bound exceeded")
            for event in events:
                require(event.get("frame") == snapshot.get("frame"),
                        "event frame differs")
                self.event_index += 1
                tagged = {**event, "order": self.event_index}
                data = tagged.get("data", {})
                if tagged.get("kind") == "native-observation":
                    observation = data.get("observation")
                    if observation == "condition-controller-evaluate":
                        self._evaluation(tagged, snapshot)
                    elif observation == "condition-controller-wrapper":
                        self._wrapper(tagged)
                    elif observation == "condition-controller-target-staled":
                        self._target_staled(tagged, snapshot, actor)
                elif (tagged.get("kind") == "native"
                      and data.get("event") in LIFECYCLE
                      and self.evaluations):
                    require(data.get("actorHandle")
                            == self.subject["handle"]["value"],
                            "lifecycle event belongs to another actor")
                    self.traces.append(deepcopy(tagged))
            successful = sum(item.get("status") == 0
                             for item in self.evaluations)
            if successful >= 2 and actor.get("motionPhase") == "MOVING":
                self.motion_samples.append({
                    "frame": snapshot["frame"],
                    "origin": [actor["origin"]["x"], actor["origin"]["y"]],
                    "target": [actor["target"]["x"], actor["target"]["y"]],
                    "kind": actor.get("motionKind"),
                    "duration": actor.get("motionDuration"),
                    "elapsed": actor.get("motionElapsed"),
                })
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _accept(self):
        call_count = len(self.evaluations)
        require(call_count >= 3 and len(self.wrappers) == call_count
                and [item["status"] for item in self.evaluations]
                    == [0] * (call_count - 1) + [3],
                "expected trigger, active holds, then STALE_TARGET")
        require([item["resultFlags"] for item in self.wrappers]
                == [1] + [0] * (call_count - 2) + [4],
                "Wild wrapper did not trigger, hold, then fail closed")
        require(self.evaluations[0]["condition"].get("triggered") is True
                and all(item["condition"].get("triggered") is False
                        for item in self.evaluations[1:-1]),
                "condition trigger or active hold differs")
        require(self.target_fault is not None, "stale-target write is missing")
        require(self.motion_samples
                and all(item["kind"] == "HOP"
                        and item["duration"] == HOP_TRAVEL_FRAMES
                        and _distance(item["origin"], item["target"])
                            == HOP_DISTANCE
                        for item in self.motion_samples),
                "conditional Hop profile was not used")
        target = self.evaluations[-2]["resolvedTarget"]["position"]
        first_motion = self.motion_samples[0]
        require(_distance(first_motion["target"], target)
                < _distance(first_motion["origin"], target),
                "conditional motion did not move toward its Follower target")
        by_name = {}
        for event in self.traces:
            by_name.setdefault(event["data"]["event"], []).append(event)
        require(all(len(by_name.get(name, [])) == 1 for name in LIFECYCLE),
                "one complete conditional intent lifecycle is missing")
        ordered = [by_name[name][0]["data"]["sequence"] for name in LIFECYCLE]
        require(ordered == sorted(set(ordered)),
                "conditional intent lifecycle order differs")
        start = by_name["MOTION_STARTED"][0]
        finish = by_name["MOTION_FINISHED"][0]
        returned = by_name["CONTROL_RETURNED"][0]
        require(start["data"].get("valueA") == LOCOMOTION_HOP
                and start["data"].get("valueB") == HOP_TRAVEL_FRAMES
                and start["order"] <= self.target_fault["order"]
                    < finish["order"]
                and finish["order"] <= returned["order"]
                    < self.evaluations[-1]["order"],
                "stale target was not held until the next intent boundary")
        require(all(item.get("motionAtEntry", {}).get("phase") == "IDLE"
                    for item in self.evaluations)
                and not any(start["frame"] < item["frame"] < finish["frame"]
                            for item in self.evaluations),
                "condition evaluation interrupted accepted motion")
        fail_closed = [item for item in self.wrappers if item["resultFlags"] & 4]
        require(len(fail_closed) == 1
                and fail_closed[0]["frame"] == self.evaluations[-1]["frame"]
                and not any(event["order"] >= fail_closed[0]["order"]
                            and event["data"]["event"]
                                in ("INTENT_CREATED", "MOTION_STARTED")
                            for event in self.traces),
                "STALE_TARGET did not stop the next intent")
        reader = self._reader(self.cleanup, closed=True)
        state_reset = reader.get("controlledStateReset", {})
        require(reader.get("guestMemoryWriteBytes") == 28
                and reader.get("guestMemoryWriteOperations") == 9
                and state_reset.get("bytesWritten") == 20
                and state_reset.get("writeOperations") == 2
                and state_reset.get("stateAfterHex") == "00" * 16
                and state_reset.get("activeApplicationMaskAfterHex")
                    == "00" * 4
                and state_reset.get("stateAddress")
                    == (self.evaluations[0]["statePointer"]
                        + state_reset.get("preparedIndex") * 16)
                and state_reset.get("activeApplicationMaskAddress")
                    == (self.evaluations[0]["runtimePointer"]
                        + RUNTIME_ACTIVE_MASKS_OFFSET
                        + self.evaluations[0]["slot"] * 4)
                and reader.get("catalogPatch", {}).get("restored") is True
                and reader["catalogPatch"].get("restoredSha256")
                    == reader["fixture"].get("sourceSha256")
                and reader.get("hookCleanup") == {"removed": True, "errors": []}
                and reader.get("counts")
                    == {"adapter": call_count, "wrapper": call_count}
                and all(item.get("entered") == call_count
                        and item.get("returned") == call_count
                        and item.get("nonmatchingEntries") == 0
                        for item in reader.get("callbacks", {}).values())
                and self.cleanup.get("advancedFrames") == 0,
                "condition reader cleanup differs")

    def close(self, snapshot, receipt):
        if self.closed:
            return self.result()
        try:
            require(self.initial is not None, "measurement was not armed")
            self.cleanup = deepcopy(receipt)
            self.terminal = deepcopy(snapshot)
            self.closed = True
            self._subject_actor(snapshot)
            self._accept()
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def stage(self, name):
        """Report only the one bounded wait stage owned by this meter."""
        require(name == "stale-target-observed", "unknown measurement stage")
        return self.result()["stage"] == name

    def finish(self):
        """Return the terminal result used by the shared recipe evaluator."""
        if not self.closed and not self.failures:
            self.failures.append("measurement was not closed")
        return self.result()

    def result(self):
        ready = self.closed and self.cleanup is not None and not self.failures
        stale_observed = (self.target_fault is not None
                          and bool(self.evaluations)
                          and self.evaluations[-1].get("status") == 3
                          and bool(self.wrappers)
                          and self.wrappers[-1].get("resultFlags", 0) & 4 != 0)
        return {
            "state": "failed" if self.failures else "passed" if ready else "running",
            "ready": ready,
            "passed": ready,
            "closed": self.closed,
            "stage": ("stale-target-observed"
                      if stale_observed else "observing-live-caller"),
            "acceptedProof": False,
            "observedFrames": self.frames,
            "observedFrameUnit": "completed-game-frames",
            "completedGameFrames": self.frames,
            "subject": deepcopy(self.subject),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "evaluations": deepcopy(self.evaluations),
            "wrappers": deepcopy(self.wrappers),
            "targetFault": deepcopy(self.target_fault),
            "traces": deepcopy(self.traces),
            "motionSamples": deepcopy(self.motion_samples),
            "cleanup": deepcopy(self.cleanup),
            "failures": deepcopy(self.failures),
            "scope": ("one controlled Wild Weepinbell caller, one timed Ambush "
                      "Plant condition, one live Follower target, one Hop, and "
                      "one condition-owned stale target; no Follower-caller or "
                      "mounted-target-exclusion credit"),
        }
