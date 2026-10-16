"""Measure a real Wild Pokémon throw against the stationary Route 29 player.

Prepared placement establishes two current actors. Only subsequent normal
movement, flight, and HP observations count toward the gameplay claim.
"""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_profile_feature_measurement import application_index


KIND = "player-health-throw-contact-v1"
REQUIREMENT = "current.player-health-throw-contact"
SETUP = ("throw-tile", "spawn-weepinbell", "bind-weepinbell",
         "spawn-geodude", "bind-geodude")
ORDER = ("before-throw", "launch-natural-throw", "at-launch",
         "cross-player", "after-contact")
LAUNCH_LIMIT = 240
CROSS_FRAMES = 64
MIN_FRAMES = 1 + CROSS_FRAMES
PLAYER_TILE = (585, 407)
KNOCKBACK_TILE = (585, 408)
TARGET_START = (585, 400)
SOURCE_START = (585, 402)
THROW_APPLICATION_BIT = 1 << application_index("apply-throw")
THROW_RELEASE_BIT = 1 << application_index("apply-throw-release")
# The current throw-find-position profile admits the full north line.
THROW_MAX_RANGE = 8


def require(value, message):
    if not value:
        raise ValueError(message)


class PlayerHealthThrowContactMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subjects = {}
        self.receipts = {}
        self.setup_index = 0
        self.action_index = 0
        self.observed_frames = 0
        self.launch_frames = 0
        self.cross_frames = 0
        self.launch_frame = None
        self.flight_frames = 0
        self.travel_seen = False
        self.landed = False
        self.flight_origin = None
        self.flight_duration = None
        self.flight_reservation = None
        self.flight_commit = None
        self.knockback_seen = False
        self.slide_seen = False
        self.base_face_y = None
        self.failures = []

    def _boundary(self, snapshot, fixture=True, allow_knockback=False):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int,
                "Throw proof needs a completed game boundary")
        context = snapshot.get("context", {})
        require(isinstance(context, dict)
                and (not fixture or context.get("mapId") == 33),
                "Throw proof map differs")
        require(isinstance(snapshot.get("player"), dict)
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "Throw proof left normal field control or entered battle")
        if fixture:
            player_tile = (snapshot["player"].get("x"),
                           snapshot["player"].get("y"))
            require(player_tile in ((PLAYER_TILE, KNOCKBACK_TILE)
                                   if allow_knockback else (PLAYER_TILE,)),
                    "player left the one-tile Throw path")
        if "romSha256" in snapshot:
            require(snapshot["romSha256"] == self.source["romSha256"],
                    "Throw snapshot ROM identity differs")

    def _actor(self, snapshot, subject_id):
        require(subject_id in self.subjects, "Throw actor was not bound: " + subject_id)
        selected = select_current_actor(snapshot, self.subjects[subject_id])
        actor = next(a for a in snapshot["actors"]
                     if a.get("handle") == selected["handle"])
        species = 70 if subject_id == "weepinbell" else 74
        require(actor.get("species") == species and actor.get("role") == "WILD"
                and actor.get("active") is True
                and actor.get("presentationAttached") is True,
                "Throw actor is not the current visible Wild " + subject_id)
        return actor

    def _same_boundary(self, snapshot):
        keys = ("frame", "nativeCycle", "observationBoundary", "fieldAvailable",
                "romSha256", "context", "fieldControl", "player", "actors")
        require(all(snapshot.get(key) == self.latest.get(key) for key in keys),
                "Throw HP receipt is not at the current completed boundary")

    def _health(self, row, action):
        result = row.get("receipt")
        hp = result.get("playerHealth") if isinstance(result, dict) else None
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1,
                "checked Throw HP receipt is missing")
        identity = hp.get("identity", {})
        require(identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and identity.get("romSha256") == self.source["romSha256"],
                "Throw HP ROM or overlay identity differs")
        snapshot = row["snapshot"]
        self._boundary(snapshot, allow_knockback=action == "after-contact")
        self._actor(snapshot, "weepinbell")
        self._actor(snapshot, "geodude")
        require(hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("maxHp") == 100
                and hp.get("hp") == hp.get("savedHp")
                and hp.get("recoveryPending") is False
                and hp.get("frameActive") is False,
                "Throw HP read differs from current field and save")
        expected = (80, 20, 1) if action == "after-contact" \
            else (100, 0, 0)
        require((hp.get("hp"), hp.get("lastDamage"), hp.get("acceptedHits"))
                == expected, "Throw damage or recorded damage differs")
        health_frame = hp.get("lastHealthFrame")
        require(type(health_frame) is int and health_frame >= 0,
                "Throw HP clock is missing")
        if action == "at-launch":
            require(self.launch_frame == snapshot["frame"],
                    "Throw launch HP was not read at the launch boundary")
            before = self.receipts["before-throw"]
            require(health_frame - before["lastHealthFrame"]
                    == snapshot["frame"] - before["frame"],
                    "Throw HP clock did not advance with field frames before launch")
        if action == "after-contact":
            require((snapshot["player"]["x"], snapshot["player"]["y"])
                    == KNOCKBACK_TILE and self.knockback_seen,
                    "Throw did not push the player one tile along the flight")
            require(self.slide_seen,
                    "Throw knockback did not use a flat stationary slide")
            require(self.landed and self.flight_frames > 0 and self.travel_seen,
                    "Throw HP changed without a measured airborne crossing")
            launch = self.receipts["at-launch"]
            require(health_frame - launch["lastHealthFrame"]
                    == snapshot["frame"] - launch["frame"],
                    "Throw HP clock did not advance with the completed flight frames")
        if action == "before-throw":
            self.base_face_y = snapshot["player"].get("face_y")
            require(type(self.base_face_y) is int,
                    "Throw player face height is missing")
        self.receipts[action] = deepcopy(hp)

    def _sample(self, sample, action):
        self._boundary(sample, allow_knockback=action == "cross-player")
        if action == "cross-player":
            self.knockback_seen |= (
                (sample["player"]["x"], sample["player"]["y"])
                == KNOCKBACK_TILE)
            if sample["player"].get("movement_cmd") == 62:
                require(sample["player"].get("face_y")
                        == self.base_face_y,
                        "Throw slide changed the player's face height")
                self.slide_seen = True
        source = self._actor(sample, "geodude")
        target = self._actor(sample, "weepinbell")
        if action == "launch-natural-throw":
            self.launch_frames += 1
            require(self.launch_frames <= LAUNCH_LIMIT,
                    "natural Throw did not launch within its frame limit")
            if (target.get("motionKind") == "HOP"
                    and source.get("matchedLayerMask", 0) & THROW_RELEASE_BIT):
                require(self.launch_frame is None
                        and target.get("motionPhase") == "MOVING"
                        and source.get("matchedLayerMask", 0) & THROW_RELEASE_BIT,
                        "Weepinbell Hop is not Geodude's active Throw launch")
                origin = target.get("origin", {})
                landing = target.get("target", {})
                carrier = source.get("logical", {})
                carrier_pose = source.get("engineObject", {})
                require((origin.get("x"), origin.get("y"))
                        == (carrier.get("x"), carrier.get("y"))
                        and origin.get("x") == 585
                        and type(origin.get("y")) is int
                        and 0 < PLAYER_TILE[1] - origin["y"] <= THROW_MAX_RANGE
                        and (carrier_pose.get("x"), carrier_pose.get("y"))
                            == (origin["x"], origin["y"])
                        and (carrier_pose.get("pos_x"), carrier_pose.get("pos_z"))
                            == ((origin["x"] << 16) + 0x8000,
                                (origin["y"] << 16) + 0x8000)
                        and (landing.get("x"), landing.get("y")) == PLAYER_TILE
                        and type(target.get("motionDuration")) is int
                        and target["motionDuration"] > 1
                        and target.get("motionElapsed") == 0
                        and type(target.get("reservationId")) is int
                        and target["reservationId"] > 0
                        and type(target.get("commitSequence")) is int
                        and target["commitSequence"] >= 0,
                        "thrown actor did not launch from Geodude toward the player")
                self.flight_origin = (origin["x"], origin["y"])
                self.flight_duration = target["motionDuration"]
                self.flight_reservation = target["reservationId"]
                self.flight_commit = target["commitSequence"]
                self.launch_frame = sample["frame"]
        else:
            self.cross_frames += 1
            require(self.cross_frames <= CROSS_FRAMES,
                    "Throw crossing has more frames than declared")
            if target.get("motionKind") == "HOP" and not self.landed:
                require((target.get("origin", {}).get("x"),
                         target.get("origin", {}).get("y")) == self.flight_origin
                        and (target.get("target", {}).get("x"),
                             target.get("target", {}).get("y")) == PLAYER_TILE
                        and target.get("motionDuration") == self.flight_duration
                        and target.get("reservationId") == self.flight_reservation
                        and target.get("commitSequence") == self.flight_commit,
                        "Throw flight changed source or target")
                elapsed, duration = target.get("motionElapsed"), target.get("motionDuration")
                if type(elapsed) is int and type(duration) is int \
                        and 0 < elapsed < duration \
                        and target.get("motionPhase") == "MOVING":
                    self.flight_frames += 1
                    render = target.get("render", {})
                    if render.get("x") == 585 \
                            and self.flight_origin[1] < render.get("y", -1) < 407:
                        self.travel_seen = True
            elif self.flight_frames > 0 and not self.landed:
                logical = target.get("logical", {})
                if (logical.get("x"), logical.get("y")) == PLAYER_TILE \
                        and target.get("motionPhase") in ("IDLE", "SETTLING"):
                    require(target.get("motionKind") == "NONE"
                            and (target.get("origin", {}).get("x"),
                                 target.get("origin", {}).get("y")) == self.flight_origin
                            and (target.get("target", {}).get("x"),
                                 target.get("target", {}).get("y")) == PLAYER_TILE
                            and target.get("motionElapsed") == self.flight_duration
                            and target.get("motionDuration") == self.flight_duration
                            and target.get("reservationId") == 0
                            and target.get("commitSequence") == self.flight_commit + 1,
                            "Throw landing is not the completed first flight")
                    self.landed = True
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "Throw proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "Throw initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "Throw initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "Throw setup order differs")
                command = row.get("command")
                require(command == ("teleport", "spawn", "bind", "spawn", "bind")
                        [self.setup_index], "Throw setup command differs")
                snapshot = row["snapshot"]
                self._boundary(snapshot)
                require(snapshot["frame"] >= self.latest["frame"],
                        "Throw setup clock reversed")
                if command == "spawn":
                    result = row.get("receipt", {}).get("value", {})
                    require(result.get("species") == (70 if self.setup_index == 1 else 74)
                            and type(result.get("slot")) is int
                            and type(result.get("personality")) is int,
                            "Throw native spawn identity differs")
                if command == "bind":
                    subject_id = "weepinbell" if self.setup_index == 2 else "geodude"
                    self.subjects[subject_id] = deepcopy(row["receipt"])
                    actor = self._actor(snapshot, subject_id)
                    if subject_id == "weepinbell":
                        require((actor.get("logical", {}).get("x"),
                                 actor.get("logical", {}).get("y")) == TARGET_START,
                                "Weepinbell left its prepared idle tile")
                    else:
                        require(actor.get("logical", {}).get("x") == SOURCE_START[0]
                                and 400 <= actor.get("logical", {}).get("y", -1) <= 404,
                                "Geodude differs from its prepared approach line")
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP)
                    and row.get("phase") == "observe"
                    and self.action_index < len(ORDER),
                    "Throw observation started before setup or has extra rows")
            action = ORDER[self.action_index]
            require(row.get("action") == action,
                    "Throw action order differs")
            if action in ("launch-natural-throw", "cross-player"):
                require("command" not in row,
                        "Throw step is not a native completed-frame stream")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    require(self.launch_frame is None
                            or action != "launch-natural-throw",
                            "Throw launch action ran past its first flight frame")
                    self._sample(sample, action)
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if action == "launch-natural-throw":
                    if self.launch_frame is not None:
                        self.action_index += 1
                elif self.cross_frames == CROSS_FRAMES:
                    self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe",
                    "Throw action is not a checked player HP read")
            snapshot = row.get("snapshot")
            require(isinstance(snapshot, dict),
                    "Throw HP read has no current snapshot")
            self._same_boundary(snapshot)
            self._health(row, action)
            self.latest = deepcopy(snapshot)
            self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) \
            and self.launch_frame is not None and self.cross_frames == CROSS_FRAMES \
            and self.landed and self.travel_seen and self.flight_frames > 0 \
            and self.knockback_seen and self.slide_seen
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "launchFrame": self.launch_frame,
                "flightFrames": self.flight_frames,
                "landed": self.landed,
                "hpAfterThrow": self.receipts.get("after-contact", {}).get("hp"),
                "knockbackSeen": self.knockback_seen,
                "slideSeen": self.slide_seen,
                "subjects": deepcopy(self.subjects)}

    def stage(self, name):
        require(name == "launched", "unknown Player HP Throw stage")
        return not self.failures and self.launch_frame is not None

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Throw proof ended before a complete flight and HP read")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
