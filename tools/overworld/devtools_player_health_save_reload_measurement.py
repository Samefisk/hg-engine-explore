"""Check one natural Ram, stock Save write, and private cartridge reload."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor


KIND = "player-health-save-reload-v1"
REQUIREMENT = "current.player-health-save-reload"
SETUP = ("ram-tile", "spawn-onix", "bind-onix")
ORDER = ("allow-natural-ram", "before-save", "open-menu", "release-x",
         "select-save-down", "release-down", "select-save-right", "release-right",
         "open-save", "wait-save-menu", "confirm-first", "release-first",
         "wait-overwrite", "confirm-overwrite", "release-overwrite", "wait-flash",
         "wait-saved-text", "close-save", "settle-field", "before-reload",
         "reload", "after-reload")
STEPS = {"allow-natural-ram": (105, []), "open-menu": (1, ["X"]),
         "release-x": (15, []), "select-save-down": (1, ["DOWN"]),
         "release-down": (5, []), "select-save-right": (1, ["RIGHT"]),
         "release-right": (5, []), "open-save": (1, ["A"]),
         "wait-save-menu": (100, []), "confirm-first": (1, ["A"]),
         "release-first": (12, []), "wait-overwrite": (220, []),
         "confirm-overwrite": (1, ["A"]), "release-overwrite": (12, []),
         "wait-saved-text": (180, []), "close-save": (1, ["B"]),
         "settle-field": (20, [])}
OBSERVED_FRAMES = sum(frames for frames, _ in STEPS.values())
READS = ("before-save", "before-reload", "after-reload")


def require(condition, message):
    if not condition:
        raise ValueError(message)


class PlayerHealthSaveReloadMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subject = None
        self.setup_index = 0
        self.action_index = 0
        self.steps = {name: 0 for name in STEPS}
        self.observed_frames = 0
        self.receipts = {}
        self.write = None
        self.reload = None
        self.failures = []

    def _boundary(self, snapshot, map_id=33):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int
                and isinstance(snapshot.get("context"), dict)
                and isinstance(snapshot.get("player"), dict)
                and (map_id is None or (
                    snapshot["context"].get("mapId") == map_id
                    and (snapshot["player"].get("x"), snapshot["player"].get("y"))
                        == (585, 407))),
                "save proof lacks the current Route 29 field boundary")

    def _onix(self, snapshot):
        require(self.subject is not None, "save proof has no bound Onix")
        selected = select_current_actor(snapshot, self.subject)
        actor = next((actor for actor in snapshot.get("actors", [])
                      if actor.get("handle") == selected["handle"]), None)
        require(isinstance(actor, dict) and actor.get("species") == 95
                and actor.get("role") == "WILD" and actor.get("active") is True
                and actor.get("presentationAttached") is True,
                "save proof lacks the current visible Wild Onix")
        return actor

    def _health(self, row, action):
        snap = row.get("snapshot")
        self._boundary(snap)
        require(all(snap.get(key) == self.latest.get(key) for key in (
                    "frame", "nativeCycle", "observationBoundary", "fieldAvailable",
                    "romSha256", "sourceSaveSha256", "context", "player", "actors",
                    "fieldControl")),
                "save HP read differs from the last completed game boundary")
        receipt = row.get("receipt", {}).get("playerHealth")
        require(isinstance(receipt, dict) and receipt.get("schemaVersion") == 1,
                "save proof lacks a checked player HP receipt")
        identity = receipt.get("identity", {})
        require(identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and identity.get("romSha256") == self.source["romSha256"]
                and receipt.get("frame") == snap["frame"]
                and receipt.get("nativeCycle") == snap["nativeCycle"]
                and receipt.get("hp") == receipt.get("savedHp") == 67
                and receipt.get("maxHp") == 100
                and receipt.get("recoveryPending") is False,
                "save proof HP, save owner, or ROM identity differs")
        if action == "before-save":
            self._onix(snap)
            require(receipt.get("lastDamage") == 33
                    and receipt.get("acceptedHits") == 1,
                    "save proof damage is not one real Onix Ram")
        draw, resource = receipt.get("barDraw"), receipt.get("barResources")
        require(isinstance(draw, dict) and isinstance(resource, dict)
                and draw.get("available") is True
                and draw.get("receiptVersion") == 2
                and draw.get("fillWidth") == 44
                and draw.get("requestedFill") == 30
                and draw.get("drawnFill") == 30
                and draw.get("submittedSprites") == 1
                and draw.get("completeSubmission") is True
                and draw.get("claim") == "native-oam-submission"
                and draw.get("hardwareApplied") is None
                and resource.get("available") is True
                and resource.get("bound") is True
                and resource.get("fieldMatches") is True
                and resource.get("fieldOwner") == receipt.get("fieldSystem")
                and resource.get("textureKey") == 134 + int(draw.get("danger") is True),
                "save proof lacks the injured native bar submission")
        if action == "after-reload":
            require(self.reload is not None
                    and snap.get("sourceSaveSha256") == self.reload["export"]["sha256"],
                    "reloaded HP is not from the exported cartridge bytes")
        self.receipts[action] = deepcopy(receipt)

    def _wait(self, row):
        receipt, snap = row.get("receipt"), row.get("snapshot")
        self._boundary(snap)
        require(isinstance(receipt, dict)
                and receipt.get("schemaVersion") == 1
                and receipt.get("observedWriteState12") is True
                and receipt.get("startSaveState") in (2, 10, 11, 12)
                and type(receipt.get("endSaveState")) is int
                and 13 <= receipt["endSaveState"] <= 15
                and type(receipt.get("nativeCycles")) is int
                and 1 <= receipt["nativeCycles"] <= 2000
                and receipt.get("startNativeCycle") == self.latest["nativeCycle"]
                and receipt.get("completedGameFrames") == snap["frame"] - self.latest["frame"]
                and isinstance(receipt.get("snapshot"), dict)
                and receipt["snapshot"].get("frame") == snap["frame"]
                and receipt["snapshot"].get("nativeCycle") == snap["nativeCycle"],
                "stock Save write lacks its bounded state-12 completion receipt")
        self.write = deepcopy(receipt)

    def _reload(self, row):
        receipt, snap = row.get("receipt"), row.get("snapshot")
        require(self.write is not None, "cartridge reload occurred before stock Save write")
        self._boundary(snap)
        boundary = receipt.get("saveReload") if isinstance(receipt, dict) else None
        require(isinstance(boundary, dict), "private cartridge reload receipt is missing")
        export, loaded = boundary.get("export", {}), boundary.get("loaded", {})
        require(boundary.get("state") == "loaded"
                and boundary.get("sourceSessionId") != boundary.get("newSessionId")
                and boundary.get("sourceFrame") == self.latest["frame"]
                and boundary.get("sourceSaveSha256") == self.latest.get("sourceSaveSha256")
                and boundary.get("sourceRomSha256") == self.source["romSha256"]
                and isinstance(export.get("sha256"), str)
                and len(export["sha256"]) == 64
                and export["sha256"] != boundary["sourceSaveSha256"]
                and loaded.get("sha256") == export["sha256"]
                and loaded.get("size") == export.get("size")
                and boundary.get("loadedSaveSha256") == export["sha256"]
                and snap.get("romSha256") == self.source["romSha256"]
                and snap.get("sourceSaveSha256") == export["sha256"]
                and receipt.get("snapshot") == snap
                and receipt.get("recordingRestart", {}).get("frame") == snap["frame"],
                "private cartridge reload did not load the exact written bytes")
        self.reload = deepcopy(boundary)

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "save proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "save proof initial boundary is duplicate")
                self._boundary(row["initialSnapshot"], map_id=None)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "save proof initial boundary is missing")
            phase = row.get("phase")
            if phase == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "save proof setup action order differs")
                action = SETUP[self.setup_index]
            else:
                require(phase == "observe" and self.setup_index == len(SETUP)
                        and self.action_index < len(ORDER)
                        and row.get("action") == ORDER[self.action_index],
                        "save proof action order differs")
                action = ORDER[self.action_index]
            if action in STEPS:
                require("command" not in row, "save proof step lacks native frame stream")
                for sample, _, _ in validate_raw_chunk(row, self.latest):
                    self._boundary(sample)
                    require(self.steps[action] < STEPS[action][0],
                            "save proof step exceeded its fixed game-frame count")
                    if action == "allow-natural-ram":
                        self._onix(sample)
                    self.latest = deepcopy(sample)
                    self.steps[action] += 1
                    self.observed_frames += 1
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if self.steps[action] == STEPS[action][0]:
                    self.action_index += 1
                return self.result()
            snap = row.get("snapshot")
            self._boundary(snap)
            require(action == "reload" or snap["frame"] >= self.latest["frame"],
                    "save proof command boundary reversed")
            command = row.get("command")
            if action == "ram-tile":
                require(command == "teleport"
                        and row.get("receipt", {}).get("preparedOnly") is True
                        and row["receipt"].get("snapshot") == snap,
                        "save proof Ram tile was not a checked teleport")
            elif action == "spawn-onix":
                require(command == "spawn", "save proof Onix did not use native spawn")
            elif action == "bind-onix":
                require(command == "bind", "save proof Onix bind is missing")
                self.subject = deepcopy(row.get("receipt"))
                actor = self._onix(snap)
                require((actor.get("logical", {}).get("x"),
                         actor.get("logical", {}).get("y")) == (585, 412),
                        "save proof Onix did not start five tiles south")
            elif action in READS:
                require(command == "player-health.observe",
                        "save proof HP checkpoint is not an authenticated read")
                self._health(row, action)
            elif action == "wait-flash":
                require(command == "save.wait", "save proof lacks stock Save write wait")
                self._wait(row)
            elif action == "reload":
                require(command == "save.reload", "save proof lacks private cartridge reload")
                self._reload(row)
            self.latest = deepcopy(snap)
            if phase == "setup": self.setup_index += 1
            else: self.action_index += 1
        except (KeyError, StopIteration, TypeError, ValueError) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = (not self.failures and self.setup_index == len(SETUP)
                 and self.action_index == len(ORDER)
                 and all(self.steps[name] == count for name, (count, _) in STEPS.items())
                 and self.observed_frames == OBSERVED_FRAMES
                 and set(self.receipts) == set(READS)
                 and self.write is not None and self.reload is not None)
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "hpBeforeSave": self.receipts.get("before-save", {}).get("hp"),
                "hpBeforeReload": self.receipts.get("before-reload", {}).get("hp"),
                "hpAfterReload": self.receipts.get("after-reload", {}).get("hp"),
                "fillAfterReload": self.receipts.get("after-reload", {}).get("barDraw", {}).get("drawnFill"),
                "saveWritten": self.write is not None,
                "saveReloaded": self.reload is not None,
                "onix": deepcopy(self.subject)}

    def finish(self):
        result = self.result()
        if not result["ready"] and not self.failures:
            self.failures.append("save proof ended before its stock write and HP reload checkpoints")
        return {"passed": result["ready"] and not self.failures,
                "failures": list(self.failures)}
