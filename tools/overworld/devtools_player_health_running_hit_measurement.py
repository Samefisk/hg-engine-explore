"""One native running admission, real Ambush hit, and immediate idle return."""
from copy import deepcopy

from tools.overworld.devtools_player_health_ambush_jump_measurement import (
    PlayerHealthAmbushJumpMeasurement, SETUP, require,
)
from tools.overworld.devtools_player_health_hop_contact_measurement import _inside_swept_body
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_movement_predicates import player_settled_at, normal_input_at_edge
from tools.overworld.devtools_raw_chunk import validate_raw_chunk

KIND = "player-health-running-hit-v1"
REQUIREMENT = "current.player-health-running-hit"
RUN_LIMIT = 300
RETURN_LIMIT = 40
NEUTRAL_FRAMES = 16
MIN_FRAMES = 18
ORDER = ("before-contact", "run-to-contact", "at-contact", "finish-knockback",
         "neutral-after-knockback", "after-knockback")
AMBUSH_BIT = 1 << application_index("apply-ambush")


def action_spec():
    stage = lambda name: dict(kind="measurement-stage", measurement=KIND, stage=name, when="final")
    return ((ORDER[0], "player-health.observe", {}),
            (ORDER[1], "step", dict(frames=RUN_LIMIT, keys=["UP", "B"], until=stage("running-contact"))),
            (ORDER[2], "player-health.observe", {}),
            (ORDER[3], "step", dict(frames=RETURN_LIMIT, keys=[], until=stage("knockback-returned"))),
            (ORDER[4], "step", dict(frames=NEUTRAL_FRAMES, keys=[])),
            (ORDER[5], "player-health.observe", {}))


def validate_recipe(test):
    require(test["id"] == "player-hp.running-hit" and test["mode"] == "prepared"
            and test["requirements"] == [REQUIREMENT]
            and test["subjects"] == [dict(id="weepinbell", species=70, role="WILD", acquire="spawn")]
            and test["measurements"] == [dict(kind=KIND, subject="weepinbell")]
            and [(a["id"], a["op"], a["args"]) for a in test["setup"]] == [
                (SETUP[0], "teleport", dict(map=33, x=585, z=407, facing=1)),
                (SETUP[1], "spawn", dict(species=70, form=0, role="wild", level=5, x=585, z=404)),
                (SETUP[2], "bind", dict(subject="weepinbell"))]
            and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == action_spec()
            and test["assertions"] == [dict(kind="measurement-complete", measurement=KIND, when="final")]
            and test["budgets"]["maxFrames"] <= 450
            and test["budgets"]["minObservedFrames"] == MIN_FRAMES,
            "running-hit fixture or normal input contract differs")


