"""Check that adjacent Onix Ram leaves a stationary player unhurt."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_ram_until_crash_measurement import RAM_MASK


KIND = "player-health-ram-low-speed-v1"
REQUIREMENT = "current.player-health-ram-low-speed"
SETUP = ("ram-tile", "spawn-onix", "bind-onix")
ORDER = ("before-ram", "wait-ram-application", "allow-adjacent-ram", "after-ram")
ACTIVE_MASK = RAM_MASK
LIMITS = {"wait-ram-application": 120, "allow-adjacent-ram": 80}


def require(value, message):
    if not value:
        raise ValueError(message)


class PlayerHealthRamLowSpeedMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.setup_index = 0
        self.action_index = 0
        self.counts = {action: 0 for action in LIMITS}
        self.observed_frames = 0
        self.active_frames = 0
        self.receipts = {}
        self.failures = []

    def _boundary(self, snapshot, fixture=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "low-speed Ram needs a completed, battle-free field frame")
        if fixture:
            require(snapshot.get("context", {}).get("mapId") == 33
                    and (snapshot.get("player", {}).get("x"),
                         snapshot.get("player", {}).get("y")) == (585, 407),
                    "low-speed Ram player left the Route 29 fixture")

    def _onix(self, snapshot):
        require(self.subject is not None, "low-speed Ram has no bound Onix")
        selected = select_current_actor(snapshot, self.subject)
        actor = next((item for item in snapshot.get("actors", [])
                      if item.get("handle") == selected["handle"]), None)
        require(isinstance(actor, dict) and actor.get("species") == 95
                and actor.get("role") == "WILD"
                and actor.get("active") is True
                and actor.get("presentationAttached") is True
                and (actor.get("logical", {}).get("x"),
                     actor.get("logical", {}).get("y")) == (585, 408),
                "low-speed Ram lost the current adjacent Wild Onix")
        return actor

    def _same_boundary(self, snapshot):
        for key in ("frame", "nativeCycle", "observationBoundary",
                    "fieldAvailable", "romSha256", "context", "player",
                    "actors", "fieldControl"):
            require(snapshot.get(key) == self.latest.get(key),
                    "low-speed Ram HP read is not at the current field frame")

    def _health(self, row, action):
        snapshot = row.get("snapshot")
        self._boundary(snapshot)
        self._same_boundary(snapshot)
        self._onix(snapshot)
        receipt = row.get("receipt", {})
        hp = receipt.get("playerHealth") if isinstance(receipt, dict) else None
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1
                and hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("identity", {}).get("descriptorVersion") == 1
                and hp["identity"].get("overlayId") == 161
                and hp["identity"].get("overlaySha256") == self.source["overlaySha256"]
                and hp["identity"].get("romSha256") == self.source["romSha256"]
                and hp.get("maxHp") == 100
                and hp.get("hp") == 100 and hp.get("savedHp") == 100
                and hp.get("acceptedHits") == 0 and hp.get("lastDamage") == 0
                and hp.get("protectionFrames") == 0
                and hp.get("recoveryPending") is False
                and hp.get("frameActive") is False,
                "low-speed Ram HP, save, or protection receipt differs")
        if action == "after-ram":
            before = self.receipts["before-ram"]
            require(hp.get("lastHealthFrame") - before.get("lastHealthFrame")
                    == self.observed_frames,
                    "low-speed Ram HP clock skipped completed game frames")
        self.receipts[action] = deepcopy(hp)

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "low-speed Ram row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "low-speed Ram initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "low-speed Ram initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "low-speed Ram setup order differs")
                action = SETUP[self.setup_index]
                require(row.get("command") == {"ram-tile": "teleport",
                       "spawn-onix": "spawn", "bind-onix": "bind"}[action],
                        "low-speed Ram setup command differs")
                snapshot = row.get("snapshot")
                self._boundary(snapshot)
                require(snapshot["frame"] >= self.latest["frame"],
                        "low-speed Ram setup clock reversed")
                if action == "ram-tile":
                    require(row.get("receipt", {}).get("preparedOnly") is True
                            and row["receipt"].get("snapshot") == snapshot,
                            "Ram tile was not a checked prepared teleport")
                elif action == "spawn-onix":
                    spawn = row.get("receipt", {}).get("value", {})
                    require(spawn.get("species") == 95
                            and type(spawn.get("slot")) is int,
                            "low-speed Ram native Onix spawn differs")
                else:
                    self.subject = deepcopy(row.get("receipt"))
                    self._onix(snapshot)
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(row.get("phase") == "observe"
                    and self.setup_index == len(SETUP)
                    and self.action_index < len(ORDER)
                    and row.get("action") == ORDER[self.action_index],
                    "low-speed Ram observation order differs")
            action = ORDER[self.action_index]
            if action in LIMITS:
                require("command" not in row,
                        "low-speed Ram step is not a native frame stream")
                samples = list(validate_raw_chunk(row, self.latest))
                require(samples and self.counts[action] + len(samples) <= LIMITS[action],
                        "low-speed Ram step exceeded its frame limit")
                for sample, _, _ in samples:
                    self._boundary(sample)
                    actor = self._onix(sample)
                    if action == "allow-adjacent-ram":
                        self.active_frames += bool(actor.get("matchedLayerMask", 0) & RAM_MASK)
                    self.latest = deepcopy(sample)
                    self.counts[action] += 1
                    self.observed_frames += 1
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if action == "wait-ram-application":
                    if not self._onix(self.latest).get("matchedLayerMask", 0) & RAM_MASK:
                        require(self.counts[action] < LIMITS[action],
                                "adjacent Onix did not gain its Ram application")
                        return self.result()
                else:
                    if self.counts[action] < LIMITS[action]:
                        return self.result()
                    require(self.active_frames >= 34,
                            "Ram application was too short for the measured contact boundary")
                self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe",
                    "low-speed Ram needs a checked HP read")
            self._health(row, action)
            self.latest = deepcopy(row["snapshot"])
            self.action_index += 1
        except (KeyError, StopIteration, TypeError, ValueError) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        return {"ready": not self.failures
                and self.setup_index == len(SETUP)
                and self.action_index == len(ORDER)
                and self.counts["wait-ram-application"] >= 1
                and self.counts["allow-adjacent-ram"] == 80
                and self.active_frames >= 34,
                "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "neutralFrames": self.counts["allow-adjacent-ram"],
                "activeFrames": self.active_frames,
                "hpAfterWindow": self.receipts.get("after-ram", {}).get("hp"),
                "acceptedHitsAfterWindow": self.receipts.get("after-ram", {}).get("acceptedHits"),
                "onix": deepcopy(self.subject),
                "failures": list(self.failures)}

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("low-speed Ram proof ended before its declared actions")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}

    def stage(self, name):
        return name == "ram-active" and self.action_index >= 2 and not self.failures
