"""One current Ambush Weepinbell hits, then the player jumps south one tile."""

from copy import deepcopy

from tools.overworld.devtools_player_health_hop_contact_measurement import _inside_swept_body
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor


KIND = "player-health-ambush-jump-v1"
REQUIREMENT = "current.player-health-ambush-jump"
SETUP = ("ambush-tile", "spawn-weepinbell", "bind-weepinbell")
ORDER = ("before-contact", "wait-ambush-contact", "at-contact",
         "finish-player-jump", "after-jump")
WAIT_LIMIT = 300
JUMP_FRAMES = 40
MIN_FRAMES = 1 + JUMP_FRAMES
PLAYER_TILE = (585, 407)
LANDING_TILE = (585, 408)
AMBUSH_BIT = 1 << 25


def require(condition, message):
    if not condition:
        raise ValueError(message)


class PlayerHealthAmbushJumpMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.setup_index = 0
        self.action_index = 0
        self.observed_frames = 0
        self.wait_frames = 0
        self.jump_frames = 0
        self.crossing_frame = None
        self.flight_frames = 0
        self.jump_arc_seen = False
        self.stationary_command_seen = False
        self.final_tile = None
        self.base_face_y = None
        self.before_hp = None
        self.after_hp = None
        self.failures = []

    def _boundary(self, snapshot, fixture=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int
                and snapshot.get("romSha256") == self.source["romSha256"]
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "Ambush needs a current completed field frame without battle")
        if fixture:
            require(snapshot.get("context", {}).get("mapId") == 33,
                    "Ambush left Route 29 map 33")
            player = snapshot.get("player", {})
            require((player.get("x"), player.get("y"))
                    in (PLAYER_TILE, LANDING_TILE),
                    "Ambush moved the player outside the one-tile south path")

    def _actor(self, snapshot):
        require(self.subject is not None, "Weepinbell is not bound")
        selected = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"]
                     if a.get("handle") == selected["handle"])
        require(actor.get("species") == 70 and actor.get("role") == "WILD"
                and actor.get("active") is True
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True,
                "bound Weepinbell is not a current visible Wild actor")
        return actor

    def _profile(self, snapshot, actor, cache):
        require(isinstance(cache, dict)
                and cache.get("frame") == snapshot["frame"]
                and cache.get("nativeCycle") == snapshot["nativeCycle"]
                and actor.get("behaviorFingerprint")
                    in snapshot.get("nativeObservation", {}).get("profileFingerprints", [])
                and actor.get("matchedLayerMask", 0) & AMBUSH_BIT,
                "Ambush condition is not resolved at the contact frame")
        matching = [row for row in cache.get("resolvedProfiles", [])
                    if row.get("resolved") is True
                    and row.get("fingerprint") == actor["behaviorFingerprint"]]
        require(len(matching) == 1
                and matching[0].get("sourceSha256") == self.source["profileSha256"]
                and matching[0].get("appliedOverrides", 0) & AMBUSH_BIT,
                "Ambush has no matching current profile")
        raw = bytes.fromhex(matching[0].get("resultHex", ""))
        require(len(raw) == 216 and raw[12] == 2
                and tuple(raw[72:75]) == (1, 16, 20)
                and raw[79] == 6,
                "Ambush lacks attacking 1/16/20 and Jump1")

    def _health(self, row, expected):
        snapshot = row.get("snapshot")
        self._boundary(snapshot)
        self._actor(snapshot)
        require(all(snapshot.get(key) == self.latest.get(key)
                    for key in ("frame", "nativeCycle", "context", "player", "actors")),
                "Ambush HP read is not at the last completed frame")
        hp = row.get("receipt", {}).get("playerHealth")
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1
                and hp.get("identity", {}).get("descriptorVersion") == 1
                and hp["identity"].get("overlayId") == 161
                and hp["identity"].get("romSha256") == self.source["romSha256"]
                and hp["identity"].get("overlaySha256") == self.source["overlaySha256"]
                and hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("maxHp") == 100
                and hp.get("hp") == hp.get("savedHp")
                and hp.get("frameActive") is False
                and hp.get("recoveryPending") is False
                and (hp.get("hp"), hp.get("lastDamage"), hp.get("acceptedHits"))
                    == expected,
                "Ambush live/saved HP, damage, or hit count differs")
        return deepcopy(hp)

    def _sample(self, sample, cache, phase):
        self._boundary(sample)
        actor = self._actor(sample)
        previous = self._actor(self.latest)
        require(sample["frame"] == self.latest["frame"] + 1
                and sample["nativeCycle"] > self.latest["nativeCycle"],
                "Ambush raw frames skip or reverse")
        player = sample["player"]
        tile = (player["x"], player["y"])
        if phase == "wait-ambush-contact":
            self.wait_frames += 1
            require(self.wait_frames <= WAIT_LIMIT and tile == PLAYER_TILE,
                    "player moved before the measured Ambush contact")
            if (actor.get("motionKind") == "HOP"
                    and actor.get("motionPhase") == "MOVING"
                    and type(actor.get("motionElapsed")) is int
                    and type(actor.get("motionDuration")) is int
                    and 0 < actor["motionElapsed"] < actor["motionDuration"]):
                origin, target = actor.get("origin", {}), actor.get("target", {})
                if (origin.get("x") == target.get("x") == PLAYER_TILE[0]
                        and origin.get("y", 1000) < PLAYER_TILE[1]
                        and target.get("y", -1) > PLAYER_TILE[1]):
                    self.flight_frames += 1
                    if _inside_swept_body(previous.get("engineObject", {}),
                                          actor.get("engineObject", {}), player):
                        self._profile(sample, actor, cache)
                        self.crossing_frame = sample["frame"]
        else:
            self.jump_frames += 1
            require(self.jump_frames <= JUMP_FRAMES,
                    "Ambush jump exceeded its declared frame window")
            if player.get("movement_cmd") == 62:
                self.stationary_command_seen = True
                require(type(player.get("face_y")) is int,
                        "Ambush jump has no native face height")
                self.jump_arc_seen |= player["face_y"] > self.base_face_y
            if tile == LANDING_TILE:
                self.final_tile = tile
            require(tile in (PLAYER_TILE, LANDING_TILE),
                    "Ambush jump left the one-tile south path")
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def stage(self, name):
        if name != "airborne-crossed":
            raise ValueError("unknown Ambush measurement stage")
        return not self.failures and self.crossing_frame == self.latest.get("frame")

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "Ambush row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "Ambush initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "Ambush initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index]
                        and row.get("command") == ("teleport", "spawn", "bind")[self.setup_index],
                        "Ambush setup order differs")
                snapshot = row.get("snapshot")
                self._boundary(snapshot)
                require((snapshot["player"]["x"], snapshot["player"]["y"])
                        == PLAYER_TILE, "Ambush setup tile differs")
                if self.setup_index == 1:
                    value = row.get("receipt", {}).get("value", {})
                    require(value.get("species") == 70
                            and type(value.get("slot")) is int
                            and type(value.get("personality")) is int,
                            "Weepinbell native spawn identity differs")
                if self.setup_index == 2:
                    self.subject = deepcopy(row.get("receipt"))
                    self._actor(snapshot)
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP)
                    and row.get("phase") == "observe"
                    and self.action_index < len(ORDER)
                    and row.get("action") == ORDER[self.action_index],
                    "Ambush observation order differs")
            action = ORDER[self.action_index]
            if action in ("wait-ambush-contact", "finish-player-jump"):
                require("command" not in row,
                        "Ambush step lacks raw completed game frames")
                if action == "wait-ambush-contact":
                    require(len(row.get("samples", [])) == 1
                            and isinstance(row.get("profileCache"), dict),
                            "Ambush wait needs one frame and matching profile cache")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    require(action != "wait-ambush-contact"
                            or self.crossing_frame is None,
                            "Ambush wait passed the first crossing")
                    self._sample(sample, row.get("profileCache"), action)
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if action == "wait-ambush-contact" and self.crossing_frame is not None:
                    self.action_index += 1
                elif action == "finish-player-jump" and self.jump_frames == JUMP_FRAMES:
                    self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe",
                    "Ambush HP read is not a checked native receipt")
            if action == "before-contact":
                self.before_hp = self._health(row, (100, 0, 0))
                self.base_face_y = row["snapshot"]["player"].get("face_y")
                require(type(self.base_face_y) is int,
                        "Ambush baseline face height is missing")
            else:
                require(self.crossing_frame is not None,
                        "Ambush HP changed without a measured contact")
                if action == "at-contact":
                    require(self.crossing_frame == self.latest["frame"],
                            "Ambush HP was not read at the crossing frame")
                self.after_hp = self._health(row, (80, 20, 1))
                require(self.after_hp["lastHealthFrame"]
                        - self.before_hp["lastHealthFrame"]
                        == self.latest["frame"] - self.before_hp["frame"],
                        "Ambush HP clock skipped a game frame")
                if action == "after-jump":
                    require((row["snapshot"]["player"]["x"],
                             row["snapshot"]["player"]["y"]) == LANDING_TILE
                            and self.jump_arc_seen and self.stationary_command_seen,
                            "Ambush did not finish a one-tile south player jump")
            self.latest = deepcopy(row["snapshot"])
            self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) \
            and self.crossing_frame is not None and self.flight_frames > 0 \
            and self.jump_frames == JUMP_FRAMES and self.final_tile == LANDING_TILE \
            and self.jump_arc_seen and self.stationary_command_seen
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures), "crossingFrame": self.crossing_frame,
                "flightFrames": self.flight_frames, "hpAfter":
                None if self.after_hp is None else self.after_hp["hp"],
                "jumpArcSeen": self.jump_arc_seen,
                "stationaryCommandSeen": self.stationary_command_seen,
                "finalTile": list(self.final_tile) if self.final_tile else None,
                "subject": deepcopy(self.subject)}

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Ambush ended before exact damage and one-tile jump")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
