"""One normal-save HP initialization receipt at a completed field boundary."""

from copy import deepcopy


class PlayerHealthInitialMeasurement:
    def __init__(self, test, source):
        self.action = test["actions"][0]["id"]
        self.source = source
        self.initial = None
        self.receipt = None
        self.failures = []

    def observe_record(self, row):
        try:
            if not isinstance(row, dict):
                raise ValueError("HP row is missing")
            if "initialSnapshot" in row:
                if self.initial is not None or row.get("phase") != "setup":
                    raise ValueError("HP initial boundary is duplicate or misplaced")
                self.initial = deepcopy(row["initialSnapshot"])
                if (self.initial.get("observationBoundary")
                        != "main-task-queue-completion"
                        or self.initial.get("fieldAvailable") is False):
                    raise ValueError("HP initial field boundary is unavailable")
            elif "boundarySnapshot" in row:
                if self.initial is None or self.receipt is not None:
                    raise ValueError("HP observation boundary is misplaced")
                self.initial = deepcopy(row["boundarySnapshot"])
            elif row.get("command") == "player-health.observe":
                if (self.initial is None or self.receipt is not None
                        or row.get("phase") != "observe"
                        or row.get("action") != self.action
                        or row.get("snapshot") != self.initial):
                    raise ValueError("HP receipt is not the declared read-only action")
                result = row.get("receipt")
                hp = result.get("playerHealth") if isinstance(result, dict) else None
                if not isinstance(hp, dict) or hp.get("schemaVersion") != 1:
                    raise ValueError("HP observer receipt is missing or has wrong version")
                identity = hp.get("identity")
                if (not isinstance(identity, dict)
                        or identity.get("descriptorVersion") != 1
                        or identity.get("overlayId") != 161
                        or identity.get("overlaySha256") != self.source["overlaySha256"]
                        or identity.get("romSha256") != self.source["romSha256"]):
                    raise ValueError("HP observer build identity differs")
                if (hp.get("frame") != self.initial.get("frame")
                        or hp.get("nativeCycle") != self.initial.get("nativeCycle")
                        or hp.get("hp") != 100 or hp.get("savedHp") != 100
                        or hp.get("maxHp") != 100
                        or type(hp.get("checkpointSpawn")) is not int
                        or not 1 <= hp["checkpointSpawn"] <= 30
                        or hp.get("lastDamage") != 0
                        or hp.get("acceptedHits") != 0
                        or hp.get("recoveryPending") is not False
                        or hp.get("restFrames") != 0
                        or hp.get("protectionFrames") != 0):
                    raise ValueError("old save did not initialize to full, safe player HP")
                self.receipt = deepcopy(hp)
            else:
                raise ValueError("unexpected HP proof row")
        except (KeyError, TypeError, ValueError) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        return {"ready": self.receipt is not None and not self.failures,
                "observedFrames": 1 if self.receipt is not None else 0,
                "observedFrameUnit": "read-only-completed-field-boundary",
                "failures": list(self.failures),
                "hp": self.receipt["hp"] if self.receipt else None,
                "checkpointSpawn": self.receipt["checkpointSpawn"] if self.receipt else None,
                "overlaySha256": self.receipt["identity"]["overlaySha256"]
                if self.receipt else None}

    def finish(self):
        if self.receipt is None and not self.failures:
            self.failures.append("player HP observation is missing")
        return {"passed": self.receipt is not None and not self.failures,
                "failures": list(self.failures)}
