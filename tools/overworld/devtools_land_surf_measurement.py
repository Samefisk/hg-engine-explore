"""Bounded Cherrygrove Surf-attempt separation from existing spawn receipts."""
from copy import deepcopy
import struct


KIND = "land-surf-separation-v1"
REQUIREMENT = "legacy.cherrygrove-surf-spawn-terrain"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def _boundary(snapshot):
    return {
        "frame": snapshot["frame"],
        "nativeCycle": snapshot["nativeCycle"],
        "context": deepcopy(snapshot["context"]),
        "player": [snapshot["player"]["x"], snapshot["player"]["y"]],
        "nativeSequence": snapshot["nativeObservation"]["sequence"],
    }


class LandSurfMeasurement:
    """Require two natural Surf Tentacool failures in a land-only window."""

    def __init__(self, test, *, max_frames):
        require(test.get("mode") == "prepared"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "mankey", "species": 56,
                    "role": "FOLLOWER", "acquire": "existing",
                }]
                and type(max_frames) is int and 1 <= max_frames <= 320,
                "land/surf measurement requires one bounded field-anchored fixture")
        self.max_frames = max_frames
        self.initial = None
        self.terminal = None
        self.last_frame = None
        self.last_native_cycle = None
        self.attempts = []
        self.land_spawns = []
        self.failures = []
        self.frames = 0
        self.closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    def arm(self, subject, snapshot):
        require(self.initial is None and snapshot.get("observationBoundary")
                == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0
                and snapshot.get("context", {}).get("mapId") == 67
                and snapshot.get("player", {}).get("x") == 543
                and snapshot.get("player", {}).get("y") == 393
                and snapshot.get("nativeObservation", {}).get("coverageComplete") is True
                and snapshot.get("nativeObservation", {}).get("error") is None
                and snapshot.get("nativeObservation", {}).get("eventsDropped") == 0
                and subject.get("species") == 56
                and subject.get("role") == "FOLLOWER",
                "land/surf measurement requires the reviewed Cherrygrove boundary")
        self.initial = _boundary(snapshot)
        self.last_frame = snapshot["frame"]
        self.last_native_cycle = snapshot["nativeCycle"]
        return self.result()

    @staticmethod
    def _attempt(data, frame):
        context = data.get("worldContext")
        require(isinstance(context, dict) and context.get("mapId") == 67
                and data.get("returnWorldContext") == context
                and data.get("statePointer") == context.get("statePointer")
                and data.get("fieldPointer") == context.get("fieldPointer")
                and type(context.get("fieldEpoch")) is int and context["fieldEpoch"] > 0
                and type(context.get("mapGeneration")) is int
                and context["mapGeneration"] > 0,
                "Tentacool attempt has a stale Cherrygrove context")
        require(data.get("setupMode") == "prepared"
                and data.get("terrain") == 1,
                "Tentacool attempt is not Surf")
        encounter = data.get("inputEncounter")
        require(isinstance(encounter, dict) and encounter.get("species") == 72
                and encounter.get("form") == 0
                and type(encounter.get("personality")) is int
                and encounter["personality"] > 0
                and type(encounter.get("level")) is int
                and 1 <= encounter["level"] <= 100,
                "Tentacool attempt identity is invalid")
        raw_hex = data.get("inputPrefixHex")
        require(isinstance(raw_hex, str) and len(raw_hex) == 40,
                "Tentacool attempt lacks its native input")
        try:
            raw = bytes.fromhex(raw_hex)
        except ValueError as error:
            raise ValueError("Tentacool native input is not hexadecimal") from error
        x, y, personality, species, form, level = struct.unpack("<ii4xIHBB", raw)
        require([x, y] == data.get("inputPosition") == [-1, -1]
                and (personality, species, form, level) == (
                    encounter["personality"], 72, 0, encounter["level"]),
                "Tentacool failed target or native identity differs")
        receipts = data.get("resolverReceipts")
        require(isinstance(receipts, list) and 1 <= len(receipts) <= 64,
                "Tentacool attempt lacks bounded resolver provenance")
        resolved = receipts[-1]
        request_hex = resolved.get("requestHex")
        require(resolved.get("resolved") is True
                and resolved.get("finalizationId") == data.get("finalizationId")
                and resolved.get("inputEncounter") == encounter
                and isinstance(request_hex, str) and len(request_hex) == 40,
                "Tentacool resolver provenance differs")
        try:
            request = bytes.fromhex(request_hex)
        except ValueError as error:
            raise ValueError("Tentacool resolver request is not hexadecimal") from error
        require(int.from_bytes(request[:2], "little") == 72
                and request[8] == encounter["level"] and request[9] == 1,
                "Tentacool resolver lost Surf encounter context")
        require(data.get("returnValue") == 0
                and data.get("pairEligible") is False
                and data.get("preparedEncounter") is None
                and data.get("position") is None,
                "Tentacool finalized in land-only window")
        return {
            "frame": frame,
            "sequence": data["sequence"],
            "finalizationId": data["finalizationId"],
            "slot": data["slot"],
            "level": encounter["level"],
            "terrain": data["terrain"],
            "inputPosition": deepcopy(data["inputPosition"]),
            "returnValue": data["returnValue"],
        }

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("frame") == self.last_frame + 1
                    and snapshot.get("nativeCycle") >= self.last_native_cycle
                    and snapshot.get("context") == self.initial["context"],
                    "land/surf completed frame or Cherrygrove context changed")
            require(not any(actor.get("active") is True and actor.get("role") == "WILD"
                            and actor.get("species") == 72
                            for actor in snapshot.get("actors", [])),
                    "Tentacool actor exists in land-only window")
            for event in events:
                data = event.get("data", {})
                if event.get("kind") != "native-observation" \
                        or data.get("observation") != "spawn-finalized" \
                        or data.get("inputEncounter", {}).get("species") != 72:
                    continue
                if data.get("returnValue") == 1:
                    self.land_spawns.append({"frame": snapshot["frame"],
                                             "sequence": data.get("sequence")})
                    raise ValueError("Tentacool finalized in land-only window")
                attempt = self._attempt(data, snapshot["frame"])
                require(attempt["finalizationId"] not in {
                    item["finalizationId"] for item in self.attempts},
                    "Tentacool finalization was counted twice")
                self.attempts.append(attempt)
                require(len(self.attempts) <= 8,
                        "land/surf attempt bound exceeded")
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "land/surf frame bound exceeded")
            self.last_frame = snapshot["frame"]
            self.last_native_cycle = snapshot["nativeCycle"]
            if self.ready:
                self.terminal = _boundary(snapshot)
        except (ValueError, KeyError, TypeError, struct.error) as error:
            self._fail(error)
        return self.result()

    @property
    def ready(self):
        return len(self.attempts) >= 2 and not self.land_spawns and not self.failures

    def stage(self, name):
        if name != "two-attempts":
            raise ValueError("unknown land/surf measurement stage")
        return self.ready

    def finish(self):
        if not self.failures and not self.ready:
            self._fail("land/surf measurement did not observe two Surf attempts")
        self.closed = True
        return self.result()

    def result(self):
        return {
            "kind": KIND,
            "requirements": [REQUIREMENT],
            "passed": self.closed and self.ready,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "surfAttempts": deepcopy(self.attempts),
            "tentacoolLandSpawns": deepcopy(self.land_spawns),
        }
