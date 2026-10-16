"""Check one live Onix Ram, then stationary and moving healing."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_ram_until_crash_measurement import RAM_MASK


KIND = "player-health-ram-rest-v1"
REQUIREMENT = "current.player-health-ram-rest"
STEPS = {"allow-natural-ram": 170, "settle-safe-field": 2,
         "stand-five-seconds": 300,
         "stand-one-more-second": 60, "move-again": 16}
ORDER = ("before-ram", "allow-natural-ram", "after-ram",
         "safe-rest-tile", "settle-safe-field", "before-rest",
         "stand-five-seconds",
         "after-five-seconds", "stand-one-more-second", "after-heal",
         "move-again", "after-move")


def require(value, message):
    if not value:
        raise ValueError(message)


class PlayerHealthRamRestMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.receipts = {}
        self.steps = {key: 0 for key in STEPS}
        self.observed_frames = 0
        self.action_index = 0
        self.safe_tile = None
        self.moved = False
        self.failures = []
        self.after_teleport = False
        self._setup_index = 0
        self.completed_charge_times = []
        self.completed_charge_thresholds = []
        self.completed_charge_targets = set()
        self.knockbackSeen = False
        self.jumpArcSeen = False
        self.stationaryCommandSeen = False
        self.baseFaceY = None

    def _boundary(self, snapshot, map_id=None):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and isinstance(snapshot.get("frame"), int)
                and isinstance(snapshot.get("nativeCycle"), int),
                "HP proof needs a completed field boundary")
        require(isinstance(snapshot.get("context"), dict)
                and (map_id is None or snapshot["context"].get("mapId") == map_id),
                "HP proof map differs")
        require(isinstance(snapshot.get("player"), dict)
                and snapshot.get("fieldControl", {}).get("taskPointer", 0) == 0,
                "HP proof left normal field control")

    def _current_onix(self, snapshot):
        require(self.subject is not None, "Onix was not bound")
        selected = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot["actors"]
                     if item.get("handle") == selected["handle"])
        require(actor.get("species") == 95 and actor.get("role") == "WILD"
                and actor.get("active") is True
                and actor.get("presentationAttached") is True,
                "Ram source is not the current visible Wild Onix")
        return actor

    def _same_completed_boundary(self, snapshot):
        # A read-only command can add terrain or advance an event cursor at the
        # same paused boundary. Compare the game state and clock, not those
        # diagnostic envelopes.
        keys = ("frame", "nativeCycle", "observationBoundary",
                "fieldAvailable", "romSha256", "context", "fieldControl",
                "player", "actors")
        require(all(snapshot.get(key) == self.latest.get(key) for key in keys),
                "HP receipt is not at the current completed boundary")

    def _health(self, row, action):
        result = row.get("receipt")
        hp = result.get("playerHealth") if isinstance(result, dict) else None
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1,
                "checked player HP receipt is missing")
        identity = hp.get("identity", {})
        require(identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and identity.get("romSha256") == self.source["romSha256"],
                "player HP ROM or overlay identity differs")
        snapshot = row["snapshot"]
        require(hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("maxHp") == 100
                and hp.get("hp") == hp.get("savedHp")
                and hp.get("recoveryPending") is False
                and hp.get("frameActive") is False,
                "player HP read differs from its current field/save boundary")
        require(type(hp.get("healRemainder")) is int
                and 0 <= hp["healRemainder"] < 60,
                "player HP healing remainder is invalid")
        if action in ("before-ram", "after-ram"):
            self._boundary(snapshot, 33)
            self._current_onix(snapshot)
            expected_tile = (585, 404) if action == "after-ram" else (585, 407)
            require((snapshot["player"]["x"], snapshot["player"]["y"])
                    == expected_tile,
                    "Ram did not jump the player three tiles away")
            if action == "before-ram":
                self.baseFaceY = snapshot["player"].get("face_y")
                require(type(self.baseFaceY) is int,
                        "Ram player face height is missing")
        else:
            self._boundary(snapshot, 34)
        expected = {
            "before-ram": (100, 0, 0, 0),
            "after-ram": (67, 33, 1, None),
            "before-rest": (67, 33, 1, None),
            "after-five-seconds": (67, 33, 1, 300),
            "after-heal": (77, 33, 1, 300),
            "after-move": None,
        }[action]
        if action == "after-move":
            previous = self.receipts["after-heal"]
            expected = (previous["hp"] + (previous["healRemainder"]
                        + STEPS["move-again"] * 10) // 60, 33, 1, 300)
        require((hp.get("hp"), hp.get("lastDamage"), hp.get("acceptedHits"))
                == expected[:3]
                and (expected[3] is None or hp.get("restFrames") == expected[3]),
                "Ram damage or stillness healing differs")
        if action == "before-rest":
            require(type(hp.get("restFrames")) is int
                    and 0 <= hp["restFrames"] <= 5
                    and hp["healRemainder"] == 0,
                    "prepared arrival consumed too much of the rest clock")
        if action == "after-ram":
            require(hp.get("protectionFrames", 0) <= 60,
                    "Ram protection window is invalid")
            require(any(256 // row["travelTime"] >= row["minimumImpactSpeed"]
                        for row in self.completed_charge_thresholds),
                    "Ram hit before a completed fast Walk tile")
        if action in ("after-five-seconds", "after-heal"):
            previous = self.receipts["before-rest" if action == "after-five-seconds"
                                     else "after-five-seconds"]
            expected_frames = 300 if action == "after-five-seconds" else 60
            require(hp.get("lastHealthFrame") - previous.get("lastHealthFrame")
                    == expected_frames,
                    "rest clock skipped a completed game frame")
            require((snapshot["player"]["x"], snapshot["player"]["y"])
                    == self.safe_tile, "rest player left the safe tile")
            require(hp["healRemainder"]
                    == self.receipts["before-rest"]["restFrames"] * 10,
                    "rest healing does not match the measured arrival clock")
        if action == "after-move":
            require(self.moved and hp["restFrames"] == 300
                    and hp["healRemainder"] == (self.receipts["after-heal"]["healRemainder"] + STEPS["move-again"] * 10) % 60
                    and hp["lastHealthFrame"] - self.receipts["after-heal"]["lastHealthFrame"] == STEPS["move-again"],
                    "moving healing lost its measured travel, eligible clock or remainder")
        self.receipts[action] = deepcopy(hp)

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "HP proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "HP proof initial boundary is misplaced")
                self._boundary(row["initialSnapshot"])
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "HP proof initial boundary is missing")
            if row.get("phase") == "setup":
                setup = ("ram-tile", "spawn-onix", "bind-onix")
                require(self._setup_index < len(setup)
                        and row.get("action") == setup[self._setup_index],
                        "HP proof setup order differs")
                command = row.get("command")
                require(command == ("teleport", "spawn", "bind")[self._setup_index],
                        "HP proof setup command differs")
                snapshot = row["snapshot"]
                self._boundary(snapshot, 33)
                require(snapshot["frame"] >= self.latest["frame"],
                        "HP proof setup clock reversed")
                if command == "teleport":
                    require((snapshot["player"]["x"], snapshot["player"]["y"])
                            == (585, 407), "Ram setup tile differs")
                if command == "bind":
                    self.subject = deepcopy(row["receipt"])
                    self._current_onix(snapshot)
                self.latest = deepcopy(snapshot)
                self._setup_index += 1
                return self.result()
            require(self._setup_index == 3 and row.get("phase") == "observe",
                    "HP proof observation started before exact setup")
            require(self.action_index < len(ORDER), "HP proof has extra action rows")
            action = ORDER[self.action_index]
            require(row.get("action") == action, "HP proof action order differs")
            if action in STEPS:
                require("command" not in row, "HP step is not a native frame stream")
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    self._boundary(sample, 34 if self.after_teleport else 33)
                    require(self.steps[action] < STEPS[action],
                            "HP step has more frames than its declared action")
                    if not self.after_teleport:
                        actor = self._current_onix(sample)
                        for event in events:
                            self._charge_commit(event, actor)
                        require(not any(
                            follower.get("role") == "FOLLOWER"
                            and follower.get("logical", {}).get("x") == 585
                            and 406 <= follower.get("logical", {}).get("y", -1) <= 411
                            for follower in sample.get("actors", [])),
                            "follower blocks the Ram lane or knockback tile")
                        player_tile = (sample["player"]["x"], sample["player"]["y"])
                        require(player_tile in ((585, 407), (585, 406),
                                                (585, 405), (585, 404)),
                                "Ram moved the player outside the jump path")
                        self.knockbackSeen |= player_tile == (585, 404)
                        command = sample["player"].get("movement_cmd")
                        face_y = sample["player"].get("face_y")
                        base_y = self.baseFaceY
                        if player_tile[1] in (406, 405):
                            require(command == 62,
                                    "Ram knockback played a walking command")
                            self.stationaryCommandSeen = True
                        if type(face_y) is int and type(base_y) is int \
                                and face_y > base_y:
                            self.jumpArcSeen = True
                        origin = actor.get("origin", {})
                        target = actor.get("target", {})
                        duration = actor.get("motionDuration")
                        elapsed = actor.get("motionElapsed")
                        if isinstance(duration, int) and 0 < duration <= 12:
                            require(origin.get("x") == 585
                                    and target.get("x") == 585
                                    and target.get("y") == origin.get("y", 0) - 1,
                                    "Ram Walk turned before collision")
                            tile = (target.get("x"), target.get("y"))
                            if elapsed == duration and tile not in self.completed_charge_targets:
                                self.completed_charge_targets.add(tile)
                                self.completed_charge_times.append(duration)
                    elif action != "move-again":
                        require((sample["player"]["x"], sample["player"]["y"])
                                == self.safe_tile, "rest measurement is not standing still")
                    else:
                        self.moved |= (sample["player"]["x"], sample["player"]["y"]) != self.safe_tile
                    self.latest = deepcopy(sample)
                    self.steps[action] += 1
                    self.observed_frames += 1
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if self.steps[action] == STEPS[action]:
                    self.action_index += 1
                return self.result()
            command = row.get("command")
            require(command == ("teleport" if action == "safe-rest-tile"
                                else "player-health.observe"),
                    "HP proof observation command differs")
            snapshot = row.get("snapshot")
            require(isinstance(snapshot, dict) and snapshot["frame"] >= self.latest["frame"],
                    "HP proof command boundary reversed")
            if action == "safe-rest-tile":
                receipt = row.get("receipt", {})
                require(receipt.get("preparedOnly") is True
                        and receipt.get("snapshot") == snapshot,
                        "safe rest tile is not the checked prepared Teleport")
                self._boundary(snapshot, 34)
                self.safe_tile = (550, 381)
                require((snapshot["player"]["x"], snapshot["player"]["y"])
                        == self.safe_tile, "safe rest tile differs")
                self.after_teleport = True
            else:
                self._same_completed_boundary(snapshot)
                self._health(row, action)
            self.latest = deepcopy(snapshot)
            self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        return {"ready": not self.failures and self.knockbackSeen
                and self.jumpArcSeen and self.stationaryCommandSeen
                and self.action_index == len(ORDER)
                and self.observed_frames == sum(STEPS.values()),
                "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "hpAfterRam": self.receipts.get("after-ram", {}).get("hp"),
                "knockbackSeen": self.knockbackSeen,
                "jumpArcSeen": self.jumpArcSeen,
                "stationaryCommandSeen": self.stationaryCommandSeen,
                "hpAfterRest": self.receipts.get("after-heal", {}).get("hp"),
                "movementHealing": bool(self.receipts.get("after-move")) and self.moved,
                "completedChargeTimes": list(self.completed_charge_times),
                "completedChargeThresholds": deepcopy(self.completed_charge_thresholds),
                "onix": deepcopy(self.subject)}

    def _charge_commit(self, event, actor):
        data = event.get("data", {})
        if event.get("kind") != "native-observation" \
                or data.get("observation") != "walk-policy" \
                or data.get("operation") != 3 or data.get("slot") != actor["handle"]["slot"]:
            return
        subject = data.get("publicSubject", {})
        require(all(subject.get(k) == actor.get(k) for k in (
            "handle", "subjectIdentity", "species", "role",
            "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")),
            "Ram completed tile has a stale policy owner")
        if not subject.get("matchedLayerMask", 0) & RAM_MASK:
            return
        request = bytes.fromhex(data["requestHex"])
        lane = bytes.fromhex(data["laneHex"])
        before = bytes.fromhex(data["policyBeforeHex"])
        require(len(request) == 28 and request[:4] == b"\x01\x00\x1c\x00"
                and request[8:10] == bytes((actor["handle"]["slot"], 3))
                and request[11] == 1 and data.get("returnValue") == 1
                and len(lane) == 80 and lane[72] == 1 and lane[73] > 0
                and len(before) == 36,
                "Ram completed tile has no resolved impact threshold")
        time = before[25] or before[2]
        require(1 <= time <= 32 and subject.get("motionKind") == "WALK"
                and subject.get("motionElapsed") == subject.get("motionDuration") == time,
                "Ram speed receipt is not a completed Walk tile")
        self.completed_charge_thresholds.append({"frame": event["frame"],
            "travelTime": time, "minimumImpactSpeed": lane[73]})

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Ram/rest proof ended before its declared actions")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
