"""One held Stantler run with post-cap variance fade and eased speed changes.

The mounted callback reader and completed-queue MotionRecorder are the same
ones used by the existing Cyndaquil S4 pacing witness. This meter only changes
the route and the expectation for successive displayed travel times.
"""
from copy import deepcopy

from tools.overworld.devtools_mount_pacing_measurement import MountedPacingMeasurement
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel
from tools.overworld.devtools_mount_gait import check_gait, check_ground_camera


MOTIONS = 13
NOMINAL_START = 6
FASTEST = 2
VARIANCE = 2
ACCELERATION_STEP = 1
FIRST_COMMIT = 2


def stop_skid_tail(last_walk_time):
    """Authored Sprint stop: displayed time selects distance, then doubles time."""
    count = 0 if last_walk_time >= 7 else 1 if last_walk_time >= 5 else 2 if last_walk_time >= 2 else 4
    return count, min(32, last_walk_time * 2)


def variance_width(index):
    """First cap-speed tile keeps full width; later committed Walks fade it."""
    first_cap = (NOMINAL_START - FASTEST + ACCELERATION_STEP - 1) // ACCELERATION_STEP
    return max(0, VARIANCE - max(0, index - first_cap) * ACCELERATION_STEP)


def keyed_walk_duration(index, subject_identity, encounter_generation, commit_sequence, *, fade=True):
    """Independent keyed draw; fade=False models the rejected old behavior."""
    state = (subject_identity ^ (encounter_generation << 16) ^ commit_sequence) & 0xFFFFFFFF
    state ^= state >> 16
    state = (state * 0x7FEB352D) & 0xFFFFFFFF
    state ^= state >> 15
    state = (state * 0x846CA68B) & 0xFFFFFFFF
    state ^= state >> 16
    nominal = max(FASTEST, NOMINAL_START - index * ACCELERATION_STEP)
    width = variance_width(index) if fade else VARIANCE
    return min(32, nominal + (((state >> 24) * (width + 1)) >> 8))


