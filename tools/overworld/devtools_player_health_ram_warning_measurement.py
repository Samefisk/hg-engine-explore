"""Check a native amber bar receipt during one active, undamaged Onix Ram."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_ram_until_crash_measurement import RAM_MASK


KIND = "player-health-ram-warning-v1"
REQUIREMENT = "current.player-health-ram-warning"
ACTIVE_MASK = RAM_MASK  # Compatibility name for copied fixtures; only the Ram bit is required.
SETUP = ("ram-tile", "spawn-onix", "bind-onix")
ORDER = ("wait-ram-application", "wait-active-charge", "read-charge-warning")
LIMITS = {"wait-ram-application": 120, "wait-active-charge": 40}


def require(value, message):
    if not value:
        raise ValueError(message)


class PlayerHealthRamWarningMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.setup_index = 0
        self.action_index = 0
        self.counts = {action: 0 for action in LIMITS}
        self.observed_frames = 0
        self.charge_frame = None
        self.warning = None
        self.failures = []

    def _boundary(self, snapshot, ram_tile=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int
                and (not ram_tile
                    or (snapshot.get("context", {}).get("mapId") == 33
                        and (snapshot.get("player", {}).get("x"),
                             snapshot.get("player", {}).get("y")) == (585, 407)))
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "Ram warning lacks a stationary current Route 29 field frame")

    def _onix(self, snapshot):
        require(self.subject is not None, "Ram warning has no bound Onix")
        selected = select_current_actor(snapshot, self.subject)
        actor = next((actor for actor in snapshot.get("actors", [])
                      if actor.get("handle") == selected["handle"]), None)
        require(isinstance(actor, dict) and actor.get("species") == 95
                and actor.get("role") == "WILD"
                and actor.get("active") is True
                and actor.get("presentationAttached") is True,
                "Ram warning lacks the current visible Wild Onix")
        return actor

    def _same_boundary(self, snapshot):
        for key in ("frame", "nativeCycle", "observationBoundary",
                    "fieldAvailable", "romSha256", "context", "player",
                    "actors", "fieldControl"):
            require(snapshot.get(key) == self.latest.get(key),
                    "Ram warning HP read is not at the charge frame")

    def _health(self, row):
        snapshot = row.get("snapshot")
        self._boundary(snapshot)
        self._same_boundary(snapshot)
        actor = self._onix(snapshot)
        require(snapshot["frame"] == self.charge_frame
                and actor.get("matchedLayerMask", 0) & RAM_MASK
                and actor.get("motionKind") == "WALK"
                and actor.get("motionPhase") == "MOVING"
                and actor.get("movementPolicy", {}).get("direction") != 255,
                "Ram warning HP read lost the active charge")
        receipt = row.get("receipt", {})
        hp = receipt.get("playerHealth") if isinstance(receipt, dict) else None
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1
                and hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("identity", {}).get("descriptorVersion") == 1
                and hp["identity"].get("overlayId") == 161
                and hp["identity"].get("overlaySha256") == self.source["overlaySha256"]
                and hp["identity"].get("romSha256") == self.source["romSha256"]
                and hp.get("hp") == 100 and hp.get("savedHp") == 100
                and hp.get("acceptedHits") == 0
                and hp.get("lastDamage") == 0
                and hp.get("recoveryPending") is False,
                "Ram warning HP receipt is stale or already hit")
        draw = hp.get("barDraw", {})
        resource = hp.get("barResources", {})
        require(draw.get("available") is True
                and draw.get("receiptVersion") == 2
                and draw.get("claim") == "native-oam-submission"
                and draw.get("hardwareApplied") is None
                and draw.get("danger") is True
                and draw.get("requestedFill") == 44
                and draw.get("drawnFill") == 44
                and draw.get("submittedSprites") == 1
                and draw.get("completeSubmission") is True
                and resource.get("available") is True
                and resource.get("bound") is True
                and resource.get("fieldMatches") is True
                and resource.get("fieldOwner") == hp.get("fieldSystem")
                and resource.get("textureKey") == 201,
                "active Ram charge did not submit the amber full-HP bar")
        self.warning = deepcopy(hp)

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "Ram warning row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "Ram warning initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], ram_tile=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "Ram warning initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "Ram warning setup order differs")
                action = SETUP[self.setup_index]
                expected = {"ram-tile": "teleport", "spawn-onix": "spawn",
                            "bind-onix": "bind"}[action]
                require(row.get("command") == expected,
                        "Ram warning setup command differs")
                snapshot = row.get("snapshot")
                self._boundary(snapshot)
                require(snapshot["frame"] >= self.latest["frame"],
                        "Ram warning setup frame reversed")
                if action == "ram-tile":
                    require(row.get("receipt", {}).get("preparedOnly") is True
                            and row["receipt"].get("snapshot") == snapshot,
                            "Ram tile was not a checked prepared teleport")
                elif action == "spawn-onix":
                    spawn = row.get("receipt", {}).get("value", {})
                    require(spawn.get("species") == 95
                            and type(spawn.get("slot")) is int,
                            "Ram warning native Onix spawn differs")
                else:
                    self.subject = deepcopy(row.get("receipt"))
                    actor = self._onix(snapshot)
                    require((actor.get("logical", {}).get("x"),
                             actor.get("logical", {}).get("y")) == (585, 412),
                            "Ram warning Onix did not start five tiles south")
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(row.get("phase") == "observe"
                    and self.setup_index == len(SETUP)
                    and self.action_index < len(ORDER)
                    and row.get("action") == ORDER[self.action_index],
                    "Ram warning observation action order differs")
            action = ORDER[self.action_index]
            if action in LIMITS:
                require("command" not in row, "Ram wait is not a completed-frame stream")
                samples = list(validate_raw_chunk(row, self.latest))
                require(samples and self.counts[action] + len(samples) <= LIMITS[action],
                        "Ram warning wait exceeded its frame limit")
                for sample, _, _ in samples:
                    self._boundary(sample)
                    actor = self._onix(sample)
                    if action == "wait-active-charge":
                        require(actor.get("matchedLayerMask", 0) & RAM_MASK,
                                "Ram application ended before the charge")
                    self.latest = deepcopy(sample)
                    self.counts[action] += 1
                    self.observed_frames += 1
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                actor = self._onix(self.latest)
                if action == "wait-ram-application":
                    if not actor.get("matchedLayerMask", 0) & RAM_MASK:
                        require(self.counts[action] < LIMITS[action],
                                "Onix did not enter the Ram application")
                        return self.result()
                else:
                    if (actor.get("motionKind") != "WALK"
                            or actor.get("motionPhase") != "MOVING"
                            or actor.get("movementPolicy", {}).get("direction") == 255):
                        require(self.counts[action] < LIMITS[action],
                                "Onix did not start an active Ram Walk")
                        return self.result()
                    self.charge_frame = self.latest["frame"]
                self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe",
                    "Ram warning needs a checked HP read")
            self._health(row)
            self.latest = deepcopy(row["snapshot"])
            self.action_index += 1
        except (KeyError, StopIteration, TypeError, ValueError) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        return {"ready": not self.failures and self.setup_index == len(SETUP)
                and self.action_index == len(ORDER)
                and self.charge_frame is not None and self.warning is not None
                and self.observed_frames >= 2,
                "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "chargeFrame": self.charge_frame,
                "warningSubmitted": self.warning is not None,
                "onix": deepcopy(self.subject)}

    def stage(self, name):
        return not self.failures and ((name == "ram-active" and self.action_index >= 1)
            or (name == "charge-started" and self.charge_frame is not None))

    def finish(self):
        report = self.result()
        if not report["ready"] and not self.failures:
            self.failures.append("Ram warning ended before its active charge receipt")
        return {"passed": report["ready"] and not self.failures,
                "failures": list(self.failures)}
