"""Fail-closed proof of one ordinary, profile-attacking Wild Mankey Hop."""

from copy import deepcopy
from fractions import Fraction

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor


KIND = "player-health-hop-contact-v1"
REQUIREMENT = "current.player-health-hop-contact"
SETUP = ("open-area", "spawn-mankey", "bind-mankey")
ORDER = ("settle-spawn", "before-hop", "wait-crossing-hop", "after-contact")
WAIT_LIMIT = 500
MIN_FRAMES = 1
PLAYER_TILE = (585, 407)
LONG_HOP_BIT = 1 << 17
THROW_BIT = 1 << 19


def require(value, message):
    if not value:
        raise ValueError(message)


def _inside_swept_body(before, after, player):
    """Check the observed body segment against the player's 3-D contact box."""
    bounds = (("pos_x", "face_x", -0x8000, 0x8000),
              ("pos_y", "face_y", -0x4000, 0x14000),
              ("pos_z", "face_z", -0x8000, 0x8000))
    enter, leave = Fraction(0), Fraction(1)
    changed = False
    for name, face, lower, upper in bounds:
        start = before.get(name)
        end = after.get(name)
        anchor = player.get(name)
        facing = player.get(face)
        require(all(type(value) is int for value in (start, end, anchor, facing)),
                "Hop body or player native pose is missing")
        start -= anchor + facing
        end -= anchor + facing
        delta = end - start
        changed |= delta != 0
        if delta == 0:
            if not lower <= start <= upper:
                return False
            continue
        first = Fraction(lower - start, delta)
        last = Fraction(upper - start, delta)
        if first > last:
            first, last = last, first
        enter, leave = max(enter, first), min(leave, last)
        if enter > leave:
            return False
    return changed and enter <= leave


class PlayerHealthHopContactMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.latest_profile_cache = None
        self.subject = None
        self.before_health = None
        self.after_health = None
        self.setup_index = 0
        self.action_index = 0
        self.observed_frames = 0
        self.wait_frames = 0
        self.crossing_frame = None
        self.flight = None
        self.flight_attacking = False
        self.flight_frames = 0
        self.settled_at_bind = False
        self.failures = []

    def _boundary(self, snapshot, fixture=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int,
                "Hop proof needs a completed game boundary")
        require(snapshot.get("romSha256") == self.source["romSha256"],
                "Hop snapshot ROM differs")
        if fixture:
            require(snapshot.get("context", {}).get("mapId") == 33
                    and (snapshot.get("player", {}).get("x"),
                         snapshot.get("player", {}).get("y")) == PLAYER_TILE
                    and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                    "Hop left the player fixture or normal field control")

    def _actor(self, snapshot, profile_cache=None):
        require(self.subject is not None, "Wild Mankey is not bound")
        selected = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"]
                     if a.get("handle") == selected["handle"])
        require(actor.get("species") == 56 and actor.get("role") == "WILD"
                and actor.get("active") is True
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True,
                "bound Mankey is not the current visible Wild actor")
        others = [a for a in snapshot["actors"]
                  if a.get("role") == "WILD" and a.get("active") is True
                  and a.get("handle") != selected["handle"]]
        if others:
            cache = profile_cache or {
                "frame": snapshot["frame"], "nativeCycle": snapshot["nativeCycle"],
                "resolvedProfiles": snapshot.get("nativeObservation", {}).get("resolvedProfiles")}
            require(cache.get("frame") == snapshot["frame"]
                    and cache.get("nativeCycle") == snapshot["nativeCycle"]
                    and isinstance(cache.get("resolvedProfiles"), list),
                    "other Wild profile cache is not current")
            for other in others:
                select_current_actor(snapshot, other)
                require(other.get("species") != 56
                        and other.get("motionKind") in ("NONE", "WALK")
                        and other.get("behaviorFingerprint")
                            in snapshot.get("nativeObservation", {}).get("profileFingerprints", []),
                        "another Wild actor could be a Throw target")
                matched = [row for row in cache["resolvedProfiles"]
                           if row.get("resolved") is True
                           and row.get("fingerprint") == other["behaviorFingerprint"]]
                require(len(matched) == 1
                        and matched[0].get("sourceSha256") == self.source["profileSha256"]
                        and matched[0].get("appliedOverrides") == other.get("matchedLayerMask"),
                        "another Wild actor lacks its current resolved profile")
                raw = bytes.fromhex(matched[0].get("resultHex", ""))
                require(len(raw) == 216
                        and raw[72:75] == b"\0\0\0"
                        and raw[152:155] == b"\0\0\0",
                        "another Wild actor could supply a Throw or collision")
        return actor

    def _attack_profile(self, snapshot, actor, profile_cache):
        require(profile_cache.get("frame") == snapshot["frame"]
                and profile_cache.get("nativeCycle") == snapshot["nativeCycle"]
                and actor.get("behaviorFingerprint") in snapshot.get("nativeObservation", {}).get("profileFingerprints", []),
                "Hop profile cache is not at this raw frame")
        profiles = profile_cache.get("resolvedProfiles")
        require(isinstance(profiles, list), "current resolved profiles are missing")
        matched = [row for row in profiles if row.get("resolved") is True
                   and row.get("fingerprint") == actor.get("behaviorFingerprint")]
        require(len(matched) == 1, "Mankey has no unique current resolved profile")
        row = matched[0]
        require(row.get("sourceSha256") == self.source["profileSha256"]
                and type(row.get("appliedOverrides")) is int
                and type(actor.get("matchedLayerMask")) is int,
                "Mankey resolved profile source or masks differ")
        raw = bytes.fromhex(row.get("resultHex", ""))
        require(len(raw) == 216 and raw[12] == 2
                and row["appliedOverrides"] & LONG_HOP_BIT
                and actor["matchedLayerMask"] & LONG_HOP_BIT,
                "Mankey does not retain its resolved Long Hop")
        if not (row["appliedOverrides"] & THROW_BIT
                and actor["matchedLayerMask"] & THROW_BIT):
            require((raw[72], raw[73], raw[74]) == (0, 0, 0),
                    "unmatched Throw condition still grants damage")
            return False
        require((raw[72], raw[73], raw[74]) == (1, 16, 20),
                "active Mankey Owner lacks its 20-HP contact profile")
        return True

    def _health(self, row, expected):
        snapshot = row.get("snapshot")
        require(isinstance(snapshot, dict) and self.latest is not None,
                "Hop HP read has no current boundary")
        self._boundary(snapshot)
        self._actor(snapshot)
        require(all(snapshot.get(key) == self.latest.get(key)
                    for key in ("frame", "nativeCycle", "context", "player", "actors")),
                "Hop HP read is not at the last completed boundary")
        health = row.get("receipt", {}).get("playerHealth")
        require(isinstance(health, dict) and health.get("schemaVersion") == 1
                and health.get("identity", {}).get("descriptorVersion") == 1
                and health["identity"].get("overlayId") == 161
                and health["identity"].get("romSha256") == self.source["romSha256"]
                and health["identity"].get("overlaySha256") == self.source["overlaySha256"]
                and health.get("frame") == snapshot["frame"]
                and health.get("nativeCycle") == snapshot["nativeCycle"]
                and health.get("maxHp") == 100
                and health.get("hp") == health.get("savedHp")
                and health.get("frameActive") is False
                and health.get("recoveryPending") is False,
                "Hop HP read differs from current field and save")
        require((health.get("hp"), health.get("lastDamage"), health.get("acceptedHits"))
                == expected, "Hop contact damage or hit count differs")
        require(type(health.get("lastHealthFrame")) is int,
                "Hop HP clock is missing")
        return deepcopy(health)

    def _sample(self, sample, profile_cache):
        self._boundary(sample)
        actor = self._actor(sample, profile_cache)
        prior = self._actor(self.latest, self.latest_profile_cache)
        require(sample["frame"] == self.latest["frame"] + 1
                and sample["nativeCycle"] > self.latest["nativeCycle"],
                "Hop completed-frame stream skips or reverses")
        self.observed_frames += 1
        self.wait_frames += 1
        require(self.wait_frames <= WAIT_LIMIT,
                "ordinary Hop did not cross player within its frame limit")
        moving = actor.get("motionKind") == "HOP" \
            and actor.get("motionPhase") == "MOVING" \
            and type(actor.get("motionElapsed")) is int \
            and type(actor.get("motionDuration")) is int \
            and 0 < actor["motionElapsed"] < actor["motionDuration"]
        if moving:
            current_flight = (tuple(actor.get("origin", {}).get(k) for k in ("x", "y")),
                              tuple(actor.get("target", {}).get(k) for k in ("x", "y")),
                              actor["motionDuration"])
            if self.flight != current_flight or prior.get("motionKind") != "HOP":
                self.flight = current_flight
                self.flight_frames = 0
                self.flight_attacking = self._attack_profile(sample, actor, profile_cache)
            self.flight_frames += 1
            before = prior.get("engineObject")
            after = actor.get("engineObject")
            player = sample.get("player")
            require(isinstance(before, dict) and isinstance(after, dict)
                    and isinstance(player, dict), "Hop native body pose is missing")
            if self.flight_attacking and _inside_swept_body(before, after, player):
                require(self.crossing_frame is None
                        and self.flight_frames > 0,
                        "Hop crossing is duplicate or lacks a flight")
                self.crossing_frame = sample["frame"]
        self.latest = deepcopy(sample)
        self.latest_profile_cache = deepcopy(profile_cache)

    def stage(self, name):
        if name != "airborne-crossed":
            raise ValueError("unknown Hop proof stage")
        return not self.failures and self.crossing_frame == self.latest.get("frame")

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "Hop proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "Hop initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "Hop initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index]
                        and row.get("command") == ("teleport", "spawn", "bind")[self.setup_index],
                        "Hop setup order differs")
                snapshot = row.get("snapshot")
                self._boundary(snapshot)
                if self.setup_index == 1:
                    value = row.get("receipt", {}).get("value", {})
                    require(value.get("species") == 56
                            and type(value.get("slot")) is int
                            and type(value.get("personality")) is int,
                            "Mankey native spawn identity differs")
                if self.setup_index == 2:
                    self.subject = deepcopy(row.get("receipt"))
                    actor = self._actor(snapshot)
                    self.settled_at_bind = actor.get("motionKind") == "NONE" \
                        and actor.get("motionPhase") == "IDLE"
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP)
                    and row.get("phase") == "observe"
                    and self.action_index < len(ORDER)
                    and (row.get("action") == ORDER[self.action_index]
                         or self.action_index == 0
                         and self.settled_at_bind
                         and row.get("action") == "before-hop"),
                    "Hop observation order differs")
            if self.action_index == 0 and row.get("action") == "before-hop":
                self.action_index = 1
            if self.action_index == 0:
                require("command" not in row, "spawn settle is not a raw frame stream")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    self._boundary(sample)
                    self._actor(sample)
                    self.latest = deepcopy(sample)
                    self.observed_frames += 1
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if self.latest["actors"]:
                    actor = self._actor(self.latest)
                    if actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE":
                        self.action_index += 1
            elif self.action_index == 1:
                require(row.get("command") == "player-health.observe",
                        "Hop baseline is not a checked HP read")
                actor = self._actor(row["snapshot"])
                require(actor.get("motionKind") == "NONE"
                        and actor.get("motionPhase") == "IDLE",
                        "Hop baseline began during an earlier motion")
                self.before_health = self._health(row, (100, 0, 0))
                self.action_index += 1
            elif self.action_index == 2:
                require("command" not in row, "Hop wait is not a raw frame stream")
                require(len(row.get("samples", [])) == 1
                        and isinstance(row.get("profileCache"), dict),
                        "Hop needs one frame and its matching resolved profile cache")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    require(self.crossing_frame is None,
                            "Hop wait ran beyond its first crossing")
                    self._sample(sample, row["profileCache"])
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if self.crossing_frame is not None:
                    self.action_index += 1
            else:
                require(row.get("command") == "player-health.observe"
                        and self.crossing_frame == self.latest["frame"],
                        "Hop HP was not read at the crossing boundary")
                self.after_health = self._health(row, (80, 20, 1))
                require(self.after_health["lastHealthFrame"]
                        - self.before_health["lastHealthFrame"]
                        == self.latest["frame"] - self.before_health["frame"],
                        "Hop HP clock has a missing field frame")
                self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) \
            and self.crossing_frame is not None and self.after_health is not None \
            and self.flight_attacking is True
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "crossingFrame": self.crossing_frame,
                "flightFrames": self.flight_frames,
                "settledAtBind": self.settled_at_bind,
                "ordinaryHop": self.flight_attacking and self.flight is not None,
                "flight": deepcopy(self.flight),
                "hpAfterHop": self.after_health.get("hp") if self.after_health else None,
                "subject": deepcopy(self.subject), "failures": list(self.failures)}

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("ordinary attacking Hop did not cross and damage the player")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
