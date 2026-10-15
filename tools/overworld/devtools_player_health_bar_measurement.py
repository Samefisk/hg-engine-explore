"""Check full and injured native HP-bar submission around one real Ram."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor


KIND = "player-health-bar-v1"
REQUIREMENT = "current.player-health-bar"
SETUP = ("ram-tile", "spawn-onix", "bind-onix")
ORDER = ("before-ram", "allow-natural-ram", "after-ram")
STEPS = {"allow-natural-ram": 105}
OBSERVED_FRAMES = STEPS["allow-natural-ram"]


def require(value, message):
    if not value:
        raise ValueError(message)


class PlayerHealthBarMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.setup_index = 0
        self.action_index = 0
        self.steps = {action: 0 for action in STEPS}
        self.observed_frames = 0
        self.receipts = {}
        self.failures = []

    def _boundary(self, snapshot, map_id=None):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int
                and isinstance(snapshot.get("player"), dict)
                and isinstance(snapshot.get("fieldControl"), dict)
                and isinstance(snapshot.get("context"), dict)
                and (map_id is None or snapshot["context"].get("mapId") == map_id),
                "bar proof lacks its current completed field boundary")

    def _same_boundary(self, snapshot):
        for key in ("frame", "nativeCycle", "observationBoundary", "fieldAvailable",
                    "romSha256", "context", "player", "actors", "fieldControl"):
            require(snapshot.get(key) == self.latest.get(key),
                    "bar receipt is not at the last completed game boundary")

    def _onix(self, snapshot):
        require(self.subject is not None, "bar proof has no bound Onix")
        selected = select_current_actor(snapshot, self.subject)
        actor = next((actor for actor in snapshot.get("actors", [])
                      if actor.get("handle") == selected["handle"]), None)
        require(isinstance(actor, dict) and actor.get("species") == 95
                and actor.get("role") == "WILD" and actor.get("active") is True
                and actor.get("presentationAttached") is True,
                "bar damage did not come from the current visible Wild Onix")
        return actor

    def _health(self, row, action):
        snapshot = row.get("snapshot")
        self._boundary(snapshot, 33)
        self._same_boundary(snapshot)
        result = row.get("receipt")
        hp = result.get("playerHealth") if isinstance(result, dict) else None
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1,
                "bar proof lacks a checked player HP receipt")
        identity = hp.get("identity", {})
        require(identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and identity.get("romSha256") == self.source["romSha256"]
                and hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("maxHp") == 100
                and hp.get("savedHp") == hp.get("hp")
                and hp.get("recoveryPending") is False,
                "bar proof HP/save or ROM identity differs")
        draw, resource = hp.get("barDraw"), hp.get("barResources")
        require(isinstance(draw, dict) and isinstance(resource, dict)
                and draw.get("available") is True
                and draw.get("receiptVersion") == 2
                and draw.get("fillWidth") == 44
                and draw.get("claim") == "native-oam-submission"
                and draw.get("hardwareApplied") is None
                and resource.get("available") is True,
                "bar proof lacks its authenticated native submission receipt")
        expected_hp = 100 if action == "before-ram" else 67
        require(hp.get("hp") == expected_hp,
                "bar proof HP differs from the full or Ram-damaged state")
        if action == "after-ram":
            self._onix(snapshot)
            require(hp.get("lastDamage") == 33 and hp.get("acceptedHits") == 1,
                    "bar damage is not one real Onix Ram")
        if action == "before-ram":
            self._onix(snapshot)
            require(hp.get("lastDamage") == 0 and hp.get("acceptedHits") == 0
                    and draw.get("danger") is False,
                    "full bar did not start before Ram damage")
        if action in ("before-ram", "after-ram"):
            fill = 44 if action == "before-ram" else 30
            require(draw.get("requestedFill") == fill
                    and draw.get("drawnFill") == fill
                    and draw.get("submittedSprites") == 1
                    and draw.get("completeSubmission") is True
                    and resource.get("bound") is True
                    and resource.get("fieldMatches") is True
                    and resource.get("fieldOwner") == hp.get("fieldSystem")
                    and resource.get("paletteSourceDmaReadable") is True
                    and resource.get("paletteSourceHasColors") is True
                    and resource.get("paletteVramMatchesSource") is True
                    and resource.get("textureKey")
                        == expected_hp * 2 + int(draw.get("danger") is True),
                    "bar fill or native palette data differs")
        require(snapshot["fieldControl"].get("taskPointer", 0) == 0,
                "visible bar was observed while a field task was active")
        self.receipts[action] = deepcopy(hp)

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "bar proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "bar initial boundary is duplicate or misplaced")
                self._boundary(row["initialSnapshot"])
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "bar initial boundary is missing")
            phase = row.get("phase")
            if phase == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "bar setup action order differs")
                action = SETUP[self.setup_index]
            else:
                require(phase == "observe" and self.setup_index == len(SETUP)
                        and self.action_index < len(ORDER)
                        and row.get("action") == ORDER[self.action_index],
                        "bar observation action order differs")
                action = ORDER[self.action_index]
            if action in STEPS:
                require("command" not in row, "bar step is not a native frame stream")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    self._boundary(sample)
                    require(self.steps[action] < STEPS[action],
                            "bar step exceeded its declared frame budget")
                    if action == "allow-natural-ram":
                        self._boundary(sample, 33)
                        self._onix(sample)
                        require((sample["player"]["x"], sample["player"]["y"])
                                == (585, 407), "player left the Ram fixture")
                    self.latest = deepcopy(sample)
                    self.steps[action] += 1
                    if phase == "observe":
                        self.observed_frames += 1
                        if on_sample is not None:
                            on_sample(sample, self.observed_frames)
                if self.steps[action] == STEPS[action]:
                    if phase == "setup": self.setup_index += 1
                    else: self.action_index += 1
                return self.result()
            snapshot = row.get("snapshot")
            self._boundary(snapshot)
            require(snapshot["frame"] >= self.latest["frame"],
                    "bar command boundary reversed")
            command = row.get("command")
            if action == "ram-tile":
                require(command == "teleport"
                        and row.get("receipt", {}).get("preparedOnly") is True
                        and row["receipt"].get("snapshot") == snapshot,
                        "bar tile was not a checked prepared teleport")
                self._boundary(snapshot, 33)
                require((snapshot["player"]["x"], snapshot["player"]["y"]) == (585, 407),
                        "bar fixture tile differs")
            elif action == "spawn-onix":
                require(command == "spawn", "bar Onix setup did not use native spawn")
                self._boundary(snapshot, 33)
            elif action == "bind-onix":
                require(command == "bind", "bar Onix bind is missing")
                self.subject = deepcopy(row.get("receipt"))
                actor = self._onix(snapshot)
                require((actor.get("logical", {}).get("x"),
                         actor.get("logical", {}).get("y")) == (585, 412),
                        "bar Onix did not start five tiles south")
            else:
                require(command == "player-health.observe",
                        "bar checkpoint is not a checked HP read")
                self._health(row, action)
            self.latest = deepcopy(snapshot)
            if phase == "setup": self.setup_index += 1
            else: self.action_index += 1
        except (KeyError, StopIteration, TypeError, ValueError) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        return {"ready": not self.failures and self.setup_index == len(SETUP)
                and self.action_index == len(ORDER)
                and self.observed_frames == OBSERVED_FRAMES
                and all(self.steps[action] == frames for action, frames in STEPS.items())
                and set(self.receipts) == {"before-ram", "after-ram"},
                "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "hpAfterRam": self.receipts.get("after-ram", {}).get("hp"),
                "fullFill": self.receipts.get("before-ram", {}).get("barDraw", {}).get("drawnFill"),
                "injuredFill": self.receipts.get("after-ram", {}).get("barDraw", {}).get("drawnFill"),
                "onix": deepcopy(self.subject)}

    def finish(self):
        report = self.result()
        if not report["ready"] and not self.failures:
            self.failures.append("bar proof ended before all native checkpoints")
        return {"passed": report["ready"] and not self.failures,
                "failures": list(self.failures)}
