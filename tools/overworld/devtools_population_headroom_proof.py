"""Acceptance rows and copied-data controls for saturated-population headroom.

The copied controls change retained rows and prove checker sensitivity only.
They do not prove that the live recorder sees the same fault.
"""
from copy import deepcopy

from tools.overworld.devtools_main_loop_probe import (
    MAX_ZERO_STUTTER_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
)
from tools.overworld.devtools_population_headroom_measurement import (
    KIND,
    MAP_ID,
    MIN_ACTIVE_ACTORS,
    MIN_PLAYER_STEPS,
    MIN_SATURATED_PERCENT,
    MIN_WAIT_ARM9_TICKS,
    MINIMUM_CREDITED_LOOPS,
    P1_WAIT_ARM9_TICKS,
    P5_WAIT_ARM9_TICKS,
    REQUIREMENT,
    SPAWNS,
    need,
)

CLAIMS = ("live-actor-identity", "natural-input", "population-bounds", "frame-pacing")
FAULT_NAMES = ("late-loop", "low-idle-loop", "thin-headroom-tail", "missing-wait-ticks",
               "under-saturated", "short-window", "wrong-map", "wrong-saved-mankey")
FAULTS = tuple(KIND + ":" + name for name in FAULT_NAMES)
# Enough rows below the 5th-percentile floor to move that percentile (index 36
# of the 720 credited loops) while leaving the 1st percentile above its floor.
THIN_TAIL_ROWS = 40
THIN_TAIL_WAIT = (P1_WAIT_ARM9_TICKS + P5_WAIT_ARM9_TICKS) // 2


def _rule(name, operator, **bound):
    return dict(name=name, operator=operator, type="integer",
                validator="meaningful-observation", **bound)