def walk_progress(elapsed, duration, prior):
    """Independent integer reference for the mounted render-only curve."""
    if elapsed >= duration:
        return 256
    t = elapsed * 256 // duration
    if not prior:
        return t
    remaining = 256 - t
    tangent = t * remaining // 256
    tangent = tangent * remaining // 256
    slope = min(768, duration * 256 // prior)
    adjustment = (slope - 256) * tangent
    adjustment = (1 if adjustment >= 0 else -1) * (abs(adjustment) // 256)
    return max(0, min(256, t + adjustment))


def walk_step_fx32(elapsed, duration, prior):
    """The fresh Walk is stock linear; only a continuing Walk uses Q8 easing."""
    return (65536 * elapsed // duration if not prior
            else 256 * walk_progress(elapsed, duration, prior))


class EasedMountedMotionRecorder(MotionRecorder):
    """Use the authored easing path at a zero-pause tile boundary."""

    def _successor_pose(self, actor, current):
        progress = walk_progress(1, actor["motionDuration"], current["duration"])
        return [(actor["origin"][axis] << 16) + 0x8000
                + (actor["target"][axis] - actor["origin"][axis]) * progress * 256
                for axis in ("x", "y")]


class StantlerMountedMotionRecorder(EasedMountedMotionRecorder):
    MOVING_KINDS = MotionRecorder.MOVING_KINDS + ("SKID",)
    CONTINUOUS_GROUND_KINDS = ("WALK", "SKID")

    def _successor_pose(self, actor, current):
        if actor["motionKind"] == "SKID":
            return MotionRecorder._successor_pose(self, actor, current)
        return super()._successor_pose(actor, current)


def require_one_frame_callbacks(motion, callbacks):
    """Require both real poses when a one-frame Walk has one queue sample."""
    if motion.get("travelEnd", {}).get("observedBy") != "one-frame-successor":
        return True
    origin_x = (motion["origin"][0] << 16) + 32768
    target_x = (motion["target"][0] << 16) + 32768
    lane_z = (motion["origin"][1] << 16) + 32768
    origin = dict(zip(("x", "y"), motion["origin"]))
    target = dict(zip(("x", "y"), motion["target"]))
    matched = [e for e in callbacks if e["frame"] == motion["startFrame"]
               and e["data"]["publicSubject"].get("origin") == origin
               and e["data"]["publicSubject"].get("target") == target
               and e["data"]["publicSubject"].get("motionDuration") == 1]
    starts = [e for e in matched if e["data"]["publicSubject"].get("motionPhase") == "MOVING"
              and e["data"]["publicSubject"].get("motionElapsed") == 0
              and e["data"]["player"]["pos_x"] == origin_x
              and e["data"]["player"]["pos_z"] == lane_z]
    ends = [e for e in matched if e["data"]["publicSubject"].get("motionPhase") == "COMMIT_PENDING"
            and e["data"]["publicSubject"].get("motionElapsed") == 1
            and e["data"]["player"]["pos_x"] == target_x
            and e["data"]["player"]["pos_z"] == lane_z]
    if not starts or not ends or not (
            starts[0]["data"]["returnActorFrame"] < ends[0]["data"]["returnActorFrame"]
            and starts[0]["data"]["returnNativeCycle"] <= ends[0]["data"]["returnNativeCycle"]):
        raise ValueError("one-frame mounted Walk lacks same-frame origin and endpoint callbacks")
    return True


def require_continuous_one_frame_cadence(previous, successor):
    """A held run at one frame per tile must advance a tile every frame."""
    if previous["duration"] != 1 or successor["duration"] != 1 \
            or previous["target"] != successor["origin"]:
        return True
    endpoint = previous["travelEnd"]["frame"]
    if previous.get("lastEndpointFrame", endpoint) != endpoint \
            or successor["startFrame"] != endpoint + 1:
        raise ValueError("one-frame mounted Walk paused before the next tile")
    return True


class MountedSpeedSlewMeasurement(MountedPacingMeasurement):
    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        self._require(self.initial is None, "mounted speed reader already armed")
        self.subject = deepcopy(subject)
        selected = select_current_actor(snapshot, subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        self._require(actor.get("species") == 234 and actor.get("role") == "MOUNTED"
                      and actor.get("inputOwnership") == 1 and actor.get("motionPhase") == "IDLE"
                      and actor.get("reservationId") == 0, "requires idle mounted Stantler")
        self.initial, self.actor = deepcopy(snapshot), deepcopy(actor)
        value = self._reader(receipt, False)
        self._require(value.get("counts") == self.counts, "reader already contains callbacks")
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})
        self.last = deepcopy(snapshot)
        self._window(snapshot, MOTIONS)
        self.windows[-1]["recorder"] = StantlerMountedMotionRecorder()
        self.windows[-1]["cameraLockedFrames"] = 0
        self.windows[-1]["shadowFrames"] = []
        self.windows[-1]["gaitFrames"] = []

    def observe(self, snapshot, events):
        if self.windows and not self.failures:
            try:
                actor = self._actor(snapshot)
            except (ValueError, KeyError, TypeError) as error:
                self.failures.append(str(error))
                return self.result()
            index = actor["commitSequence"] - FIRST_COMMIT
            if actor["motionKind"] == "WALK" and 0 <= index < MOTIONS \
                    and variance_width(index) == 0 and actor["motionDuration"] != FASTEST:
                self.failures.append("mounted speed variance did not fade at nominal maximum")
        if self.windows and self.windows[0]["joined"] >= MOTIONS and not self.failures:
            pair = snapshot.get("mountPacing", {}).get("latestCompletedPose", {})
            actor = self._actor(snapshot)
            if pair.get("input", {}).get("heldKeys") != 0 or actor["motionKind"] not in ("NONE", "SKID"):
                self.failures.append("mounted stop-skid tail has input or unexpected motion")
        value = super().observe(snapshot, events)
        if not self.failures:
            try:
                draw = snapshot.get("mountedDrawPose", {})
                camera = snapshot.get("camera", {})
                actor = self._actor(snapshot)
                pair = snapshot["mountPacing"]["latestCompletedPose"]
                gait_pose = check_gait(pair, required=True)
                gait = pair["gait"]
                self._require(gait["input"]["options"] == 0x5A,
                              "mounted gait does not use the authored default controls")
                prior_rows = self.windows[-1]["gaitFrames"]
                check_ground_camera(dict(pair=pair, camera=camera), prior_rows[-1] if prior_rows else None)
                if prior_rows:
                    previous = prior_rows[-1]["pair"]["gait"]
                    if gait["session"] == previous["session"] and gait["stamp"] != previous["stamp"]:
                        self._require(gait["previous"] == previous["pose"],
                                      "mounted gait phase or damping reset between frames")
                self._require(camera.get("targetPointer") == draw.get("player", {}).get("objectPointer", 0) + 0x70,
                              "mounted camera is not bound to the player position")
                self._require(draw.get("mount", {}).get("objectPointer") == actor["engineIdentity"]["pointer"],
                              "mounted draw owner differs")
                shadows = draw.get("shadows")
                self._require(isinstance(shadows, list), "mounted shadow slots are missing")
                mount_pose = draw["mount"]
                mount_shadows = [shadow for shadow in shadows
                                 if shadow.get("owner") == mount_pose["objectPointer"]]
                self._require(len(mount_shadows) == 1,
                              "mounted shadow owner count differs")
                shadow = mount_shadows[0]
                self._require(type(shadow.get("flags")) is int and shadow["flags"] & 1
                              and shadow.get("hidden") == 0
                              and shadow.get("callback") in (0x021FD719, 0x021FD92D)
                              and isinstance(shadow.get("position"), list)
                              and len(shadow["position"]) == 3
                              and all(type(value) is int for value in shadow["position"]),
                              "mounted live shadow is missing")
                self._require(all(shadow["position"][axis] == mount_pose["position"][axis]
                                  for axis in (0, 1, 2)),
                              "mounted shadow trails its mount")
                # Prepared setup can expose one idle frame before the player
                # graphics task is ready. It is not part of the held Walk;
                # require the full sprite/shadow pose on every motion frame.
                if draw["player"].get("graphicsPointer") == 0 \
                        and actor["motionKind"] == "NONE" \
                        and actor["motionPhase"] == "IDLE" \
                        and not self.windows[-1]["recorder"].completed \
                        and self.windows[-1]["recorder"].current is None:
                    return value
                player_shadows = [value for value in shadows
                                  if value.get("owner") == draw["player"]["objectPointer"]]
                self._require(all(type(value.get("hidden")) is int
                                  and value["hidden"] != 0 for value in player_shadows),
                              "player shadow is visible while mounted")
                self.windows[-1]["shadowFrames"].append(dict(
                    frame=snapshot["frame"], mount=deepcopy(mount_pose["position"]),
                    shadows=deepcopy(shadows),
                    mountPointer=mount_pose["objectPointer"],
                    playerPointer=draw["player"]["objectPointer"]))
                for key in ("player", "mount"):
                    pose = draw[key]
                    self._require(type(pose.get("graphicsPointer")) is int
                                  and 0x02000000 <= pose["graphicsPointer"] < 0x02400000
                                  and isinstance(pose.get("graphics"), list)
                                  and len(pose["graphics"]) == 3,
                                  "mounted visible sprite pose is missing")
                    expected = [sum(pose[part][axis] for part in
                                    ("position", "face", "extra", "jump"))
                                + (0x6000 if axis == 2 else 0)
                                for axis in (0, 1, 2)]
                    actual = [pose["graphics"][axis] for axis in (0, 1, 2)]
                    self._require(actual == expected,
                                  "mounted visible sprite lags the camera target")
                self.windows[-1]["cameraLockedFrames"] += 1
                self.windows[-1]["gaitFrames"].append(dict(frame=snapshot["frame"],
                    pair=deepcopy(pair), draw=deepcopy(draw), camera=deepcopy(camera)))
            except (KeyError, TypeError, ValueError) as error:
                self.failures.append(str(error))
                return self.result()
        return value

    def _join(self, window, motion):
        index = window["joined"]
        skid = index >= MOTIONS
        expected_kind, kind_id = ("SKID", 4) if skid else ("WALK", 1)
        self._require(index < window["expected"] and complete_travel(motion)
                      and motion["kind"] == expected_kind
                      and motion["target"] == [motion["origin"][0] + 1, motion["origin"][1]]
                      and motion["commitAfter"] == (motion["commitBefore"] + 1) & 0xFFFFFFFF,
                      "mounted speed motion is not the expected Right Walk or stop skid")
        duration = motion["duration"]
        expected = window["stopSkidDuration"] if skid else keyed_walk_duration(
            index, self.actor["subjectIdentity"],
            self.actor["handle"]["encounterGeneration"], motion["commitBefore"])
        self._require(type(duration) is int
                      and motion["commitBefore"] == FIRST_COMMIT + index
                      and duration == expected,
                      "mounted speed lost its keyed variance value")
        if index:
            previous = window["recorder"].completed[index - 1]
            self._require(motion["origin"] == previous["target"],
                          "mounted speed route skips a tile")
            require_continuous_one_frame_cadence(previous, motion)
            if not skid and duration != previous["duration"]:
                window["easedTransitions"] = window.get("easedTransitions", 0) + 1
        for sample in motion["samples"]:
            prior = window["recorder"].completed[index - 1]["duration"] if index and not skid else 0
            expected = (motion["origin"][0] << 16) + 32768 \
                + walk_step_fx32(sample["elapsed"], duration, prior)
            self._require(sample["render"][0] == expected
                          and sample["render"][2] == (motion["origin"][1] << 16) + 32768
                          and sample["jumpOffset"] == 0,
                          "mounted speed Walk did not use the eased tile path")
        if index and motion["samples"]:
            previous = window["recorder"].completed[index - 1]
            endpoint = (previous["target"][0] << 16) + 32768
            first = motion["samples"][0]
            self._require(0 <= first["render"][0] - endpoint <= 65536,
                          "mounted speed Walk snaps across a tile boundary")
        successor = window["recorder"].current
        if successor is not None and successor is not motion:
            require_continuous_one_frame_cadence(motion, successor)
        expected_events = (("MOTION_STARTED", motion["startFrame"], kind_id, duration),
                           ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], kind_id),
                           ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], kind_id),
                           ("CONTROL_RETURNED", motion["finishFrame"], 1, motion["commitAfter"]))
        sequences = []
        for name, frame, a, b in expected_events:
            matches = [e["data"] for e in window["traces"]
                       if e["frame"] == frame and e["data"].get("event") == name]
            self._require(len(matches) == 1 and matches[0].get("reason") == "OK"
                          and (matches[0].get("valueA"), matches[0].get("valueB")) == (a, b),
                          "missing native " + name)
            sequences.append(matches[0]["sequence"])
        self._require(sequences == sorted(set(sequences)), "mounted speed lifecycle order differs")
        start = next(e["data"] for e in window["traces"] if e["frame"] == motion["startFrame"]
                     and e["data"].get("event") == "MOTION_STARTED")
        finish = next(e["data"] for e in window["traces"] if e["frame"] == motion["finishFrame"]
                      and e["data"].get("event") == "MOTION_FINISHED")
        callbacks = [e for e in window["callbacks"]
                     if start["actorFrame"] <= e["data"]["returnActorFrame"] <= finish["actorFrame"]]
        self._require(bool(callbacks), "mounted speed motion lacks presentation callback")
        require_one_frame_callbacks(motion, callbacks)
        leading = sum(sample["elapsed"] == 0 for sample in motion["samples"])
        window["leadingZero"] = max(window["leadingZero"], leading)
        self._require(leading <= 1, "mounted speed Walk has extra leading zero")
        if index:
            previous = window["recorder"].completed[index - 1]
            ends = [e for e in window["callbacks"]
                    if e["data"]["publicSubject"].get("target") == dict(zip(("x", "y"), previous["target"]))
                    and e["data"]["publicSubject"].get("motionElapsed") == previous["duration"]]
            starts = [e for e in callbacks
                      if e["data"]["publicSubject"].get("origin") == dict(zip(("x", "y"), motion["origin"]))]
            self._require(bool(ends) and bool(starts), "mounted speed boundary callback is missing")
            gap = starts[0]["data"]["returnNativeCycle"] - ends[-1]["data"]["returnNativeCycle"]
            window["boundaryGap"] = max(window["boundaryGap"], gap)
            self._require(0 <= gap <= 2, "mounted speed native boundary gap exceeds two cycles")
        if index == MOTIONS - 1:
            count, skid_duration = stop_skid_tail(duration)
            window.update(expected=MOTIONS + count, stopSkidCount=count, stopSkidDuration=skid_duration)

    @property
    def main_complete(self):
        return bool(self.windows and not self.failures and self.windows[0]["joined"] >= MOTIONS)

    @property
    def ready(self):
        rows = self.windows[0]["gaitFrames"] if self.windows else []
        return self.main_complete and self._complete(self.windows[0]) and self.frames >= 62 and len(rows) >= 62 \
            and all(rows[-1]["pair"]["gait"]["pose"][key] == 0
                    for key in ("bodyY", "riderY", "leanX", "leanZ"))

    def stage(self, name):
        return {"main-started": self.started == MOTIONS,
                "main-complete": self.main_complete,
                "gait-settled": self.ready}.get(name, False)

    def close(self, receipt, snapshot):
        self._require(self.ready and snapshot == self.last,
                      "mounted speed run is incomplete at close")
        value = self._reader(receipt, True)
        self._require(value["counts"] == self.counts, "mounted speed reader callbacks were lost")
        control = value.get("latestCompletedPose", {}).get("avatarControl", {})
        self._require(type(control.get("flags")) is int and not control["flags"] & 1
                      and control.get("playerMoveState") in (0, 3),
                      "mounted speed control is not released")
        self.cleanup = deepcopy(receipt)
        self.closed = True
        return self.finish()

    def result(self):
        proof = {}
        if self.closed and self.ready and not self.failures:
            window = self.windows[0]
            durations = [m["duration"] for m in window["recorder"].completed[:MOTIONS]]
            gait_rows = window["gaitFrames"]
            lean_signs = [int(any(row["pair"]["gait"]["pose"]["leanX"] * sign > 0
                                 for row in gait_rows)) for sign in (-1, 1)]
            rows = (("natural-input", "held-right-walk-count", MOTIONS, MOTIONS, "eq"),
                    ("live-actor-identity", "mounted-stantler-identity", [1, "MOUNTED", 234, 1], [1, "MOUNTED", 234, 1], "eq"),
                    ("rendered-motion", "continuous-walk-count", min(window["joined"], MOTIONS), MOTIONS, "eq"),
                    ("rendered-motion", "paired-position-mismatch-count", window["deltaMismatch"], 0, "eq"),
                    ("rendered-motion", "camera-locked-draw-frame-count", window["cameraLockedFrames"], 47, "gte"),
                    ("rendered-motion", "mounted-shadow-aligned-frame-count", len(window["shadowFrames"]), 62, "gte"),
                    ("rendered-motion", "distance-gait-and-seat-frame-count", len(gait_rows), 62, "gte"),
                    ("rendered-motion", "gait-acceleration-braking-observed", lean_signs, [1, 1], "eq"),
                    ("rendered-motion", "gait-settled-after-release", int(self.ready), 1, "eq"),
                    ("rendered-motion", "authored-stop-skid-tail", int(self._complete(window)), 1, "eq"),
                    ("frame-pacing", "authored-variance-tile-count", len(durations), MOTIONS, "eq"),
                    ("rendered-motion", "eased-speed-transition-count", window.get("easedTransitions", 0), 1, "gte"),
                    ("frame-pacing", "maximum-callback-gap", window["callbackGap"], 2, "lte"),
                    ("frame-pacing", "maximum-boundary-gap", window["boundaryGap"], 2, "lte"),
                    ("engine-boundary", "player-step-callback-count", len(window["steps"][:MOTIONS]), MOTIONS, "eq"),
                    ("control-release", "released-player-control", [1, 0, 1], [1, 0, 1], "eq"))
            for claim, name, actual, expected, operator in rows:
                proof.setdefault(claim, []).append(dict(name=name, actual=actual,
                                                          expected=expected, operator=operator))
        return dict(passed=self.closed and self.ready and not self.failures,
                    proofEvidence=proof, subject=deepcopy(getattr(self, "subject", None)),
                    initial=deepcopy(self.initial), closed=self.closed, acceptedProof=False,
                    cleanup=deepcopy(getattr(self, "cleanup", None)), failures=list(self.failures),
                    frames=self.frames, started=self.started, mainComplete=self.main_complete,
                    ready=self.ready, callbackClock="native return cycles",
                    completedClock="main-task-queue completions",
                    windows=[{k: deepcopy(v) for k, v in window.items() if k != "recorder"} |
                             {"motions": deepcopy(window["recorder"].completed)}
                             for window in self.windows])
