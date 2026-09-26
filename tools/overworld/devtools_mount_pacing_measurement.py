"""Pure seven-Walk mounted pacing witness; never drives or accepts a ROM.

Completed queue frames feed MotionRecorder. Native callback return cycles feed
pacing. These clocks are deliberately never substituted for one another.
"""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_mount_pacing_observer import IDENTITY, ENGINE

# Mounted inherits Cyndaquil's normal Default Owner lane: 16-frame Walk,
# one frame faster after each three committed tiles. Follower's 8-frame cap
# is not part of a mounted request. Keep this authored vector independent of
# observed durations so disabled acceleration still fails.
MAIN_DURATIONS = (16, 16, 16, 15, 15, 15, 14)


def check_pair_pose(data):
    """Raise on an invalid raw pair; return True for the unchanged valid pose."""
    from tools.overworld.devtools_mount_gait import normalized_pair
    normalized = normalized_pair(data)
    player, mount = normalized["player"], normalized["mount"]
    # South gives the mount extra depth in front of the rider. Other
    # directions and the rider height stay unchanged.
    offsets = {0: (0, 32768), 1: (0, -40960), 2: (32768, 0), 3: (-32768, 0),
               4: (32768, 32768), 5: (-32768, 32768),
               6: (32768, -32768), 7: (-32768, -32768)}
    facing = player.get("facing")
    if type(facing) is not int or facing not in offsets:
        raise ValueError("mounted base, facing or rider offset differs")
    offset_x, offset_z = offsets[facing]
    if not (all(type(obj.get(prefix+a)) is int for obj in (player,mount)
                for prefix in ("pos_", "face_", "unk88_", "unk94_") for a in "xyz")
            and all(player["pos_"+a] == mount["pos_"+a] for a in "xyz")
            and player["facing"] == mount["facing"]
            and player["face_y"] - mount["face_y"] == 32768
            and player["unk88_y"] == mount["unk88_y"] == 0
            and all(sum(player[p+a]-mount[p+a] for p in ("face_","unk88_","unk94_")) == expected
                    for a,expected in (("x",offset_x),("y",32768),("z",offset_z)))):
        raise ValueError("mounted base, facing or rider offset differs")
    return True


