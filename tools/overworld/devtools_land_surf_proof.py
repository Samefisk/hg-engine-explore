"""Acceptance rows and copied-data controls for Cherrygrove land/Surf separation."""
from copy import deepcopy

from tools.overworld.devtools_land_surf_measurement import KIND, REQUIREMENT, require


CLAIMS = ("terrain-selection",)
FAULTS = (
    "land-surf-missing-attempt",
    "land-surf-wrong-terrain",
    "land-surf-tentacool-created",
)


def contract():
    return {
        "terrain-selection": [
            {
                "name": "surf-attempt-count", "operator": "gt",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": 1,
            },
            {
                "name": "tentacool-land-spawn-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 0,
            },
        ],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT]
            and len(meter.get("surfAttempts", [])) >= 2
            and meter.get("tentacoolLandSpawns") == [],
            "land/surf proof lacks two rejected Surf attempts")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "land/surf private session did not close cleanly")
    attempts = meter["surfAttempts"]
    require(all(item.get("terrain") == 1 and item.get("inputPosition") == [-1, -1]
                and item.get("returnValue") == 0 for item in attempts),
            "land/surf proof receipt changed")
    return [
        {
            "claim": "terrain-selection", "name": "surf-attempt-count",
            "value": len(attempts), "operator": "gt", "minimum": 1,
            "passed": len(attempts) > 1,
        },
        {
            "claim": "terrain-selection", "name": "tentacool-land-spawn-count",
            "value": len(meter["tentacoolLandSpawns"]), "operator": "eq",
            "expected": 0, "passed": meter["tentacoolLandSpawns"] == [],
        },
    ]


class LandSurfNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown land/surf copied fault")
        self.fault = fault
        self.applied = False

    @staticmethod
    def _is_attempt(event):
        data = event.get("data", {})
        return (event.get("kind") == "native-observation"
                and data.get("observation") == "spawn-finalized"
                and data.get("inputEncounter", {}).get("species") == 72)

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or self.applied:
            return row
        changed = deepcopy(row)
        events = changed.get("events", [])
        for index, event in enumerate(events):
            if not self._is_attempt(event):
                continue
            if self.fault == "land-surf-missing-attempt":
                del events[index]
            elif self.fault == "land-surf-wrong-terrain":
                event["data"]["terrain"] = 0
            else:
                event["data"]["returnValue"] = 1
            self.applied = True
            return changed
        return row


Negative = LandSurfNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "land/surf copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "land-surf-missing-attempt": "land/surf measurement did not observe two Surf attempts",
        "land-surf-wrong-terrain": "Tentacool attempt is not Surf",
        "land-surf-tentacool-created": "Tentacool finalized in land-only window",
    }[fault]
    require(expected in text,
            "land/surf copied control failed for an unrelated reason: " + fault)