class PlayerHealthRunningHitMeasurement(PlayerHealthAmbushJumpMeasurement):
    def __init__(self, source):
        super().__init__(source)
        self.context = self.field = self.renderer = None
        self.running_frame = self.admission_frame = self.terminal_frame = None
        self.contact_tile = self.terminal_tile = None
        self.return_frames = self.neutral_frames = 0

    def _boundary(self, sample, fixture=True):
        super()._boundary(sample, fixture=False)
        if fixture:
            require(sample.get("context", {}).get("mapId") == 33,
                    "running-hit left current Route29")
            require(not any(a.get("active") is True and a.get("role") == "MOUNTED"
                            for a in sample.get("actors", [])), "running-hit must be on foot")
        if self.context is not None:
            require(sample.get("context") == self.context
                    and sample.get("fieldControl", {}).get("fieldPointer") == self.field,
                    "running-hit changed its current Field owner")

    def _profile(self, sample, actor, cache):
        require(isinstance(cache, dict) and cache.get("frame") == sample["frame"]
                and cache.get("nativeCycle") == sample["nativeCycle"]
                and actor.get("matchedLayerMask", 0) & AMBUSH_BIT
                and actor.get("behaviorFingerprint") in sample.get("nativeObservation", {}).get("profileFingerprints", []),
                "running-hit lacks current Ambush profile")
        profiles = [p for p in cache.get("resolvedProfiles", [])
                    if p.get("resolved") is True and p.get("fingerprint") == actor["behaviorFingerprint"]]
        require(len(profiles) == 1 and profiles[0].get("sourceSha256") == self.source["profileSha256"]
                and profiles[0].get("appliedOverrides", 0) & AMBUSH_BIT,
                "running-hit profile source differs")
        raw = bytes.fromhex(profiles[0].get("resultHex", ""))
        require(len(raw) == 216 and raw[12] == 2 and tuple(raw[72:75]) == (1, 16, 20) and raw[79] == 6,
                "running-hit lacks attacking 1/16/20 and Jump1")

    def _idle_animation(self, sample):
        player = sample["player"]
        words = player.get("movement_render_words")
        require(type(player.get("movement_animation")) is int and player["movement_animation"] == 0
                and isinstance(words, list) and len(words) == 8
                and all(type(w) is int and 0 <= w <= 0xFFFFFFFF for w in words)
                and words[1] == self.renderer and words[1] != 0
                and (words[0] >> 16) & 255 == 0,
                "running-hit terminal animation is not idle in the same completed frame")

    def _sample(self, sample, cache, action, events):
        self._boundary(sample)
        actor, previous = self._actor(sample), self._actor(self.latest)
        player = sample["player"]
        require(sample["frame"] == self.latest["frame"] + 1 and sample["nativeCycle"] > self.latest["nativeCycle"],
                "running-hit raw frames skip or reverse")
        if action == "run-to-contact":
            self.wait_frames += 1
            require(self.wait_frames <= RUN_LIMIT and normal_input_at_edge(
                    sample, self.latest, 66, first=self.wait_frames == 1, events=events),
                    "running-hit lacks normal UP+B input")
            for event in events:
                data = event.get("data", {})
                if event.get("kind") == "native-observation" and data.get("observation") == "player-step-admitted":
                    require(data.get("mapId") == 33 and data.get("direction") == 0
                            and type(data.get("objectPointer")) is int and data["objectPointer"] != 0
                            and data.get("objectAfter", {}).get("movement_cmd") == 88
                            and data.get("target") == [player["x"], player["y"]],
                            "running-hit native Run admission differs")
                    self.admission_frame = sample["frame"]
            if player.get("movement_cmd") == 88 and player.get("movement_animation") == 9:
                require(self.admission_frame is not None and self.admission_frame <= sample["frame"],
                        "running-hit has no real Run admission")
                self.running_frame = sample["frame"]
            if (actor.get("motionKind") == "HOP" and actor.get("motionPhase") == "MOVING"
                    and 0 < actor.get("motionElapsed", 0) < actor.get("motionDuration", 0)
                    and player.get("movement_cmd") == 62 and player.get("face_y", 0) > self.base_face_y
                    and _inside_swept_body(previous.get("engineObject", {}), actor.get("engineObject", {}), player)):
                require(self.running_frame is not None and self.running_frame < sample["frame"],
                        "running-hit lacks an earlier real Run")
                origin, target = actor.get("origin", {}), actor.get("target", {})
                require(origin.get("x") == target.get("x") == player["x"]
                        and target.get("y", -1) > origin.get("y", 9999),
                        "running-hit incoming Ambush direction differs")
                self._profile(sample, actor, cache)
                self.crossing_frame = sample["frame"]
                self.contact_tile = (player["x"], player["y"])
                self.stationary_command_seen = self.jump_arc_seen = True
                self.flight_frames += 1
        else:
            release_edge = (action == "finish-knockback" and self.return_frames == 0
                            and player.get("movement_cmd") == 62
                            and player.get("face_y", 0) > self.base_face_y)
            require(normal_input_at_edge(sample, self.latest, 0, first=release_edge, events=events),
                    "running-hit neutral input is missing")
            tile = (player["x"], player["y"])
            expected = (self.contact_tile[0], self.contact_tile[1] + 1)
            require(tile in (self.contact_tile, expected), "running-hit left its one-tile knockback path")
            if action == "finish-knockback":
                self.return_frames += 1
                require(self.return_frames <= RETURN_LIMIT, "running-hit exceeded native return bound")
                if (player.get("movement_cmd") == 255 and player.get("movement_step") == 0
                        and player.get("face_y") == self.base_face_y and tile == expected
                        and player_settled_at(sample, 33, *tile)):
                    self._idle_animation(sample)
                    self.terminal_frame, self.terminal_tile = sample["frame"], tile
            else:
                require(self.terminal_frame is not None and tile == self.terminal_tile
                        and player.get("face_y") == self.base_face_y
                        and player_settled_at(sample, 33, *tile),
                        "running-hit did not keep its neutral settled terminal")
                self._idle_animation(sample)
                self.neutral_frames += 1
                require(self.neutral_frames <= NEUTRAL_FRAMES, "running-hit exceeded neutral bound")
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def stage(self, name):
        require(name in ("running-contact", "knockback-returned"), "unknown running-hit stage")
        frame = self.crossing_frame if name == "running-contact" else self.terminal_frame
        return not self.failures and frame is not None and frame == self.latest["frame"]

    def observe_record(self, row, on_sample=None):
        try:
            if row.get("phase") == "setup":
                # Existing Ambush setup owns exact spawn/bind/placement order.
                return super().observe_record(row, on_sample=on_sample)
            require(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                    and self.action_index < len(ORDER) and row.get("action") == ORDER[self.action_index],
                    "running-hit action order differs")
            action = ORDER[self.action_index]
            if action in ("run-to-contact", "finish-knockback", "neutral-after-knockback"):
                require("command" not in row, "running-hit needs dense native frames")
                if action != "neutral-after-knockback":
                    require(len(row.get("samples", [])) == 1, "running-hit stops only at one-frame boundaries")
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    require(self.crossing_frame is None if action == "run-to-contact" else
                            self.terminal_frame is None if action == "finish-knockback" else True,
                            "running-hit passed its first semantic boundary")
                    self._sample(sample, row.get("profileCache"), action, events)
                    if on_sample is not None: on_sample(sample, self.observed_frames)
                if (action == "run-to-contact" and self.crossing_frame is not None
                        or action == "finish-knockback" and self.terminal_frame is not None
                        or action == "neutral-after-knockback" and self.neutral_frames == NEUTRAL_FRAMES):
                    self.action_index += 1
            else:
                require(row.get("command") == "player-health.observe", "running-hit HP read is not native")
                if action == "before-contact":
                    self.context = deepcopy(row["snapshot"].get("context"))
                    self.field = row["snapshot"].get("fieldControl", {}).get("fieldPointer")
                    require(type(self.field) is int and self.field > 0, "running-hit has no current Field")
                    self.before_hp = self._health(row, (100, 0, 0))
                    self.base_face_y = row["snapshot"]["player"].get("face_y")
                    words = row["snapshot"]["player"].get("movement_render_words")
                    require(type(self.base_face_y) is int and isinstance(words, list) and len(words) == 8,
                            "running-hit native renderer baseline is missing")
                    self.renderer = words[1]
                else:
                    require(self.crossing_frame is not None, "running-hit has no measured contact")
                    self.after_hp = self._health(row, (80, 20, 1))
                    require(self.after_hp["lastHealthFrame"] - self.before_hp["lastHealthFrame"]
                            == self.latest["frame"] - self.before_hp["frame"], "running-hit HP clock differs")
                    if action == "at-contact":
                        require(self.latest["frame"] == self.crossing_frame, "running-hit HP read missed contact")
                    else:
                        require(self.neutral_frames == NEUTRAL_FRAMES, "running-hit lacks16 neutral terminal frames")
                self.latest = deepcopy(row["snapshot"])
                self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) and self.terminal_frame is not None
        return dict(ready=ready, observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
                    failures=list(self.failures), subject=deepcopy(self.subject), runAdmissionFrame=self.admission_frame,
                    runningFrame=self.running_frame, crossingFrame=self.crossing_frame, terminalFrame=self.terminal_frame,
                    terminalTile=list(self.terminal_tile) if self.terminal_tile else None,
                    neutralFrames=self.neutral_frames, hpAfter=None if self.after_hp is None else self.after_hp["hp"])

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("running-hit ended before same-frame idle and16 neutral terminal frames")
        return dict(passed=self.result()["ready"], failures=list(self.failures))