class MountedPacingMeasurement:
    def __init__(self, max_frames):
        if type(max_frames) is not int or not 1 <= max_frames <= 1200:
            raise ValueError("invalid mounted pacing frame bound")
        self.max_frames = max_frames
        self.initial = None
        self.closed = False
        self.frames = 0
        self.failures = []
        self.windows = []
        self.sequence = 0
        self.streams = {}
        self.counts = {"presentation": 0, "playerStep": 0}
        self.last = None

    def _require(self, ok, message):
        if not ok:
            raise ValueError(message)

    def _actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        self._require(all(actor.get(k) == self.actor.get(k) for k in IDENTITY)
                      and actor.get("inputOwnership") == 1
                      and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
                      and engine_binding_identity(actor.get("engineIdentity")) ==
                      engine_binding_identity(self.actor.get("engineIdentity"))
                      and snapshot["context"] == self.initial["context"],
                      "mounted identity, profile or context changed")
        return actor

    def _reader(self, receipt, closed):
        value = receipt.get("mountPacing", receipt)
        self._require(value.get("armed") is True and value.get("closed") is closed
                      and value.get("failure") is None and value.get("acceptedProof") is False
                      and value.get("guestMemoryWrites") == 0
                      and value.get("subject") == self.subject
                      and value.get("startFrame") == self.initial["frame"],
                      "missing or changed mounted reader receipt")
        return value

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        self._require(self.initial is None, "mounted pacing already armed")
        self.subject = deepcopy(subject)
        selected = select_current_actor(snapshot, subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        self._require(actor.get("species") == 155 and actor.get("role") == "MOUNTED"
                      and actor.get("inputOwnership") == 1 and actor.get("motionPhase") == "IDLE"
                      and actor.get("reservationId") == 0, "requires idle mounted Cyndaquil")
        self.initial, self.actor = deepcopy(snapshot), deepcopy(actor)
        value = self._reader(receipt, False)
        self._require(value.get("counts") == self.counts, "reader already contains callbacks")
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})
        self.last = deepcopy(snapshot)
        self._window(snapshot, 7)

    def _window(self, snapshot, count):
        # The speed-slew meter derives from this one. Import its scoped
        # recorder only when opening a window, after both modules have loaded.
        from tools.overworld.devtools_mount_speed_slew_measurement import EasedMountedMotionRecorder

        self.windows.append(dict(expected=count, origin=deepcopy(self._actor(snapshot)["logical"]),
            recorder=EasedMountedMotionRecorder(), traces=[], callbacks=[], steps=[], joined=0,
            callbackGap=0, boundaryGap=0, leadingZero=0, deltaMismatch=0,
            startFrame=snapshot["frame"], startCycle=snapshot["nativeCycle"]))

    def _callback(self, event, actor):
        data, window = event["data"], self.windows[-1]
        kind = data["kind"]
        self._require(kind in self.counts and data.get("subject") == self.subject
            and all(data["publicSubject"].get(k) == self.actor.get(k) for k in IDENTITY)
            and data.get("sourceIdentity") == self.actor["sourceIdentity"]
            and all(data["engineIdentity"].get(k) == self.actor["engineIdentity"].get(k) for k in ENGINE)
            and data.get("playerPointer") == self.actor["engineIdentity"]["anchorPointer"]
            and data.get("mountPointer") == self.actor["engineIdentity"]["pointer"], "callback subject differs")
        self.counts[kind] += 1
        self._require(sum(self.counts.values()) <= 4096, "callback bound exceeded")
        from tools.overworld.devtools_mount_gait import normalized_pair
        normalized = normalized_pair(data)
        player, mount = normalized["player"], normalized["mount"]
        self._pair(data)
        if kind == "playerStep":
            self._require(data.get("eventConsumed") == 0, "world step consumed an event")
            window["steps"].append(deepcopy(event))
            self._require(len(window["steps"]) <= window["expected"], "extra world-step callback")
            return
        # Read all four native position vectors. A changed offset is not hidden
        # by checking only the common logical target or base coordinates.
        pair = []
        for axis in "xyz":
            values = [sum(obj[prefix + axis] for prefix in ("pos_", "face_", "unk88_", "unk94_"))
                      for obj in (player, mount)]
            pair.append(values[0] - values[1])
        if window["callbacks"]:
            prior = window["callbacks"][-1]
            previous_pair = prior["pair"]
            if pair != previous_pair:
                window["deltaMismatch"] += 1
                raise ValueError("rider and Pokemon rendered delta differ")
            gap = data["returnNativeCycle"] - prior["data"]["returnNativeCycle"]
            window["callbackGap"] = max(window["callbackGap"], gap)
            self._require(gap <= 2, "native presentation callback gap exceeds two cycles")
        window["callbacks"].append({**deepcopy(event), "pair": pair})

    def _pair(self, data):
        return check_pair_pose(data)

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            self._require(self.initial is not None and not self.closed, "pacing window is not open")
            actor = self._actor(snapshot)
            reader = self._reader(snapshot["mountPacing"], False)
            native = snapshot["nativeObservation"]
            self._require(native.get("installedBeforeBoot") is True and native.get("coverageComplete") is True
                          and native.get("error") is None
                          and all(native.get(k) == 0 for k in ("eventsDropped","profilesEvicted")),
                          "native coverage is incomplete")
            pose = snapshot.get("mountPacing", {}).get("latestCompletedPose")
            self._require(isinstance(pose, dict) and pose.get("boundary") == "main-task-queue-completion"
                          and pose.get("frame") == snapshot["frame"]
                          and pose.get("nativeCycle") == snapshot["nativeCycle"], "missing completed pair pose")
            self._pair(pose)
            self._require(pose.get("subject") == self.subject
                          and all(pose["publicSubject"].get(k) == actor.get(k) for k in IDENTITY)
                          and pose.get("playerPointer") == actor["engineIdentity"]["anchorPointer"]
                          and pose.get("mountPointer") == actor["engineIdentity"]["pointer"],
                          "completed pair owner differs")
            self._require(snapshot["frame"] == self.last["frame"] + 1
                          and snapshot["nativeCycle"] > self.last["nativeCycle"], "completed clock gap")
            self.frames += 1
            self._require(self.frames <= self.max_frames, "mounted pacing frame bound exceeded")
            window = self.windows[-1]
            for event in events:
                data = event.get("data", {})
                self._require(event.get("frame") == snapshot["frame"], "event completion frame differs")
                if event.get("kind") == "native-observation":
                    self._require(data.get("sequence") == self.sequence + 1, "native receipt sequence gap")
                    self.sequence += 1
                    self._require(self.last["nativeCycle"] <= data["entryNativeCycle"] <=
                        data["returnNativeCycle"] <= snapshot["nativeCycle"], "native callback clock differs")
                    if data.get("observation") in ("mount-pacing-presentation", "mount-pacing-player-step"):
                        self._callback(event, actor)
                elif event.get("kind") == "native":
                    stream, sequence = data["traceStream"], data["sequence"]
                    self._require(stream not in self.streams or sequence == self.streams[stream] + 1,
                                  "semantic sequence gap")
                    self.streams[stream] = sequence
                    if data.get("actorHandle") == self.actor["handle"]["value"]:
                        self._require(data.get("actor") == {k: v for k, v in self.actor["handle"].items() if k != "value"},
                                      "semantic generation differs")
                        self._require(data.get("event") not in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND"),
                                      "motion canceled or rebound")
                        window["traces"].append(deepcopy(event))
                        self._require(len(window["traces"]) <= 256, "semantic trace bound exceeded")
                elif event.get("kind") == "trace-status" and data.get("code") == "ring-overwrite":
                    # Overwriting events already retained by the host is not
                    # lost evidence. Match the shared acceleration contract.
                    self._require(type(data.get("unreadEventsLost")) is int
                        and data["unreadEventsLost"] == 0
                        and data.get("coverageComplete", True) is True
                        and data.get("diagnosticOnly") is True
                        and type(data.get("count")) is int and data["count"] > 0
                        and type(data.get("traceStream")) is int
                        and data["traceStream"] > 0 and data["traceStream"] in self.streams,
                        "mounted pacing trace lost unread events")
                elif event.get("kind") == "trace-status":
                    raise ValueError("trace status interrupts pacing window")
            self._require(snapshot["nativeObservation"]["sequence"] == self.sequence, "missing native receipt")
            self._require(reader.get("counts") == self.counts, "reader callbacks were lost")
            from tools.overworld.devtools_mount_gait import check_gait
            ground_player = deepcopy(snapshot["player"])
            ground_player["unk88_y"] -= check_gait(pose)["riderY"]
            window["recorder"].observe(snapshot["frame"], actor, ground_player)
            self._require(not window["recorder"].failures, "mounted motion: " + str(window["recorder"].failures))
            self._require(self._starts(window) <= window["expected"], "extra mounted motion")
            while window["joined"] < len(window["recorder"].completed):
                self._join(window, window["recorder"].completed[window["joined"]])
                window["joined"] += 1
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _join(self, window, motion):
        from tools.overworld.devtools_mount_speed_slew_measurement import walk_step_fx32

        if window is self.windows[0]:
            self._require(window["joined"] < len(MAIN_DURATIONS)
                          and motion["duration"] == MAIN_DURATIONS[window["joined"]],
                          "mounted Cyndaquil acceleration duration differs")
        self._require(motion["kind"] == "WALK" and motion["target"] == [motion["origin"][0]+1, motion["origin"][1]],
                      "motion is not one Right Walk")
        prior = window["recorder"].completed[window["joined"]-1]["duration"] if window["joined"] else 0
        for sample in motion["samples"]:
            expected = (motion["origin"][0] << 16) + 32768 \
                + walk_step_fx32(sample["elapsed"], motion["duration"], prior)
            self._require(sample["render"][0] == expected and sample["render"][2] == (motion["origin"][1] << 16)+32768
                          and sample["jumpOffset"] == 0, "mounted Walk pose differs from eased path")
        expected = (("MOTION_STARTED", motion["startFrame"], 1, motion["duration"]),
                    ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 1),
                    ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 1),
                    ("CONTROL_RETURNED", motion["finishFrame"], 1, motion["commitAfter"]))
        sequences = []
        for name, frame, a, b in expected:
            matches = [e["data"] for e in window["traces"] if e["frame"] == frame and e["data"].get("event") == name]
            self._require(len(matches) == 1 and matches[0].get("reason") == "OK"
                and (matches[0].get("valueA"), matches[0].get("valueB")) == (a,b), "missing native " + name)
            sequences.append(matches[0]["sequence"])
        self._require(sequences == sorted(set(sequences)), "motion lifecycle order differs")
        start_trace = next(e["data"] for e in window["traces"] if e["frame"] == motion["startFrame"]
                           and e["data"].get("event") == "MOTION_STARTED")
        finish_trace = next(e["data"] for e in window["traces"] if e["frame"] == motion["finishFrame"]
                            and e["data"].get("event") == "MOTION_FINISHED")
        callbacks = [e for e in window["callbacks"] if start_trace["actorFrame"] <=
                     e["data"]["returnActorFrame"] <= finish_trace["actorFrame"]]
        self._require(bool(callbacks), "missing motion presentation callbacks")
        zero_cycles = sum(sample["elapsed"] == 0 for sample in motion["samples"])
        window["leadingZero"] = max(window["leadingZero"], zero_cycles)
        self._require(zero_cycles <= 1, "leading zero exceeds one completed movement frame")
        if window["joined"]:
            prior = window["recorder"].completed[window["joined"]-1]
            previous = [e for e in window["callbacks"] if e["data"]["publicSubject"].get("target") ==
                        dict(zip(("x","y"),prior["target"])) and
                        e["data"]["publicSubject"].get("motionElapsed") == prior["duration"]]
            current = [e for e in callbacks if e["data"]["publicSubject"].get("origin") ==
                       dict(zip(("x","y"),motion["origin"]))]
            self._require(bool(previous) and bool(current), "missing native boundary callback")
            gap = current[0]["data"]["returnNativeCycle"] - previous[-1]["data"]["returnNativeCycle"]
            window["boundaryGap"] = max(window["boundaryGap"], gap)
            self._require(0 <= gap <= 2, "native motion boundary gap exceeds two cycles")

    @staticmethod
    def _starts(window):
        return sum(e["data"].get("event") == "MOTION_STARTED" for e in window["traces"])

    @property
    def started(self):
        return self._starts(self.windows[0]) if self.windows else 0

    def _complete(self, window):
        return window["joined"] == window["expected"] and window["recorder"].current is None \
            and len(window["steps"]) == window["expected"] and all(
                sum(e["data"].get("event") == name for e in window["traces"]) == window["expected"]
                for name in ("MOTION_STARTED","LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"))

    @property
    def main_complete(self):
        return bool(self.windows and not self.failures and self._complete(self.windows[0]))

    @property
    def ready(self):
        return self.main_complete and len(self.windows) == 2 and self._complete(self.windows[1])

    def begin_recovery(self, snapshot):
        self._require(self.main_complete and len(self.windows) == 1 and snapshot == self.last,
                      "seven Walks are not complete at recovery boundary")
        self._window(snapshot, 1)

    def stage(self, name):
        return {"main-started": self.started == 7, "main-complete": self.main_complete,
                "recovery-started": len(self.windows) == 2 and self._starts(self.windows[1]) == 1,
                "recovery-complete": self.ready}.get(name, False)

    def close(self, receipt, snapshot):
        self._require(self.ready and snapshot == self.last, "recovery is incomplete")
        value = self._reader(receipt, True)
        self._require(value["counts"] == self.counts, "reader callbacks were lost")
        control = value.get("latestCompletedPose", {}).get("avatarControl", {})
        self._require(type(control.get("flags")) is int and not control["flags"] & 1
                      and control.get("playerMoveState") in (0, 3), "recovery control is not released")
        self.recovery_control = [1, control["flags"] & 1, 1]
        self.cleanup = deepcopy(receipt)
        self.closed = True
        return self.finish()

    def finish(self):
        if not self.closed and not self.failures:
            self.failures.append("mounted pacing reader was not closed")
        return self.result()

    def result(self):
        proof = {}
        if self.closed and self.ready and not self.failures:
            w = self.windows[0]
            rows = [("natural-input", "held-input-tile-distance", 7, 7, "eq"),
                ("live-actor-identity", "mounted-smoothness-cyndaquil-identity", [1,"MOUNTED",155,1], [1,"MOUNTED",155,1], "eq"),
                ("rendered-motion", "rendered-motion-count", w["joined"], 7, "eq"),
                ("rendered-motion", "pair-delta-mismatch-count", w["deltaMismatch"], 0, "eq"),
                ("frame-pacing", "maximum-callback-gap", w["callbackGap"], 2, "lte"),
                ("frame-pacing", "maximum-boundary-gap", w["boundaryGap"], 2, "lte"),
                ("frame-pacing", "maximum-leading-zero-frames", w["leadingZero"], 1, "lte"),
                ("engine-boundary", "normal-player-step-callback-count", len(w["steps"]), 7, "eq"),
                ("control-release", "recovery-terminal-state", self.recovery_control, [1,0,1], "eq")]
            for claim, name, actual, expected, operator in rows:
                proof.setdefault(claim, []).append(dict(name=name, actual=actual, expected=expected, operator=operator))
        return dict(passed=self.closed and self.ready and not self.failures, proofEvidence=proof,
                    subject=deepcopy(getattr(self,"subject",None)), initial=deepcopy(self.initial),
                    closed=self.closed, acceptedProof=False, cleanup=deepcopy(getattr(self,"cleanup",None)),
                    failures=list(self.failures), frames=self.frames, started=self.started,
                    mainComplete=self.main_complete, ready=self.ready,
                    callbackClock="native return cycles", completedClock="main-task-queue completions",
                    windows=[{k: deepcopy(v) for k,v in w.items() if k != "recorder"} |
                             {"motions": deepcopy(w["recorder"].completed)} for w in self.windows])