def contract():
    return {
        "live-actor-identity": [dict(
            name="headroom-follower-identity", operator="eq", type="array",
            validator="meaningful-observation", expected=[56, "FOLLOWER", 1])],
        "natural-input": [
            _rule("headroom-player-step-count", "gte", minimum=MIN_PLAYER_STEPS),
            _rule("headroom-player-settled-at-end", "eq", expected=1),
        ],
        "population-bounds": [
            _rule("headroom-armed-active-actor-count", "gte", minimum=MIN_ACTIVE_ACTORS),
            _rule("headroom-saturated-loop-percent", "gte", minimum=MIN_SATURATED_PERCENT),
        ],
        "frame-pacing": [
            _rule("headroom-credited-loop-count", "gte", minimum=MINIMUM_CREDITED_LOOPS),
            _rule("headroom-late-main-loop-count", "eq", expected=0),
            _rule("headroom-maximum-native-cycles", "lte", maximum=NORMAL_MAIN_LOOP_NATIVE_CYCLES),
            _rule("headroom-maximum-frame-sequence", "lte", maximum=NORMAL_MAIN_LOOP_NATIVE_CYCLES),
            _rule("headroom-maximum-arm9-ticks", "lte", maximum=MAX_ZERO_STUTTER_ARM9_TICKS),
            _rule("headroom-player-render-stall-count", "eq", expected=0),
            _rule("headroom-loops-without-wait-ticks", "eq", expected=0),
            _rule("headroom-minimum-wait-arm9-ticks", "gte", minimum=MIN_WAIT_ARM9_TICKS),
            _rule("headroom-first-percentile-wait-arm9-ticks", "gte", minimum=P1_WAIT_ARM9_TICKS),
            _rule("headroom-fifth-percentile-wait-arm9-ticks", "gte", minimum=P5_WAIT_ARM9_TICKS),
        ],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    pacing = meter.get("pacing") or {}
    headroom = meter.get("headroom") or {}
    population = meter.get("population") or {}
    player = meter.get("player") or {}
    subject = (meter.get("subjects") or {}).get("mankey") or {}
    credited = meter.get("observedFrames")
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True
         and meter.get("closed") is True and meter.get("acceptedProof") is False
         and meter.get("failures") == []
         and meter.get("requirements") == [REQUIREMENT]
         and meter.get("observedFrameUnit") == "completed-main-loop-return"
         and replay.get("observedFrames") == credited
         and type(credited) is int and credited >= MINIMUM_CREDITED_LOOPS
         and subject.get("species") == 56 and subject.get("role") == "FOLLOWER"
         and subject.get("identityVerified") is True
         and pacing.get("sampleCount") == credited == headroom.get("waitSampleCount")
         == len(headroom.get("samples", []))
         and len(population.get("spawned", [])) + population.get("alreadyFullRequests", -1)
         + population.get("startupSkippedRequests", -1) == len(SPAWNS)
         and meter.get("timingWindow") is not None
         and player.get("finalTile") and player.get("steps", 0) >= MIN_PLAYER_STEPS,
         "population headroom proof is not one complete saturated Route30 window")
    need(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "population headroom private session did not close cleanly")
    rows = [
        ("live-actor-identity", "headroom-follower-identity",
         [subject["species"], subject["role"], int(subject["identityVerified"])],
         "eq", [56, "FOLLOWER", 1]),
        ("natural-input", "headroom-player-step-count", player["steps"], "gte", MIN_PLAYER_STEPS),
        ("natural-input", "headroom-player-settled-at-end", int(player.get("settled") is True), "eq", 1),
        ("population-bounds", "headroom-armed-active-actor-count",
         population["armedActiveActors"], "gte", MIN_ACTIVE_ACTORS),
        ("population-bounds", "headroom-saturated-loop-percent",
         population["saturatedPercent"], "gte", MIN_SATURATED_PERCENT),
        ("frame-pacing", "headroom-credited-loop-count", credited, "gte", MINIMUM_CREDITED_LOOPS),
        ("frame-pacing", "headroom-late-main-loop-count", pacing["lateMainLoopCount"], "eq", 0),
        ("frame-pacing", "headroom-maximum-native-cycles",
         pacing["maximumNativeCycles"], "lte", NORMAL_MAIN_LOOP_NATIVE_CYCLES),
        ("frame-pacing", "headroom-maximum-frame-sequence",
         pacing["maximumFrameSequence"], "lte", NORMAL_MAIN_LOOP_NATIVE_CYCLES),
        ("frame-pacing", "headroom-maximum-arm9-ticks",
         pacing["maximumArm9Ticks"], "lte", MAX_ZERO_STUTTER_ARM9_TICKS),
        ("frame-pacing", "headroom-player-render-stall-count", pacing["renderStallCount"], "eq", 0),
        ("frame-pacing", "headroom-loops-without-wait-ticks",
         credited - headroom["waitSampleCount"], "eq", 0),
        ("frame-pacing", "headroom-minimum-wait-arm9-ticks",
         headroom["minimum"], "gte", MIN_WAIT_ARM9_TICKS),
        ("frame-pacing", "headroom-first-percentile-wait-arm9-ticks",
         headroom["p1"], "gte", P1_WAIT_ARM9_TICKS),
        ("frame-pacing", "headroom-fifth-percentile-wait-arm9-ticks",
         headroom["p5"], "gte", P5_WAIT_ARM9_TICKS),
    ]
    output = []
    for claim, name, value, operator, expected in rows:
        key = "expected" if operator == "eq" else ("minimum" if operator == "gte" else "maximum")
        passed = value == expected if operator == "eq" else (
            value >= expected if operator == "gte" else value <= expected)
        output.append({"claim": claim, "name": name, "value": value,
                       "operator": operator, key: expected, "passed": passed})
    return output


