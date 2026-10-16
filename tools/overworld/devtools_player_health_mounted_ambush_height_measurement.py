"""A mounted Ambush hit uses one jump anchor and restores rider seat height."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor


KIND = "player-health-mounted-ambush-height-v1"
REQUIREMENT = "current.player-health-mounted-ambush-height"
SETUP = ("ambush-tile", "prepare-cyndaquil", "mount-cyndaquil", "settle-mount",
         "bind-cyndaquil", "spawn-weepinbell", "bind-weepinbell")
ORDER = ("before-contact", "observe-ambush", "after-ambush")
OBSERVE_FRAMES = 150
MIN_FRAMES = OBSERVE_FRAMES
PLAYER_TILE = (585, 407)
AMBUSH_BIT = 1 << 25


def require(condition, message):
    if not condition:
        raise ValueError(message)


class PlayerHealthMountedAmbushHeightMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.mount_subject = None
        self.setup_index = 0
        self.mount_settle_frames = 0
        self.action_index = 0
        self.observed_frames = 0
        self.wait_frames = 0
        self.flight_frames = 0
        self.final_tile = None
        self.base_face_y = None
        self.base_mount_face_y = None
        self.base_player_unk88_y = None
        self.base_mount_unk88_y = None
        self.final_mount_face_y = None
        self.final_player_face_y = None
        self.before_hp = None
        self.after_hp = None
        self.jump_arc_seen = False
        self.base_player_pos_y = None
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
            require(type(player.get("x")) is int and type(player.get("y")) is int
                    and abs(player["x"]-PLAYER_TILE[0])+abs(player["y"]-PLAYER_TILE[1]) <= 8,
                    "mounted Ambush moved outside its bounded knockback area")

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

    def _mount(self, snapshot):
        require(self.mount_subject is not None, "mounted Cyndaquil is not bound")
        selected = select_current_actor(snapshot, self.mount_subject)
        actor = next(a for a in snapshot["actors"]
                     if a.get("handle") == selected["handle"])
        require(actor.get("species") == 155 and actor.get("role") == "MOUNTED"
                and actor.get("active") is True
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 1,
                "bound Cyndaquil is not the current mounted actor")
        engine = actor.get("engineObject", {})
        require(type(engine.get("face_y")) is int
                and type(engine.get("unk88_y")) is int,
                "mounted Cyndaquil pose is missing")
        return actor

    def _health(self, row, expected):
        snapshot = row.get("snapshot")
        self._boundary(snapshot)
        self._actor(snapshot)
        self._mount(snapshot)
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
                and hp.get("recoveryPending") is False,
                "Ambush live/saved HP, damage, or hit count differs")
        if expected is None:
            hits = hp.get("acceptedHits")
            require(type(hits) is int and 1 <= hits <= 4
                    and hp.get("hp") == 100 - 20 * hits
                    and hp["hp"] <= 80 and hp.get("lastDamage") == 20,
                    "mounted Ambush did not cause measured 20-HP hit(s)")
        else:
            require((hp.get("hp"), hp.get("lastDamage"), hp.get("acceptedHits")) == expected,
                    "mounted Ambush initial HP differs")
        return deepcopy(hp)

    def _sample(self, sample):
        self._boundary(sample)
        actor = self._actor(sample)
        mount = self._mount(sample)["engineObject"]
        require(sample["frame"] == self.latest["frame"] + 1
                and sample["nativeCycle"] >= self.latest["nativeCycle"],
                "Ambush raw frames skip or reverse")
        player = sample["player"]
        tile = (player["x"], player["y"])
        self.wait_frames += 1
        require(self.wait_frames <= OBSERVE_FRAMES
                and player.get("pos_x") == mount.get("pos_x")
                and player.get("pos_z") == mount.get("pos_z")
                and player.get("face_y") - mount["face_y"] == 32768,
                "mounted hit split its shared anchor or seat height")
        if (player.get("face_y", self.base_face_y) > self.base_face_y
                or player.get("pos_y", self.base_player_pos_y) > self.base_player_pos_y):
            self.jump_arc_seen = True
        if (actor.get("motionKind") == "HOP"
                and actor.get("motionPhase") == "MOVING"
                and actor.get("matchedLayerMask", 0) & AMBUSH_BIT
                and type(actor.get("motionElapsed")) is int
                and type(actor.get("motionDuration")) is int
                and 0 < actor["motionElapsed"] < actor["motionDuration"]):
            origin, target = actor.get("origin", {}), actor.get("target", {})
            if (origin.get("x") == target.get("x") == PLAYER_TILE[0]
                    and origin.get("y", 1000) < PLAYER_TILE[1]
                    and target.get("y", -1) >= PLAYER_TILE[1] - 1):
                self.flight_frames += 1
        self.final_tile = tile
        self.latest = deepcopy(sample)
        self.observed_frames += 1

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
                        and row.get("action") == SETUP[self.setup_index],
                        "Ambush setup order differs")
                if self.setup_index == 3:
                    require("command" not in row, "mount settle is not a raw frame stream")
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        self._boundary(sample)
                        self.latest = deepcopy(sample)
                        self.mount_settle_frames += 1
                    require(self.mount_settle_frames <= 16, "mount settle exceeded 16 frames")
                    if self.mount_settle_frames == 16:
                        self.setup_index += 1
                    return self.result()
                require(row.get("command") == ("teleport", "party", "spawn", None,
                                               "bind", "spawn", "bind")[self.setup_index],
                        "Ambush setup command differs")
                snapshot = row.get("snapshot")
                self._boundary(snapshot)
                require((snapshot["player"]["x"], snapshot["player"]["y"])
                        == PLAYER_TILE, "Ambush setup tile differs")
                if self.setup_index == 4:
                    self.mount_subject = deepcopy(row.get("receipt"))
                    self._mount(snapshot)
                if self.setup_index == 5:
                    value = row.get("receipt", {}).get("value", {})
                    require(value.get("species") == 70
                            and type(value.get("slot")) is int
                            and type(value.get("personality")) is int,
                            "Weepinbell native spawn identity differs")
                if self.setup_index == 6:
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
            if action == "observe-ambush":
                require("command" not in row,
                        "Ambush step lacks raw completed game frames")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    self._sample(sample)
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if self.wait_frames == OBSERVE_FRAMES:
                    self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe",
                    "Ambush HP read is not a checked native receipt")
            if action == "before-contact":
                self.before_hp = self._health(row, (100, 0, 0))
                self.base_face_y = row["snapshot"]["player"].get("face_y")
                self.base_player_pos_y = row["snapshot"]["player"].get("pos_y")
                require(type(self.base_face_y) is int,
                        "Ambush baseline face height is missing")
                mount = self._mount(row["snapshot"])["engineObject"]
                self.base_mount_face_y = mount["face_y"]
                self.base_player_unk88_y = row["snapshot"]["player"].get("unk88_y")
                self.base_mount_unk88_y = mount["unk88_y"]
                require(self.base_face_y - self.base_mount_face_y == 32768
                        and self.base_player_unk88_y == self.base_mount_unk88_y == 0,
                        "mounted pre-hit seat or gait height differs")
            else:
                require(self.flight_frames > 0 and self.wait_frames == OBSERVE_FRAMES,
                        "mounted Ambush lacked ordinary active Hop frames")
                self.after_hp = self._health(row, None)
                require(self.after_hp["lastHealthFrame"]
                        - self.before_hp["lastHealthFrame"]
                        == self.latest["frame"] - self.before_hp["frame"],
                        "Ambush HP clock skipped a game frame")
                player = row["snapshot"]["player"]
                mount = self._mount(row["snapshot"])["engineObject"]
                self.final_player_face_y = player.get("face_y")
                self.final_mount_face_y = mount["face_y"]
                require(self.final_player_face_y == self.base_face_y
                        and self.final_mount_face_y == self.base_mount_face_y
                        and self.final_player_face_y - self.final_mount_face_y == 32768
                        and player.get("unk88_y") == mount["unk88_y"] == 0,
                        "mounted rider or mount retained hit elevation")
            self.latest = deepcopy(row["snapshot"])
            self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) \
            and self.wait_frames == OBSERVE_FRAMES and self.flight_frames > 0 \
            and self.final_tile != PLAYER_TILE and self.jump_arc_seen and self.after_hp is not None \
            and self.final_player_face_y == self.base_face_y \
            and self.final_mount_face_y == self.base_mount_face_y
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "flightFrames": self.flight_frames, "hpAfter":
                None if self.after_hp is None else self.after_hp["hp"],
                "acceptedHits": None if self.after_hp is None else self.after_hp["acceptedHits"],
                "jumpArcSeen": self.jump_arc_seen,
                "finalTile": list(self.final_tile) if self.final_tile else None,
                "subject": deepcopy(self.subject),
                "mountSubject": deepcopy(self.mount_subject),
                "baselineFaceY": [self.base_face_y, self.base_mount_face_y],
                "finalFaceY": [self.final_player_face_y, self.final_mount_face_y]}

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("mounted Ambush ended before damage and stable height")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
