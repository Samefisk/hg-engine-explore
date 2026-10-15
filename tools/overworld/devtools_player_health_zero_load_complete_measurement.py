"""One checksum-valid zero-HP Continue, stock blackout, and released field."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk

KIND = "player-health-zero-load-v1"
REQUIREMENT = "current.player-health-zero-load"
SETUP = ("message-ready", "dismiss-message", "release-message",
         "arrival-or-free", "dismiss-arrival", "release-arrival",
         "arrival-or-free-again", "dismiss-arrival-again", "release-arrival-again",
         "field-free")
ORDER = ("after-recovery", "normal-step", "release-step", "after-step")
READS = ("after-recovery", "after-step")
EXPECTED_SPAWN = 3
EXPECTED_MAP = 158
EXPECTED_POSITION = (4, 13)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class PlayerHealthZeroLoadMeasurement:
    def __init__(self, source):
        self.source = source
        self.fixture = None
        self.latest = None
        self.frames = 0
        self.boot_native_gap_cycles = 0
        self.root_pointer = None
        self.stock_pointer = None
        self.root_started = False
        self.root_ended = False
        self.message_ready = False
        self.message_input = False
        self.arrival_inputs = 0
        self.reads = {}
        self.first_position = None
        self.first_steps = None
        self.moved = False
        self.failures = []

    def _trace(self, sample, *, initial=False):
        require(sample.get("observationBoundary") == "main-task-queue-completion"
                and sample.get("romSha256") == self.source["romSha256"]
                and sample.get("sourceSaveSha256") == self.fixture["fixtureSha256"],
                "zero-load frame differs from current ROM or private save")
        row = sample.get("zeroLoadRecovery")
        require(isinstance(row, dict) and row.get("frame") == sample.get("frame")
                and row.get("nativeCycle") == sample.get("nativeCycle")
                and type(row.get("field")) is int
                and type(row.get("messageInputReady")) is bool,
                "zero-load native task trace is absent or stale")
        root, stock = row.get("root"), row.get("stock")
        if root is not None:
            require(isinstance(root, dict) and type(root.get("pointer")) is int
                    and 0 <= root.get("state", -1) <= 2
                    and (self.root_pointer is None or root["pointer"] == self.root_pointer)
                    and not self.root_ended,
                    "zero-load blackout root restarted or changed")
            self.root_pointer = root["pointer"]
            self.root_started = True
        if stock is not None:
            require(root is not None and isinstance(stock, dict)
                    and type(stock.get("pointer")) is int
                    and 0 <= stock.get("state", -1) <= 6
                    and (self.stock_pointer is None or stock["pointer"] == self.stock_pointer),
                    "zero-load stock blackout task changed or lost its root")
            self.stock_pointer = stock["pointer"]
        if self.root_started and row["field"] and root is None:
            require(stock is None, "zero-load stock task survived its root")
            self.root_ended = True
        if row["messageInputReady"]:
            require(root is not None and stock is not None and stock["state"] == 4,
                    "zero-load blackout input flag has no stock message task")
            self.message_ready = True
        if not initial:
            require(self.latest is not None and sample["frame"] == self.latest["frame"] + 1
                    and sample["nativeCycle"] >= self.latest["nativeCycle"],
                    "zero-load observation skipped or reversed a completed frame")
        self.latest = deepcopy(sample)

    def _initial(self, row):
        require(self.latest is None and row.get("phase") == "setup", "duplicate zero-load boot")
        fixture = row.get("zeroLoadFixture")
        require(isinstance(fixture, dict) and fixture.get("kind") == "player-health-zero-load-fixture"
                and fixture.get("hp") == 0 and fixture.get("checkpointSpawn") == EXPECTED_SPAWN
                and fixture.get("sourceSha256") == self.source["sourceSaveSha256"]
                and isinstance(fixture.get("fixtureSha256"), str)
                and len(fixture["fixtureSha256"]) == 64,
                "zero-load private fixture manifest is missing or differs")
        self.fixture = deepcopy(fixture)
        snap = row["initialSnapshot"]
        boot = snap.get("bootRecovery", {})
        require(boot.get("kind") == "player-health-pending-blackout"
                and boot.get("boundary") == "paused-native-cycle-end"
                and boot.get("acceptedProof") is False
                and boot.get("actorClockReady") is False
                and boot.get("recoveryInputSent") is False
                and boot.get("saveSha256") == fixture["fixtureSha256"]
                and boot.get("copyBase") == fixture["copyBase"]
                and boot.get("saveCount") == fixture["saveCount"]
                and boot.get("hp") == 0
                and boot.get("checkpointSpawn") == EXPECTED_SPAWN,
                "zero-load boot did not preserve zero HP and one pending recovery")
        history = boot.get("preBootFrames")
        require(isinstance(history, list) and 1 <= len(history) <= 4096
                and history[-1] == snap.get("zeroLoadRecovery")
                and history[-1].get("frame") == snap.get("frame"),
                "zero-load preboot native history is incomplete")
        # The stock pause may happen after many native updates. Each completed
        # queue is retained, including the interval before a field exists.
        for index, trace in enumerate(history, 1):
            require(isinstance(trace, dict) and trace.get("frame") == index
                    and type(trace.get("nativeCycle")) is int
                    and (index == 1 or trace["nativeCycle"] >= history[index - 2]["nativeCycle"]),
                    "zero-load preboot task history has a gap")
            partial = {"observationBoundary": "main-task-queue-completion",
                       "romSha256": self.source["romSha256"],
                       "sourceSaveSha256": fixture["fixtureSha256"],
                       "frame": index, "nativeCycle": trace["nativeCycle"],
                       "zeroLoadRecovery": trace}
            self._trace(partial, initial=True)
        require(self.root_started and not self.root_ended and self.stock_pointer is not None
                and self.message_ready and self.latest["zeroLoadRecovery"]["messageInputReady"],
                "zero-load boot has no one live blackout message wait")
        self.latest = deepcopy(snap)

    def _health(self, row):
        snap = row.get("snapshot")
        require(isinstance(snap, dict) and self.latest is not None
                and snap.get("frame") == self.latest.get("frame")
                and snap.get("nativeCycle") == self.latest.get("nativeCycle")
                and snap.get("sourceSaveSha256") == self.fixture["fixtureSha256"]
                and snap.get("fieldAvailable") is True
                and snap.get("fieldControl", {}).get("taskPointer") == 0
                and snap.get("context", {}).get("mapId") == EXPECTED_MAP,
                "zero-load HP read is not at the free saved checkpoint")
        hp = row.get("receipt", {}).get("playerHealth")
        identity = hp.get("identity", {}) if isinstance(hp, dict) else {}
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1
                and identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and identity.get("romSha256") == self.source["romSha256"]
                and hp.get("frame") == snap["frame"]
                and hp.get("nativeCycle") == snap["nativeCycle"]
                and hp.get("hp") == hp.get("savedHp") == hp.get("maxHp") == 100
                and hp.get("recoveryPending") is False
                and hp.get("checkpointSpawn") == EXPECTED_SPAWN
                and hp.get("pause", {}).get("fieldTaskActive") is False
                and hp.get("economy") == self.fixture["baselineEconomy"],
                "zero-load HP, save, recovery, or economy differs at task release")
        party = snap.get("party")
        require(isinstance(party, list) and 1 <= len(party) <= 6
                and all(p.get("identityVerified") is True
                        and type(p.get("maxHp")) is int and p["maxHp"] > 0
                        and p.get("hp") == p["maxHp"] and p.get("status") == 0
                        for p in party), "stock blackout did not heal the full party")
        self.reads[row["action"]] = deepcopy(hp)
        if row["action"] == "after-recovery":
            player = snap.get("player", {})
            self.first_position = (player.get("x"), player.get("y"))
            self.first_steps = snap.get("nativeObservation", {}).get("playerStepCount")
            require(self.first_position == EXPECTED_POSITION
                    and type(self.first_steps) is int,
                    "stock recovery did not reach the saved checkpoint tile")
        else:
            player = snap.get("player", {})
            steps = snap.get("nativeObservation", {}).get("playerStepCount")
            require(self.first_position is not None and type(steps) is int
                    and steps > self.first_steps
                    and (player.get("x"), player.get("y")) != self.first_position,
                    "normal player input did not move after blackout task release")
            self.moved = True

    def stage(self, name):
        if self.latest is None:
            return False
        row = self.latest.get("zeroLoadRecovery", {})
        field_free = (self.root_ended and self.latest.get("fieldAvailable") is True
                      and self.latest.get("fieldControl", {}).get("taskPointer") == 0
                      and self.latest.get("context", {}).get("mapId") == EXPECTED_MAP)
        if name == "message-ready":
            return bool(row.get("messageInputReady") and not self.message_input)
        if name == "arrival-or-free":
            return bool(field_free or self.message_input and self.latest.get("dialogue", {}).get("known") is True
                        and self.latest["dialogue"].get("state") in ("page-wait", "script-button-wait"))
        if name == "field-free":
            return bool(field_free)
        raise ValueError("unknown zero-load stage")

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "zero-load proof row is missing")
            if "initialSnapshot" in row:
                self._initial(row)
                return self.result()
            require(self.latest is not None, "zero-load boot boundary is missing")
            if row.get("command") == "player-health.observe":
                require(row.get("phase") == "observe" and row.get("action") in READS
                        and row["action"] not in self.reads and self.stage("field-free"),
                        "zero-load HP read is out of order")
                self._health(row)
                return self.result()
            if row.get("command") == "skip":
                require(row.get("phase") == "setup"
                        and row.get("action") in ("dismiss-arrival", "release-arrival",
                                                  "dismiss-arrival-again", "release-arrival-again")
                        and self.stage("field-free"),
                        "zero-load optional input was skipped before task release")
                return self.result()
            require("command" not in row and row.get("phase") in ("setup", "observe")
                    and row.get("action") in SETUP + ORDER,
                    "unexpected zero-load command or action")
            action = row["action"]
            if action == "dismiss-message":
                require(self.stage("message-ready"), "blackout A was sent before the stock wait")
            if action.startswith("dismiss-arrival"):
                require(self.stage("arrival-or-free") and not self.stage("field-free"),
                        "arrival A was sent without an authenticated script wait")
            previous = self.latest
            boot_gap = 0
            samples, intervals = row.get("samples"), row.get("cycleIntervals")
            if (action == "dismiss-message" and self.frames == 0
                    and isinstance(samples, list) and len(samples) == 1
                    and isinstance(samples[0], dict)
                    and type(samples[0].get("nativeCycle")) is int
                    and samples[0]["nativeCycle"] == self.latest["nativeCycle"] + 2):
                # Boot stops at a native-cycle endpoint, while its snapshot
                # names the last completed main queue. One queue-free boot
                # cycle may therefore precede the first measured input cycle.
                # Its absence is bounded by adjacent completed frame numbers
                # and the measured dispatch/phase sequence of this one step.
                interval = intervals[0] if isinstance(intervals, list) and len(intervals) == 1 else {}
                interval = interval if isinstance(interval, dict) else {}
                dispatch = interval.get("guestDispatches")
                dispatch = dispatch if isinstance(dispatch, dict) else {}
                phases = interval.get("nativePhases")
                phases = phases if isinstance(phases, dict) else {}
                require(row.get("nativeCycles") == 1
                        and samples[0].get("frame") == self.latest["frame"] + 1
                        and interval.get("completedGameFrame") == samples[0]["frame"]
                        and dispatch.get("frameSequence") == samples[0]["nativeCycle"]
                        and phases.get("frameSequence") == samples[0]["nativeCycle"],
                        "zero-load boot-to-input native gap lacks one coherent measured cycle")
                previous = {"frame": self.latest["frame"],
                            "nativeCycle": self.latest["nativeCycle"] + 1}
                boot_gap = 1
            validated = validate_raw_chunk(row, previous)
            self.boot_native_gap_cycles += boot_gap
            for sample, _, _ in validated:
                self._trace(sample)
                self.frames += 1
                if on_sample is not None:
                    on_sample(sample, self.frames)
            if action == "dismiss-message":
                self.message_input = True
            if action.startswith("dismiss-arrival"):
                self.arrival_inputs += 1
        except (KeyError, TypeError, ValueError) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = (not self.failures and self.root_started and self.root_ended
                 and self.message_input and set(self.reads) == set(READS) and self.moved)
        return {"ready": ready, "observedFrames": self.frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures), "rootStarts": int(self.root_started),
                "rootEnds": int(self.root_ended), "messageInputSent": self.message_input,
                "bootNativeGapCycles": self.boot_native_gap_cycles,
                "arrivalInputs": self.arrival_inputs, "checkpointSpawn": EXPECTED_SPAWN,
                "checkpointMap": EXPECTED_MAP, "normalStep": self.moved,
                "hpAfterRecovery": self.reads.get("after-recovery", {}).get("hp"),
                "hpAfterStep": self.reads.get("after-step", {}).get("hp")}

    def finish(self):
        result = self.result()
        if not result["ready"] and not self.failures:
            self.failures.append("zero-load recovery, checkpoint, or normal step is incomplete")
        return {"passed": result["ready"] and not self.failures,
                "failures": list(self.failures)}