class PopulationHeadroomNegative:
    """Copied-data faults; each changes one retained fact and one checker reason."""

    def __init__(self, fault):
        need(fault in FAULTS, "unknown copied fault")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False
        self.first = None
        self.changed_rows = 0

    @staticmethod
    def _samples(row):
        samples = {s["frame"]: s for s in row.get("samples", [])}
        if row.get("snapshot") is not None:
            samples[row["snapshot"]["frame"]] = row["snapshot"]
        return samples.values()

    def _pacing_events(self, row):
        """Credited pacing rows with a previous loop, once the window is armed."""
        return [event.get("data", {}) for event in row.get("events", [])
                if event.get("data", {}).get("observation") == "stock-main-loop-pacing"
                and self.first is not None
                and event["data"].get("afterQueueFrame", -1) >= self.first
                and isinstance(event["data"].get("intervalFromPrevious"), dict)]

    def mutate(self, row, subjects):
        if row.get("command") == "main-loop-pacing.arm":
            self.first = row["receipt"]["probe"]["firstObservedQueueFrame"]
            if self.fault == "short-window":
                changed = deepcopy(row)
                probe = changed["receipt"]["probe"]
                probe["lastObservedQueueFrame"] = probe["firstObservedQueueFrame"] + MINIMUM_CREDITED_LOOPS - 1
                self.applied = True
                return changed
        if row.get("phase") != "observe" or (self.applied and self.fault != "under-saturated"):
            return row
        changed = deepcopy(row)
        if self.fault in ("wrong-map", "wrong-saved-mankey"):
            for sample in self._samples(changed):
                if self.fault == "wrong-map":
                    sample["context"]["mapId"] = MAP_ID - 1
                else:
                    next(p for p in sample["party"] if p["slot"] == 2)["personality"] += 1
                self.applied = True
                return changed
        elif self.fault == "under-saturated":
            # Two regular Wild slots are empty in every observed frame: five actors.
            for sample in self._samples(changed):
                victims = [a for a in sample["actors"]
                           if a.get("active") is True and a.get("role") == "WILD"][:2]
                for victim in victims:
                    victim["active"] = False
                    self.applied = True
            return changed if self.applied else row
        else:
            events = self._pacing_events(changed)
            for data in events:
                if self.fault == "late-loop":
                    data["frameCounter"] = NORMAL_MAIN_LOOP_NATIVE_CYCLES + 3
                    data["intervalFromPrevious"].update(
                        arm9Ticks=MAX_ZERO_STUTTER_ARM9_TICKS * 2,
                        nativeCycles=NORMAL_MAIN_LOOP_NATIVE_CYCLES + 3,
                        frameSequence=NORMAL_MAIN_LOOP_NATIVE_CYCLES + 3)
                    self.applied = True
                elif self.fault == "missing-wait-ticks":
                    for key in ("waitArm9Ticks", "waitEntrySite", "waitEntryArm9Timestamp", "waitScope"):
                        data.pop(key, None)
                    self.applied = True
                else:
                    wait = MIN_WAIT_ARM9_TICKS - 1 if self.fault == "low-idle-loop" else THIN_TAIL_WAIT
                    data["waitArm9Ticks"] = wait
                    data["waitEntryArm9Timestamp"] = data["guestClock"]["arm9Timestamp"] - wait
                    self.changed_rows += 1
                    if self.fault == "low-idle-loop" or self.changed_rows >= THIN_TAIL_ROWS:
                        self.applied = True
                if self.applied:
                    break
            return changed if events else row
        return row


Negative = PopulationHeadroomNegative

_EXPECTED = {
    "late-loop": "route observed an extra game frame",
    "low-idle-loop": "idle headroom below its per-loop floor",
    "thin-headroom-tail": "5th percentile is below its floor",
    "missing-wait-ticks": "pacing row lacks waitArm9Ticks",
    "under-saturated": "fewer than six active actors",
    "short-window": "armed pacing window is shorter than the required credited loops",
    "wrong-map": "current Route30 field or source differs",
    "wrong-saved-mankey": "saved Mankey party identity differs",
}


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False, "copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    need(_EXPECTED[fault.rsplit(":", 1)[1]] in text,
         "copied fault failed for an unrelated reason: " + fault)
